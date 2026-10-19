from typing import Annotated

from fastapi import Depends, Path, Request

from ..services.fresh import FreshService


def get_service(request: Request) -> FreshService:
    return request.app.state.service


Service = Annotated[FreshService, Depends(get_service)]
ItemId = Annotated[str, Path(min_length=1)]
