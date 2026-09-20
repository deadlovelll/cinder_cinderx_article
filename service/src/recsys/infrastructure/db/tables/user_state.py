
from sqlalchemy import BigInteger, Column, DateTime, String, Table, func

from recsys.infrastructure.db.metadata import metadata

user_state = Table(
    "user_state",
    metadata,
    Column("user_id", BigInteger, primary_key=True, autoincrement=False),
    Column("recent_items", String, nullable=False, server_default=""),
    Column("purchased_items", String, nullable=False, server_default=""),
    Column("disliked_items", String, nullable=False, server_default=""),
    Column("updated_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
)
