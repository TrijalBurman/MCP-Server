import json, os
from pathlib import Path
import httpx, streamlit as st

AGENT_URL=os.getenv("AGENT_URL","http://localhost:8001")
MCP_URL=os.getenv("MCP_SERVER_URL","http://localhost:8000")
st.set_page_config(page_title="Knowledge Copilot",page_icon="🧠",layout="wide")
st.markdown("""<style>
.tool-call-block{background:#1e2130;border-left:3px solid #4dabf7;padding:8px 12px;border-radius:4px;font-family:monospace;font-size:.85em;margin:4px 0}
.thought-block{background:#1a1a2e;border-left:3px solid #a855f7;padding:8px 12px;border-radius:4px;font-size:.85em;margin:4px 0;font-style:italic}
</style>""",unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages=[]
if "show_trace" not in st.session_state: st.session_state.show_trace=False

def call_agent(msg,hist):
    with httpx.Client(timeout=300) as c:
        r=c.post(f"{AGENT_URL}/chat",json={"message":msg,"history":hist}); r.raise_for_status(); return r.json()

def mcp(tool,params=None):
    with httpx.Client(timeout=60) as c:
        r=c.post(f"{MCP_URL}/mcp/tools/call",json={"tool":tool,"params":params or {}}); r.raise_for_status()
        return r.json().get("result",{})

def render_trace(trace,steps):
    with st.expander(f"🔍 Agent trace ({steps} steps)"):
        for i,s in enumerate(trace,1):
            if s.get("thought"): st.markdown(f'<div class="thought-block">💭 Thought {i}: {s["thought"]}</div>',unsafe_allow_html=True)
            if s.get("action"):  st.markdown(f'<div class="tool-call-block">🔧 {s["action"]}({json.dumps(s["action_input"])})</div>',unsafe_allow_html=True)
            if s.get("observation"):
                with st.expander(f"Observation {i}"):
                    try: st.json(json.loads(s["observation"]))
                    except: st.text(s["observation"])

with st.sidebar:
    st.title("🧠 Knowledge Copilot"); st.caption("Local-First AI — fully offline"); st.divider()
    st.subheader("📄 Documents")
    up=st.file_uploader("Drop files (PDF,MD,TXT,DOCX)",type=["pdf","md","txt","docx"],accept_multiple_files=True,label_visibility="collapsed")
    if up:
        d=Path("/app/data/documents")
        if not d.exists(): d=Path("../data/documents")
        d.mkdir(parents=True,exist_ok=True)
        for f in up: (d/f.name).write_bytes(f.getvalue())
        st.success(f"Saved {len(up)} file(s)")
    if st.button("🔄 Ingest Documents"):
        with st.spinner("Indexing..."):
            try: r=mcp("ingest_documents"); st.success(f"Indexed {r.get('documents_indexed','?')} chunks!")
            except Exception as e: st.error(str(e))
    st.divider(); st.subheader("⚙️ Settings")
    st.session_state.show_trace=st.toggle("Show agent reasoning trace",value=st.session_state.show_trace)
    if st.button("🗑️ Clear conversation"): st.session_state.messages=[]; st.rerun()
    st.divider()
    with st.expander("📋 Project Status"):
        try: st.markdown(mcp("list_project_status").get("status","_No status_"))
        except: st.caption("MCP server not reachable")
    with st.expander("📝 Notes"):
        try:
            notes=mcp("list_notes").get("notes",[])
            [st.markdown(f"**{n['title']}**") for n in notes] if notes else st.caption("No notes yet")
        except: st.caption("MCP server not reachable")
    with st.expander("⚖️ Decisions"):
        try:
            dec=mcp("read_decisions",{"limit":10}).get("decisions",[])
            [st.markdown(f"**#{d['id']} {d['title']}**\n\n_{d.get('rationale','')}_{chr(10)}---") for d in reversed(dec)] if dec else st.caption("No decisions yet")
        except: st.caption("MCP server not reachable")

st.title("💬 Knowledge Copilot")
st.caption("Powered by qwen2.5:7b · MCP Memory · Local RAG — 100% offline")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"]=="assistant" and msg.get("trace") and st.session_state.show_trace:
            render_trace(msg["trace"],msg.get("steps",0))

if prompt:=st.chat_input("Ask anything about your project or documents..."):
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    hist=[{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[:-1]]
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                res=call_agent(prompt,hist); answer=res.get("answer","No response.")
                trace=res.get("trace",[]); steps=res.get("steps",0)
                st.markdown(answer)
                if trace and st.session_state.show_trace: render_trace(trace,steps)
                entry={"role":"assistant","content":answer,"trace":trace,"steps":steps}
            except Exception as e:
                answer=f"❌ Error: {e}"; st.error(answer); entry={"role":"assistant","content":answer}
    st.session_state.messages.append(entry)
