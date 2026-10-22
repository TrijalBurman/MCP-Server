# LocalMind 10-minute group speaking script

Updated 17 October 2026 for the greeting, metadata, citation and source-card fixes.
This script matches the updated Word and PDF guide. Historical experiments remain
separate from current software checks; see [the deliverables index](../README.md).

Guide: Dr. Sonali Kothari · Symbiosis Institute of Technology · Bachelor of Computer Science Engineering · Academic year 23–27.

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

RAG means retrieval-augmented generation. We retrieve evidence and provide selected passages with the question to a language model. Qwen runs locally through Ollama. This laptop uses the optional Qwen3.5 nine-billion-parameter profile with twelve thousand two hundred eighty-eight context tokens. Source defaults remain four billion parameters and eight thousand one hundred ninety-two tokens. The paper measured the earlier model. References help us inspect evidence; they do not guarantee a correct answer.

**Action:** Point to the MCP server block; no extra terminal is needed.

MCP has a different purpose: it is a standard interface for discovering and calling tools. Our custom local server provides search, document reading, memory recall, and project functions through a real stdio connection. RAG is the information-finding approach; MCP is the tool connection. It is not a model, database, or automatic accuracy improvement.

**Action:** Point to Memory and Projects; leave the architecture visible.

An explicit memory persists in SQLite and can be retrieved in a later conversation. That is separate from the temporary model context and does not retrain its weights. Internal model-selected tools are read-only and bounded. The development setup used an RTX 5050, Ryzen 7 250, and sixteen gigabytes of RAM; that does not establish a universal performance guarantee.

**Action:** Return to Library and hand keyboard control to Gayatri.

Document evidence now includes actual filenames, paths and document identifiers. The display groups excerpts from the same file while preserving their original citation numbers. Gayatri will demonstrate the prepared Lighthouse samples. We will compare the response with its source and save an explicit memory.

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

Historically, both generation conditions matched all requested values on zero of twenty-four answerable questions. The context fitter could discard retrieved evidence after serialization. These are historical measurements. The context repair and later safeguards are implemented in the Linux and Windows versions; the old results remain visible for comparison.

**Action:** Point to the repaired production replay and evidence-retention rows.

The production repair uses the actual serialized UTF-eight size to fit evidence. All sixty-four replay requests retained initial references, stayed within budget and completed without errors. Single-pass RAG matched every requested value on seven of twenty-four answerable questions; the agent did so on three. These were reused questions, not a held-out test or general accuracy. No extra model-selected tool calls occurred.

**Action:** Point to the historical long-summary row, not a new summary result.

The earlier long-document experiment retained ten of twenty-four requested values across three final summaries. It was not rerun. Current question answering uses query-centered excerpts, but bounded context can still omit facts. A later small, post-selected nine-billion-parameter development probe passed eight known-fact checks and declined two unknowns. This is separate from the paper benchmark and does not establish general accuracy.

**Action:** Show the remaining limits; leave settings unchanged.

Current file lists and exact filename checks use index metadata. Greetings now bypass retrieval, avoiding invented project context. Uncited substantive document replies get one retry, including requests such as explain the setup. Failed reference checks show exact excerpts. The local suites passed one hundred sixty-three Linux tests and two hundred Windows-copy tests on Linux, with six native checks skipped. Valid citations still do not prove every claim. Scanned PDFs need external OCR, and the database is not encrypted.

**Action:** Show next steps, then return to the title or app overview.

Next steps are stronger long-document coverage, broader held-out evaluation and native Windows GPU testing, which remains unmeasured. Local OCR is another possible extension. These improvements remain proposed. LocalMind combines a working local workflow with measurements of its remaining limits. Thank you to Dr. Sonali Kothari and the panel. We welcome your questions.

## Exact demo inputs

**Question:** What storage does the Lighthouse project use?

**Memory command:** /remember Use only the supplied Lighthouse sample files in this presentation.

Demo address: http://127.0.0.1:8766. Project: Lighthouse Presentation. Allow at most ten seconds for a model response; use the source reader and manual Memory form if needed.

**Before the timer:** Prepare the two supplied files and project on a fresh
checkout, and warm the selected model. An initial HDD load can take about a
minute or longer; do not spend the timed demonstration waiting for model initialization.

The repaired replay retained evidence in 64/64 requests. Complete fact-value matches were 7/24 for RAG and 3/24 for MCP on reused synthetic questions. The historical 0/24 baseline and 10/24 summary-value result remain separately labeled; summaries were not rerun.

## Preparation and measurement notes

Start the Linux demo, if needed, with `bash output/presentation/start-presentation-demo.sh`
from the checkout root. The main app is on port 8765; the separate demo is on 8766
when its launcher is running. Port 8766 has not been verified for this latest
document update. Prepare the sample library and project before starting the timer.

A single live `hello` check took **0.0931 seconds** and bypassed both the model
and retrieval. This is greeting-route latency, not model-answer speed. Separate
metadata smoke checks returned **7 indexed files**, **1 exact api.md match**, and
**0 matches for an absent test filename**. These checks do not measure answer accuracy.

The earlier 178-test-per-interpreter native Windows CI run checked a previous
commit. The latest Windows copy was tested on Linux with six native checks
skipped; native Windows GPU inference remains unmeasured. Historical rehearsal
records and screenshots are dated prepared evidence, not a newly repeated live demo.
