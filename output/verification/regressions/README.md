# Citation-retry regression verification

These are the final local test logs recorded on 17 October 2026, before repository
publication. The suites exercised scripted model responses and temporary data;
they did not download models or measure language-model accuracy.

- Linux: **135 passed**.
- Windows copy executed on Linux: **172 passed, 6 native-platform checks skipped**.
- Both application copies passed lint and whitespace checks.
- The 30 answer-grounding cases cover successful retries, failure paths, one-retry
  limits, omitted tool schemas/drafts, exact evidence/card matching, and both
  normal and forced synthesis paths.

[The summary](citation-retry-regression-summary.json) records source/test hashes
and names the raw logs. Native Windows GPU inference was not tested in these
runs. The existing Starlette/httpx deprecation warning did not cause failures.
