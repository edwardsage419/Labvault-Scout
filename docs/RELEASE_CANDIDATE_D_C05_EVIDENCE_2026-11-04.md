# D-C05 evidence addendum (2026-11-04 UTC)

This is evidence reconciliation only. It grants no release or compatibility approval.

Development branch develop-v0.3.0 was verified at `2fc1ee5f57d2855181d504a6fb8829f856803cca`. Stable main was `4877a9a8c794ba7d78d229ef395ad7f9d38961c9`.

Candidate `0.4.0rc1` is recorded in pyproject.toml, src/labvault_scout/__init__.py and RELEASE_NOTES_0_4_0_RC1.md.

GitHub Actions [run 41386826567](https://github.com/edwardsage419/Labvault-Scout/actions/runs/41386826567) completed successfully at the candidate metadata commit, with Windows, Ubuntu and macOS on Python 3.10 and 3.12 all successful. It supersedes the pre-version-update run 41382188397 cited in the historical candidate notes.

D-C05: TECHNICAL EVIDENCE SATISFIED for the fixed pre-addendum HEAD; FORMAL RELEASE GATE OPEN. The historical D gate's 0.3.2 status is preserved as dated evidence.

D-C01: OPEN. Real v0.3.2-generated POSIX report containing `C:sample.csv` is rejected by candidate validation. Maintain fail-closed validation and await owner acceptance of the disclosed compatibility change.

D-FREEZE: OPEN. Final semantic diff review, a new exact HEAD check, six successful CI jobs for the final commit and a freeze record remain necessary. This addendum changes HEAD, so its own CI must be checked.

Phases A, B and C retain their prior bounded evidence. This addendum does not claim new scanner tests, isolated installation, or public sample runs.

No changes to main, PR merge, tag or Release are authorized.
