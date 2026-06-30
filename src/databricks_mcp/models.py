"""Pydantic response models — these define the agent-facing tool schemas."""

from __future__ import annotations

from pydantic import BaseModel


class TableInfo(BaseModel):
    name: str
    column_count: int


class ColumnInfo(BaseModel):
    name: str
    type: str


class TableSchema(BaseModel):
    table: str
    columns: list[ColumnInfo]
    row_count: int


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool


class ColumnProfile(BaseModel):
    column: str
    null_fraction: float
    distinct_count: int
    min: str | None
    max: str | None
