
from pydantic import BaseModel


class EventResponse(BaseModel):
    recorded: bool
    weight: int
