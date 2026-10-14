from functools import lru_cache

@lru_cache
def _w():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()

def get_reads():
    from backend.reads import Reads
    return Reads.instance()

def get_suggestions():
    from backend.suggestions import SuggestionRepo
    return SuggestionRepo.instance(_w())

def get_jobs():
    from backend.jobs import Jobs
    return Jobs(_w())

def get_supervisor():
    from backend.supervisor import Supervisor
    return Supervisor(_w())

_genie = None

def get_genie():
    import os
    from fastapi import HTTPException
    global _genie
    space = os.environ.get("GENIE_SPACE_ID")
    if not space:
        raise HTTPException(503, "Genie is not configured.")
    if _genie is None:
        from backend.genie import GenieService
        _genie = GenieService(_w(), space)
    return _genie
