# build.py — prompt-shield-signatures pipeline

Single-file build pipeline for the v1 signature feed.
Dependencies: Python 3.10+, `pyyaml`, `jsonschema`.

```
pip install pyyaml jsonschema
```

By default the script assumes the layout `<repo>/pipeline/scripts/build.py` and
operates on `<repo>/v1/source/`, `<repo>/v1/signatures.json`, and
`<repo>/schema/`. Override with `--root <path>`.

## Subcommands

### `validate`
Validates every YAML file in `v1/source/` against the per-signature JSON Schema
(`schema/schema.json`). Also enforces:

- No duplicate `id` values across files.
- Every `type: regex` pattern compiles under Python `re.compile`.

Errors are printed one per line as `<file>: field '<path>': <message>` — no
Python tracebacks. See **[SCHEMA.md](../../SCHEMA.md)** in the repo root for the
source-of-truth on what each field means.

```
python build.py validate
```

### `build [--dry-run]`
Re-validates, then merges every YAML into `v1/signatures.json` with this exact
envelope:

```json
{
  "$schema": "https://raw.githubusercontent.com/mthamil107/prompt-shield-signatures/main/schema/signatures-schema-v1.json",
  "version": "1",
  "generated_at": "<deterministic-iso8601>",
  "signature_count": <N>,
  "signatures": [ ... sorted by id ascending ... ]
}
```

- Sorted by `id` ascending.
- `json.dump(..., sort_keys=True, indent=2)` — stable git diffs.
- `generated_at` is **deterministic**: it is the latest mtime across
  `v1/source/*.yml`, NOT `datetime.now()`. This stops CI from rewriting
  `signatures.json` on every run.

`--dry-run` validates and reports without writing the file.

```
python build.py build
python build.py build --dry-run
```

### `sign`
Local-only. Calls `minisign -Sm v1/signatures.json` to produce
`v1/signatures.json.minisig`. Reads the secret-key path from
`$MINISIGN_SECRET_KEY` or prompts interactively. Never run this in CI — the
command refuses to run when `$CI` is truthy.

```
export MINISIGN_SECRET_KEY=/path/to/minisign.key
python build.py sign
```

If `minisign` isn't on PATH the script prints platform-specific install hints
for Linux, macOS, and Windows and exits 1.

### `verify`
Calls `minisign -Vm v1/signatures.json -P <pubkey>` where `<pubkey>` is the
`MAINTAINER_PUBLIC_KEY` constant at the top of `build.py`. The constant pins
the maintainer's ed25519 public key (key ID `31F125ADDE54B24A`). To rotate the
key, see [`../THREAT-MODEL.md`](../THREAT-MODEL.md).

```
python build.py verify
```

### `--help`
Standard argparse help, listing all subcommands.

```
python build.py --help
python build.py build --help
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | success |
| 1    | expected failure (bad input, missing tool, schema violation, missing signature file) |
| 2    | argparse / unexpected error |

## Cross-platform notes

- Pure stdlib + `pyyaml` + `jsonschema`. Works on Linux (CI) and Windows
  (local dev).
- Files are written with `newline="\n"` so signatures.json has stable line
  endings on Windows too.
