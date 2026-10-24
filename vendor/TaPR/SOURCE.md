# Vendored TaPR

- Source: https://github.com/saurf4ng/TaPR (redirects to https://github.com/wshw4ng/TaPR)
- Commit: `47d316127f6c96d2fb6e5e2acd91d61307de99ce`
- Files: `TaPR.py` and `LICENSE` (MIT), taken from that commit with `git show <commit>:<file>`
- `TaPR.py` sha256: `0ada5df354e6f8d06581c5b19eaf659cee656be8c0f3a22ac32f55c66e74b6b1`
- `LICENSE` sha256: `ae047f8fa761aece6b4fa76db819a8a268d86a233f650cdf9b0cbc9b8c424526`
- Status: unmodified. Do not edit `TaPR.py`; `src/tsfm_ad/tapr_wrap.py` loads it in memory and checks the sha256.

Why vendored: the repository has no installable package. Known quirks are kept as they are and handled in the
wrapper (PLAN.md section 9): the file loaders are not used, and detection uses `>` theta where the paper uses `>=`.
