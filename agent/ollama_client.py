import logging, os
import httpx
log = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL","http://ollama:11434").rstrip("/")
        self.model    = os.getenv("OLLAMA_MODEL","qwen2.5:7b")
        self._client  = httpx.AsyncClient(timeout=300)

    async def generate(self, prompt, system=""):
        r = await self._client.post(f"{self.base_url}/api/generate",json={
            "model":self.model,"prompt":prompt,"system":system,"stream":False,
            "options":{"temperature":0.2,"top_p":0.9,"num_ctx":8192}})
        r.raise_for_status(); return r.json().get("response","").strip()

    async def aclose(self): await self._client.aclose()
