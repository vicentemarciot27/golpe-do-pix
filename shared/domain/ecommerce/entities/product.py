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
    max_installments: int | None # More pythonic, you could do this with Optional[int]
    is_free_shipping: bool 
    rating: int | None # the extracted rating is generally null since it's not always available
    rating_amount: int | None # the extracted amount is generally null since it's not always available
    sold_amount: int | None # the extracted amount is generally null since it's not always available
    # metadata
    extraction_date: datetime
    version: int = 1
