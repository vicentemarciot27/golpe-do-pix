from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class Currency(Enum):
  BRL = "BRL"
  USD = "USD"
  EUR = "EUR"
  GBP = "GBP"
  JPY = "JPY"
  KRW = "KRW"
  CNY = "CNY"
  INR = "INR"
  MXN = "MXN"

@dataclass
class Product:
    id: str
    title: str
    url: str
    price: float
    currency: Currency
    is_installment_payment_available: bool
    max_installments: int | None
    is_free_shipping: bool
    rating: int | None
    rating_amount: int | None
    sold_amount: int | None
    extraction_date: datetime
    # v2 fields for price analysis
    base_product_id: int | None = None
    search_key: str | None = None
    is_relevant: bool | None = None
    version: int = 1
