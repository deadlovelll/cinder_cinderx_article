
from sqlalchemy import BigInteger, Column, SmallInteger, String, Table

from recsys.infrastructure.db.metadata import metadata

pins = Table(
    "pins",
    metadata,
    Column("segment", String(16), primary_key=True),
    Column("slot", SmallInteger, primary_key=True),
    Column("item_id", BigInteger, nullable=False),
)
