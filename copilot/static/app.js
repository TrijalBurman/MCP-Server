"use strict";

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const state = {
  view: "chat", status: null, settings: null, roots: [], projects: [], sessions: [],
  session: null, messages: [], chatProject: null, attachment: null, draft: "", chatBusy: false,
  libraryQuery: "", libraryOffset: 0, memoryQuery: "", memoryProject: "", projectDetail: null,
  routeVersion: 0, modal: null, lastIndexRunning: false, statusBusy: false, connected: false,
};

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = String(value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "value") node.value = String(value);
    else if (key === "disabled" || key === "hidden") node[key] = Boolean(value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child !== undefined && child !== null && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function icon(name, extraClass = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `icon ${extraClass}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

function button(label, action, options = {}) {
  return el("button", { type: "button", class: `button ${options.class || ""}`.trim(), onclick: action, disabled: options.disabled, title: options.title }, options.icon ? icon(options.icon) : null, label);
}

function iconButton(name, label, action, extraClass = "") {
  return el("button", { type: "button", class: `icon-button ${extraClass}`.trim(), "aria-label": label, title: label, onclick: action }, icon(name));
}

function errorText(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(item => item.msg || item.message || String(item)).join("; ");
  if (value && typeof value === "object") return value.message || JSON.stringify(value);
  return "The local service could not complete this request.";
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 240000);
  try {
    const response = await fetch(`/api${path}`, {
      method: options.method || "GET", headers: options.body !== undefined ? { "Content-Type": "application/json" } : {},
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal, credentials: "same-origin",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorText(data?.detail || data?.error || `The local service returned ${response.status}.`));
    if (!data) throw new Error("The local service returned an unreadable response.");
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local service took too long to respond. Check that it is still running.");
    if (error instanceof TypeError) throw new Error("Cannot reach the local copilot service. Start the application and try again.");
    throw error;
  } finally { clearTimeout(timeout); }
}

function toast(message, type = "success") {
  const node = el("div", { class: `toast ${type === "error" ? "error" : ""}`, role: type === "error" ? "alert" : "status" },
    icon(type === "error" ? "x" : "check"), el("div", { class: "toast-message", text: message }), iconButton("x", "Dismiss", () => node.remove()));
  $("#toast-region").append(node);
  setTimeout(() => node.remove(), type === "error" ? 13000 : 5500);
}

function inlineError(message) { return el("div", { class: "inline-error", role: "alert", text: message }); }
function loading() { return el("div", { class: "loading-state", role: "status" }, icon("refresh"), "Reading your local workspace…"); }
function formatDate(value) {
  if (!value) return "";
  const date = new Date(typeof value === "number" ? (value < 100000000000 ? value * 1000 : value) : value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function formatSize(bytes) {
  const amount = Number(bytes) || 0;
  if (amount < 1024) return `${amount} B`;
  if (amount < 1024 ** 2) return `${(amount / 1024).toFixed(1)} KB`;
  return `${(amount / 1024 ** 2).toFixed(1)} MB`;
}
function projectName(id) { return state.projects.find(project => String(project.id) === String(id))?.name || "Project"; }
function numericId(value) { return value === "" || value === null || value === undefined ? null : Number(value); }
function saveSession(id) { try { id ? localStorage.setItem("localmind.session", String(id)) : localStorage.removeItem("localmind.session"); } catch (_) { /* Storage can be disabled in a browser. */ } }

function pageHeader(eyebrow, title, description, action) {
  return el("div", { class: "page-header" }, el("div", {}, el("div", { class: "eyebrow", text: eyebrow }), el("h1", { text: title }), el("p", { text: description })), action);
}

function emptyState(name, title, description, action) {
  return el("div", { class: "empty-state" }, el("div", { class: "empty-icon" }, icon(name)), el("div", {}, el("h2", { text: title }), el("p", { text: description }), action));
}

function projectSelect(value, placeholder = "All projects", attributes = {}) {
  const select = el("select", { class: "field-select", ...attributes }, el("option", { value: "", text: placeholder }),
    state.projects.map(project => el("option", { value: project.id, text: project.name })));
  select.value = value === null || value === undefined ? "" : String(value);
  return select;
}

function safeInline(text) {
  const fragment = document.createDocumentFragment();
  // Only emphasis and code are rendered. HTML and links stay as text.
  const expression = /(\*\*([^\n]*?)\*\*|`([^`\n]+)`)/g;
  let offset = 0, match;
  while ((match = expression.exec(text)) !== null) {
    fragment.append(document.createTextNode(text.slice(offset, match.index)));
    fragment.append(el(match[2] !== undefined ? "strong" : "code", { text: match[2] !== undefined ? match[2] : match[3] }));
    offset = expression.lastIndex;
  }
  fragment.append(document.createTextNode(text.slice(offset)));
  return fragment;
}

function markdown(text) {
  const container = el("div", { class: "message-content" });
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  let paragraph = [], list = null, code = null;
  function flush() { if (paragraph.length) container.append(el("p", {}, safeInline(paragraph.join("\n")))); paragraph = []; list = null; }
  for (const line of lines) {
    if (/^\s*```/.test(line)) {
      flush();
      if (code !== null) { container.append(el("pre", {}, el("code", { text: code.join("\n") }))); code = null; }
      else code = [];
      continue;
    }
    if (code !== null) { code.push(line); continue; }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    const ordered = /^\s*\d+[.)]\s+(.+)$/.exec(line);
    if (heading) { flush(); container.append(el(`h${Math.min(heading[1].length + 1, 4)}`, {}, safeInline(heading[2]))); }
    else if (bullet || ordered) {
      if (paragraph.length) flush();
      const kind = ordered ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== kind) { list = el(kind); container.append(list); }
      list.append(el("li", {}, safeInline((bullet || ordered)[1])));
    } else if (/^>\s?/.test(line)) { flush(); container.append(el("blockquote", {}, safeInline(line.replace(/^>\s?/, "")))); }
    else if (!line.trim()) flush();
    else { list = null; paragraph.push(line); }
  }
  flush();
  if (code !== null) container.append(el("pre", {}, el("code", { text: code.join("\n") })));
  return container;
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(String(text)); toast("Copied to clipboard."); }
  catch (_) { toast("Your browser could not copy this text. Select it and copy manually.", "error"); }
}

function setSidebar(open) {
  $("#sidebar").classList.toggle("open", open);
  $("#sidebar-scrim").hidden = !open;
  $("#mobile-menu").setAttribute("aria-expanded", String(open));
}

function renderSessions() {
  const list = $("#recent-list");
  list.replaceChildren();
  if (!state.sessions.length) { list.append(el("p", { class: "sidebar-empty", text: "Your conversations will live here." })); return; }
  for (const session of state.sessions.slice(0, 35)) {
    list.append(el("div", { class: `recent-row ${String(state.session?.id) === String(session.id) ? "active" : ""}` },
      el("button", { class: "recent-button", title: session.title, text: session.title || "New conversation", onclick: () => openSession(session) }),
      el("button", { class: "recent-delete", "aria-label": `Delete conversation ${session.title}`, title: "Delete conversation", onclick: () => deleteSession(session) }, icon("trash"))));
  }
}

async function refreshLists() {
  const results = await Promise.allSettled([api("/sessions"), api("/projects"), api("/roots")]);
  const [sessions, projects, roots] = results;
  if (sessions.status === "fulfilled") state.sessions = sessions.value.sessions || [];
  if (projects.status === "fulfilled") state.projects = projects.value.projects || [];
  if (roots.status === "fulfilled") state.roots = roots.value.roots || [];
  renderSessions();
}

async function pollStatus() {
  if (state.statusBusy) return;
  state.statusBusy = true;
  try {
    const previousRunning = state.lastIndexRunning;
    state.status = await api("/status", { timeout: 12000 });
    state.settings = state.status.settings;
    state.connected = true;
    state.lastIndexRunning = Boolean(state.status.indexing?.running);
    updateStatus();
    if (previousRunning && !state.lastIndexRunning) {
      const job = state.status.indexing;
      if (job.error) toast(job.error, "error");
      else if (job.result) toast(`Indexing complete. ${job.result.indexed || 0} updated, ${job.result.unchanged || 0} unchanged${job.result.skipped ? `, ${job.result.skipped} skipped` : ""}.`);
      if (state.view === "library") renderView("library");
      else if (state.view === "chat" && !state.session && !state.chatBusy) renderChat();
    }
  } catch (error) {
    state.connected = false;
    updateStatus();
  } finally { state.statusBusy = false; }
}

function updateStatus() {
  const pill = $("#runtime-pill");
  const runtime = state.status?.ollama;
  pill.className = "runtime-pill";
  if (!state.connected) {
    pill.classList.add("disconnected"); $("#runtime-label").textContent = "Local service unavailable";
  } else if (runtime?.chat_ready) {
    const model = state.settings?.chat_model || "ready";
    const modelLabel = /^qwen3:4b(?:$|-)/i.test(model) ? "Qwen3 4B" : model;
    pill.classList.add("online"); $("#runtime-label").textContent = `Local model · ${modelLabel}`;
    pill.title = `Local model: ${model}. View local model settings.`;
  } else {
    pill.classList.add("offline"); $("#runtime-label").textContent = "Extractive mode";
    pill.title = "View local model settings";
  }
  const stats = state.status?.stats || {};
  $("#library-count").textContent = stats.documents ?? 0;
  $("#memory-count").textContent = stats.memories ?? 0;
  $("#projects-count").textContent = stats.projects ?? 0;
  $$('[data-index-button]').forEach(node => { node.disabled = Boolean(state.status?.indexing?.running) || (node.dataset.requiresRoots === "true" && !state.roots.length); });
  const indicator = $("#index-status");
  if (indicator) renderIndexStatus(indicator);
  const chatMode = $("#chat-mode-label");
  if (chatMode) chatMode.textContent = runtime?.chat_ready ? "Local model + your library" : "Local excerpts · model not ready";
}

function renderIndexStatus(container) {
  const job = state.status?.indexing;
  container.replaceChildren(); container.classList.toggle("busy", Boolean(job?.running));
  if (!job) return;
  if (job.running) {
    const progress = job.progress || {};
    const count = progress.processed ?? progress.current ?? ((progress.indexed || 0) + (progress.unchanged || 0) + (progress.skipped || 0) + (progress.errors?.length || 0));
    container.append(icon("refresh"), el("span", { text: `Indexing locally${count !== undefined ? ` · ${count} files processed` : "…"}${progress.phase ? ` · ${progress.phase}` : ""}` }));
    if (progress.current_path || progress.path) container.append(el("span", { class: "small-text", text: String(progress.current_path || progress.path).split(/[\\/]/).pop() }));
  } else if (job.error) container.append(icon("x"), el("span", { text: job.error }));
  else if (job.result) {
    const result = job.result;
    container.append(icon("check"), el("span", { text: `${result.indexed || 0} updated · ${result.unchanged || 0} unchanged · ${result.skipped || 0} skipped` }));
    if (result.embedding_warning) container.append(el("span", { text: result.embedding_warning }));
    if (result.errors?.length) {
      container.append(el("details", { class: "index-errors" }, el("summary", { text: `${result.errors.length} file${result.errors.length === 1 ? "" : "s"} could not be indexed` }),
        el("div", { class: "index-error-list" }, result.errors.map(item => el("p", { text: `${item.path}: ${item.error}` })))));
    }
  } else if (state.roots.length) container.append(icon("shield"), el("span", { text: "Original files stay in their folders. Reindex after adding or changing files." }));
}

async function renderView(view = state.view) {
  const allowed = ["chat", "library", "memory", "projects", "settings"];
  state.view = allowed.includes(view) ? view : "chat";
  const requestedView = state.view;
  const version = ++state.routeVersion;
  setSidebar(false);
  $("#view-title").textContent = ({ chat: "Copilot", library: "Library", memory: "Memory", projects: "Projects", settings: "Settings" })[state.view];
  $$("[data-view]").forEach(node => node.classList.toggle("active", node.dataset.view === state.view));
  if (location.hash !== `#${state.view}`) history.replaceState(null, "", `#${state.view}`);
  const main = $("#main");
  main.scrollTop = 0;
  if (state.view === "chat") { renderChat(); return; }
  main.replaceChildren(loading());
  try {
    if (requestedView === "library") await renderLibrary(version);
    if (requestedView === "memory") await renderMemory(version);
    if (requestedView === "projects") await renderProjects(version);
    if (requestedView === "settings") await renderSettings(version);
  } catch (error) {
    if (version !== state.routeVersion) return;
    main.replaceChildren(el("div", { class: "view-error" }, el("h2", { text: "Couldn’t open this workspace" }), el("p", { text: error.message }), button("Try again", () => renderView(), { icon: "refresh" })));
  }
}

function newConversation(projectId = null) {
  if (state.chatBusy) { toast("Your current reply is still running. Wait for it to finish before opening a new conversation."); return; }
  state.session = null; state.messages = []; state.attachment = null; state.draft = ""; state.chatProject = projectId;
  saveSession(null); renderSessions(); renderView("chat");
}

async function openSession(session) {
  if (state.chatBusy) { toast("Your current reply is still running. Wait for it to finish before changing conversations."); return; }
  try {
    const result = await api(`/sessions/${encodeURIComponent(session.id)}/messages`);
    state.session = session; state.messages = result.messages || []; state.chatProject = session.project_id ?? null;
    state.attachment = null; state.draft = ""; saveSession(session.id); renderSessions(); renderView("chat");
  } catch (error) { toast(error.message, "error"); }
}

async function deleteSession(session) {
  if (state.chatBusy) return;
  if (!window.confirm(`Delete “${session.title || "New conversation"}” and its messages?`)) return;
  try {
    await api(`/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE" });
    if (String(state.session?.id) === String(session.id)) newConversation();
    await refreshLists(); await pollStatus();
  } catch (error) { toast(error.message, "error"); }
}

function welcome() {
  const documents = state.status?.stats?.documents || 0;
  const roots = state.roots.length;
  const cards = [
    { icon: "library", title: "Explore your library", text: "Find a file, read its contents, or get a clear summary.", action: () => renderView("library") },
    { icon: "memory", title: "Give your ideas a home", text: "Save the context you want your copilot to remember.", action: () => memoryModal() },
    { icon: "project", title: "Make room for a project", text: "Turn an idea into a plan, with memory that stays.", action: () => projectModal() },
  ];
  const connectedCopy = documents ? `${documents} document${documents === 1 ? "" : "s"} indexed from ${roots} local folder${roots === 1 ? "" : "s"}. Ask a question to start exploring.`
    : roots ? "Your folder is connected. Index its files to make them available for search." : "Connect a folder on your laptop to make its files available here.";
  return el("section", { class: "welcome" },
    el("div", { class: "welcome-heading" }, icon("spark"), "A LITTLE CLARITY, CLOSE TO HOME"),
    el("h1", {}, "Your knowledge.", el("br"), el("em", { text: "More connected." })),
    el("p", { class: "welcome-description", text: "A thoughtful space for your files, ideas, and projects. Ask, discover, and build — with everything staying on your laptop." }),
    el("div", { class: "welcome-actions" }, cards.map(card => el("button", { class: "action-card", onclick: card.action }, el("div", { class: "action-icon" }, icon(card.icon)), el("h3", { text: card.title }), el("p", { text: card.text }), icon("arrow", "card-arrow")))),
    el("div", { class: "connection-card" }, el("div", { class: "connection-icon" }, icon(documents ? "check" : "folder")), el("div", { class: "connection-copy" }, el("strong", { text: documents ? "Your library is ready" : roots ? "Let’s make your files searchable" : "Start with a folder, make it yours" }), el("p", { text: connectedCopy })), button(documents || roots ? "Open library" : "Connect folder", () => documents || roots ? renderView("library") : folderModal(), { icon: "arrow" })),
    el("div", { class: "welcome-footer" }, icon("shield"), "Your files. Your device. Your peace of mind."));
}

function renderChat() {
  const main = $("#main");
  const scroll = el("div", { class: "chat-scroll", id: "chat-scroll" });
  if (!state.session && !state.messages.length) scroll.append(welcome());
  else {
    const conversation = el("div", { class: "conversation", "aria-live": "polite", "aria-relevant": "additions" },
      el("div", { class: "conversation-header" }, el("div", {}, el("div", { class: "eyebrow", text: state.chatProject ? projectName(state.chatProject) : "YOUR LOCAL WORKSPACE" }), el("h1", { text: state.session?.title || "New conversation" })), button("New conversation", () => newConversation(state.chatProject), { icon: "plus", class: "small", disabled: state.chatBusy })));
    state.messages.forEach(message => conversation.append(messageNode(message)));
    if (state.chatBusy) conversation.append(el("div", { class: "message assistant", role: "status" }, assistantHeading(), el("div", { class: "pending-dots", "aria-label": "Working with your local knowledge" }, el("span"), el("span"), el("span")), el("div", { class: "small-text muted", text: state.status?.ollama?.chat_ready ? "Searching your library and thinking locally…" : "Finding relevant excerpts in your library…" })));
    scroll.append(conversation);
  }
  const project = projectSelect(state.chatProject, "Personal workspace", { "aria-label": "Conversation project", disabled: state.chatBusy || Boolean(state.session), onchange: event => { state.chatProject = numericId(event.target.value); } });
  const input = el("textarea", { id: "chat-input", rows: "2", "aria-label": "Message your local copilot", placeholder: "Ask a question about your files, ideas, or projects…", disabled: state.chatBusy, maxlength: "24000" });
  input.value = state.draft;
  input.addEventListener("input", () => { state.draft = input.value; input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 170)}px`; send.disabled = state.chatBusy || !input.value.trim(); });
  input.addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!state.chatBusy && input.value.trim()) sendMessage(); } });
  const send = el("button", { class: "send-button", type: "submit", "aria-label": "Send message", title: "Send message", disabled: state.chatBusy || !state.draft.trim() }, icon("up"));
  const form = el("form", { class: "composer", onsubmit: event => { event.preventDefault(); sendMessage(); } },
    state.attachment ? el("div", { class: "attachment-pill" }, icon("file"), el("span", { text: state.attachment.title }), iconButton("x", "Remove attached document", () => { state.attachment = null; renderChat(); })) : null,
    input, el("div", { class: "composer-bottom" }, iconButton("plus", "Choose a document from your library", () => renderView("library")), el("span", { class: "composer-hint", text: "Enter to send · Shift + Enter for a new line" }), send));
  const composer = el("div", { class: "composer-wrap" }, el("div", { class: "composer-context" }, el("div", { class: "project-control" }, icon("project"), project), el("span", { id: "chat-mode-label", text: state.status?.ollama?.chat_ready ? "Local model + your library" : "Local excerpts · model not ready" })), form, el("p", { class: "composer-disclaimer", text: "AI can make mistakes. Follow the sources and verify what matters." }));
  main.replaceChildren(el("div", { class: "chat-page" }, scroll, composer));
  if (state.messages.length) requestAnimationFrame(() => { scroll.scrollTop = scroll.scrollHeight; });
}

function assistantHeading() { return el("div", { class: "assistant-top" }, el("span", { class: "assistant-avatar" }, icon("spark")), "LocalMind"); }

function messageNode(message) {
  if (message.role === "user") return el("div", { class: "message user" }, el("div", { class: "user-message", text: message.content }));
  const node = el("div", { class: "message assistant" }, assistantHeading(), markdown(message.content));
  if (message.warning) node.append(el("div", { class: "warning-note", text: message.warning }));
  if (message.sources?.length) {
    node.append(el("div", { class: "sources-label", text: "From your library" }), el("div", { class: "sources" }, message.sources.slice(0, 12).map((source, index) => el("button", {
      class: "source-card", title: source.path || source.title, onclick: () => source.document_id ? openDocument(source.document_id) : toast("This source does not include a document reference.", "error"),
    }, el("span", { class: "source-number", text: index + 1 }), el("div", { class: "source-info" }, el("div", { class: "source-title", text: source.title || "Local document" }), el("div", { class: "source-path", text: `${source.path || ""}${source.page ? ` · page ${source.page}` : ""}` }))))));
  }
  if (message.trace?.length) node.append(el("details", { class: "tool-trace" }, el("summary", { text: `${message.trace.length} local tool action${message.trace.length === 1 ? "" : "s"}` }),
    message.trace.slice(0, 30).map(item => el("div", { class: "trace-item" }, icon("terminal"), el("div", {}, el("strong", { text: item.tool || "Local tool" }), el("div", { class: "trace-detail", text: typeof item.detail === "string" ? item.detail : JSON.stringify(item.detail || "") }))))));
  node.append(el("div", { class: "message-tools" }, iconButton("copy", "Copy response", () => copyText(message.content)), el("span", { text: "Processed on your device" })));
  return node;
}

async function sendMessage(override) {
  const text = String(override || state.draft).trim();
  if (!text || state.chatBusy) return;
  state.chatBusy = true; state.draft = "";
  const attachment = state.attachment;
  const optimistic = { role: "user", content: text, pending: true };
  state.messages.push(optimistic); renderChat();
  try {
    if (!state.session) {
      state.session = await api("/sessions", { method: "POST", body: { title: text.slice(0, 70), project_id: state.chatProject } });
      saveSession(state.session.id);
    }
    const result = await api("/chat", { method: "POST", body: { session_id: state.session.id, message: text, project_id: state.chatProject, document_id: attachment?.id || null }, timeout: 600000 });
    state.messages = state.messages.filter(message => message !== optimistic);
    state.messages.push({ role: "user", content: text }, { role: "assistant", ...result });
    state.attachment = null;
    await refreshLists();
    await pollStatus();
  } catch (error) {
    state.messages = state.messages.filter(message => message !== optimistic);
    state.draft = text;
    if (state.session) {
      try { state.messages = (await api(`/sessions/${state.session.id}/messages`)).messages || state.messages; } catch (_) { /* Keep the visible conversation if reconnection fails. */ }
    }
    toast(error.message, "error");
  } finally {
    state.chatBusy = false;
    if (state.view === "chat") renderChat();
    renderSessions();
  }
}

async function renderLibrary(version) {
  const query = state.libraryQuery.trim();
  const requests = [api("/roots"), api(`/documents?q=${encodeURIComponent(query)}&limit=30&offset=${state.libraryOffset}`)];
  if (query) requests.push(api("/search", { method: "POST", body: { query, limit: 6 } }));
  const [rootData, documentsData, searchData] = await Promise.all(requests);
  if (version !== state.routeVersion) return;
  state.roots = rootData.roots || [];
  const page = el("div", { class: "page" }, pageHeader("YOUR PERSONAL KNOWLEDGE", "Library", "A clear view of the files you’ve connected. All on this device.", button("Connect folder", () => folderModal(), { class: "primary", icon: "plus" })));
  const folderList = el("div", { class: "folder-list" });
  if (!state.roots.length) folderList.append(emptyState("folder", "Choose where your knowledge lives", "Connect a folder on your hard disk or SSD. Notes, PDFs, documents, and code become searchable."));
  for (const root of state.roots) {
    const reindex = button("Reindex", () => startIndex(root.id), { class: "small", icon: "refresh", disabled: state.status?.indexing?.running });
    reindex.dataset.indexButton = "true";
    folderList.append(el("div", { class: "folder-row" }, el("div", { class: "folder-badge" }, icon("folder")), el("div", { class: "folder-info" }, el("strong", { text: root.label || root.path.split(/[\\/]/).filter(Boolean).pop() || root.path }), el("span", { class: "folder-path", text: root.path, title: root.path })), el("div", { class: "folder-actions" }, reindex, iconButton("trash", "Remove folder from library", () => removeRoot(root), "danger"))));
  }
  const indexAll = button("Index all folders", () => startIndex(), { icon: "refresh", class: "small", disabled: !state.roots.length || state.status?.indexing?.running });
  indexAll.dataset.indexButton = "true";
  indexAll.dataset.requiresRoots = "true";
  const indexStatus = el("div", { class: "index-status", id: "index-status", "aria-live": "polite" });
  page.append(el("section", { class: "panel folder-panel" }, el("div", { class: "panel-header" }, el("div", {}, el("h2", { text: "Connected folders" }), el("p", { text: "You choose the folders. Your copilot reads the supported files within them." })), indexAll), folderList, indexStatus));
  const searchInput = el("input", { type: "search", value: state.libraryQuery, placeholder: "Search filenames or ask something about their contents…", "aria-label": "Search library", maxlength: "2000" });
  const searchForm = el("form", { class: "search-bar", onsubmit: event => { event.preventDefault(); state.libraryQuery = searchInput.value; state.libraryOffset = 0; renderView("library"); } }, icon("search"), searchInput, el("button", { type: "submit", class: "button small", text: "Search" }));
  searchInput.addEventListener("input", () => { state.libraryQuery = searchInput.value; });
  searchInput.addEventListener("search", () => { if (!searchInput.value) { state.libraryQuery = ""; state.libraryOffset = 0; renderView("library"); } });
  page.append(el("div", { class: "library-toolbar" }, searchForm, el("span", { class: "result-count", text: `${documentsData.total ?? documentsData.documents?.length ?? 0} document${documentsData.total === 1 ? "" : "s"}` })));
  if (query) {
    const hits = searchData?.results || [];
    const section = el("section", { class: "search-results" }, el("div", { class: "section-caption" }, icon("search"), `Content matches · ${hits.length}`));
    if (!hits.length) section.append(el("p", { class: "small-text muted", text: "No matching excerpts found. Try a specific phrase, filename, or a different question." }));
    hits.forEach(hit => section.append(el("div", { class: "search-hit" }, el("div", { class: "search-hit-top" }, el("button", { class: "search-hit-title", text: hit.title, onclick: () => openDocument(hit.document_id) }), button("Read document", () => openDocument(hit.document_id), { icon: "arrow", class: "small subtle" })), el("div", { class: "search-hit-path", text: `${hit.path || ""}${hit.page ? ` · page ${hit.page}` : ""}` }), el("p", { class: "search-excerpt", text: hit.text }))));
    page.append(section);
  }
  const documents = documentsData.documents || [];
  if (!documents.length) page.append(el("div", { class: "table-panel" }, emptyState("file", query ? "No filenames match this search" : "Your library has room to grow", query ? "Content matches appear above when relevant excerpts are available." : "Connect a folder and index its files. Your documents will appear here, ready to read and explore.")));
  else {
    const table = el("table", { class: "document-table" }, el("thead", {}, el("tr", {}, el("th", { text: "Document", scope: "col" }), el("th", { class: "document-type", text: "Type", scope: "col" }), el("th", { class: "document-size", text: "Size", scope: "col" }), el("th", { class: "document-updated", text: "Indexed", scope: "col" }), el("th", { scope: "col" }, el("span", { class: "sr-only", text: "Actions" })))),
      el("tbody", {}, documents.map(doc => el("tr", {}, el("td", {}, el("button", { class: "document-name", onclick: () => openDocument(doc.id) }, icon("file"), el("span", {}, el("span", { class: "document-title", text: doc.title }), el("span", { class: "document-subpath", title: doc.path, text: doc.path })))), el("td", { class: "document-type" }, el("span", { class: "file-tag", text: String(doc.extension || "text").replace(/^\./, "") })), el("td", { class: "document-size", text: formatSize(doc.size) }), el("td", { class: "document-updated", text: formatDate(doc.updated_at) }), el("td", {}, iconButton("chevron", `Read ${doc.title}`, () => openDocument(doc.id)))))));
    const total = documentsData.total ?? documents.length;
    page.append(el("div", { class: "table-panel" }, table, el("div", { class: "pagination" }, el("span", { text: `${state.libraryOffset + 1}–${state.libraryOffset + documents.length} of ${total}` }), el("div", { class: "pagination-actions" }, button("Previous", () => { state.libraryOffset = Math.max(0, state.libraryOffset - 30); renderView("library"); }, { class: "small", disabled: state.libraryOffset === 0 }), button("Next", () => { state.libraryOffset += 30; renderView("library"); }, { class: "small", disabled: state.libraryOffset + documents.length >= total })))));
  }
  $("#main").replaceChildren(page); renderIndexStatus(indexStatus);
}

async function startIndex(rootId) {
  try {
    await api("/index", { method: "POST", body: rootId !== undefined ? { root_id: rootId } : {} });
    toast("Indexing started. You can keep using your workspace.");
    await pollStatus();
  } catch (error) { toast(error.message, "error"); }
}

async function removeRoot(root) {
  if (state.status?.indexing?.running) { toast("Wait for indexing to finish before removing a folder."); return; }
  if (!window.confirm(`Remove “${root.label || root.path}” from this library? Its indexed copies will be removed. Original files stay on your disk.`)) return;
  try { await api(`/roots/${root.id}`, { method: "DELETE" }); await refreshLists(); await pollStatus(); renderView("library"); toast("Folder removed from the library."); }
  catch (error) { toast(error.message, "error"); }
}

function openModal(title, description, content, className = "") {
  closeModal();
  const layer = $("#modal-layer");
  const dialog = el("section", { class: `modal ${className}`, role: "dialog", "aria-modal": "true", "aria-labelledby": "modal-title", tabindex: "-1" },
    el("div", { class: "modal-header" }, el("div", {}, el("h2", { id: "modal-title", text: title }), el("p", { text: description })), iconButton("x", "Close dialog", closeModal)), content);
  const previousFocus = document.activeElement;
  layer.replaceChildren(dialog); layer.hidden = false;
  state.modal = { dialog, previousFocus };
  requestAnimationFrame(() => { ($("input,textarea,select,button", content) || dialog).focus(); });
  return dialog;
}

function closeModal() {
  if (!state.modal) return;
  const previous = state.modal.previousFocus;
  $("#modal-layer").hidden = true; $("#modal-layer").replaceChildren(); state.modal = null;
  if (previous?.isConnected) previous.focus();
}

function formField(label, input, help) {
  const id = input.id || `field-${Math.random().toString(36).slice(2, 9)}`;
  input.id = id;
  return el("div", { class: "modal-field" }, el("label", { class: "field-label", for: id, text: label }), input, help ? el("p", { class: "field-help", text: help }) : null);
}

function folderModal() {
  const path = el("input", { class: "field-input", type: "text", placeholder: "D:\\Knowledge or C:\\Users\\Your Name\\Documents", required: true, autocomplete: "off", spellcheck: "false" });
  const label = el("input", { class: "field-input", type: "text", placeholder: "e.g. University notes", maxlength: "120" });
  const submit = el("button", { class: "button primary", type: "submit" }, icon("folder"), "Connect & index");
  const error = el("div");
  const form = el("form", { class: "modal-content", onsubmit: async event => {
    event.preventDefault(); if (!path.value.trim()) return;
    submit.disabled = true; error.replaceChildren();
    try {
      const root = await api("/roots", { method: "POST", body: { path: path.value.trim(), label: label.value.trim() } });
      closeModal(); await refreshLists(); await pollStatus(); await renderView("library");
      toast("Folder connected. Your original files stay where they are.");
      await startIndex(root.id);
    } catch (failure) { error.replaceChildren(inlineError(failure.message)); }
    finally { submit.disabled = false; }
  } }, formField("Local folder path", path, "Paste the full path of a folder on this laptop. Its subfolders will be included. Hidden files, credentials, and common dependency folders are excluded."), formField("Folder label (optional)", label), error,
    el("div", { class: "modal-buttons" }, button("Cancel", closeModal), submit));
  openModal("Connect a local folder", "Give your copilot a place to start. Choose a folder you want it to read.", form);
}

async function openDocument(id) {
  openModal("Opening document…", "Reading its locally indexed contents.", el("div", { class: "modal-content" }, loading()));
  const opened = state.modal;
  try {
    const doc = await api(`/documents/${encodeURIComponent(id)}`);
    if (state.modal !== opened) return;
    const toolbar = el("div", { class: "reader-toolbar" }, el("span", { class: "file-tag", text: `Full extracted text · ${String(doc.extension || "text").replace(/^\./, "")} · ${formatSize(doc.size)}` }),
      el("a", { class: "button small", href: `/api/documents/${encodeURIComponent(id)}/download`, download: "" }, icon("download"), "Download text"),
      button("Summarize in chat", () => summarizeDocument(doc), { class: "primary small", icon: "spark", disabled: state.chatBusy }));
    const body = el("div", { class: "reader-body" }, doc.text ? el("pre", { class: "reader-text", text: doc.text }) : el("p", { class: "reader-empty", text: "This file has no extractable text. Image-only PDFs need OCR before their contents can be indexed." }));
    const dialog = el("section", { class: "modal reader-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "modal-title", tabindex: "-1" },
      el("div", { class: "modal-header" }, el("div", {}, el("h2", { id: "modal-title", text: doc.title }), el("p", { class: "reader-path", text: doc.path })), iconButton("x", "Close document", closeModal)), toolbar, body);
    $("#modal-layer").replaceChildren(dialog); state.modal.dialog = dialog;
    $("button", dialog)?.focus();
  } catch (error) {
    if (state.modal !== opened) return;
    $(".modal-content", state.modal.dialog).replaceChildren(inlineError(error.message), button("Close", closeModal));
  }
}

function summarizeDocument(doc) {
  if (state.chatBusy) return;
  closeModal(); newConversation(); state.attachment = { id: doc.id, title: doc.title };
  renderChat(); sendMessage(`Summarize “${doc.title}”. Explain its main points, key details, and any useful next steps. Ground the summary in the document.`);
}

async function renderMemory(version) {
  const params = new URLSearchParams({ q: state.memoryQuery });
  if (state.memoryProject) params.set("project_id", state.memoryProject);
  const data = await api(`/memories?${params}`);
  if (version !== state.routeVersion) return;
  const page = el("div", { class: "page" }, pageHeader("CONTEXT THAT STAYS WITH YOU", "Memory", "Keep the details, decisions, and preferences worth remembering.", button("Add memory", () => memoryModal(), { class: "primary", icon: "plus" })));
  const query = el("input", { type: "search", value: state.memoryQuery, placeholder: "Search your memories…", "aria-label": "Search memories", maxlength: "2000" });
  const form = el("form", { class: "search-bar", onsubmit: event => { event.preventDefault(); state.memoryQuery = query.value; renderView("memory"); } }, icon("search"), query, el("button", { type: "submit", class: "button small", text: "Search" }));
  query.addEventListener("input", () => { state.memoryQuery = query.value; });
  query.addEventListener("search", () => { if (!query.value) { state.memoryQuery = ""; renderView("memory"); } });
  const project = projectSelect(state.memoryProject, "All projects", { "aria-label": "Filter memories by project", onchange: event => { state.memoryProject = event.target.value; renderView("memory"); } });
  page.append(el("div", { class: "filter-toolbar" }, form, project));
  const memories = data.memories || [];
  if (!memories.length) page.append(el("div", { class: "table-panel" }, emptyState("memory", state.memoryQuery || state.memoryProject ? "No memories match these filters" : "A little context goes a long way", state.memoryQuery || state.memoryProject ? "Try another phrase or choose a different project." : "Save a note, a preference, or a decision. Your copilot can recall it in future conversations.", state.memoryQuery || state.memoryProject ? null : button("Save your first memory", () => memoryModal(), { class: "primary", icon: "plus" }))));
  else page.append(el("div", { class: "memory-grid" }, memories.map(memory => el("article", { class: "memory-card" },
    el("div", { class: "memory-card-head" }, el("span", { class: `kind-tag ${["decision", "preference"].includes(memory.kind) ? memory.kind : ""}`, text: memory.kind || "note" }), el("div", { class: "memory-card-actions" }, iconButton("edit", "Edit memory", () => memoryModal(memory.project_id, memory)), iconButton("trash", "Delete memory", () => deleteMemory(memory), "danger"))),
    el("p", { class: "memory-content", text: memory.content }),
    el("div", { class: "memory-card-footer" }, el("span", { class: "memory-scope", text: memory.project_id ? projectName(memory.project_id) : "Personal memory" }), el("span", { text: formatDate(memory.created_at) }))))));
  $("#main").replaceChildren(page);
}

function memoryModal(projectId = state.memoryProject, memory = null) {
  const content = el("textarea", { class: "field-input", placeholder: "What would you like your copilot to remember?", required: true, maxlength: "20000" });
  content.value = memory?.content || "";
  const kind = el("select", { class: "field-input" }, el("option", { value: "note", text: "Note" }), el("option", { value: "decision", text: "Decision" }), el("option", { value: "preference", text: "Preference" }));
  if (memory && !["note", "decision", "preference"].includes(memory.kind)) kind.append(el("option", { value: memory.kind, text: memory.kind }));
  kind.value = memory?.kind || "note";
  const project = projectSelect(projectId, "Personal memory", { class: "field-input" });
  const error = el("div");
  const submit = el("button", { type: "submit", class: "button primary" }, icon("check"), "Save memory");
  const form = el("form", { class: "modal-content", onsubmit: async event => {
    event.preventDefault(); if (!content.value.trim()) return; submit.disabled = true; error.replaceChildren();
    try {
      await api(memory ? `/memories/${memory.id}` : "/memories", { method: memory ? "PUT" : "POST", body: { content: content.value.trim(), kind: kind.value, project_id: numericId(project.value) } });
      closeModal(); await pollStatus();
      if (state.view === "projects" && state.projectDetail) renderView("projects"); else renderView("memory");
      toast(memory ? "Memory updated on this device." : "Memory saved on this device.");
    } catch (failure) { error.replaceChildren(inlineError(failure.message)); }
    finally { submit.disabled = false; }
  } }, formField("Memory", content, "Write the context you want to keep. Memories are stored locally and available to your copilot."), el("div", { class: "modal-row" }, formField("Type", kind), formField("Scope", project)), error, el("div", { class: "modal-buttons" }, button("Cancel", closeModal), submit));
  openModal(memory ? "Edit memory" : "Remember something", memory ? "Keep your saved context useful and up to date." : "Useful context for your next conversation, and the one after that.", form);
}

async function deleteMemory(memory) {
  if (!window.confirm("Delete this saved memory?")) return;
  try { await api(`/memories/${memory.id}`, { method: "DELETE" }); await pollStatus(); renderView("memory"); toast("Memory deleted."); }
  catch (error) { toast(error.message, "error"); }
}

async function renderProjects(version) {
  const data = await api("/projects");
  if (version !== state.routeVersion) return;
  state.projects = data.projects || [];
  if (state.projectDetail) { await renderProjectDetail(version); return; }
  const page = el("div", { class: "page" }, pageHeader("IDEAS WITH SOMEWHERE TO GO", "Projects", "A home for each project, its plans, and the context behind them.", button("New project", () => projectModal(), { class: "primary", icon: "plus" })));
  if (!state.projects.length) page.append(el("div", { class: "table-panel" }, emptyState("project", "Good projects start with an idea", "Create a project, keep its context together, and let your local copilot help shape a plan.", button("Create your first project", () => projectModal(), { class: "primary", icon: "plus" }))));
  else page.append(el("div", { class: "projects-grid" }, state.projects.map(project => el("button", { class: "project-card", onclick: () => { state.projectDetail = project.id; renderView("projects"); } }, el("div", { class: "folder-badge" }, icon("project")), el("h2", { text: project.name }), el("p", { text: project.description || "Add memories and create a plan to build your project’s context." }), el("div", { class: "project-card-footer" }, el("span", { text: `Created ${formatDate(project.created_at)}` }), icon("arrow"))))));
  $("#main").replaceChildren(page);
}

function projectModal() {
  const name = el("input", { class: "field-input", type: "text", placeholder: "e.g. Final year research", required: true, maxlength: "120" });
  const description = el("textarea", { class: "field-input", placeholder: "What are you working toward? Add useful context, goals, or constraints.", maxlength: "12000" });
  const error = el("div");
  const submit = el("button", { type: "submit", class: "button primary" }, icon("plus"), "Create project");
  const form = el("form", { class: "modal-content", onsubmit: async event => {
    event.preventDefault(); if (!name.value.trim()) return; submit.disabled = true; error.replaceChildren();
    try {
      const project = await api("/projects", { method: "POST", body: { name: name.value.trim(), description: description.value.trim() } });
      state.projectDetail = project.id; closeModal(); await refreshLists(); await pollStatus(); renderView("projects"); toast("Your project is ready.");
    } catch (failure) { error.replaceChildren(inlineError(failure.message)); }
    finally { submit.disabled = false; }
  } }, formField("Project name", name), formField("Description (optional)", description), error, el("div", { class: "modal-buttons" }, button("Cancel", closeModal), submit));
  openModal("Make room for a project", "Start with a name. Build its context as you go.", form);
}

async function renderProjectDetail(version) {
  const id = state.projectDetail;
  const [project, memoryData] = await Promise.all([api(`/projects/${id}`), api(`/memories?project_id=${id}`)]);
  if (version !== state.routeVersion) return;
  const page = el("div", { class: "page" }, el("button", { class: "back-button", onclick: () => { state.projectDetail = null; renderView("projects"); } }, icon("arrow"), "All projects"),
    pageHeader("PROJECT WORKSPACE", project.name, `Created ${formatDate(project.created_at)} · Stored on this device`, button("Open project chat", () => newConversation(project.id), { class: "primary", icon: "chat", disabled: state.chatBusy })));
  const prompt = el("textarea", { class: "field-input plan-prompt", placeholder: "Optional: describe the plan you need, your timeline, or important constraints.", maxlength: "12000", "aria-label": "Instructions for project plan" });
  const result = el("div");
  function showPlan(content, path) {
    result.replaceChildren(el("div", { class: "plan-content" }, markdown(content), el("div", { class: "project-actions" }, button("Copy plan", () => copyText(content), { icon: "copy", class: "small" })),
      path ? el("p", { class: "plan-path", text: `Saved locally: ${path}` }) : null));
  }
  if (project.plan) showPlan(project.plan, project.plan_path);
  const generate = button("Generate project plan", async () => {
    generate.disabled = true; generate.replaceChildren(icon("refresh"), "Thinking locally…"); result.replaceChildren();
    try {
      const plan = await api(`/projects/${id}/plan`, { method: "POST", body: { prompt: prompt.value.trim() }, timeout: 600000 });
      showPlan(plan.content, plan.path);
      toast("Project plan created and saved locally.");
    } catch (error) { result.replaceChildren(inlineError(error.message)); }
    finally { generate.disabled = false; generate.replaceChildren(icon("spark"), "Generate project plan"); }
  }, { class: "primary", icon: "spark" });
  const planPanel = el("section", { class: "panel" }, el("div", { class: "panel-header" }, el("div", {}, el("h2", { text: "From idea to next steps" }), el("p", { text: "Create a plan using your project description, saved memory, and local model." }))), prompt, generate, result);
  if (!state.status?.ollama?.chat_ready) planPanel.append(el("p", { class: "field-help", text: "A local chat model is needed to generate a plan. You can add project memories while setting it up." }), button("Model settings", () => renderView("settings"), { class: "subtle small", icon: "arrow" }));
  const memories = memoryData.memories || [];
  const memoryPanel = el("section", { class: "panel" }, el("div", { class: "panel-header" }, el("div", {}, el("h2", { text: "Project memory" }), el("p", { text: `${memories.length} saved ${memories.length === 1 ? "memory" : "memories"}` })), button("Add", () => memoryModal(project.id), { class: "small", icon: "plus" })),
    memories.length ? memories.map(memory => el("div", { class: "project-memory" }, el("span", { class: "kind-tag", text: memory.kind || "note" }), el("p", { text: memory.content }))) : el("p", { class: "small-text muted", text: "Keep goals, decisions, and working preferences here. They’ll be available in project conversations." }));
  page.append(el("div", { class: "project-detail-layout" }, el("div", {}, el("section", { class: "panel" }, el("div", { class: "panel-header" }, el("h2", { text: "About this project" })), el("p", { class: "project-description", text: project.description || "This project has no description yet. Add memories to give your copilot useful context." })), planPanel), el("div", {}, memoryPanel)));
  $("#main").replaceChildren(page);
}

async function renderSettings(version) {
  const settings = await api("/settings");
  if (version !== state.routeVersion) return;
  state.settings = settings;
  const runtime = state.status?.ollama || {};
  const modelNames = runtime.models || [];
  function modelSelect(selected, label) {
    const names = [...new Set([selected, ...modelNames].filter(Boolean))];
    const canonicalName = name => name.includes(":") ? name : `${name}:latest`;
    const installed = name => modelNames.some(candidate => canonicalName(candidate) === canonicalName(name));
    const select = el("select", { class: "field-input", "aria-label": label }, names.map(name => el("option", { value: name, text: `${name}${!installed(name) ? " (not installed)" : ""}` })));
    select.value = selected || ""; return select;
  }
  const chat = modelSelect(settings.chat_model, "Local chat model");
  const embedding = modelSelect(settings.embedding_model, "Local embedding model");
  const context = el("input", { class: "field-input", type: "number", value: settings.context_size || 8192, min: "4096", max: "16384", step: "1024", required: true });
  const feedback = el("div");
  const save = el("button", { type: "submit", class: "button primary" }, icon("check"), "Save settings");
  const form = el("form", { class: "panel", onsubmit: async event => {
    event.preventDefault(); save.disabled = true; feedback.replaceChildren();
    try {
      state.settings = await api("/settings", { method: "PUT", body: { chat_model: chat.value, embedding_model: embedding.value, context_size: Number(context.value) } });
      await pollStatus(); toast("Local model settings saved."); renderView("settings");
    } catch (error) { feedback.replaceChildren(inlineError(error.message)); }
    finally { save.disabled = false; }
  } }, el("div", { class: "panel-header" }, el("div", {}, el("h2", { text: "Your local models" }), el("p", { text: "Choose from models available in your local Ollama runtime." }))),
    el("div", { class: "settings-field" }, formField("Chat model", chat, "The model that reasons, summarizes, and works with your copilot’s local tools.")),
    el("div", { class: "settings-field" }, formField("Embedding model", embedding, "Turns file excerpts into searchable vectors. Reindex folders after changing this model.")),
    el("div", { class: "settings-field" }, formField("Context window (tokens)", context, "Choose 4,096–16,384 tokens. 8,192 is a practical starting point for a laptop with 16 GB RAM; larger windows use more memory.")), feedback,
    el("div", { class: "settings-actions" }, save, el("span", { class: "field-help", text: "Selecting a model never downloads it." })));
  const runtimePanel = el("section", { class: "panel" }, el("div", { class: "panel-header" }, el("h2", { text: "Local runtime" }), icon("terminal")),
    el("div", { class: "runtime-line" }, el("span", { text: "Ollama" }), el("strong", { text: runtime.online ? "Connected" : "Not connected" })),
    el("div", { class: "runtime-line" }, el("span", { text: "Chat model" }), el("strong", { text: runtime.chat_ready ? "Ready" : "Not ready" })),
    el("div", { class: "runtime-line" }, el("span", { text: "Semantic search" }), el("strong", { text: runtime.embedding_ready ? "Ready" : "Keyword search available" })),
    el("p", { class: "runtime-description", text: "Documents, search, and memory work without a chat model. Until the model is ready, chat returns local excerpts instead of a generated answer." }));
  if (runtime.error) runtimePanel.append(el("p", { class: "runtime-error", text: runtime.error }));
  if (!runtime.chat_ready || !runtime.embedding_ready) runtimePanel.append(el("p", { class: "field-help", text: "Run setup-models.cmd from this project's scripts folder once, then start.cmd. Downloads need an internet connection; processing stays local. The Windows edition uses its own local model service." }), el("div", { class: "setup-commands", text: "scripts\\setup-models.cmd\nscripts\\start.cmd" }));
  runtimePanel.append(button("Refresh status", async () => { await pollStatus(); renderView("settings"); }, { class: "subtle small", icon: "refresh" }));
  const privacy = el("section", { class: "panel" }, el("div", { class: "panel-header" }, el("h2", { text: "A private workspace" }), icon("shield")),
    el("div", { class: "privacy-item" }, icon("check"), "Your files are read from folders you choose."),
    el("div", { class: "privacy-item" }, icon("check"), "Document text, conversations, and memories stay on this device."),
    el("div", { class: "privacy-item" }, icon("check"), "The copilot uses your local model. No paid cloud API is needed."),
    el("div", { class: "eyebrow", text: "LOCAL DATA FOLDER" }), el("div", { class: "data-path", text: settings.data_dir || "Unavailable" }));
  const page = el("div", { class: "page" }, pageHeader("MAKE IT FEEL LIKE YOURS", "Settings", "A little setup for a copilot that runs close to home."), el("div", { class: "settings-layout" }, el("div", {}, form), el("div", { class: "settings-side" }, runtimePanel, privacy)));
  $("#main").replaceChildren(page);
}

$("#new-chat").addEventListener("click", () => newConversation());
$(".brand").addEventListener("click", event => { event.preventDefault(); renderView("chat"); });
$$("[data-view]").forEach(node => node.addEventListener("click", () => { if (node.dataset.view === "projects") state.projectDetail = null; renderView(node.dataset.view); }));
$("#runtime-pill").addEventListener("click", () => renderView("settings"));
$("#mobile-menu").addEventListener("click", () => setSidebar(!$("#sidebar").classList.contains("open")));
$("#sidebar-scrim").addEventListener("click", () => setSidebar(false));
$("#modal-layer").addEventListener("click", event => { if (event.target === event.currentTarget) closeModal(); });
document.addEventListener("keydown", event => {
  if (event.key === "Escape") { if (state.modal) closeModal(); else setSidebar(false); }
  if (event.key === "Tab" && state.modal) {
    const focusable = $$("button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex='0']", state.modal.dialog);
    if (!focusable.length) { event.preventDefault(); state.modal.dialog.focus(); return; }
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || !state.modal.dialog.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !state.modal.dialog.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  }
});
window.addEventListener("hashchange", () => { const view = location.hash.slice(1); if (view !== state.view) renderView(view); });

async function boot() {
  await Promise.allSettled([pollStatus(), refreshLists()]);
  let saved;
  try { saved = localStorage.getItem("localmind.session"); } catch (_) { /* Storage is optional. */ }
  const session = state.sessions.find(item => String(item.id) === saved);
  if (session) {
    try { state.messages = (await api(`/sessions/${session.id}/messages`)).messages || []; state.session = session; state.chatProject = session.project_id ?? null; }
    catch (_) { saveSession(null); }
  }
  renderSessions();
  renderView(location.hash.slice(1) || "chat");
  setInterval(pollStatus, 4500);
}

renderChat();
boot();
