"""The write path of /events, and the source the graph is built from offline."""

from sqlalchemy import (
    BigInteger, Column, DateTime, Index, SmallInteger, String, Table, func,
)

from recsys.infrastructure.db.metadata import metadata

interactions = Table(
    "interactions",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", BigInteger, nullable=False),
    Column("item_id", BigInteger, nullable=False),
    Column("kind", String(16), nullable=False),  # view | cart | purchase | dislike
    Column("weight", SmallInteger, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
    Index("ix_interactions_user_created", "user_id", "created_at"),
)
