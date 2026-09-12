"""Quantised embeddings, values packed so the startup load does not build 10^5"""

from sqlalchemy import BigInteger, Column, Integer, SmallInteger, String, Table

from recsys.infrastructure.db.metadata import metadata

item_embeddings = Table(
    "item_embeddings",
    metadata,
    Column("item_id", BigInteger, primary_key=True, autoincrement=False),
    Column("dim", SmallInteger, nullable=False),
    Column("vec", String, nullable=False),   # base64 of int8 values
    Column("norm", Integer, nullable=False),
)
