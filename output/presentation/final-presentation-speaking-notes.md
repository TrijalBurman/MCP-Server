# LocalMind final presentation speaking notes

Updated 22 October 2026. This is the slide-by-slide script for the final submission PowerPoint. The separate demo and speaking guide remains supporting navigation and viva material.

The 12 main slides total **10 minutes, including a two-minute demonstration**. Slide 13 contains backup references. Timing is an allocated rehearsal schedule, not a measured recording. Read the speech paragraphs aloud. Read action cues silently.

Guide: **Dr. Sonali Kothari**. Institution: **Symbiosis Institute of Technology**. Degree: **BACHELOR OF COMPUTER SCIENCE ENGINEERING**. Academic year: **23–27**.

| Speaker | Main slides | Time |
| --- | --- | --- |
| Trijal Burman | 1–3 | 00:00–02:15 |
| Tiya Singh | 4–7 | 02:15–04:30 |
| Gayatri Rajesh Apotikar | 8, demonstration | 04:30–06:30 |
| Nimita Jestin | 9–12 | 06:30–10:00 |

Prepare and warm the sample workspace before the timer. Keep the source reader available if a model reply is slow or incorrect. Verify the selected demo URL before presenting. No current service readiness is implied by this document.

## Slide 1: LocalMind

Trijal Burman. 00:00–00:35 (35 seconds).

Good morning. We are Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar and Nimita Jestin. Under the guidance of Dr. Sonali Kothari, we present LocalMind. It is a local knowledge workspace that combines document retrieval, persistent project memory and a custom MCP tool server. We use existing local models rather than training a new language model.

Student PRNs: Trijal 23070123145. Tiya 23070123144. Gayatri 23070123055. Nimita 23070122259.

**Source notes, not spoken:** Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 2: Problem statement and objectives

Trijal Burman. 00:35–01:25 (50 seconds).

A useful project decision might be in a PDF, a note, code or an earlier conversation. A normal chat has a limited input window and can lose that context. Our objective is to search approved local information and make it reusable. Local-first means the intended workflow can run without a hosted inference API after installation and model downloads. Hardware, power and storage still cost money. Local processing also does not make every answer correct.

**Source notes, not spoken:** Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 3: Literature review and project positioning

Trijal Burman. 01:25–02:15 (50 seconds).

The project builds on established work. RAG supplies retrieved passages to generation. Reciprocal rank fusion combines ranked search results. Agent research motivates tool use, and memory systems motivate persistence beyond a context window. MCP standardizes the connection to tools. Our contribution is a constrained local systems integration and its evaluation. We do not claim a new retrieval algorithm or that no comparable system exists. Tiya will explain the architecture. Object descriptions here simplify the cited systems and do not claim faithful reproduction.

**Source notes, not spoken:** P. Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, NeurIPS 33, 2020. https://arxiv.org/abs/2005.11401
G. V. Cormack, C. L. A. Clarke and S. Büttcher, Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods, SIGIR, 2009, pp. 758–759. https://doi.org/10.1145/1571941.1572114
S. Yao et al., ReAct: Synergizing Reasoning and Acting in Language Models, ICLR, 2023. https://openreview.net/forum?id=WE_vluYUL-X
C. Packer et al., MemGPT: Towards LLMs as Operating Systems, arXiv:2310.08560, 2023, revised 2024. https://arxiv.org/abs/2310.08560
N. F. Liu et al., Lost in the Middle: How Language Models Use Long Contexts, TACL 12, 2024, pp. 157–173. https://aclanthology.org/2024.tacl-1.9/
Model Context Protocol contributors, Model Context Protocol Specification, revision 2025-11-25. https://modelcontextprotocol.io/specification/2025-11-25

## Slide 4: System architecture

Tiya Singh. 02:15–02:45 (30 seconds).

The browser talks to the local FastAPI application. The agent connects to our custom MCP server over stdio. Approved source folders pass through extraction into the library and SQLite store. Ollama provides local chat and embeddings. The diagram shows selected flows, because the application also calls the library directly during indexing and explicit user actions. The boundary assumes local clients and locally served model artifacts.

**Source notes, not spoken:** Source image: figure from output/blackbook/localmind-blackbook.docx, word/media/image3.png. Implementation sources: copilot/server.py, copilot/agent.py, copilot/mcp_server.py, copilot/store.py. Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 5: Retrieval, memory and MCP

Tiya Singh. 02:45–03:25 (40 seconds).

A document is split into overlapping passages. FTS5 performs lexical search and EmbeddingGemma represents passages as vectors. RRF combines their ranks. The selected evidence enters the model input. A saved memory stays in SQLite, which differs from retraining a model or retaining everything in its context. MCP discovers tools and carries structured calls. The internal model has seven read tools, at most four rounds and six additional tool executions per turn. Explicit UI actions can save memory or draft a plan. The application does not execute arbitrary project code.

**Source notes, not spoken:** P. Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, NeurIPS 33, 2020. https://arxiv.org/abs/2005.11401
G. V. Cormack, C. L. A. Clarke and S. Büttcher, Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods, SIGIR, 2009, pp. 758–759. https://doi.org/10.1145/1571941.1572114
Model Context Protocol contributors, Model Context Protocol Specification, revision 2025-11-25. https://modelcontextprotocol.io/specification/2025-11-25
https://sqlite.org/fts5.html
Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 6: Grounding controls

Tiya Singh. 03:25–03:55 (30 seconds).

Earlier failures mixed a partial passage search with file inventory questions and could lose evidence during context fitting. The current routes use catalog metadata for exact file identity and bypass retrieval for a greeting. Context fitting measures the serialized request and packages complete evidence records. An uncited substantive reply can receive one tool-free retry. A failed check returns exact excerpts. These controls improve traceability and evidence delivery, but a valid citation alone cannot prove a claim.

**Source notes, not spoken:** Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 7: Implementation and laptop configuration

Tiya Singh. 03:55–04:30 (35 seconds).

The prototype ran on the listed laptop. Its source defaults use Qwen3 4B with eight thousand one hundred ninety-two context tokens. The optional development profile uses Qwen3.5 9B at twelve thousand two hundred eighty-eight tokens with partial CPU offload. The model files stay on the hard drive. The frozen paper results use the earlier 4B model. We cannot attribute later development differences to model size alone because prompts, context and integration also changed. Gayatri will demonstrate the workflow.

**Source notes, not spoken:** https://fastapi.tiangolo.com/
https://uvicorn.dev/
https://py.sdk.modelcontextprotocol.io/v1/
https://docs.ollama.com/api/introduction
Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 8: Two-minute demonstration

Gayatri Rajesh Apotikar. 04:30–06:30 (120 seconds).

Before the timer: warm the model. Prepare examples/knowledge and the Lighthouse Presentation project in the separate demo workspace. Check its actual address, normally http://127.0.0.1:8766 when started with output/presentation/start-presentation-demo.sh. The main app uses port 8765. The slide image is dated prepared evidence, not proof of a current live service.

04:30–04:55: Open Library, read lighthouse-project.md, and show Storage decision. Say: These are supplied sample files. The source explicitly says SQLite.

04:55–05:30: In Lighthouse Presentation project chat, ask exactly: What storage does the Lighthouse project use? Wait no more than ten seconds for an already warm model. Compare its source card with the document. If it fails, abstains or takes longer, show the source reader and move on.

05:30–06:05: Send /remember Use only the supplied Lighthouse sample files in this presentation. Open Memory and filter to Lighthouse Presentation. Use the manual Add memory form if chat is busy.

06:05–06:30: Reload Memory and show the saved entry. Say: The reload illustrates persistence through this reload. Storage tests separately cover restarts. Hand over to Nimita.

**Source notes, not spoken:** Supplied corpus: examples/knowledge/lighthouse-project.md and examples/knowledge/study-notes.txt. Navigation and timing: output/presentation/10-minute-group-script.md. Image: dated rehearsal screenshot embedded in current blackbook. No new rehearsal or performance observation is claimed.

## Slide 9: Retrieval results on LM-Synth v1

Nimita Jestin. 06:30–07:15 (45 seconds).

Our evaluation uses authored fictional documents rather than a representative personal archive. Complete-evidence success asks whether the top five retrieved passages contain every required fact in the correct document. Lexical and hybrid retrieval cover ninety-six of ninety-six answerable questions. Dense retrieval covers ninety-one. Hybrid matches lexical coverage on this identifier-rich corpus, so we do not claim it is always better. These are retrieval results. They do not establish one hundred percent answer accuracy.

**Source notes, not spoken:** Frozen experiment sources: research/evaluation/results/paper-statistics.json and output/pdf/localmind-ieee-research-paper.tex, Retrieval Effectiveness section. CES@5 percentages are 96/96 = 100%, 91/96 = 94.7917%, and 96/96 = 100%. All methods cover all questions at ten results. No new run.

## Slide 10: Generation results and the context repair

Nimita Jestin. 07:15–08:20 (65 seconds).

The original generator matched zero complete answers out of twenty-four in each condition. It incorrectly abstained on the positive questions because the context fitter could discard evidence after serialization. The production repair retained initial evidence in all sixty-four requests and kept every call within its serialized input budget. Complete answer matches became seven of twenty-four for RAG and three of twenty-four for the MCP agent. All-fact value match is a string alias proxy, not independently judged semantic correctness. Missing-value phrase counts concern eight separate unknown questions. No extra model-selected tool calls occurred, so this set shows no observed adaptive tool-use benefit. The small sample, wide intervals and reused questions limit interpretation. Historical summaries retained ten of twenty-four requested values across three dossiers and have not been rerun after this repair.

**Source notes, not spoken:** Sources: output/pdf/localmind-ieee-research-paper.tex, generation Table and Production Replay section. research/evaluation/results/paper-statistics.json. output/verification/context-fitting-fix.json. All displayed rows use the historical Qwen3 4B experiment. Original counts are two separate 0/24 conditions, not one pooled sample. Production replay RAG AFVM 7/24, agent 3/24. Summary 10/24 historical only.

## Slide 11: Verification and remaining limits

Nimita Jestin. 08:20–09:05 (45 seconds).

Functional tests answer a different question from model accuracy. The recorded suites passed one hundred sixty-three Linux tests and two hundred Windows-copy tests on Linux, with six native checks skipped. Later native Windows CI passed two hundred six tests on each interpreter, with a fake model service. That checks runtime behavior rather than GPU inference or answer accuracy. Next steps include held-out factuality and citation entailment evaluation, better long-document coverage, local OCR and actual Windows 11 GPU measurements. The database currently lacks application-level encryption.

**Source notes, not spoken:** Sources: output/verification/local-routing-fix.json and output/verification/local-routing-fix.md. Native CI run https://github.com/TrijalBurman/MCP-Server/actions/runs/39056375542 at Windows commit da05653. Linux counts describe the recorded 17 October snapshot rather than an unrun current suite. N. F. Liu et al., Lost in the Middle: How Language Models Use Long Contexts, TACL 12, 2024, pp. 157–173. https://aclanthology.org/2024.tacl-1.9/

## Slide 12: Conclusion

Nimita Jestin. 09:05–10:00 (55 seconds).

LocalMind brings approved local files, relational project memory, local inference and a real MCP connection into one working application. Its measurements show why finding evidence and producing a correct answer must be evaluated separately. The context repair fixes an observed evidence-delivery failure, while later controls improve file identity and source inspection. Important answers still need comparison with source text. We have documented limitations rather than substituting software test counts for semantic accuracy. Thank you to Dr. Sonali Kothari and the evaluation panel. We welcome your questions.

At 10:00 stop the timed presentation. The next slide contains selected references for viva discussion.

**Source notes, not spoken:** Local project sources: output/pdf/localmind-ieee-research-paper.tex, research/literature-reading-list.md, output/verification/context-fitting-fix.json, output/verification/local-routing-fix.md, output/verification/model-upgrade.md. Historical experiments ran 17 October 2026. This presentation introduces no new benchmark.

## Slide 13: Selected references

All members. Backup slide, outside the timed presentation.

Selected background references are listed here. Full source links appear below and the blackbook contains the expanded bibliography. The project uses established RAG, fusion, memory and protocol ideas. No cited work establishes LocalMind performance. The current paper is a draft unless the group supplies evidence of publication. Literature descriptions come from the project reading list and existing manuscript, without a new systematic review.

**Source notes, not spoken:** P. Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, NeurIPS 33, 2020. https://arxiv.org/abs/2005.11401
G. V. Cormack, C. L. A. Clarke and S. Büttcher, Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods, SIGIR, 2009, pp. 758–759. https://doi.org/10.1145/1571941.1572114
S. Yao et al., ReAct: Synergizing Reasoning and Acting in Language Models, ICLR, 2023. https://openreview.net/forum?id=WE_vluYUL-X
C. Packer et al., MemGPT: Towards LLMs as Operating Systems, arXiv:2310.08560, 2023, revised 2024. https://arxiv.org/abs/2310.08560
N. F. Liu et al., Lost in the Middle: How Language Models Use Long Contexts, TACL 12, 2024, pp. 157–173. https://aclanthology.org/2024.tacl-1.9/
Model Context Protocol contributors, Model Context Protocol Specification, revision 2025-11-25. https://modelcontextprotocol.io/specification/2025-11-25

## Submission status

The presentation requires review and approval by the project guide before university submission. This document does not certify that approval. The existing research paper is a draft unless the group separately supplies publication evidence.
