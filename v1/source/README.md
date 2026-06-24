# Adding a new signature

Each signature is exactly one YAML file in this directory. CI merges every
`sig-NNNN.yml` here into the published `v1/signatures.json` artifact.

## File naming

- Format: `sig-NNNN.yml` where `NNNN` is a 4-digit zero-padded integer.
- Examples: `sig-0001.yml`, `sig-0042.yml`, `sig-1337.yml`.
- The filename's numeric portion MUST match the `id:` field inside.

## Picking the next free ID

IDs are immutable once published — never reuse, renumber, or recycle.

To find the next free ID:

```bash
ls v1/source/sig-*.yml | sed -E 's|.*/sig-0*([0-9]+)\.yml|\1|' | sort -n | tail -1
```

Add 1 to that number and zero-pad to four digits. If there are gaps in the
sequence (e.g. a signature was withdrawn pre-publish), **do not fill them** —
always take the next number above the current max. Gaps preserve audit history.

For draft PRs that may collide, reserve your range in the PR description
("claiming sig-0057..sig-0062") and a maintainer will confirm before merge.

## Required minimum

See `schema/SCHEMA.md` for the authoritative field list. Every signature must
have `id`, `type`, `pattern`, `category`, `severity`, `attack_class`,
`source.origin`, `source.reference`, `first_seen`, and `description`.

## Quality bar

- **Test mentally for false positives** on benign English before submitting.
  Patterns like a bare `ignore` are too noisy; require word boundaries and a
  modifier ("ignore previous instructions").
- **Prefer specificity** over coverage. One tight regex beats five loose ones.
- **Add `notes:`** when the FPR profile is non-obvious or rollout needs care.
- **Use `confidence: 0.7-0.98`** honestly. Reserve 0.95+ for patterns that are
  essentially unambiguous (literal canonical strings, published adversarial
  suffixes).

## Source provenance

Every signature must cite where the pattern came from:

| `source.origin` | When to use |
|---|---|
| `garak` | Patterns derived from NVIDIA garak probe classes. Reference the probe path. |
| `owasp` | OWASP LLM Top 10 (LLM01) examples and variants. |
| `community` | In-the-wild collections (jailbreakchat, GitHub, blog posts). Reference the most-cited URL. |
| `anthropic-paper` | Patterns documented in Anthropic research papers. |
| `adversarial-fatigue` | Patterns surfaced by the `prompt-shield` adversarial-fatigue technique. |

## Withdrawals

To retire a signature, open a PR that deletes the file and notes the rationale
in the PR description. CI's uniqueness check will keep the ID permanently
retired — do not reissue it.
