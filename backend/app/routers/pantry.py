from fastapi import APIRouter, Response

from ..models import PantryInput, PantryItem
from .dependencies import Csrf, ItemId, Service

router = APIRouter(prefix="/pantry", tags=["Pantry"])


@router.get("", response_model=list[PantryItem], operation_id="listPantry")
def list_pantry(service: Service):
    return service.list_pantry()


@router.post("", response_model=PantryItem, operation_id="createPantryItem")
def create(service: Service, data: PantryInput, csrf: Csrf):
    return service.create_pantry(data)


@router.put("/{id}", response_model=PantryItem, operation_id="updatePantryItem")
def update(service: Service, id: ItemId, data: PantryInput, csrf: Csrf):
    return service.update_pantry(id, data)


@router.delete("/{id}", status_code=204, operation_id="deletePantryItem")
def delete(service: Service, id: ItemId, csrf: Csrf):
    service.delete_pantry(id)
    return Response(status_code=204)
