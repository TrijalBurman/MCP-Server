import logging, os, sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from memory.project_memory import ProjectMemory
from memory.decisions_log  import DecisionsLog
from rag.embeddings        import LocalEmbedder
from rag.vector_store      import VectorStore
from rag.document_loader   import DocumentLoader

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)-8s %(name)s %(message)s")
log = logging.getLogger("mcp-server")

MEMORY_DIR=os.getenv("MEMORY_DIR","/app/data/memory"); DOCUMENTS_DIR=os.getenv("DOCUMENTS_DIR","/app/data/documents")
VECTOR_DB_DIR=os.getenv("VECTOR_DB_DIR","/app/data/vector_db"); EMBED_MODEL=os.getenv("EMBED_MODEL","all-MiniLM-L6-v2")
HOST=os.getenv("HOST","0.0.0.0"); PORT=int(os.getenv("PORT","8000"))
pm=dl=vs=doc=None

@asynccontextmanager
async def lifespan(app):
    global pm,dl,vs,doc
    for d in [MEMORY_DIR,DOCUMENTS_DIR,VECTOR_DB_DIR,os.path.join(MEMORY_DIR,"notes")]: os.makedirs(d,exist_ok=True)
    pm=ProjectMemory(MEMORY_DIR); dl=DecisionsLog(MEMORY_DIR)
    emb=LocalEmbedder(EMBED_MODEL); vs=VectorStore(VECTOR_DB_DIR,emb); doc=DocumentLoader(DOCUMENTS_DIR,vs)
    log.info("MCP server ready."); yield

app=FastAPI(title="MCP Memory Server",lifespan=lifespan)

@app.get("/health")
def health(): return {"status":"ok"}

async def _read_mem(p):   return {"content":pm.read_status(p.get("section"))}
async def _write_mem(p):  pm.write_status(p["section"],p["content"]); return {"success":True}
async def _log_dec(p):    return {"success":True,"entry":dl.log_decision(p["title"],p["rationale"],p.get("outcome",""))}
async def _read_dec(p):   return {"decisions":dl.read_decisions(int(p.get("limit",20)))}
async def _add_note(p):   return {"success":True,"path":pm.add_note(p["title"],p["body"],p.get("tags",[]))}
async def _list_notes(p): return {"notes":pm.list_notes()}
async def _status(p):     return {"status":pm.full_status()}
async def _search(p):     return {"results":vs.search(p["query"],int(p.get("top_k",5)))}
async def _ingest(p):     return {"success":True,"documents_indexed":doc.ingest_all()}
async def _del_note(p):   return {"success":pm.delete_note(p["title"])}

TOOLS={
    "read_memory":        {"fn":_read_mem,   "description":"Read project status","parameters":{"section":"Optional section"}},
    "write_memory":       {"fn":_write_mem,  "description":"Write a section","parameters":{"section":"Name","content":"Markdown"}},
    "log_decision":       {"fn":_log_dec,    "description":"Log a decision","parameters":{"title":"Title","rationale":"Why","outcome":"Optional"}},
    "read_decisions":     {"fn":_read_dec,   "description":"Read past decisions","parameters":{"limit":"Max"}},
    "add_note":           {"fn":_add_note,   "description":"Save a note","parameters":{"title":"Title","body":"Body","tags":"Tags"}},
    "list_notes":         {"fn":_list_notes, "description":"List notes","parameters":{}},
    "list_project_status":{"fn":_status,     "description":"Full project status","parameters":{}},
    "search_documents":   {"fn":_search,     "description":"Semantic search over docs","parameters":{"query":"Query","top_k":"Count"}},
    "ingest_documents":   {"fn":_ingest,     "description":"Index all documents","parameters":{}},
    "delete_note":        {"fn":_del_note,   "description":"Delete a note","parameters":{"title":"Title"}},
}

class ToolReq(BaseModel): tool:str; params:dict={}

@app.post("/mcp/tools/call")
async def call_tool(r:ToolReq):
    if r.tool not in TOOLS: raise HTTPException(404,f"Tool '{r.tool}' not found")
    try: return JSONResponse({"result":await TOOLS[r.tool]["fn"](r.params)})
    except KeyError as e: raise HTTPException(422,f"Missing param: {e}")
    except Exception as e: log.exception("Tool %s failed",r.tool); raise HTTPException(500,str(e))

@app.get("/mcp/tools/list")
def list_tools():
    return {"tools":[{"name":n,"description":m["description"],"parameters":m["parameters"]} for n,m in TOOLS.items()]}

if __name__=="__main__": uvicorn.run(app,host=HOST,port=PORT,log_level="info")
