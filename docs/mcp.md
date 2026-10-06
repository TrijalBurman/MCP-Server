# Custom MCP memory server

`copilot.mcp_server` is a real [official Python SDK v1](https://py.sdk.modelcontextprotocol.io/v1/) FastMCP server. The dependency is pinned to `mcp>=1.20,<2` so the application and tests use the same maintained API family. Its transport is **stdio**: an MCP client launches it as a child process and communicates through stdin/stdout. There is no unauthenticated network MCP listener.

## Connect a local client

The sample [Windows configuration](../examples/mcp-client.json) uses an absolute executable and data directory with spaces in the account/project names. **Replace `C:\Users\Your Name\Projects\Local Knowledge\MCP-Server` with your actual checkout directory in both fields.** Preserve JSON's doubled backslashes. Merge the `mcpServers` entry into the format expected by your local client. Run `scripts\setup.cmd` first so `python -m copilot.mcp_server` works outside the repository's current directory.

The executable is `<checkout>\.venv\Scripts\python.exe`, with arguments `-X utf8 -m copilot.mcp_server`. Set `COPILOT_DATA_DIR` to exactly the app's data directory, normally `<checkout>\.local-copilot`, and `COPILOT_OLLAMA_URL` to `http://127.0.0.1:11435`. The managed model server must be running for local semantic search. A different data directory creates a separate memory database. Client JSON does not necessarily expand `%USERPROFILE%`, `$env:USERPROFILE`, or `~`, so use concrete absolute paths.

To start the stdio server manually from PowerShell:

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m copilot.mcp_server
```

Keep the client and its inference local to preserve the local data boundary. An external hosted client receives the contents returned by this server even though the server itself only talks to local resources.

## Tools

| Tool | Arguments | Result | Change permitted |
| --- | --- | --- | --- |
| `knowledge_search` | `query`, `limit=8` | `{results: [...]}` with document/page/offset evidence | None |
| `list_documents` | `query=""`, `limit=100`, `offset=0` | `{documents: [...]}` | None |
| `read_document` | `document_id`, `offset=0`, `length=12000` | Extracted text page, total characters, next offset | None |
| `recall` | `project_id=null`, `query=""` | `{memories: [...]}` | None |
| `search_conversations` | `query`, `limit=6`, `project_id=null` | `{messages: [...]}` with saved session context | None |
| `list_projects` | None | `{projects: [...]}` | None |
| `list_sources` | None | `{roots: [...]}` | None |
| `remember` | `content`, `kind="note"`, `project_id=null` | Saved memory record | Explicit user-requested memory write |
| `forget` | `memory_id` | `{deleted: bool}` | Explicit user-requested memory deletion |
| `create_project` | `name`, `description=""` | Project record | Explicit user-requested project creation |

Tools have protocol annotations describing read-only and destructive behavior. Write tools are available to external clients; the application's model only receives read-only tool schemas. No MCP tool approves arbitrary new folders, traverses an arbitrary requested path, starts a network request to the internet, or runs a command.

Search limits are 1–30 results, document list pages are 1–200 entries, and reader pages are 1–50,000 characters. Offsets are nonnegative character positions, not byte positions. Blank searches, invalid identifiers, and invalid bounds return MCP tool errors.

## Read every extracted character

Call `list_documents` or `knowledge_search` to get a document ID, then read it:

```json
{"document_id": 1, "offset": 0, "length": 12000}
```

A result has this shape:

```json
{
  "document_id": 1,
  "title": "notes.md",
  "path": "D:\\Knowledge\\notes.md",
  "text": "...",
  "offset": 0,
  "length": 12000,
  "total": 28700,
  "next_offset": 12000,
  "indexed_at": "...",
  "snapshot": true
}
```

Continue with `offset=next_offset` until `next_offset` is `null`. Concatenating the returned `text` pages recovers the complete stored extraction without a top-k search limit. Calling with `offset=total` returns an empty page; an offset greater than `total` is an error.

The reader validates that the source still exists, remains inside an approved local root, has no symbolic-link, junction, or reparse-point components, and matches its indexed modification time and size. A changed or unavailable source returns an instruction to reindex. It never interprets a document ID as an arbitrary filesystem path. UNC/device paths, mapped network drives, drive roots, and system folders are outside the Windows source policy.

## Resources

- `memory://overview`: JSON containing local memory/index statistics and approved source folders.
- `memory://projects/{project_id}`: JSON with a project's metadata and its explicit saved memories.

Project resources use positive numeric project IDs returned by `list_projects` or `create_project`.

## Protocol verification

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m pytest -q tests/test_mcp.py
```

The tests create a temporary source folder and database, start a real subprocess with `StdioServerParameters`, initialize an SDK `ClientSession`, discover tools/resources, exercise memory writes against shared storage, search saved conversations, and read a document larger than one page. They also check invalid pagination and changed/deleted sources. No network model service or paid API is needed. The Linux baseline has been exercised; native Windows CI results are tracked separately in the [validation record](validation.md) and remain pending until confirmed.

Do not add `print()` calls to this server: stdout is reserved for protocol messages. Diagnostics must go to stderr. The executable can be run manually, but it waits for protocol input and is not an interactive command prompt.
