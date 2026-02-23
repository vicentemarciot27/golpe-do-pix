from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BaseProduct:
    """
    Represents a canonical/base product for price comparison across platforms.

    A BaseProduct is used to match auction items and ecommerce products
    to enable price analysis and max bid calculation.

    The 'other' field stores product-specific attributes that vary by category:
    - Electronics: storage, connectivity, processor, RAM
    - Vehicles: year, mileage, engine
    - Clothing: size, material
    """
    name: str
    brand: str | None
    model: str | None
    color: str | None
    other: dict[str, Any] = field(default_factory=dict)

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_search_signature(self) -> str:
        """
        Generate a normalized signature for matching similar products.
        Used for deduplication and search matching.

        Includes: brand, name, model, color, and all 'other' attributes.
        Example: "samsung smartphone galaxy s24 ultra preto 256gb 12gb"
        """
        parts = []

        if self.brand:
            parts.append(self.brand.lower().strip())

        parts.append(self.name.lower().strip())

        if self.model:
            parts.append(self.model.lower().strip())

        if self.color:
            parts.append(self.color.lower().strip())

        # Add all 'other' attributes (storage, ram, etc.)
        if self.other:
            for key in sorted(self.other.keys()):
                value = self.other[key]
                if value:
                    parts.append(str(value).lower().strip())

        return " ".join(parts)

    def matches(self, other: "BaseProduct", strict: bool = False) -> bool:
        """
        Check if two base products represent the same item.

        Args:
            other: Another BaseProduct to compare
            strict: If True, color and 'other' attributes must also match
        """
        name_match = self.name.lower().strip() == other.name.lower().strip()
        brand_match = (
            (self.brand is None and other.brand is None) or
            (self.brand and other.brand and
             self.brand.lower().strip() == other.brand.lower().strip())
        )
        model_match = (
            (self.model is None and other.model is None) or
            (self.model and other.model and
             self.model.lower().strip() == other.model.lower().strip())
        )

        basic_match = name_match and brand_match and model_match

        if not strict:
            return basic_match

        color_match = (
            (self.color is None and other.color is None) or
            (self.color and other.color and
             self.color.lower().strip() == other.color.lower().strip())
        )

        return basic_match and color_match
