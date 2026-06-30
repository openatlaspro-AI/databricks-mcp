"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend: str  # "duckdb" | "databricks"
    max_rows: int
    # Databricks (only required when backend == "databricks")
    databricks_hostname: str | None
    databricks_http_path: str | None
    databricks_token: str | None


def load_settings() -> Settings:
    return Settings(
        backend=os.getenv("DB_BACKEND", "duckdb").strip().lower(),
        max_rows=int(os.getenv("MAX_ROWS", "1000")),
        databricks_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        databricks_token=os.getenv("DATABRICKS_TOKEN"),
    )
