"""The error body every failing request returns."""

from pydantic import BaseModel


class Problem(BaseModel):
    title: str
    detail: str = ""
    status: int
