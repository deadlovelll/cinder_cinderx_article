"""The co-visitation graph in CSR order, so the startup load is a sequential scan."""

from sqlalchemy import BigInteger, Column, Index, Integer, Table

from recsys.infrastructure.db.metadata import metadata

covisitation = Table(
    "covisitation",
    metadata,
    Column("src", BigInteger, primary_key=True, autoincrement=False),
    Column("dst", BigInteger, primary_key=True, autoincrement=False),
    Column("weight", Integer, nullable=False),
    Index("ix_covis_src", "src"),
)
