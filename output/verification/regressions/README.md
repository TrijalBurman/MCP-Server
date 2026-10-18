# Application regression verification

The citation-retry logs below are historical local test logs recorded on 17 October 2026, before repository
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

## Local routing and exact file identity

The later routing repair passed **163 Linux tests** and **200 Windows-copy tests
on Linux**, with **six native checks skipped**. The 28 added cases cover neutral
greeting routes, mixed requests, imperative citation checks, exact long titles
and file identities, long-path recovery and forced-final evidence delivery.

- [Linux suite log](local-routing-linux-pytest.log)
- [Windows-copy suite log](local-routing-windows-on-linux-pytest.log)
- [Linux lint](local-routing-linux-lint.log) and [Windows-copy lint](local-routing-windows-lint.log)
- [Current source hashes and live checks](../local-routing-fix.json)

Suite checks use synthetic temporary data and scripted inference, rather than
measuring a model's answer accuracy. No native Windows GPU claim follows from
these Linux-hosted runs.
