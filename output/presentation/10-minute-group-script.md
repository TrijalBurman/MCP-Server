# LocalMind 10-minute group speaking script

Current Markdown script, updated for the grounding repair and model upgrade,
17 October 2026. The exported PDF/Word guide remains the earlier context-repair
snapshot; see [the deliverables index](../README.md).

Guide: Dr. Sonali Kothari · Symbiosis Institute of Technology · Minors in AIML · Academic year 23–27.

Read the speech paragraphs aloud. Action cues are silent. The two-minute demonstration is included in the total. Speaking roles are presentation assignments.

## Trijal Burman — 00:00–02:15

**Action:** Show the project title page or the app welcome screen; face the panel.

Good morning, respected panel members. We are Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar, and Nimita Jestin from SIT. Under the guidance of Dr. Sonali Kothari, we are presenting LocalMind: a Local-First Agentic Knowledge Copilot with a Custom MCP Memory Server.

**Action:** Keep the problem statement visible; do not start clicking through the app yet.

Our problem is scattered knowledge and lost project context. A useful decision may be in a document, a lecture note, or an earlier conversation. Finding it again takes effort, and an ordinary chat has a limited context window. We wanted a workspace that helps a person find, inspect, and reuse their own approved information.

**Action:** Point to the Library, Memory, and Projects labels without opening them.

The prototype searches supported local files, shows source references, reads extracted document text, saves explicit memories, and drafts project plans. It uses existing local models rather than training a new large model. A saved memory belongs in a database; a relevant passage is supplied to the model when a request is made.

**Action:** Show the scope statement or privacy note.

Local-first does not mean unrestricted drive access. The user chooses folders on the HDD or SSD. Initial software and model downloads need internet, but the intended workflow can then run offline without a paid hosted API. Hardware, electricity, and storage still have costs. Local processing also does not guarantee that every generated statement is correct.

**Action:** Bring the architecture figure into view and turn toward Tiya.

Tiya will now explain how retrieval, persistent storage, and our custom MCP server work together. The speaking roles we have assigned today are presentation roles, not a claim about each person's individual implementation contribution.

## Tiya Singh — 02:15–04:30

**Action:** Trace the approved-folder to extraction to SQLite path on the architecture figure.

The workflow starts with an approved folder. Supported text is extracted and divided into smaller overlapping passages. SQLite stores the complete extracted text, passage information, conversations, and memories. EmbeddingGemma represents passages as numerical vectors, while SQLite full-text search finds matching words. The retrieval layer combines these signals to select useful evidence.

**Action:** Point to the retrieval-to-model connection.

RAG means retrieval-augmented generation. We retrieve evidence and provide selected passages with the question to a language model. Qwen runs locally through Ollama; this laptop now uses the optional Qwen3.5 nine-billion-parameter profile. The paper measured the earlier four-billion-parameter model. Numbered references let us inspect the evidence, but retrieval does not guarantee a correct answer.

**Action:** Point to the MCP server block; no extra terminal is needed.

MCP has a different purpose: it is a standard interface for discovering and calling tools. Our custom local server provides search, document reading, memory recall, and project functions through a real stdio connection. RAG is the information-finding approach; MCP is the tool connection. It is not a model, database, or automatic accuracy improvement.

**Action:** Point to Memory and Projects; leave the architecture visible.

An explicit memory persists in SQLite and can be retrieved in a later conversation. That is separate from the temporary model context and does not retrain its weights. Internal model-selected tools are read-only and bounded. The development setup used an RTX 5050, Ryzen 7 250, and sixteen gigabytes of RAM; that does not establish a universal performance guarantee.

**Action:** Return to Library and hand keyboard control to Gayatri.

Gayatri will demonstrate the prepared Lighthouse samples. We will check the actual source and save a memory, rather than treating a confident-looking response as proof of correctness.

## Gayatri Rajesh Apotikar — 04:30–06:30

**Action:** D1: Open Library and read lighthouse-project.md at its Storage decision section.

These are two supplied sample files, not personal documents. They were indexed before this timed demo. The Lighthouse document explicitly says to use SQLite for extracted text, conversations, and project memories. We can inspect that source directly.

**Action:** D2: Close the reader, open the prepared project conversation, and send the exact storage question. Wait no more than ten seconds.

I am asking a question whose answer is written in the sample. Once the response is ready, I compare it with its source card. If it disagrees or abstains, the document remains the evidence we should trust.

**Action:** D3: Send the explicit /remember command. Open Memory, choose the project filter, and show the saved note.

Now I explicitly ask the application to save a demo preference. It appears in this project's Memory view. This save is an intentional database operation, not a claim that the language model has permanently learned the note.

**Action:** D4: Reload Memory once; then stop clicking and show the evaluation table.

The note is still listed after the page reloads. Persistence across application restarts is also covered by storage tests. Nimita will now explain what our measured results support and where the prototype still needs improvement.

## Nimita Jestin — 06:30–10:00

**Action:** Show the evaluation table and point to retrieval coverage.

Our evaluation used authored fictional documents, not a representative personal archive. Hybrid retrieval included all required reference facts within its first five passages for ninety-six of ninety-six answerable retrieval questions. This is coverage on a small synthetic corpus, not one hundred percent answer accuracy. Lexical retrieval also reached the same coverage at five.

**Action:** Point to the historical baseline and earlier diagnostic rows.

Historically, both generation conditions matched all requested values on zero of twenty-four answerable questions. The context fitter could discard retrieved evidence after serialization. An earlier evaluation-only diagnostic produced seven and three complete matches. These are historical measurements. The published Linux and Windows versions now contain the context repair and later grounding fixes.

**Action:** Point to the repaired production replay and evidence-retention rows.

The production repair fits a complete-character prefix using its actual serialized UTF-eight size. All sixty-four replay requests retained initial reference evidence, stayed within budget, and completed without request errors. Single-pass RAG matched all requested values on seven of twenty-four answerable questions; the agent did so on three. Average fact-value matching was thirty-seven point five and twenty-seven point zero eight percent. These are reused questions, not a held-out test or general accuracy. No extra model-selected tool calls occurred.

**Action:** Point to the historical long-summary row, not a new summary result.

The earlier long-document experiment retained ten of twenty-four requested values across three final summaries. It was not rerun. The current app uses query-centered excerpts instead of fixed prefixes, while bounded context can still omit facts. A later small nine-billion-parameter development check answered eight known-fact questions with supporting references and declined two unknowns. That is separate from the paper benchmark, not a general accuracy result.

**Action:** Show the remaining limits; leave settings unchanged.

Current file lists and exact filename checks use the actual index. Uncited document answers get one retry; failed citation checks show exact excerpts. Valid references still do not prove every claim. Other limits include no OCR, readable database storage and access restricted to approved supported files. The latest local suites passed one hundred thirty-five Linux tests and one hundred seventy-two Windows-copy tests on Linux. Native Windows GPU inference remains untested.

**Action:** Show next steps, then return to the title or app overview.

Next steps are stronger long-document coverage, broader held-out evaluation and native Windows GPU testing. Local OCR is another possible extension. The implemented repairs and their regression tests are published; these other improvements remain proposed. LocalMind combines a working local workflow with measurements of its remaining limits. Thank you to Dr. Sonali Kothari and the panel. We welcome your questions.

## Exact demo inputs

**Question:** What storage does the Lighthouse project use?

**Memory command:** /remember Use only the supplied Lighthouse sample files in this presentation.

Demo address: http://127.0.0.1:8766. Project: Lighthouse Presentation. Allow at most ten seconds for a model response; use the source reader and manual Memory form if needed.

**Before the timer:** Prepare the two supplied files and project on a fresh
checkout, and warm the selected model. An initial HDD load can take about a
minute; do not spend the timed demonstration waiting for model initialization.

The repaired replay retained evidence in 64/64 requests. Complete fact-value matches were 7/24 for RAG and 3/24 for MCP on reused synthetic questions. The historical 0/24 baseline and 10/24 summary-value result remain separately labeled; summaries were not rerun.
