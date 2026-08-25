import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from agent import ReActAgent
from mcp_client import MCPClient
from ollama_client import OllamaClient

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)-8s %(name)s %(message)s")
HOST=os.getenv("HOST","0.0.0.0"); PORT=int(os.getenv("PORT","8001"))
ollama_c=mcp_c=agent=None

@asynccontextmanager
async def lifespan(app):
    global ollama_c,mcp_c,agent
    ollama_c=OllamaClient(); mcp_c=MCPClient(); agent=ReActAgent(ollama_c,mcp_c)
    logging.getLogger("agent-api").info("Agent ready."); yield
    await ollama_c.aclose(); await mcp_c.aclose()

app=FastAPI(title="Knowledge Copilot Agent",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/health")
def health(): return {"status":"ok"}

class ChatReq(BaseModel): message:str; history:list=[]
class ChatRes(BaseModel): answer:str; trace:list; steps:int; truncated:bool=False

@app.post("/chat",response_model=ChatRes)
async def chat(r:ChatReq):
    if not r.message.strip(): raise HTTPException(400,"Empty message")
    try: return ChatRes(**(await agent.run(r.message,r.history)))
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/tools")
async def tools(): return {"tools":await mcp_c.list_tools()}

if __name__=="__main__": uvicorn.run(app,host=HOST,port=PORT,log_level="info")
