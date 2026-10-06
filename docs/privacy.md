# Privacy and local access

## Data flow

The browser connects to the local app at `127.0.0.1:8765`. The Windows launcher manages a private Ollama server at `127.0.0.1:11435`, separate from a tray instance on 11434. The app writes local SQLite storage, and its MCP client starts a native local stdio subprocess sharing that database. No application feature sends document text or conversation contents to a hosted API. All frontend assets are bundled locally, with no CDN or analytics requests.

Package installation and the optional runtime/model setup scripts contact package registries and official Ollama download servers. Once dependencies and models are available, inference and normal application use work offline. The setup scripts do not upload your indexed documents.

## What the copilot can read

The user adds specific ordinary folders on fixed or removable local drives, such as `D:\Knowledge`. The scanner follows those approved roots and supported files only. It skips hidden entries, known credentials, dependency/build directories, unsupported formats, and the application's data folder. Whole drive roots, Windows system folders, UNC/device paths, mapped network drives, symbolic links, junctions, and other reparse points are excluded. OneDrive placeholders and reparse-backed folders need an ordinary local copy. Nothing silently scans an entire drive.

The index stores complete extracted text. Search returns selected chunks; the document reader returns text from the stored extraction snapshot. MCP reads validate that the source still lies under its approved local root, has no reparse-point ancestors, and has not changed or disappeared. Native source reads validate Windows handles and resolved paths while preventing write/delete sharing. Rescanning refreshes changed documents and removes successfully enumerated deleted files. Removing a root purges its indexed documents and chunks.

These exclusions are practical safeguards, not a guarantee that every possible secret is recognized. An ordinary Markdown note can contain a password. Choose source folders according to what you want the assistant and local application to access.

## Memory changes and document instructions

Documents and previous chat messages are untrusted reference material. Their contents should not become instructions to run commands or change memory. The built-in chat agent uses read-only MCP retrieval tools. It does not execute shell commands or create arbitrary files in your source folders.

The application lets you explicitly save, edit, and delete memories and create projects. Chat also accepts a direct `/remember <note>` or `remember that <note>` command from the user's message, handled by a deterministic command parser before model inference. Retrieved documents and tool outputs cannot invoke that parser. Project plans retrieve approved indexed evidence over local MCP and append local file references when sources are found. The standalone MCP server additionally exposes `remember`, `forget`, and `create_project` for authorized external clients. Tool annotations distinguish read-only operations and destructive memory deletion, but a client must respect user authorization; annotations alone are not access control.

An external MCP client receives your local text. If you connect a cloud model or cloud-enabled client to this server, that client can transmit returned data beyond the laptop. Use a local client and local model for an entirely local workflow.

## Storage and machine access

The app's data directory defaults to `<checkout>\.local-copilot` and contains extracted document text, chunks, vectors, explicit memories, project descriptions, conversations, and generated plans. It uses an ordinary SQLite database with write-ahead logging; it does not implement encryption at rest. Back up the full directory after stopping the app and MCP clients. Copying only the main database while it is active can miss pending WAL data. Runtime binaries, model weights, and logs stay under `<checkout>\.runtime`.

The web app is intended for a trusted single user on a laptop, with a loopback listener. Do not expose it to a public interface or port-forward it. Other processes running under your account may access the same files. OS account separation, filesystem permissions, full-disk encryption, and local malware protection remain outside this application's implementation.

## Local model runtime

The app accepts only HTTP loopback Ollama URLs and rejects cloud-tagged model names. It also checks model metadata before inference and refuses models configured for remote inference. Windows launchers set `OLLAMA_NO_CLOUD=1`, the private loopback host, and the checkout's model directory for their managed process. They do not change permanent Windows environment variables, install a service, or stop an unrelated tray server. The app does not download models from its user interface.

CMD wrappers use an execution policy limited to their PowerShell invocation; they do not persist a user or machine policy change. Stopping processes requires a matching workspace, executable, and recorded creation time. The scripts act on their own local processes and never reclaim a port by killing an unrelated application's process.

Deleting an explicit memory removes that database row. Deleting a conversation removes its saved messages. Generated project plans are separate files in the data directory. Source documents on your HDD/SSD remain under your control and are not deleted when you remove an indexed root.
