import json, os
from pathlib import Path
import httpx, streamlit as st
AGENT=os.getenv("AGENT_URL","http://localhost:8001"); MCP=os.getenv("MCP_URL","http://localhost:8000")
DATA=Path(os.getenv("DATA_DIR","/app/data")); DOCS=DATA/"documents"; DOCS.mkdir(parents=True,exist_ok=True)
st.set_page_config(page_title="Knowledge Copilot", page_icon="🧠", layout="wide")
st.title("🧠 Local Knowledge Copilot")
st.caption("Private, offline project memory and document intelligence")
if "messages" not in st.session_state: st.session_state.messages=[]
with st.sidebar:
    st.header("Documents")
    uploaded=st.file_uploader("Add PDF, DOCX, Markdown, or text",type=["pdf","docx","md","txt"],accept_multiple_files=True)
    if uploaded and st.button("Save & ingest documents",use_container_width=True):
        for item in uploaded: (DOCS/item.name).write_bytes(item.getvalue())
        result=httpx.post(f"{MCP}/mcp/tools/call",json={"tool":"ingest_documents","arguments":{}},timeout=180).json()
        st.success(f"Indexed {result.get('chunks_indexed',0)} chunks")
    st.divider(); st.header("Project memory")
    if st.button("Refresh memory",use_container_width=True): st.rerun()
    try:
        status=httpx.post(f"{MCP}/mcp/tools/call",json={"tool":"list_project_status","arguments":{}},timeout=15).json()["content"]
        with st.expander("Project status"): st.markdown(status)
        decisions=httpx.post(f"{MCP}/mcp/tools/call",json={"tool":"read_decisions","arguments":{"limit":10}},timeout=15).json()["decisions"]
        with st.expander("Recent decisions"):
            for d in decisions: st.markdown(f"**#{d['id']} {d['title']}** - {d['rationale']}")
    except Exception: st.info("Memory service is starting up.")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("trace"):
            with st.expander("Agent trace"):
                for step in msg["trace"]: st.code(json.dumps(step,indent=2),language="json")
if question:=st.chat_input("Ask about your documents, decisions, or project..."):
    st.session_state.messages.append({"role":"user","content":question})
    with st.chat_message("user"): st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking locally..."):
            history=[{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[:-1]]
            try: result=httpx.post(f"{AGENT}/chat",json={"message":question,"history":history},timeout=300).json()
            except Exception as exc: result={"answer":f"I could not reach the local agent: {exc}","trace":[]}
            st.markdown(result["answer"])
            if result.get("trace"):
                with st.expander("Agent trace"):
                    for step in result["trace"]: st.code(json.dumps(step,indent=2),language="json")
    st.session_state.messages.append({"role":"assistant","content":result["answer"],"trace":result.get("trace",[])})
