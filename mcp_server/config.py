"""Central configuration schema and file-backed store.

Every user-tunable setting is declared once in ``OPTIONS`` below. Values resolve
in priority order:

    real environment variable  >  config file  >  built-in default

The config file (``config.json`` in the platform config dir) lets non-technical
users — and the CLI / GUI built on this schema — persist settings without
editing OS environment variables. An explicitly-set environment variable always
wins, so existing setups and MCP-client ``env`` blocks are never overridden.

The rest of the codebase keeps reading ``os.environ`` as before; ``apply_config_
to_env()`` (called at server startup) bridges the file into the environment for
any key the environment does not already set.
"""

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "claude-patent-creator"
GIB = 1024**3


@dataclass(frozen=True)
class Option:
    """One configurable setting. Values are stored/compared as strings because
    that is how environment variables behave."""

    key: str
    section: str
    label: str
    description: str
    type: str  # "str" | "int" | "bool" | "choice" | "secret"
    default: str = ""
    choices: tuple[str, ...] = ()
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    note: str = ""

    @property
    def is_secret(self) -> bool:
        return self.type == "secret"


OPTIONS: tuple[Option, ...] = (
    # --- Credentials ---------------------------------------------------------
    Option(
        "GOOGLE_CLOUD_PROJECT", "Credentials", "BigQuery billing project",
        "Google Cloud project ID that BigQuery prior-art searches are billed to "
        "(free tier: 1 TiB/month). Required for BigQuery search.",
        "str",
    ),
    Option(
        "USPTO_API_KEY", "Credentials", "USPTO ODP API key",
        "API key for the USPTO Open Data Portal (data.uspto.gov). Optional; "
        "enables USPTO application/grant search.",
        "secret",
    ),
    Option(
        "EPO_OPS_KEY", "Credentials", "EPO OPS key",
        "Consumer key for the EPO Open Patent Services API. Optional; enables "
        "European patent biblio/claims lookup.",
        "secret",
    ),
    Option(
        "EPO_OPS_SECRET", "Credentials", "EPO OPS secret",
        "Consumer secret paired with the EPO OPS key.",
        "secret",
    ),
    Option(
        "ANTHROPIC_API_KEY", "Credentials", "Anthropic API key",
        "Used only for API-backed HyDE query expansion when HYDE_BACKEND=api. "
        "Otherwise unused.",
        "secret",
    ),
    Option(
        "OPENAI_API_KEY", "Credentials", "OpenAI API key",
        "Alternative backend for API HyDE query expansion (HYDE_BACKEND=api).",
        "secret",
    ),
    # --- Search & performance ------------------------------------------------
    Option(
        "PATENT_BIGQUERY_MAX_BYTES_BILLED", "Search", "BigQuery cost cap (bytes)",
        "Per-query scan ceiling for BigQuery. A title search scans ~15 GiB; an "
        "abstract/claims search scans ~200+ GiB, so the 25 GiB default blocks "
        "full-text search until raised.",
        "int", default=str(25 * GIB), minimum=GIB,
        note="250 GiB ~= $1.30/query at on-demand pricing.",
    ),
    Option(
        "HYDE_BACKEND", "Search", "HyDE backend",
        "Query-expansion backend. 'api' uses Anthropic/OpenAI (consumes API "
        "quota); empty uses the local model.",
        "choice", default="", choices=("", "api"),
    ),
    Option(
        "PATENT_MPEP_USE_HYDE", "Search", "Enable HyDE expansion",
        "Whether MPEP semantic search expands the query with a hypothetical "
        "document before retrieval.",
        "bool", default="true",
    ),
    Option(
        "PATENT_ENABLE_ANTECEDENT_CHECK", "Search", "Claim antecedent-basis check",
        "Enable the (slower) antecedent-basis analysis when checking claims.",
        "bool", default="false",
    ),
    Option(
        "PATENT_MPEP_DEVICE", "Performance", "Embedding device",
        "Compute device for the embedding model. 'auto' picks the best "
        "available; 'mps' (Apple) is opt-in because it can be slower than CPU.",
        "choice", default="", choices=("", "auto", "cpu", "gpu", "cuda", "mps"),
    ),
    Option(
        "FORCE_CPU", "Performance", "Force CPU",
        "Force CPU for embeddings even if a GPU is present.",
        "bool", default="false",
    ),
    Option(
        "PATENT_TORCH_CUDA", "Performance", "CUDA wheel override",
        "Pin the PyTorch CUDA build used by setup when auto-detection can't "
        "determine the GPU architecture. Empty = auto-detect.",
        "choice", default="", choices=("", "cu126", "cu128"),
    ),
    Option(
        "PATENT_LOG_LEVEL", "Performance", "Log level",
        "Logging verbosity for the server.",
        "choice", default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    ),
)

OPTIONS_BY_KEY: dict[str, Option] = {o.key: o for o in OPTIONS}

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off", ""}


def config_dir() -> Path:
    """Platform config directory (override with PATENT_CONFIG_DIR)."""
    override = os.environ.get("PATENT_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_file() -> dict[str, str]:
    """Load known settings from the config file (unknown keys ignored)."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if k in OPTIONS_BY_KEY}


def save_value(key: str, value: str) -> Path:
    """Persist a single setting (merging with the existing file)."""
    return save_values({key: value})


def save_values(values: dict[str, str]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_file()
    for key, value in values.items():
        if key not in OPTIONS_BY_KEY:
            raise KeyError(f"Unknown setting: {key}")
        current[key] = str(value)
    # Drop blanks so the file stays minimal.
    clean = {k: v for k, v in current.items() if v != ""}
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, sort_keys=True)
    tmp.replace(path)
    # best-effort: secrets live here, so restrict perms where supported
    with contextlib.suppress(OSError):
        path.chmod(0o600)
    return path


def unset_value(key: str) -> Path:
    if key not in OPTIONS_BY_KEY:
        raise KeyError(f"Unknown setting: {key}")
    path = config_path()
    current = load_file()
    current.pop(key, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in current.items() if v != ""}, fh, indent=2, sort_keys=True)
    tmp.replace(path)
    return path


def get_effective(key: str) -> tuple[str, str]:
    """Return (value, source) for a key. source is 'env', 'file', or 'default'.
    An empty environment variable is treated as unset."""
    if key not in OPTIONS_BY_KEY:
        raise KeyError(f"Unknown setting: {key}")
    env = os.environ.get(key)
    if env not in (None, ""):
        return env, "env"  # type: ignore[return-value]
    file_vals = load_file()
    if file_vals.get(key, "") != "":
        return file_vals[key], "file"
    return OPTIONS_BY_KEY[key].default, "default"


def validate(key: str, value: str) -> Optional[str]:
    """Return an error message if value is invalid for key, else None."""
    if key not in OPTIONS_BY_KEY:
        return f"Unknown setting: {key}"
    opt = OPTIONS_BY_KEY[key]
    if opt.type == "int":
        try:
            number = int(value)
        except ValueError:
            return "must be an integer"
        if opt.minimum is not None and number < opt.minimum:
            return f"must be >= {opt.minimum}"
        if opt.maximum is not None and number > opt.maximum:
            return f"must be <= {opt.maximum}"
    elif opt.type == "bool":
        if value.lower() not in _BOOL_TRUE | _BOOL_FALSE:
            return "must be true or false"
    elif opt.type == "choice":
        if value != "" and value not in opt.choices:
            allowed = ", ".join(c for c in opt.choices if c)
            return f"must be one of: {allowed}"
    return None


def normalize(key: str, value: str) -> str:
    """Canonicalize a validated value (bools -> true/false)."""
    opt = OPTIONS_BY_KEY[key]
    if opt.type == "bool":
        return "true" if value.lower() in _BOOL_TRUE else "false"
    return value


def apply_config_to_env() -> None:
    """Inject file-backed settings into the environment for keys the environment
    does not already define, so existing os.environ readers pick them up.
    A real environment variable is never overridden."""
    for key, value in load_file().items():
        if value != "" and os.environ.get(key, "") == "":
            os.environ[key] = value
