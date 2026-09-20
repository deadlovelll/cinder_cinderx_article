
from pydantic import BaseModel


class RecommendMeta(BaseModel):
    candidates_considered: int
    dropped_by_rule: dict[str, int]
    backfilled: int
    kernel: str
