# Security Policy

`prompt-shield-signatures` is a federated threat-intelligence feed for the
`prompt-shield` prompt-injection firewall. Because downstream users may
deploy these signatures directly into a production block-list, both
**vulnerabilities in the build pipeline** and **malicious signatures
submitted via pull request** are in scope here.

## Reporting a vulnerability

Please report security issues **privately** to:

- **Email:** mthamil107@gmail.com
- **Subject prefix:** `[prompt-shield-signatures security]`

Include:

- A description of the issue and its impact.
- Steps to reproduce, if applicable.
- Any proposed mitigation.

**Expected response time: within 7 days** of receipt. If you do not hear
back within 7 days, please re-send and CC any public maintainer contact
listed in the repository's `README.md`.

Please do **not** open a public GitHub issue, discussion, or pull request
that describes the vulnerability before we have had a chance to respond.

## Reporting a malicious signature

If you believe a signature in `v1/signatures.json` or `v1/source/` is
malicious, deliberately misleading, or causes a high false-positive rate
that will break downstream users, report it using the same channel above.

Confirmed malicious signatures are handled as follows:

1. The offending signature is reverted with `git revert <sha>` so the
   audit trail is preserved.
2. The daily `publish.yml` workflow regenerates `v1/signatures.json`
   without the bad entry; in urgent cases the maintainer triggers the
   workflow manually via `workflow_dispatch` to skip the daily wait.
3. The maintainer re-signs the rebuilt file locally with minisign and
   pushes the new `.minisig`.
4. The contributor account that submitted the signature is reviewed; if
   the submission appears to be deliberately adversarial, the account is
   blocked from the repository.

## Supply-chain hardening

- The minisign **private signing key never enters CI.** Releases are
  signed only from the maintainer's local machine. A compromise of GitHub
  Actions does not produce a validly signed feed.
- CI is restricted to writing `v1/signatures.json` (rebuilds from source)
  and cannot publish signatures or rotate keys.
- All signature submissions arrive via pull request and are validated by
  `.github/workflows/validate.yml` before they can be merged.
