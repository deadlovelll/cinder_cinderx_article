
from pydantic import BaseModel


class SimilarMeta(BaseModel):
    candidates_considered: int
    dropped_by_rule: dict[str, int]
    implementation: str
