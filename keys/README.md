# `keys/` — local-only signing material

This directory is intended to hold the **maintainer's local minisign keys**
used to sign released `v1/signatures.json` artifacts.

## Rules

1. **Never commit a private key.** The repository `.gitignore` ignores
   `*.key`, `keys/*.sec`, `keys/*.private`, and `*.minisig.private` as a
   safety net, but the primary rule is operator discipline.
2. The signing keypair lives **only on the maintainer's local machine.**
   It is deliberately *not* stored in GitHub Secrets, an HSM rented by the
   project, or any CI environment. The threat model assumes a CI provider
   compromise should not produce a validly signed malicious feed.
3. The matching **public key** (`*.pub`) is fine to commit and is in fact
   the basis for verification by downstream `prompt-shield` clients —
   commit it as `keys/maintainer.pub` (or similar) once generated.

## Generating a keypair

```sh
minisign -G -p keys/maintainer.pub -s keys/maintainer.sec
```

The `.sec` file is gitignored. Back it up to encrypted offline storage
(e.g., an encrypted USB drive or a password manager attachment); if it is
lost, downstream clients will need to be re-shipped a new public key.

## Signing a release

```sh
python scripts/build.py sign
```

This script (run locally, never in CI) signs `v1/signatures.json` with the
private key and writes `v1/signatures.json.minisig`, which is committed and
pushed alongside the data.
