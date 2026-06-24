#!/usr/bin/env python3
"""Build pipeline for prompt-shield-signatures v1 feed.

Subcommands:
  validate  - Validate every YAML in v1/source/ against the per-signature schema.
  build     - Merge validated YAML into v1/signatures.json (deterministic).
  sign      - Locally sign v1/signatures.json with minisign (never run in CI).
  verify    - Verify v1/signatures.json against the hard-coded maintainer pubkey.

The script is intentionally a single file with stdlib + pyyaml + jsonschema only.
Exit codes:
  0 - success
  1 - expected failure (bad input, missing tool, schema violation)
  2 - argparse / unexpected error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    print("error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from jsonschema import Draft7Validator
    from jsonschema.exceptions import ValidationError
except ImportError:
    print("error: jsonschema is required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


# Maintainer ed25519 public key (key ID 31F125ADDE54B24A, generated 2026-06-24).
# The private half lives offline on the maintainer's machine and never enters CI.
# See THREAT-MODEL.md for the rotation policy.
MAINTAINER_PUBLIC_KEY: str = "RWRKslTerSXxMfTgML57AMf7Hwu8djP7mYxdRFopQriPW4+9UG4zcdVi"

SCHEMA_FILENAME = "schema.json"
ENVELOPE_SCHEMA_FILENAME = "signatures-schema-v1.json"
ENVELOPE_SCHEMA_URL = (
    "https://raw.githubusercontent.com/mthamil107/prompt-shield-signatures/"
    "main/schema/signatures-schema-v1.json"
)


@dataclass(frozen=True)
class Paths:
    """Container for the layout of the repo this script operates on."""

    root: Path

    @property
    def schema_file(self) -> Path:
        return self.root / "schema" / SCHEMA_FILENAME

    @property
    def envelope_schema_file(self) -> Path:
        return self.root / "schema" / ENVELOPE_SCHEMA_FILENAME

    @property
    def source_dir(self) -> Path:
        return self.root / "v1" / "source"

    @property
    def signatures_file(self) -> Path:
        return self.root / "v1" / "signatures.json"

    @property
    def minisig_file(self) -> Path:
        return self.root / "v1" / "signatures.json.minisig"


def _err(msg: str) -> None:
    """Write a single human-readable error to stderr (no traceback)."""
    print(f"error: {msg}", file=sys.stderr)


def _load_schema(paths: Paths) -> dict[str, Any]:
    """Load and parse the per-signature JSON Schema."""
    if not paths.schema_file.exists():
        _err(f"schema file not found: {paths.schema_file}")
        sys.exit(1)
    try:
        with paths.schema_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        _err(f"schema file is not valid JSON: {paths.schema_file}: {e.msg} (line {e.lineno})")
        sys.exit(1)


def _iter_source_files(paths: Paths) -> list[Path]:
    """Return a sorted list of YAML source files under v1/source/."""
    if not paths.source_dir.exists():
        _err(f"source directory not found: {paths.source_dir}")
        sys.exit(1)
    files: list[Path] = []
    for ext in ("*.yml", "*.yaml"):
        files.extend(paths.source_dir.glob(ext))
    return sorted(files)


def _coerce_dates(value: Any) -> Any:
    """Recursively coerce datetime.date/datetime → ISO-8601 strings.

    YAML 1.1 auto-parses ``2024-01-15`` into ``datetime.date``; JSON Schema
    requires ``string``. We canonicalize at load time so the schema does
    not need to know about Python types and the published JSON file is
    plain ISO strings.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _coerce_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_dates(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file, returning the parsed mapping."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _err(f"{path}: invalid YAML: {e}")
        sys.exit(1)
    if not isinstance(data, dict):
        _err(f"{path}: top-level YAML must be a mapping, got {type(data).__name__}")
        sys.exit(1)
    return _coerce_dates(data)


def _format_validation_error(path: Path, err: ValidationError) -> str:
    """Format a jsonschema ValidationError as a human-friendly one-liner."""
    field_path = ".".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: field '{field_path}': {err.message}"


def _validate_one(
    path: Path,
    doc: dict[str, Any],
    validator: Draft7Validator,
) -> list[str]:
    """Validate a single signature doc; return list of error strings (empty == OK)."""
    errors: list[str] = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        errors.append(_format_validation_error(path, err))
    if errors:
        return errors

    # Extra check 1: regex patterns must compile under Python re.
    if doc.get("type") == "regex":
        pat = doc.get("pattern", "")
        try:
            re.compile(pat)
        except re.error as e:
            errors.append(f"{path}: field 'pattern': regex does not compile under Python re: {e}")

    return errors


def _validate_all(paths: Paths) -> list[dict[str, Any]]:
    """Validate every YAML, dedupe by id, and return the parsed docs sorted by id.

    On any failure prints a human-friendly error and exits 1.
    """
    schema = _load_schema(paths)
    validator = Draft7Validator(schema)
    files = _iter_source_files(paths)
    if not files:
        _err(f"no YAML signature files found in {paths.source_dir}")
        sys.exit(1)

    all_errors: list[str] = []
    docs: list[tuple[Path, dict[str, Any]]] = []
    seen_ids: dict[str, Path] = {}

    for f in files:
        doc = _load_yaml(f)
        errors = _validate_one(f, doc, validator)
        all_errors.extend(errors)
        if errors:
            continue
        sig_id = doc.get("id")
        if not isinstance(sig_id, str):
            # The schema enforces this, so we'd have errored above; defensive guard.
            continue
        if sig_id in seen_ids:
            all_errors.append(
                f"{f}: duplicate id '{sig_id}' (first seen in {seen_ids[sig_id]})"
            )
            continue
        seen_ids[sig_id] = f
        docs.append((f, doc))

    if all_errors:
        for e in all_errors:
            _err(e)
        _err(f"validation failed: {len(all_errors)} error(s) across {len(files)} file(s)")
        sys.exit(1)

    docs.sort(key=lambda pair: pair[1]["id"])
    return [doc for _, doc in docs]


def _deterministic_generated_at(paths: Paths) -> str:
    """Derive a deterministic RFC3339 UTC timestamp from the LATEST mtime under v1/source/.

    Rationale: using datetime.now() would make every CI run produce a new
    signatures.json even when no source file changed, causing endless commit
    churn. The latest mtime is stable across rebuilds of the same source tree
    (in CI, mtimes are set from the git checkout) and updates exactly when a
    source file changes.
    """
    files = _iter_source_files(paths)
    latest = max(f.stat().st_mtime for f in files)
    dt = datetime.fromtimestamp(latest, tz=timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_validate(paths: Paths) -> int:
    """Validate every YAML signature under v1/source/.

    Checks:
      1. Each file conforms to the per-signature JSON Schema.
      2. No duplicate `id` values across files.
      3. Every `type: regex` pattern compiles under Python `re.compile`.
    """
    docs = _validate_all(paths)
    print(f"OK: {len(docs)} signature(s) validated.")
    return 0


def cmd_build(paths: Paths, dry_run: bool) -> int:
    """Merge validated YAML into v1/signatures.json.

    Output is deterministic: sorted by id, sort_keys=True, indent=2, and
    `generated_at` is derived from the latest source-file mtime.
    """
    docs = _validate_all(paths)
    envelope: dict[str, Any] = {
        "$schema": ENVELOPE_SCHEMA_URL,
        "version": "1",
        "generated_at": _deterministic_generated_at(paths),
        "signature_count": len(docs),
        "signatures": docs,
    }

    if dry_run:
        print(f"Would write {len(docs)} signatures to {paths.signatures_file}")
        return 0

    paths.signatures_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with paths.signatures_file.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(envelope, f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        _err(f"failed to write {paths.signatures_file}: {e}")
        return 1

    print(f"Wrote {len(docs)} signatures to {paths.signatures_file}")
    return 0


def _minisign_install_hint() -> str:
    return (
        "minisign is not installed or not on PATH.\n"
        "  Linux:   apt install minisign  (or: brew install minisign)\n"
        "  macOS:   brew install minisign\n"
        "  Windows: choco install minisign  (or download from https://jedisct1.github.io/minisign/)"
    )


def cmd_sign(paths: Paths) -> int:
    """Sign v1/signatures.json with minisign. Local-only; never run in CI.

    Secret key location:
      $MINISIGN_SECRET_KEY (path to .key file), or interactive prompt fallback.
    """
    if os.environ.get("CI", "").lower() in ("1", "true", "yes"):
        _err("`build.py sign` must not be run in CI. Signing happens locally.")
        return 1

    if shutil.which("minisign") is None:
        _err(_minisign_install_hint())
        return 1

    if not paths.signatures_file.exists():
        _err(
            f"{paths.signatures_file} does not exist; run `build.py build` first."
        )
        return 1

    secret_key = os.environ.get("MINISIGN_SECRET_KEY")
    if not secret_key:
        try:
            secret_key = input("Path to minisign secret key (.key): ").strip()
        except (EOFError, KeyboardInterrupt):
            _err("no secret key provided")
            return 1
    if not secret_key or not Path(secret_key).exists():
        _err(f"minisign secret key not found at: {secret_key!r}")
        return 1

    cmd = ["minisign", "-Sm", str(paths.signatures_file), "-s", secret_key]
    try:
        result = subprocess.run(cmd, check=False)
    except OSError as e:
        _err(f"failed to invoke minisign: {e}")
        return 1
    if result.returncode != 0:
        _err(f"minisign exited with status {result.returncode}")
        return 1

    print(f"Signed: {paths.minisig_file}")
    return 0


def cmd_verify(paths: Paths) -> int:
    """Verify v1/signatures.json against the hard-coded maintainer public key."""
    if shutil.which("minisign") is None:
        _err(_minisign_install_hint())
        return 1

    if not paths.signatures_file.exists():
        _err(f"{paths.signatures_file} does not exist.")
        return 1
    if not paths.minisig_file.exists():
        _err(
            f"signature file not found: {paths.minisig_file}\n"
            f"  (run `build.py sign` locally, or fetch the .minisig from the release)"
        )
        return 1

    if MAINTAINER_PUBLIC_KEY.startswith("RWQ_REPLACE_"):
        _err(
            "MAINTAINER_PUBLIC_KEY is still the alpha placeholder. "
            "Set it to the real key in build.py before relying on `verify`."
        )
        return 1

    cmd = [
        "minisign",
        "-Vm",
        str(paths.signatures_file),
        "-P",
        MAINTAINER_PUBLIC_KEY,
    ]
    try:
        result = subprocess.run(cmd, check=False)
    except OSError as e:
        _err(f"failed to invoke minisign: {e}")
        return 1
    if result.returncode != 0:
        _err(f"minisign verification failed (exit {result.returncode})")
        return 1

    print("OK: signature verified.")
    return 0


def _default_root() -> Path:
    """Repo root = the script's parent directory's parent.

    Layout assumed: <root>/pipeline/scripts/build.py
    """
    return Path(__file__).resolve().parent.parent.parent


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build.py",
        description="Build pipeline for prompt-shield-signatures v1 feed.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root (default: two directories above this script).",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    sub.add_parser("validate", help="Validate every YAML in v1/source/.")
    pb = sub.add_parser("build", help="Merge validated YAML into v1/signatures.json.")
    pb.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report the merge result without writing the file.",
    )
    sub.add_parser("sign", help="Sign v1/signatures.json with minisign (local only).")
    sub.add_parser("verify", help="Verify v1/signatures.json against the maintainer pubkey.")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = args.root.resolve() if args.root is not None else _default_root()
    if not root.exists():
        _err(f"--root path does not exist: {root}")
        return 1
    paths = Paths(root=root)

    if args.command == "validate":
        return cmd_validate(paths)
    if args.command == "build":
        return cmd_build(paths, dry_run=args.dry_run)
    if args.command == "sign":
        return cmd_sign(paths)
    if args.command == "verify":
        return cmd_verify(paths)

    # argparse with required=True already covers this; defensive fallback.
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _err("interrupted")
        sys.exit(1)
