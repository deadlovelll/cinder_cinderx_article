
from typing import Annotated

from fastapi import Depends, Request

from recsys.api.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


Injected = Annotated[Container, Depends(get_container)]
