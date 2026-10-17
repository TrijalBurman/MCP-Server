# Verification records

These records describe successive development snapshots. Later results do not
replace the earlier paper measurements or their source hashes.

| Record | Scope |
|---|---|
| [Model upgrade](model-upgrade.md) | Latest 9B/12K development configuration, citation retry, hardware and live checks; 135 Linux and 172 Windows-copy tests on Linux |
| [Regression logs](regressions/README.md) | Raw final citation-retry test logs and source hashes |
| [Answer-grounding repair](answer-grounding-fix.md) | Earlier metadata/evidence repair snapshot; 123/160 tests |
| [Context-fitting repair](context-fitting-fix.md) | Earlier exact serialized-budget repair snapshot; 62/99 tests and frozen 64-request replay |
| [Document export verification](document-update-verification.json) | Earlier PDF/Word export, page counts, rehearsal and checksums at that export time |

Historical statements about uncommitted source and readiness describe the state
when each check ran. Older document-export hashes apply to those exports; current
Markdown setup notes and the demo launcher were updated afterward. The complete
publication ZIP has a fresh `SHA256SUMS` covering its contents and a separate
outer archive checksum.
