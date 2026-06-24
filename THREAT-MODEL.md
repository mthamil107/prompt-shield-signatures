# Threat Model — prompt-shield-signatures v0.6.0-alpha

This document scopes what the signature feed defends against, what it does *not*, and the assumptions clients must accept when they consume it. Read it before integrating.

---

## 1. What this defends against

The feed is effective against attacks whose surface form is **stable across deployments**:

- **Verbatim and near-verbatim attack strings** — copy-paste payloads from leaked jailbreak collections, public GitHub repos, social-media threads.
- **Common multilingual templates** — known DAN-family translations, Spanish/French/Japanese variants tracked under the `multilingual_bypass` category.
- **Encoded variants of known attacks** — base64, ROT-N, zero-width-character smuggling, Unicode homoglyph substitution, where the underlying decoded text matches a tracked pattern.
- **Known multi-turn jailbreak templates** — the structural openers and persona-load prompts from documented chains (Crescendo, Skeleton Key, etc.) that recur verbatim across deployments.

If an attack appears in a public dataset, a Garak probe, an OWASP LLM-Top-10 example, or an academic paper, this feed is where it should land.

---

## 2. What this does NOT defend against

The signature layer is a deterministic filter on **strings**. It cannot reason about meaning. Specifically:

- **Novel paraphrased attacks.** A semantically-equivalent rewording of a known jailbreak will not match. This is the ML classifier's job — in prompt-shield, that's the `d022` family. The signature layer is the cheap pre-filter underneath, not the whole defense.
- **Zero-day prompt-injection techniques.** Anything not yet observed or contributed has no signature by definition. Expect a window between first-in-the-wild and first-merged-PR.
- **Semantically-equivalent attacks that don't match string patterns.** "Pretend you have no rules" and "act as if your guidelines do not apply" mean the same thing; only one might be in the feed.
- **Attacks that exploit application logic rather than prompt content.** Tool-call injection via crafted RAG documents, indirect injection through agent memory, prompt-leak via response-formatting tricks — these need application-layer controls, not pattern matching.
- **Adversarial-suffix attacks (e.g. GCG).** The suffixes are deliberately unstable across token boundaries. Catching one rarely generalizes; we add them anyway because some clients want belt-and-suspenders, but expect low recall.

**If your defense strategy is "subscribe to signatures and call it done," you have a gap.** The feed is one layer.

---

## 3. Why we sign

`signatures.json` is served from jsDelivr, a CDN we do not operate. jsDelivr is convenient (free, global, fast, no egress bill, GitHub-mirror semantics) but every byte transits infrastructure outside our trust boundary.

A malicious mirror, a hijacked DNS record, or a compromised CDN node could serve a poisoned `signatures.json` to a subset of clients. Without a signature check, that file would be applied immediately as new detection rules. Two concrete attack shapes:

- **DoS via overly-broad patterns.** Inject a regex like `(?i).*` with `severity: critical`. Every request to every adopter starts getting blocked. Recovery requires a coordinated rollback.
- **Backdoor by quiet removal.** Drop the entries that detect *one specific attacker's* favored payload. The feed still looks healthy — same shape, similar size, nothing obviously wrong — but a known attack now passes silently.

The minisign envelope closes this: the signing key never touches CI, never touches the CDN, and clients refuse any artifact that doesn't verify against the embedded public key.

---

## 4. Trust assumptions

These are the assumptions a consumer of the feed must accept. If any of them fails, the feed's guarantees do not hold.

- **Embedded key, not fetched key.** Clients trust the maintainer's ed25519 public key as distributed **embedded in the prompt-shield package** (in source code or a pinned config asset). The key MUST NOT be fetched from the CDN at runtime — that would defeat the entire signing layer.
- **Offline signing key.** The maintainer's private key is held offline. CI, GitHub Actions, the publish workflow, and the CDN never see it. The **daily** regeneration produces an unsigned `signatures.json`; the maintainer pulls, verifies, signs locally, and pushes the detached `.minisig` in a follow-up commit.
- **Key rotation is not yet specified.** v0.6.0-alpha has no documented rotation procedure. This is a known gap. v0.7.0 will spec the rotation flow (likely: dual-key window, embedded next-key, advance notice in `HISTORY.md`). Until then, treat a key compromise as a hard reset event requiring a coordinated client update.

### 4a. Why daily, not hourly

The README's tagline says "AV-update-like," and AV vendors publish hourly or faster. We deliberately ship at a slower cadence because the signing model demands it:

- The maintainer's private key cannot live in CI. If it did, any GitHub Actions compromise (a malicious workflow, a leaked PAT, a supply-chain attack on an `actions/*` runner image) becomes a feed-poisoning attack.
- Therefore signing happens on a human's machine, with a human in the loop.
- A human cannot reliably sign once an hour, 24×7. They can reliably sign once a day.
- Publishing unsigned content at a faster cadence would technically be "fresher" but consumer clients are required to reject unsigned data — so the user-visible cadence is still bounded by signing frequency. We choose to be honest in the metadata.

**The migration path is Sigstore Cosign (planned v0.7.0).** Sigstore enables *keyless* signing using GitHub Actions OIDC tokens, with a public transparency log replacing the private-key trust root. There is no long-lived key to compromise. Once v0.7.0 ships, the cron moves to hourly (or faster) and this constraint disappears. The schema, fetch URL, and client-side verifier are designed to coexist with both minisign and Sigstore so the migration is non-breaking.
- **Trust the contributor PR review.** Every signature is a regex or substring someone else wrote. We rely on PR review to catch overly-broad patterns before they merge. The schema's `confidence` field and the closed-enum categories are guardrails, not proofs.

---

## 5. Failure modes

What clients should do when something goes wrong:

| Failure | Correct client behavior |
|---|---|
| Feed unreachable (CDN down, network partition) | Use last-known-good cached `signatures.json`. **Never** fall back to "no rules." |
| `.minisig` missing or fails to verify | Refuse to apply the new file. Keep using the cache. Surface a warning. |
| `signature_count` does not equal `len(signatures)` | Treat as malformed. Do not apply. |
| Cache itself missing on first run | Ship the prompt-shield package with a baked-in default signature set. Bootstrap from that, then attempt to fetch. |
| Regex in a signature fails to compile on the client | Skip that one entry, log it, continue with the rest. Don't fail the whole load. |

The invariant: **a broken feed degrades to yesterday's rules, never to silent disablement.**

---

## 6. Bypass research is welcome

We will not pursue legal action against good-faith bypass research that follows responsible disclosure. If you find a way to evade signatures in the feed — or to evade the signing layer itself — please email **security@prompt-shield.dev** with a reproducer and a 90-day disclosure window.

Acknowledged bypasses will be published in [`HISTORY.md`](./HISTORY.md) with credit (or anonymized at your request) once the corresponding signatures or mitigations have shipped.

What counts as good-faith:

- You did not exfiltrate user data or pivot beyond what was needed to demonstrate the bypass.
- You did not publish details before the disclosure window closes.
- You targeted infrastructure you own, or a controlled test deployment.

What we ask in return: a clear reproducer, the prompt-shield version you tested against, and the signature IDs that should have caught the attack but didn't.
