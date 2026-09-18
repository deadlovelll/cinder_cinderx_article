
from pydantic import BaseModel


class BundleMeta(BaseModel):
    width: int
    considered: int
