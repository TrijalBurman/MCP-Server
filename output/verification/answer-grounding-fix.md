# File catalog and grounded-answer repair

Historical verification snapshot from before the later model upgrade and GitHub
publication. Its source status and test totals below describe that verification
step. See [model-upgrade.md](model-upgrade.md) for the later citation retry,
selected model and regression results, and [the deliverables index](../README.md)
for version boundaries.

Verified locally on 17 October 2026. Both normal and demonstration applications
were restarted; their existing data was preserved. The Linux and Windows source
copies contain the same agent, storage and grounding changes; Windows retains
its native source-reading checks. The repair is local, uncommitted and unpublished.

## Causes and changes

File inventory questions previously reached a model with just five ranked source
passages. The model treated partial results as a complete inventory and could
contradict itself about filenames. Inventory and exact filename requests now use
real MCP metadata tools without model inference. Pagination, duplicate basenames,
case rules and indexed-scope limits are explicit. Ambiguous multi-file or filtered
requests are clarified rather than answered from an unrelated partial search.

Document prompts previously used the first 1,000 characters and then truncated
JSON in the middle of records. They now use query-centered exact source excerpts,
complete numbered records, fair budget allocation and repacking after document
tool calls. Returned source cards correspond to delivered excerpts. Prior
assistant claims are omitted when new document evidence is available. Invalid
or missing references on document answers trigger a labeled source-excerpt
fallback. Citation checks ignore indexes inside Markdown code.

## Verification

- Linux suite: 123 passed.
- Windows copy tested on Linux: 160 passed; six native Windows checks skipped.
- Real MCP tests cover 205-file pagination, duplicates, exact filenames, absent
  files, stale chat, late facts, citation failures and multiple tool rounds.
- After restart, HTTP checks against the actual seven-file index returned all
  seven documents, one exact api.md match, and no match for a fabricated filename.
  These requests used metadata tools only. The temporary verification conversation
  was deleted and original data counts were preserved.
- Four fresh synthetic local-model smoke questions returned the three known fact
  answers (including a fact beyond character 1,000 and a two-document question)
  and abstained on the absent audit date. This is not a general accuracy study.
- Lint and whitespace checks passed. No model change or download was required.

The frozen research benchmark and previously exported academic documents were
not rerun or revised for these later changes. Their observations remain versioned
historical evidence. This repair reduces concrete failure modes; valid citation
numbers alone do not establish semantic truth. Check important claims in the
source reader. Old chat messages remain historical; ask again to get a new reply.
