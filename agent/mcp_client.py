import logging, os
import httpx
log = logging.getLogger(__name__)

class MCPClient:
    def __init__(self):
        self.base_url = os.getenv("MCP_SERVER_URL","http://mcp-server:8000").rstrip("/")
        self._client  = httpx.AsyncClient(timeout=60)

    async def list_tools(self):
        r = await self._client.get(f"{self.base_url}/mcp/tools/list")
        r.raise_for_status(); return r.json().get("tools",[])

    async def call_tool(self, tool, params):
        log.info("MCP call: %s %s", tool, params)
        r = await self._client.post(f"{self.base_url}/mcp/tools/call",json={"tool":tool,"params":params})
        r.raise_for_status(); return r.json().get("result",{})

    async def aclose(self): await self._client.aclose()
