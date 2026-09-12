"""Users."""

from sqlalchemy import BigInteger, Column, Integer, SmallInteger, String, Table

from recsys.infrastructure.db.metadata import metadata

users = Table(
    "users",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=False),
    Column("segment", String(16), nullable=False),
    Column("region", String(8), nullable=False),
    Column("age", SmallInteger, nullable=False),
    Column("median_basket_cents", Integer, nullable=False, server_default="0"),
)
