"""Bundle variables reach serverless jobs only as task parameters. apply() moves --catalog, --schema and
--lakebase-db into the env that geologic.config and geologic.lakebase read, before either is imported."""
from __future__ import annotations
import os
import sys

FLAGS = {"--catalog": "GEOLOGIC_CATALOG", "--schema": "GEOLOGIC_SCHEMA", "--lakebase-db": "LAKEBASE_DB"}
SETTING = {"--catalog": "catalog", "--schema": "schema"}   # values geologic.config.settings froze at import


def _loaded(key: str) -> str | None:
    """The value the already-imported config uses for this flag, or None when config is not loaded yet."""
    cfg = sys.modules.get("geologic.config")
    if cfg is None:
        return None
    if key in SETTING:
        return getattr(cfg.settings, SETTING[key])
    return os.environ.get(FLAGS[key])   # Lakebase reads LAKEBASE_DB at connect time


def apply(argv: list[str] | None = None) -> list[str]:
    argv = sys.argv if argv is None else argv
    keep, i = argv[:1], 1
    while i < len(argv):
        key, eq, val = argv[i].partition("=")
        if key in FLAGS:
            if not eq:
                i += 1
                val = argv[i] if i < len(argv) else ""
            if not val:
                raise SystemExit(f"{key} needs a value")
            current = _loaded(key)
            if current is not None and current != val:
                raise RuntimeError(f"{key}={val} arrived after geologic.config loaded {current!r}")
            os.environ[FLAGS[key]] = val
        else:
            keep.append(argv[i])
        i += 1
    argv[:] = keep
    return keep
