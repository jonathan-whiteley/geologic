"""Section-level patches on markdown pages. A section starts at a '## ' heading; its id is the heading slug.
Text before the first heading is the section 'intro'."""
from __future__ import annotations
import re

_H = re.compile(r"(?m)^## +(.+)$")


def slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def sections(body: str) -> list[tuple[str, str]]:
    body = body or ""
    marks = list(_H.finditer(body))
    out = []
    head = body[: marks[0].start()] if marks else body
    if head.strip():
        out.append(("intro", head.strip("\n")))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((slug(m.group(1)), body[m.start():end].strip("\n")))
    return out


def get_section(body, section_id):
    return next((t for s, t in sections(body) if s == section_id), "")


def last_section_id(body):
    secs = sections(body)
    return secs[-1][0] if secs else None


def section_containing(body, needle):
    return next((s for s, t in sections(body) if needle and needle in t), None)


def apply_patch(body, patch):
    secs, text = sections(body), patch["text"].strip("\n")
    ids = [s for s, _ in secs]
    if patch["op"] == "replace" and patch["section_id"] in ids:
        secs = [(s, text if s == patch["section_id"] else t) for s, t in secs]
    elif patch["op"] == "insert" and patch["section_id"] in ids:
        secs.insert(ids.index(patch["section_id"]) + 1, ("new", text))
    else:
        secs.append(("new", text))
    return "\n\n".join(t for _, t in secs).strip("\n") + "\n"
