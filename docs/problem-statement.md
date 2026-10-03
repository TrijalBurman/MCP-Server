# 1.2 Problem statement

Knowledge workers and students lose useful context across local notes, PDFs, Markdown files, source code, and earlier conversations. Recovering a project decision often requires remembering its filename or repeating context in a new chat. A cloud assistant can add recurring API fees and transfer private material off the laptop; a simple local chat model typically has no durable project memory or reliable way to retrieve the user's files.

This project addresses that workflow with a lightweight local knowledge copilot, persistent structured memory, and a custom Model Context Protocol (MCP) server. Documents remain on the user's HDD or SSD. The user explicitly adds source folders; the system extracts supported contents, retrieves relevant passages, and supplies cited local context to a local model. Notes, preferences, project decisions, and conversation history persist between sessions.

## Objective

Build a privacy-preserving assistant that can answer questions about local knowledge, summarize documents, recall earlier discussions, and help create project plans using local inference. The system must avoid paid cloud API dependencies, keep normal processing on the laptop, and fit a machine with an RTX 5050, Ryzen 7 250, and 16 GB RAM.

## Functional scope

- Explicitly select folders across local hard disks and SSDs, index supported documents, and rescan changes.
- Combine lexical and optional local embedding search with document and page citations.
- Read complete extracted document contents through a bounded reader, including MCP pagination.
- Keep explicit memories and project workspaces in SQLite.
- Save conversations and search earlier discussions across sessions.
- Allow a local model to select read-only MCP tools in a bounded multi-step retrieval loop.
- Generate project plans in the application data directory.
- Provide usable search and memory features when no model is running.

## Constraints and boundaries

“Fully local” applies to installed application processing and local model inference. Initial installation and model downloads require network access unless the dependencies are supplied offline. “Zero cost” means no recurring API or hosted-service fee; storage, electricity, and the laptop are still required.

Source selection is deliberate rather than unrestricted background scanning. Credentials, hidden files, symbolic links, large files, and unsupported formats are skipped. Scanned image PDFs require a separate OCR workflow. Model answers can contain errors, so citations and a complete extracted-text reader are essential. The database is persistent but not encrypted by this application.

## Acceptance criteria

1. Add a local folder and index a mix of supported documents without uploading them.
2. Ask a document question and receive local source references.
3. Fetch a complete extracted document through successive MCP pages without truncating its stored text.
4. Save a project memory, restart the application, and retrieve the same memory.
5. Recover a useful earlier conversation through an actual MCP tool call.
6. Generate a project plan using a local model and save it under the project workspace.
7. Disconnect the internet after installation and continue local use.
8. Operate search, document reading, and explicit memory storage while Ollama is unavailable.

The architecture and protocol tests establish the software behavior; actual model speed and GPU residency depend on the installed driver, runtime, and available memory.
