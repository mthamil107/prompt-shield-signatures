# Licensing

`prompt-shield-signatures` uses a **dual-licensing model** that separates the
software used to build and publish the feed from the threat-intelligence data
itself.

## Code — Apache License 2.0

All source code in this repository is licensed under the **Apache License,
Version 2.0**. This covers:

- Python scripts (`scripts/`)
- GitHub Actions workflows (`.github/workflows/`)
- JSON Schema definitions (`v1/schema.json` and any future schema files)
- Any tooling, helpers, or configuration

The full text is in [LICENSE](LICENSE).

We chose Apache 2.0 for the code because it provides an **explicit patent
grant** to contributors and users, which matters for a security tool that
implementers may embed in commercial products.

## Signature data — CC0 1.0 Universal (Public Domain Dedication)

All signature content is dedicated to the **public domain** under
[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).
This covers:

- Every file in `v1/source/`
- The published, machine-readable feed at `v1/signatures.json`
- Any future signature data formats we publish under `vN/`

You can use, redistribute, modify, and incorporate these signatures into
**any product — open source, proprietary, or commercial — without
attribution, without notice, and without legal friction.**

We chose CC0 for the data because:

1. Threat intel only has value if it is **broadly deployable**. Copyleft or
   attribution clauses create needless friction for closed-source vendors
   who want to ship the same protections as their open-source peers.
2. Many shops have legal review processes that automatically reject
   anything more restrictive than CC0 / MIT / BSD-0 for security data.
3. We do not want to imply any warranty about the data; CC0 is the
   cleanest disclaimer.

## Contributor terms

**By submitting a signature in a pull request to this repository, you agree
to dedicate that signature to the public domain under CC0 1.0 Universal.**
If you cannot make that dedication (e.g., your employer claims rights to
the signature you discovered), do not submit it — open an issue describing
the situation instead and we'll work out attribution privately.

Code contributions to `scripts/` and `.github/` follow the standard Apache
2.0 inbound = outbound convention described in Section 5 of the license.
