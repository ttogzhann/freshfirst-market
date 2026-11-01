from fastapi import APIRouter, Response

from ..models import BasketInput, BasketItem, BasketPatch, BasketView
from .dependencies import Csrf, ItemId, Service

router = APIRouter(prefix="/basket", tags=["Basket"])


@router.get(
    "", response_model=BasketView, response_model_exclude_none=True, operation_id="getBasket"
)
def basket(service: Service):
    return service.get_basket()


@router.post("/items", response_model=BasketItem, operation_id="addToBasket")
def add(service: Service, data: BasketInput, csrf: Csrf):
    return service.add_basket(data)


@router.patch("/items/{id}", response_model=BasketItem, operation_id="updateBasketItem")
def update(service: Service, id: ItemId, data: BasketPatch, csrf: Csrf):
    return service.update_basket(id, data)


@router.delete("/items/{id}", status_code=204, operation_id="removeBasketItem")
def remove(service: Service, id: ItemId, csrf: Csrf):
    service.remove_basket(id)
    return Response(status_code=204)
