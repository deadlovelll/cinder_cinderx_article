"""Backfill source."""

from sqlalchemy import BigInteger, Column, Index, Integer, Table

from recsys.infrastructure.db.metadata import metadata

popularity = Table(
    "popularity",
    metadata,
    Column("item_id", BigInteger, primary_key=True, autoincrement=False),
    Column("score", Integer, nullable=False),
    Index("ix_popularity_score", "score"),
)
