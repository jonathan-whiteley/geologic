import time
from datetime import datetime, timezone
from functools import lru_cache


@lru_cache
def _w():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def get_reads():
    from backend.reads import Reads
    return Reads.instance()


@lru_cache
def get_fix_repo():
    from backend.fixes import FixRepo
    from geologic.lakebase import from_env
    return FixRepo(from_env(_w()))


def get_store(trigger="approve"):
    from backend.warehouse_store import WarehouseStore
    return WarehouseStore(get_fix_repo(), _w(), trigger=trigger)


def get_clock():
    return lambda: datetime.now(timezone.utc)


@lru_cache
def get_publisher():
    from backend.fastpath import FastPublisher
    reads = get_reads()
    return FastPublisher(get_fix_repo(), store_factory=get_store, rules_fn=reads.rules, focus_fn=reads.focus, clock=get_clock())


@lru_cache
def _embedder():
    from geologic.clients import Embedder
    from geologic.config import settings as S
    return Embedder.from_workspace(_w(), S.embedding_endpoint)


@lru_cache
def _prompt_index():
    from geologic.clients import PromptIndex
    from geologic.config import settings as S
    return PromptIndex(_w(), S.prompt_index, _embedder())


@lru_cache
def get_search():
    from backend.search import Search
    from geologic.config import settings as S
    return Search(_prompt_index(), S.match_threshold, get_reads().scorecard)


def _write_prompt_vector(row, delete=None):
    """Embeds and upserts a newly tracked prompt into prompt_idx; deletes the suggestion vector it replaces."""
    from geologic import vectors as V
    from geologic.config import settings as S
    V.upsert(_w(), S.prompt_index, V.prompt_rows([row], [], _embedder().embed))
    if delete:
        V.delete(_w(), S.prompt_index, [delete])


@lru_cache
def get_tracker():
    from backend.search import Tracker
    return Tracker(get_reads(), lambda: get_store("track"), _write_prompt_vector, time.monotonic,
                   nearest=lambda text: (_prompt_index().nearest(text, 1) or [None])[0])


def get_chat():
    from geologic.clients import FmapiChat
    return FmapiChat.from_workspace(_w())


def get_jobs():
    from backend.jobs import Jobs
    return Jobs(_w())


_genie = None


def get_genie():
    import os
    from fastapi import HTTPException
    global _genie
    space = os.environ.get("GENIE_SPACE_ID", "")
    if space in ("", "none"):   # the v3 target ships "none" until its Genie space exists
        raise HTTPException(503, "Genie is not configured.")
    if _genie is None:
        from backend.genie import GenieService
        _genie = GenieService(_w(), space)
    return _genie
