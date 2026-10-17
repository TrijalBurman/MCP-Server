# Verified literature for the LocalMind IEEE paper

Primary papers, publisher records, author-hosted papers, and official specifications were checked during this research session. These 24 references are a focused bibliography, not an exhaustive survey. Numbering below is provisional. Technical reports and documentation are distinguished from reviewed publications. Metadata dates below are publication dates, not dates claimed for LocalMind experiments.

## Retrieval and rank fusion

**[1] Patrick Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” NeurIPS 33, 2020.** arXiv:2005.11401. [Primary paper](https://arxiv.org/abs/2005.11401).
Supports combining parametric generation with retrieved nonparametric knowledge. The original system includes trained retrieval/generation components; citing it does not establish equivalent training or performance in LocalMind.

**[2] Vladimir Karpukhin et al., “Dense Passage Retrieval for Open-Domain Question Answering,” EMNLP, 2020, pp. 6769–6781.** DOI:10.18653/v1/2020.emnlp-main.550. [Publisher paper/metadata](https://aclanthology.org/2020.emnlp-main.550/).
Supports learned dual-encoder passage retrieval as an alternative to lexical matching. Its reported benchmark gains must not be attributed to LocalMind's different embedding model or corpus.

**[3] Stephen Robertson and Hugo Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond,” Foundations and Trends in Information Retrieval, vol. 3, no. 4, pp. 333–389, 2009.** DOI:10.1561/1500000019. [Publisher-hosted paper](https://www.nowpublishers.com/article/DownloadEBook/INR-019).
Supports probabilistic lexical ranking, term-frequency saturation, and document-length normalization. Publisher search-indexed paper metadata was available; direct automated downloads returned access errors.

**[4] Gordon V. Cormack, Charles L. A. Clarke, and Stefan Büttcher, “Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods,” SIGIR, 2009, pp. 758–759.** DOI:10.1145/1571941.1572114. [Author-hosted original](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).
Supports combining rankings without calibrating raw retrieval scores: RRF(d)=Σr 1/(k+rankr(d)); the paper used k=60. DOI/title/pages were additionally checked against ACM-deposited Crossref metadata.

**[5] Nils Reimers and Iryna Gurevych, “Sentence-BERT: Sentence Embeddings Using Siamese BERT-Networks,” EMNLP-IJCNLP, 2019, pp. 3982–3992.** DOI:10.18653/v1/D19-1410. [Publisher paper](https://aclanthology.org/D19-1410/).
Supports efficient independent sentence embeddings and similarity comparisons. It is background for dense representations, not the model implemented by LocalMind.

## Agents and persistent memory

**[6] Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao, “ReAct: Synergizing Reasoning and Acting in Language Models,” ICLR, 2023.** arXiv:2210.03629, first posted 2022. [Conference paper](https://openreview.net/pdf?id=WE_vluYUL-X); [arXiv](https://arxiv.org/abs/2210.03629).
Supports interleaved information gathering and action selection. Describe LocalMind as a bounded tool-using loop inspired by this line, without claiming faithful ReAct reproduction or exposed reasoning traces.

**[7] Timo Schick et al., “Toolformer: Language Models Can Teach Themselves to Use Tools,” NeurIPS 36, 2023.** arXiv:2302.04761. [Publisher record](https://proceedings.neurips.cc/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html).
Supports learned API selection/arguments. Toolformer trains models for tool use; LocalMind uses an existing local model and runtime-enforced tool availability, without this training method.

**[8] Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, and Joseph E. Gonzalez, “MemGPT: Towards LLMs as Operating Systems,” arXiv preprint, 2023; revised 2024.** arXiv:2310.08560. [Primary report](https://arxiv.org/abs/2310.08560).
Supports hierarchical context management and persistent multi-session conversational memory. LocalMind's SQLite records and explicit memory writes differ from MemGPT's autonomous virtual-context management.

**[9] Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, and Yanlin Wang, “MemoryBank: Enhancing Large Language Models with Long-Term Memory,” AAAI, vol. 38, no. 17, pp. 19724–19731, 2024.** DOI:10.1609/aaai.v38i17.29946; arXiv:2305.10250 (2023). [Publisher record](https://ojs.aaai.org/index.php/AAAI/article/view/29946).
Supports persistent user-oriented memory and memory updating/forgetting. LocalMind does not implement the paper's Ebbinghaus-inspired forgetting mechanism or validate companionship benefits.

**[10] Weizhi Wang, Li Dong, Hao Cheng, Xiaodong Liu, Xifeng Yan, Jianfeng Gao, and Furu Wei, “Augmenting Language Models with Long-Term Memory,” NeurIPS 36, 2023.** arXiv:2306.07174. [Publisher record](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ebd82705f44793b6f9ade5a669d0f0bf-Abstract-Conference.html).
Supports memory retrieval beyond a fixed input window. LongMem trains an adaptive side network; external SQLite retrieval is a different design.

**[11] Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, and Michael S. Bernstein, “Generative Agents: Interactive Simulacra of Human Behavior,” 2023.** arXiv:2304.03442. [Author-submitted paper](https://arxiv.org/abs/2304.03442).
Supports memory streams, reflection, and retrieval in agent architectures. Cite this verified arXiv version if conference metadata is not separately imported; LocalMind does not implement simulated social agents or automatic reflection.

**[12] Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao, “Reflexion: Language Agents with Verbal Reinforcement Learning,” NeurIPS 36, 2023.** arXiv:2303.11366. [Publisher record](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html).
Supports episodic textual feedback across trials. Do not equate ordinary conversation storage with Reflexion's self-reflection and task-feedback loop. Conference and later preprint author lists can differ; the list here follows the publisher.

## Context, ownership, and protocol

**[13] Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, and Percy Liang, “Lost in the Middle: How Language Models Use Long Contexts,” TACL, vol. 12, pp. 157–173, 2024.** DOI:10.1162/tacl_a_00638; arXiv:2307.03172 (2023). [Publisher record](https://aclanthology.org/2024.tacl-1.9/).
Supports concern about position-dependent use of long contexts. It motivates selective context and evaluation, not a claim that LocalMind's summarization eliminates omissions.

**[14] Martin Kleppmann, Adam Wiggins, Peter van Hardenberg, and Mark McGranaghan, “Local-First Software: You Own Your Data, in spite of the Cloud,” Onward!, 2019.** DOI:10.1145/3359591.3359737. [Author publication record](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html); [original paper](https://martin.kleppmann.com/papers/local-first.pdf).
Supports offline operation, ownership, privacy, and user agency. Its broader collaborative/CRDT vision is not implemented by a single-laptop SQLite assistant.

**[15] Model Context Protocol contributors, “Model Context Protocol Specification,” protocol revision 2025-11-25, 2025.** Official specification, no DOI. [Versioned specification](https://modelcontextprotocol.io/specification/2025-11-25).
Supports JSON-RPC communication, capability negotiation, resources, tools, and host/client/server separation. Protocol annotations do not enforce authorization; implementations must impose access boundaries. State actual negotiated revision only if measured.

**[16] Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, and Mario Fritz, “Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection,” arXiv preprint, 2023.** arXiv:2302.12173. [Primary report](https://arxiv.org/abs/2302.12173).
Supports treating retrieved content as untrusted data. Read-only tools and input boundaries reduce capabilities; a system prompt or local execution alone is not a proof of injection resistance.

## Models and implementation references

**[17] An Yang et al., “Qwen3 Technical Report,” technical report, 2025.** arXiv:2505.09388. [Primary report](https://arxiv.org/abs/2505.09388).
Supports the Qwen3 model family's dense/MoE variants and thinking/nonthinking designs. The May report does not by itself identify a later July Instruct quantization artifact; record LocalMind's exact installed tag separately.

**[18] Henrique Schechter Vera et al., “EmbeddingGemma: Powerful and Lightweight Text Representations,” technical report, 2025.** arXiv:2509.20354. [Primary report](https://arxiv.org/abs/2509.20354); [Google DeepMind model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card).
Supports the original 300M text embedder and on-device motivation. The card specifies 2K input context and 768-dimensional outputs with truncation options; these are distinct from the chat model's context window.

**[19] Ollama, “FAQ,” official software documentation, undated/current.** No DOI. [Official FAQ](https://docs.ollama.com/faq); [Windows runtime documentation](https://docs.ollama.com/windows).
Supports local inference configuration, `OLLAMA_NO_CLOUD=1`, loopback hosting, and Windows runtime distribution. Document the runtime version actually used; vendor privacy statements do not replace an application data-flow audit.

**[20] SQLite developers, “SQLite FTS5 Extension,” official implementation documentation, undated/current.** No DOI. [FTS5 documentation](https://sqlite.org/fts5.html).
Supports embedded full-text search and FTS5's BM25 implementation. Better FTS5 BM25 matches have numerically lower scores because its implementation negates the usual score; distinguish implementation ordering from generic BM25 notation.

## Evaluation foundations

**[21] Nandan Thakur, Nils Reimers, Andreas Rücklé, Abhishek Srivastava, and Iryna Gurevych, “BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models,” NeurIPS Datasets and Benchmarks, 2021.** arXiv:2104.08663. [Publisher record](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html).
Supports heterogeneous retrieval evaluation and retaining a strong lexical baseline. The publisher spells “Heterogeneous”; the arXiv title metadata spells “Heterogenous.”

**[22] Niklas Muennighoff, Nouamane Tazi, Loic Magne, and Nils Reimers, “MTEB: Massive Text Embedding Benchmark,” EACL, 2023, pp. 2014–2037.** DOI:10.18653/v1/2023.eacl-main.148. [Publisher record](https://aclanthology.org/2023.eacl-main.148/).
Supports evaluating embeddings across tasks and languages rather than assuming one model is universally best. Public benchmark performance is not personal-corpus retrieval accuracy.

**[23] Shahul Es, Jithin James, Luis Espinosa Anke, and Steven Schockaert, “RAGAs: Automated Evaluation of Retrieval Augmented Generation,” EACL System Demonstrations, 2024, pp. 150–158.** DOI:10.18653/v1/2024.eacl-demo.16. [Publisher record](https://aclanthology.org/2024.eacl-demo.16/).
Supports separating retrieval quality, faithfulness to context, and generation quality. Proposed future metrics must not be reported as completed experiments; model judges introduce their own validity and deployment assumptions.

**[24] Tianyu Gao, Howard Yen, Jiatong Yu, and Danqi Chen, “Enabling Large Language Models to Generate Text with Citations,” EMNLP, 2023, pp. 6465–6488.** DOI:10.18653/v1/2023.emnlp-main.398. [Publisher record](https://aclanthology.org/2023.emnlp-main.398/).
Supports citation-oriented evaluation, including whether sources support claims. Showing source cards or appending references alone does not establish citation correctness or answer completeness.

## Related-work synthesis and defensible positioning

Organize related work along three axes: retrieved knowledge [1–5], agent interaction and persistent memory [6–12], and local ownership/interoperability [13–20]. Benchmark and citation literature [21–24] supplies evaluation criteria, not substitute results. A useful comparison table can distinguish inference locality, explicit memory, document retrieval, source traceability, protocol exposure, and autonomous write capability. Mark undocumented properties as unknown rather than assuming that prior work is cloud-only or lacks privacy.

LocalMind's defensible contribution is a reproducible systems integration: local model serving, bounded hybrid retrieval, structured persistent project/conversation memory, a real MCP subprocess boundary, explicit folder approval, complete-text pagination, and a local user interface. These are engineering choices assembled for a constrained laptop. RAG, rank fusion, memory, local-first principles, and tool protocols are established ideas; the bibliography does not support “first,” “no existing system,” or a new retrieval algorithm.

Separate functional verification from effectiveness. Unit/API/protocol tests can establish persistence, paging, stale-source rejection, and tool restrictions. They cannot establish Recall@k, nDCG, grounded-answer accuracy, citation precision/recall, summary coverage, usability, privacy guarantees, or speed. Report such metrics only with a specified corpus, labeled queries, evaluation rubric, model/version, settings, and reproducible measurements. Local judges or human review may preserve an offline evaluation workflow, but each needs validation.

Avoid absolute security and cost language. Local processing limits external transmission when endpoints, model metadata, and external clients are controlled; it does not encrypt SQLite, defeat malware, or eliminate prompt injection. Zero paid API fees does not mean zero storage, power, installation bandwidth, or hardware cost. Full-document extraction is not equivalent to putting an entire drive in model context, and multi-pass summaries can still lose information.
