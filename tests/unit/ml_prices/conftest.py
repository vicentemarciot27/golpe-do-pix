#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ML Prices unit test fixtures.
Contains ml_prices-specific fixtures for unit testing.
"""

from typing import List

import pytest

from config.ml_prices.settings import MLPricesSettings


# =========================
# SETTINGS
# =========================

@pytest.fixture
def ml_prices_settings() -> MLPricesSettings:
    """
    Provides ML Prices settings for unit tests.
    Uses fast, predictable values for unit testing.
    """
    return MLPricesSettings(
        pages_to_scrape=1,
        headless=True,
        page_load_timeout=10,
        explicit_wait=5,
    )


# =========================
# TEST DATA FIXTURES
# =========================

@pytest.fixture
def sample_search_terms() -> List[str]:
    """
    Provides a list of sample search terms for testing.
    """
    return [
        "smartphone",
        "notebook",
        "mouse gamer",
    ]


@pytest.fixture
def ml_base_url() -> str:
    """Provides the base URL for Mercado Livre Brazil."""
    return "https://www.mercadolivre.com.br"


@pytest.fixture
def ml_search_url() -> str:
    """Provides the search URL pattern for Mercado Livre Brazil."""
    return "https://lista.mercadolivre.com.br/{search_term}"

