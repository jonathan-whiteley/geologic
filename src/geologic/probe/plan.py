"""Probe planning helpers: chunking, epoch guard and the run health gate."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass

MAX_NOT_OK = 0.10   # a run is degraded when more than 10% of its answers are not ok


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


@dataclass(frozen=True)
class RunHealth:
    healthy: bool
    total: int
    not_ok: int
    dead_engines: tuple            # engines with zero ok answers, in expected order then first seen
    counts: dict                   # (engine, status) -> rows

    def summary(self) -> str:
        engines = list(dict.fromkeys(e for e, _ in self.counts))
        by = {e: ", ".join(f"{s}={n}" for (e2, s), n in sorted(self.counts.items()) if e2 == e) for e in engines}
        return "; ".join(f"{e}: {by[e]}" for e in engines) or "no answers"


def run_health(answers: list[dict], engines=()) -> RunHealth:
    """Unhealthy when not-ok rows exceed MAX_NOT_OK of all rows, or any engine (expected or seen) has zero ok rows.
    A degraded run must not become the baseline or the latest run."""
    counts = Counter((a["engine"], a["status"]) for a in answers)
    total, not_ok = len(answers), sum(a["status"] != "ok" for a in answers)
    names = list(dict.fromkeys([*engines, *(a["engine"] for a in answers)]))
    dead = tuple(e for e in names if counts[(e, "ok")] == 0)
    healthy = not dead and not_ok <= MAX_NOT_OK * total
    return RunHealth(healthy, total, not_ok, dead, dict(counts))
