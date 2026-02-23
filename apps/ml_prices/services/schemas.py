"""Pydantic schemas for structured LLM outputs."""

from typing import Any

from pydantic import BaseModel, Field


class ExtractedProductInfo(BaseModel):
    """Structured product information extracted from freetext."""
    name: str = Field(description="Product name/type (e.g., 'Smartphone', 'Notebook')")
    brand: str | None = Field(default=None, description="Product brand (e.g., 'Apple', 'Samsung')")
    model: str | None = Field(default=None, description="Product model (e.g., 'iPhone 15', 'Galaxy S24')")
    color: str | None = Field(default=None, description="Product color if mentioned")
    other: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional relevant attributes (storage, RAM, connectivity, etc.)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for the extraction (0-1)"
    )


class SearchKeyResult(BaseModel):
    """Optimized search key for Mercado Livre."""
    search_key: str = Field(description="Optimized search query for Mercado Livre")
    reasoning: str = Field(description="Brief explanation of the search key choice")
    alternative_keys: list[str] = Field(
        default_factory=list,
        description="Alternative search keys if the main one fails"
    )


class ProductRelevanceResult(BaseModel):
    """Result of product relevance analysis."""
    is_relevant: bool = Field(description="Whether the product matches the base product")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the relevance assessment")
    reasoning: str = Field(description="Brief explanation of why the product is/isn't relevant")
    price_category: str = Field(
        default="normal",
        description="Price category: 'normal', 'premium', 'budget', 'suspicious'"
    )


class BatchRelevanceResult(BaseModel):
    """Results of batch relevance analysis."""
    relevant_indices: list[int] = Field(
        description="Indices of products considered relevant (0-based)"
    )
    suggested_new_key: str | None = Field(
        default=None,
        description="Suggested new search key if too few relevant results found"
    )
    summary: str = Field(description="Brief summary of the analysis")
