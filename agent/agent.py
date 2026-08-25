import json, logging, os, re
from dataclasses import dataclass, field
from mcp_client import MCPClient
from ollama_client import OllamaClient
from prompts import SYSTEM_PROMPT, REACT_TEMPLATE, format_tool_descriptions
log = logging.getLogger(__name__)
MAX = int(os.getenv("MAX_REACT_STEPS","10"))

@dataclass
class Step:
    thought:str=""; action:str=""; action_input:dict=field(default_factory=dict)
    observation:str=""; is_final:bool=False; final_answer:str=""

class ReActAgent:
    def __init__(self, ollama, mcp): self.ollama=ollama; self.mcp=mcp; self._tools=[]; self._sys=""

    async def _init(self):
        if not self._tools:
            self._tools=await self.mcp.list_tools()
            self._sys=SYSTEM_PROMPT.format(tool_descriptions=format_tool_descriptions(self._tools))

    def _parse(self, text):
        s=Step()
        fa=re.search(r"Final Answer:\s*(.*)",text,re.DOTALL|re.IGNORECASE)
        if fa: s.is_final=True; s.final_answer=fa.group(1).strip(); return s
        tm=re.search(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)",text,re.DOTALL|re.IGNORECASE)
        if tm: s.thought=tm.group(1).strip()
        am=re.search(r"Action:\s*(\S+)",text,re.IGNORECASE)
        if am: s.action=am.group(1).strip()
        im=re.search(r"Action Input:\s*(\{.*?\})",text,re.DOTALL|re.IGNORECASE)
        if im:
            try: s.action_input=json.loads(im.group(1))
            except: s.action_input={"raw":im.group(1)}
        return s

    async def run(self, question, history=None):
        await self._init()
        hist="\n".join(f"{m['role'].upper()}: {m['content']}" for m in (history or [])[-10:])
        prompt=REACT_TEMPLATE.format(history=hist,question=question)
        trace=[]
        for i in range(MAX):
            out=await self.ollama.generate(prompt,self._sys)
            s=self._parse(out); trace.append(s)
            if s.is_final: return {"answer":s.final_answer,"trace":_dicts(trace),"steps":i+1}
            if s.action:
                try: obs=json.dumps(await self.mcp.call_tool(s.action,s.action_input))
                except Exception as e: obs=f"Error: {e}"
                s.observation=obs; prompt+=f"\n{out}\nObservation: {obs}\n"
            else: return {"answer":out.strip(),"trace":_dicts(trace),"steps":i+1}
        out=await self.ollama.generate(prompt+"\nProvide a Final Answer now.",self._sys)
        fa=re.search(r"Final Answer:\s*(.*)",out,re.DOTALL|re.IGNORECASE)
        return {"answer":fa.group(1).strip() if fa else out.strip(),"trace":_dicts(trace),"steps":MAX,"truncated":True}

def _dicts(t):
    return [{"thought":s.thought,"action":s.action,"action_input":s.action_input,
             "observation":s.observation,"is_final":s.is_final,"final_answer":s.final_answer} for s in t]
