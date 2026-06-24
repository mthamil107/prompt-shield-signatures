# prompt-shield-signatures

> **Federated threat-intel feed for prompt-injection defense — open-source signatures, ed25519-signed, refreshed daily. Like AV updates, but for LLMs.**

![License](https://img.shields.io/badge/code-Apache--2.0-blue)
![Data License](https://img.shields.io/badge/data-CC0-success)
![Signatures](https://img.shields.io/badge/signatures-TBD-informational)
![Validate](https://img.shields.io/badge/validate-pending-lightgrey)

> ⚠️ **v0.6.0-alpha — schema may evolve; clients should opt-in only.** No SLA or key-rotation cadence guarantee yet.

---

## What this is

This repository publishes a public, **CC0-licensed**, **ed25519-signed** list of known prompt-injection attack patterns. Clients (the [prompt-shield](https://github.com/mthamil107/prompt-shield) firewall, and anyone else who wants to consume the feed) fetch the merged JSON file daily, verify the minisign signature against the maintainer's pinned public key, and apply every entry as a detection rule.

It is the **first open-source federated threat-intel feed for LLM defense**. Existing commercial offerings (Lakera, ProtectAI, Cisco) deliberately keep their attack-pattern catalogs proprietary — that catalog *is* their business model. We think the right model for the broader ecosystem is the one anti-virus eventually settled on: shared, signed, regularly-refreshed signatures, with each adopter contributing back.

> **Why daily, not hourly?** Signing requires the maintainer's offline private key — CI never sees it. A daily cadence keeps every published `signatures.json` verifiable; an hourly cadence would either publish unsigned content or force the key into CI. **v0.7.0 migrates to [Sigstore Cosign](https://www.sigstore.dev/) keyless signing, which lifts this constraint** — at which point we move to hourly. See [`THREAT-MODEL.md`](THREAT-MODEL.md) for the full reasoning.

The mechanics are old and boring on purpose: a flat file on a CDN, a detached minisign signature, and a fetch-and-verify loop. There is nothing novel in the *delivery*; the novelty is that the *data* is open.

---

## Fetch URL

The two URLs every client needs:

- **Signatures:** `https://cdn.jsdelivr.net/gh/mthamil107/prompt-shield-signatures@main/v1/signatures.json`
- **Signature:** `https://cdn.jsdelivr.net/gh/mthamil107/prompt-shield-signatures@main/v1/signatures.json.minisig`

### Maintainer public key

```
untrusted comment: minisign public key 31F125ADDE54B24A
RWRKslTerSXxMfTgML57AMf7Hwu8djP7mYxdRFopQriPW4+9UG4zcdVi
```

**Key ID:** `31F125ADDE54B24A` · **Algorithm:** ed25519 · **Generated:** 2026-06-24 · **Rotation policy:** see [`THREAT-MODEL.md`](THREAT-MODEL.md#4-trust-assumptions). The private half lives offline on the maintainer's machine and never enters CI.

> **This is a placeholder.** The real public key will be inserted by the maintainer before the v0.6.0-alpha release tag. Clients that ship before that tag will refuse to verify. Do not paper over this in your own fork.

### Verify and apply (5 lines)

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/mthamil107/prompt-shield-signatures@main/v1/signatures.json -o signatures.json
curl -fsSL https://cdn.jsdelivr.net/gh/mthamil107/prompt-shield-signatures@main/v1/signatures.json.minisig -o signatures.json.minisig
echo "$MAINTAINER_PUBKEY" > pubkey.txt
minisign -Vm signatures.json -p pubkey.txt
jq '.signature_count' signatures.json
```

If `minisign` exits non-zero, **do not apply the file**. Fall back to your last-known-good cache. See [THREAT-MODEL.md](./THREAT-MODEL.md) for why this matters.

---

## Schema

The full schema, field semantics, and design rationale live in [`schema/SCHEMA.md`](./schema/SCHEMA.md). One representative signature looks like this:

```yaml
id: sig-0007
type: substring
pattern: "DAN mode enabled"
category: dan_jailbreak
severity: medium
attack_class: direct_injection
source:
  origin: community
  reference: "https://github.com/mthamil107/prompt-shield-signatures/pull/14"
first_seen: 2025-11-02
description: "Substring marker emitted by DAN-family jailbreaks that announce mode change."
```

Required fields: `id`, `type`, `pattern`, `category`, `severity`, `attack_class`, `source`, `first_seen`, `description`. Optional: `confidence`, `tags`, `last_updated`, `notes`, `language`.

---

## How to contribute a signature

1. **Fork** this repo.
2. **Add** a single file at `v1/source/sig-NNNN.yml`, using the next free 4-digit ID. CI rejects duplicates and gaps don't matter — pick the next integer.
3. **Open a PR.** The PR body should explain how you observed the attack (a paper, a probe ID, a reproducer prompt, a screenshot — anything an auditor could follow).
4. **CI validates** against the JSON Schema, compiles every `regex` pattern, and checks for ID collisions and exact-`pattern` duplicates.
5. **On merge**, the publish workflow regenerates `v1/signatures.json` on a daily schedule (12:00 UTC). The maintainer signs the regenerated artifact **offline** and pushes `v1/signatures.json.minisig` in a follow-up commit.
6. **Licensing:** by opening a PR you agree your contribution is released under CC0. See [`LICENSES.md`](./LICENSES.md) for full text.

---

## Licensing

| Artifact | License |
|---|---|
| Code (CI, build scripts, schema validators) | Apache 2.0 |
| Signature data (`v1/source/*.yml`, `v1/signatures.json`) | CC0 1.0 |

Why split? CC0 on the data is what lets *any* downstream firewall — commercial or open — consume the feed without a license-compatibility audit. Apache 2.0 on the code gives the build tooling a normal OSS patent grant. Both are in [`LICENSES.md`](./LICENSES.md).

---

## Threat model (summary)

We defend against **distribution of known attack strings**: once a pattern lands here, every adopter picks it up within an hour, automatically. The minisign envelope prevents a tampered CDN from feeding clients a poisoned file.

We do **not** replace ML-based detection. Paraphrased attacks, novel jailbreak families, and semantically-equivalent variants remain the classifier's job (see prompt-shield's `d022` and friends). Signatures are the fast, cheap, deterministic layer underneath.

Full details in [THREAT-MODEL.md](./THREAT-MODEL.md).

---

## Why open?

Lakera, ProtectAI, and Cisco can't open-source their intel because they sell it. That's a fine business — but it means the broader ecosystem (small teams, academic labs, OSS projects) has no shared baseline to compose against.

We think the network effects compound the other way: every adopter who contributes a signature back improves detection for everyone, including the adopter. This is how anti-virus signatures, IDS rulesets (Snort/Suricata), and CVE databases ended up working. We're betting the same shape fits LLM defense.

---

## Companion artifacts

- **Paper:** [arXiv:2604.18248](https://arxiv.org/abs/2604.18248) — *prompt-shield: a layered prompt-injection firewall* (CC BY 4.0). The signature feed is the distribution layer for the techniques described in §4.
- **Design notes:** [Zenodo DOI 10.5281/zenodo.20809165](https://doi.org/10.5281/zenodo.20809165) — implementation notes for the v0.5.0 detection techniques the signatures complement.

---

## Citation

```bibtex
@misc{promptshieldsignatures2026,
  author       = {Munirathinam, Thamilvendhan and contributors},
  title        = {{prompt-shield-signatures}: a federated threat-intel feed
                  for prompt-injection defense},
  year         = {2026},
  howpublished = {\url{https://github.com/mthamil107/prompt-shield-signatures}},
  note         = {Signature data CC0 1.0; code Apache 2.0. See also
                  arXiv:2604.18248.}
}
```
