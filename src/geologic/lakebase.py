"""Lakebase connections with a fresh OAuth token per connection (tokens expire after about an hour)."""
from __future__ import annotations
import os
import time
import uuid

class TokenCache:
    def __init__(self, mint, ttl_s: int = 1800, clock=time.time):
        self._mint, self._ttl, self._clock, self._tok, self._at = mint, ttl_s, clock, None, -1e18

    def get(self) -> str:
        if self._tok is None or self._clock() - self._at > self._ttl:
            self._tok, self._at = self._mint(), self._clock()
        return self._tok

def connect(host, db, user, token: TokenCache):
    import psycopg
    return psycopg.connect(host=host, dbname=db, user=user, password=token.get(), sslmode="require")

def from_env(w):
    host, db, user = os.environ["LAKEBASE_HOST"], os.environ.get("LAKEBASE_DB", "geologic"), os.environ["LAKEBASE_USER"]
    instance = os.environ["LAKEBASE_INSTANCE"]
    tok = TokenCache(lambda: w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[instance]).token)
    return lambda: connect(host, db, user, tok)


LAKEBASE_DEFAULTS = {
    "LAKEBASE_HOST": "ep-withered-butterfly-d1czv7t3.database.us-west-2.cloud.databricks.com",
    "LAKEBASE_DB": "geologic",
    "LAKEBASE_INSTANCE": "geologic",
}

def apply_job_defaults(w):
    """Fills LAKEBASE_* for jobs that run as a user: host/db/instance from defaults, user = the run-as identity.
    Existing env values win. No secrets here; tokens are minted at connect time."""
    for k, v in LAKEBASE_DEFAULTS.items():
        os.environ.setdefault(k, v)
    if "LAKEBASE_USER" not in os.environ:
        os.environ["LAKEBASE_USER"] = w.current_user.me().user_name
