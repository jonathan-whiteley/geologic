"""Probe planning helpers: chunking and epoch guard."""
from __future__ import annotations


def chunk(items: list, n: int) -> list[list]:
    """Split items into n roughly equal parts, largest chunks first."""
    if not items:
        return []
    n = max(1, min(n, len(items)))
    size, extra = divmod(len(items), n)
    out, i = [], 0
    for k in range(n):
        j = i + size + (1 if k < extra else 0)
        out.append(items[i:j])
        i = j
    return out


def is_current(run_epoch: int, current_epoch: int) -> bool:
    """Return True if the run was started in the current epoch."""
    return run_epoch == current_epoch
