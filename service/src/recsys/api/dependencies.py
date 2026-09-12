"""The container, reached the FastAPI way."""

from typing import Annotated

from fastapi import Depends, Request

from recsys.api.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


#: Spelled once so the four routes do not each repeat the Depends dance.
Injected = Annotated[Container, Depends(get_container)]
