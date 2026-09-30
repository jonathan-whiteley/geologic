"""SQL warehouse access, same approach as StoreSight config/database.py."""
import os
from databricks import sql
from databricks.sdk.core import Config
from backend.rows import plain

_cfg = Config()


def query(statement: str, params: dict | None = None) -> list[dict]:
    with sql.connect(server_hostname=_cfg.host, http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
                     credentials_provider=lambda: _cfg.authenticate) as conn, conn.cursor() as cur:
        cur.execute(statement, params or {})
        if cur.description is None:   # INSERT / UPDATE
            return []
        cols = [d[0] for d in cur.description]
        return [{c: plain(v) for c, v in zip(cols, r)} for r in cur.fetchall()]
