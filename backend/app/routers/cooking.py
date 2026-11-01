from fastapi import APIRouter

from ..models import CookingRecord, CookPreview, CookRequest
from .dependencies import Csrf, Service

router = APIRouter(prefix="/cooking", tags=["Cooking"])


@router.post(
    "/preview",
    response_model=CookPreview,
    response_model_exclude_none=True,
    operation_id="previewCook",
)
def preview(service: Service, data: CookRequest):
    return service.preview_cook(data)


@router.post("/confirm", response_model=CookingRecord, status_code=201, operation_id="confirmCook")
def confirm(service: Service, data: CookRequest, csrf: Csrf):
    return service.confirm_cook(data)


@router.get("/history", response_model=list[CookingRecord], operation_id="listHistory")
def history(service: Service):
    return service.list_history()
