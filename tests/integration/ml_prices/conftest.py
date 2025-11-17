#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ML Prices integration test fixtures.
Contains ml_prices-specific fixtures for integration testing.
"""

from typing import List

import pytest

from config.ml_prices.settings import MLPricesSettings, get_settings
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper


# =========================
# SETTINGS
# =========================

@pytest.fixture(scope="session")
def ml_prices_settings() -> MLPricesSettings:
    """
    Provides ML Prices settings for integration tests.
    
    Priority:
    1. config/.env.test (if exists)
    2. Environment variables with ML_PRICES_ prefix
    3. Default test values
    """
    try:
        return get_settings("config/.env.test")
    except Exception:
        # Fall back to test defaults
        return MLPricesSettings(
            pages_to_scrape=1,
            headless=False,
            page_load_timeout=30,
            explicit_wait=15,
        )


# =========================
# SCRAPER FIXTURES
# =========================

@pytest.fixture
def ml_scraper(ml_prices_settings: MLPricesSettings) -> MercadoLivreScraper:
    """
    Provides a MercadoLivreScraper instance configured for integration testing.
    """
    return MercadoLivreScraper(ml_prices_settings)


# =========================
# TEST DATA FIXTURES
# =========================

@pytest.fixture
def sample_search_terms() -> List[str]:
    """
    Provides a list of sample search terms for testing.
    Useful for parameterized integration tests.
    """
    return [
        "smartphone",
        "notebook",
        "mouse gamer",
        "teclado mecânico",
        "headset",
        "monitor",
        "webcam",
        "ssd 1tb",
    ]


@pytest.fixture
def ml_base_url() -> str:
    """Provides the base URL for Mercado Livre Brazil."""
    return "https://www.mercadolivre.com.br"


@pytest.fixture
def ml_search_url() -> str:
    """Provides the search URL pattern for Mercado Livre Brazil."""
    return "https://lista.mercadolivre.com.br/{search_term}"

