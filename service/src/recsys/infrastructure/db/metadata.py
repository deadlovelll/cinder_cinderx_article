"""The shared MetaData every table registers into."""

from sqlalchemy import MetaData

metadata = MetaData()

#: Availability is a bitmask on the read path: the set is small and fixed.
REGION_BITS = {"eu": 1, "us": 2, "apac": 4}
