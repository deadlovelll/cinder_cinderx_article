"""Impression counters inside the dedup window."""

from sqlalchemy import BigInteger, Column, DateTime, Integer, Table, func

from recsys.infrastructure.db.metadata import metadata

impressions = Table(
    "impressions",
    metadata,
    Column("user_id", BigInteger, primary_key=True, autoincrement=False),
    Column("item_id", BigInteger, primary_key=True, autoincrement=False),
    Column("shown", Integer, nullable=False, server_default="0"),
    Column("last_shown_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
)
