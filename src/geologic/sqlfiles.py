"""SQL files carry {{schema}} (catalog.schema) and {{usage_app}} tokens so one file serves every bundle target."""
from __future__ import annotations
import re


def render(text: str, *, catalog: str, schema: str) -> str:
    return text.replace("{{schema}}", f"{catalog}.{schema}").replace("{{usage_app}}", schema)


def split_statements(text: str) -> list[str]:
    out, buf, in_dollar = [], [], False
    for line in text.splitlines():
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        buf.append(line)
        if not in_dollar and not line.lstrip().startswith("--") and line.rstrip().endswith(";"):
            out.append("\n".join(buf).rstrip().rstrip(";").rstrip())
            buf = []
    if "\n".join(buf).strip():
        out.append("\n".join(buf).strip())
    code = lambda s: re.sub(r"(?m)^\s*--.*$", "", s).strip()
    lead = re.compile(r"\A(?:\s*--[^\n]*\n)+")   # comment lines before a statement are dropped
    return [lead.sub("", s).strip() for s in out if code(s)]


def run_file(path: str, run, *, catalog: str, schema: str) -> int:
    with open(path) as f:
        stmts = split_statements(render(f.read(), catalog=catalog, schema=schema))
    for s in stmts:
        run(s)
    return len(stmts)
