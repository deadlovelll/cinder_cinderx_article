"""What the event-recording use case returns to its caller."""

from pydantic import BaseModel


class EventResponse(BaseModel):
    recorded: bool
    weight: int
