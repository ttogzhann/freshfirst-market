from fastapi import APIRouter, Response

from ..models import (
    ShoppingGenerationInput,
    ShoppingInput,
    ShoppingItem,
    ShoppingPatch,
    TransferInput,
)
from .dependencies import Csrf, ItemId, Service

router = APIRouter(prefix="/shopping-list", tags=["Shopping"])
DEFAULT_GENERATION = ShoppingGenerationInput()


@router.get("", response_model=list[ShoppingItem], operation_id="getShoppingList")
def shopping(service: Service):
    return service.get_shopping()


@router.post("/generate", response_model=list[ShoppingItem], operation_id="generateShoppingList")
def generate(service: Service, csrf: Csrf, data: ShoppingGenerationInput = DEFAULT_GENERATION):
    return service.generate_shopping(data)


@router.post("/items", response_model=ShoppingItem, status_code=201, operation_id="addShoppingItem")
def add(service: Service, data: ShoppingInput, csrf: Csrf):
    return service.add_shopping(data)


@router.patch("/items/{id}", response_model=ShoppingItem, operation_id="updateShoppingItem")
def update(service: Service, id: ItemId, data: ShoppingPatch, csrf: Csrf):
    return service.update_shopping(id, data)


@router.delete("/items/{id}", status_code=204, operation_id="removeShoppingItem")
def remove(service: Service, id: ItemId, csrf: Csrf):
    service.remove_shopping(id)
    return Response(status_code=204)


@router.post(
    "/items/{id}/transfer-to-pantry", response_model=ShoppingItem, operation_id="transferToPantry"
)
def transfer(service: Service, id: ItemId, data: TransferInput, csrf: Csrf):
    return service.transfer(id, data)
