
from pydantic import BaseModel


class Problem(BaseModel):
    title: str
    detail: str = ""
    status: int
