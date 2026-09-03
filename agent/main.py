from __future__ import annotations
import json, os, re
from typing import Any
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

MCP_URL=os.getenv("MCP_URL","http://localhost:8000"); OLLAMA_URL=os.getenv("OLLAMA_URL","http://localhost:11434")
app=FastAPI(title="Knowledge Copilot Agent")
class ChatRequest(BaseModel): message:str; history:list[dict[str,str]]=Field(default_factory=list)

SYSTEM="""You are a local-first knowledge copilot. Use the available tools whenever the question concerns saved memory, decisions, notes, or documents. Never invent tool results. Reply in exactly one format: either `Thought: ...\nAction: tool_name\nAction Input: {json}` or `Final Answer: ...`."""
async def tools(client): return (await client.get(f"{MCP_URL}/mcp/tools/list")).json()["tools"]
async def invoke(client,name,args): return (await client.post(f"{MCP_URL}/mcp/tools/call",json={"tool":name,"arguments":args})).json()
def parse(text):
    action=re.search(r"Action:\s*([\w_]+)",text); raw=re.search(r"Action Input:\s*(\{.*\})",text,re.S)
    if not action or not raw: return None
    try: return action.group(1),json.loads(raw.group(1))
    except json.JSONDecodeError: return action.group(1),{"raw":raw.group(1)}
async def model(client,prompt):
    response=await client.post(f"{OLLAMA_URL}/api/generate",json={"model":"qwen2.5:7b","prompt":prompt,"stream":False,"options":{"temperature":0.2,"num_ctx":8192}})
    response.raise_for_status(); return response.json()["response"].strip()
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/tools")
async def get_tools():
    async with httpx.AsyncClient(timeout=30) as client: return {"tools":await tools(client)}
@app.post("/chat")
async def chat(req:ChatRequest):
    trace=[]
    async with httpx.AsyncClient(timeout=120) as client:
        available=await tools(client)
        prompt=SYSTEM+"\n\nTools:\n"+json.dumps(available)+"\n\nConversation:\n"+"\n".join(f"{x['role']}: {x['content']}" for x in req.history[-10:])+f"\nuser: {req.message}\n"
        for _ in range(10):
            response=await model(client,prompt); parsed=parse(response)
            if not parsed:
                answer=response.replace("Final Answer:","").strip(); return {"answer":answer,"trace":trace,"steps":len(trace)}
            name,args=parsed; observation=await invoke(client,name,args); trace.append({"thought":response.split("Action:")[0].replace("Thought:","").strip(),"action":name,"arguments":args,"observation":observation}); prompt+=response+"\nObservation: "+json.dumps(observation)+"\n"
        final=await model(client,prompt+"Provide a Final Answer now.")
        return {"answer":final.replace("Final Answer:","").strip(),"trace":trace,"steps":len(trace),"truncated":True}
