
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Index, Integer, SmallInteger, Table, func,
)

from recsys.infrastructure.db.metadata import metadata

items = Table(
    "items",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=False),
    Column("category_id", Integer, nullable=False),
    Column("brand_id", Integer, nullable=False),
    Column("price_cents", Integer, nullable=False),
    Column("margin_bps", Integer, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("stock", Integer, nullable=False, server_default="0"),
    Column("age_restricted", Boolean, nullable=False, server_default="false"),
    Column("region_mask", SmallInteger, nullable=False, server_default="7"),
    Column("created_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
    Column("promo_multiplier_bps", Integer, nullable=False, server_default="10000"),
    Index("ix_items_category", "category_id"),
)
