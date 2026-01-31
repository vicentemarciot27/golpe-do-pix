from dataclasses import dataclass

@dataclass
class Item:
  id: str
  name: str
  ncm: str
  ml_price_avg: float | None = None