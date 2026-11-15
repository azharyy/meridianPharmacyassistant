"""Define whole catalog records and the retrieval interface."""

from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import Field

from contracts.base import Contract


class ProductRecord(Contract):
    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str
    form: str
    strength: str
    price: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    active_ingredients: str = Field(min_length=1)
    uses: str = Field(min_length=1)
    warnings: str = Field(min_length=1)
    directions: str = Field(min_length=1)
    source_set_id: str = Field(min_length=1)
    source_date: date


class PolicyRecord(Contract):
    source_id: str
    title: str
    text: str


class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[ProductRecord | PolicyRecord]: ...
