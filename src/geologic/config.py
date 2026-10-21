"""Names for every Databricks object GEOlogic touches. Override with GEOLOGIC_* env vars."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field

# Verified READY on fe-vm-jdub-vm-serverless (2026-10-13).
DEFAULT_ENGINES = {
    "Claude": "databricks-claude-sonnet-5-5",
    "ChatGPT": "databricks-gpt-5-5",
    "Gemini": "databricks-gemini-3-8-flash",
    "Meta AI": "databricks-llama-4-maverick",
}


@dataclass(frozen=True)
class Settings:
    catalog: str = "jdub_demo"
    schema: str = "geologic"
    engines: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ENGINES))
    judge_endpoint: str = "databricks-claude-sonnet-4-6"
    vision_endpoint: str = "databricks-claude-sonnet-4-6"
    embedding_endpoint: str = "databricks-gte-large-en"
    strategist_endpoint: str = "geologic-content-strategist"
    vs_endpoint: str = "geologic-vs"
    match_threshold: float = 0.80     # Vector Search score for moment and search matches
    reask_fallback_s: int = 90        # re-ask wait before a rehearsed result may be shown
    embedding_dim: int = 1024         # databricks-gte-large-en

    @classmethod
    def from_env(cls) -> "Settings":
        kw = {}
        for f in ("catalog", "schema", "judge_endpoint", "vision_endpoint",
                  "embedding_endpoint", "strategist_endpoint", "vs_endpoint"):
            v = os.environ.get(f"GEOLOGIC_{f.upper()}")
            if v:
                kw[f] = v
        if os.environ.get("GEOLOGIC_MATCH_THRESHOLD"):
            kw["match_threshold"] = float(os.environ["GEOLOGIC_MATCH_THRESHOLD"])
        if os.environ.get("GEOLOGIC_REASK_FALLBACK_S"):
            kw["reask_fallback_s"] = int(os.environ["GEOLOGIC_REASK_FALLBACK_S"])
        if os.environ.get("GEOLOGIC_ENGINES"):
            kw["engines"] = json.loads(os.environ["GEOLOGIC_ENGINES"])
        return cls(**kw)

    def fq(self, name: str) -> str:
        return f"{self.catalog}.{self.schema}.{name}"

    @property
    def corpus_index(self) -> str:
        return self.fq("web_corpus_idx")

    @property
    def menu_index(self) -> str:
        return self.fq("menu_idx")

    @property
    def sources_index(self) -> str:
        return self.fq("sources_idx")

    @property
    def prompt_index(self) -> str:
        return self.fq("prompt_idx")

    @property
    def usage_app(self) -> str:
        """AI Gateway usage_context app tag (sql/gateway_views.sql filters on it)."""
        return self.schema

    @property
    def experiment(self) -> str:
        return "/Shared/" + self.schema.replace("_", "-") + "-drafting"

    @property
    def volume_path(self) -> str:
        return f"/Volumes/{self.catalog}/{self.schema}/assets"


settings = Settings.from_env()
