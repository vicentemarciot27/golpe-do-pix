# Test Architecture

This document describes the test architecture for the `golpe-do-pix` project.

## Directory Structure

```
tests/
├── conftest.py                          # Root-level, app-agnostic fixtures
├── results/                             # Test results storage (JSON files)
├── integration/
│   ├── conftest.py                      # Integration-level fixtures (optional)
│   ├── ml_prices/
│   │   ├── conftest.py                  # ML Prices integration fixtures
│   │   └── scrapers/
│   │       └── test_playwright.py
│   ├── max_bid/
│   │   ├── conftest.py                  # Max Bid integration fixtures
│   │   └── ...
│   └── {other_apps}/
│       ├── conftest.py
│       └── ...
└── unit/
    ├── conftest.py                      # Unit-level fixtures (optional)
    ├── ml_prices/
    │   ├── conftest.py                  # ML Prices unit fixtures
    │   └── ...
    ├── max_bid/
    │   ├── conftest.py                  # Max Bid unit fixtures
    │   └── ...
    └── {other_apps}/
        ├── conftest.py
        └── ...
```

## Architecture Principles

### 1. Separation of Concerns

- **Root `conftest.py`**: Infrastructure fixtures (Playwright, browser, results storage)
- **App-specific `conftest.py`**: App settings, scrapers, test data

### 2. Fixture Scoping

```python
# Root fixtures (tests/conftest.py)
- playwright_instance (session)   # Shared across all tests
- browser (session)                # Shared across all tests
- browser_context (function)       # New for each test
- browser_page (function)          # New for each test
- results (function)               # Results storage

# App fixtures (tests/{type}/{app}/conftest.py)
- {app}_settings (session/function)  # App-specific settings
- {app}_scraper (function)           # App-specific components
- sample_data (function)             # App-specific test data
```

### 3. Settings Management

Following the same pattern as `config/`:

```python
# Integration tests (slower, real scenarios)
@pytest.fixture(scope="session")
def ml_prices_settings() -> MLPricesSettings:
    try:
        return get_settings("config/.env.test")  # Priority 1: .env.test
    except Exception:
        return MLPricesSettings(                  # Priority 2: Defaults
            pages_to_scrape=1,
            headless=False,
        )

# Unit tests (fast, predictable)
@pytest.fixture
def ml_prices_settings() -> MLPricesSettings:
    return MLPricesSettings(
        pages_to_scrape=1,
        headless=True,
        page_load_timeout=10,
    )
```

## Adding a New App

When adding a new app (e.g., `rfb_auction_lots`):

### 1. Create Settings

```python
# config/rfb_auction_lots/settings.py
class RFBAuctionLotsSettings(BaseSettings):
    api_timeout: int = Field(default=30)
    max_retries: int = Field(default=3)
    
    class Config:
        env_prefix = "RFB_AUCTION_LOTS_"
```

### 2. Create Test Directories

```bash
mkdir -p tests/integration/rfb_auction_lots
mkdir -p tests/unit/rfb_auction_lots
touch tests/integration/rfb_auction_lots/__init__.py
touch tests/unit/rfb_auction_lots/__init__.py
```

### 3. Create Integration Fixtures

```python
# tests/integration/rfb_auction_lots/conftest.py
import pytest
from config.rfb_auction_lots.settings import RFBAuctionLotsSettings, get_settings

@pytest.fixture(scope="session")
def rfb_settings() -> RFBAuctionLotsSettings:
    try:
        return get_settings("config/.env.test")
    except Exception:
        return RFBAuctionLotsSettings(
            api_timeout=15,
            max_retries=2,
        )

@pytest.fixture
def sample_auction_ids() -> list:
    return ["12345", "67890"]
```

### 4. Create Unit Fixtures

```python
# tests/unit/rfb_auction_lots/conftest.py
import pytest
from config.rfb_auction_lots.settings import RFBAuctionLotsSettings

@pytest.fixture
def rfb_settings() -> RFBAuctionLotsSettings:
    return RFBAuctionLotsSettings(
        api_timeout=5,
        max_retries=1,
    )
```

## Test Markers

Tests are automatically marked based on location:

- `tests/integration/*` → `@pytest.mark.integration`, `@pytest.mark.requires_network`, `@pytest.mark.slow`
- `tests/unit/*` → `@pytest.mark.unit`

### Running Tests

```bash
# All tests
pytest

# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Specific app
pytest tests/integration/ml_prices/
pytest tests/unit/ml_prices/

# With results storage
pytest tests/integration/ml_prices/ -v
# Results saved to: tests/results/
```

## Environment Variables

### Root Level (Infrastructure)

- `PLAYWRIGHT_HEADLESS`: Control browser visibility (default: `true`)

### App Level (Via Settings)

Each app uses its own prefix (e.g., `ML_PRICES_`, `MAX_BID_`):

```bash
# Example: .env.test
ML_PRICES_HEADLESS=false
ML_PRICES_PAGES_TO_SCRAPE=1
ML_PRICES_PAGE_LOAD_TIMEOUT=30

MAX_BID_API_TIMEOUT=15
MAX_BID_MAX_RETRIES=3
```

## Fixture Resolution Order

Pytest loads fixtures in this order:

1. `tests/conftest.py` (root)
2. `tests/{integration|unit}/conftest.py` (optional)
3. `tests/{integration|unit}/{app}/conftest.py` (app-specific)
4. Test file itself

Fixtures in lower levels can override fixtures from higher levels (same name).

## Best Practices

1. **Keep root `conftest.py` app-agnostic**: Only infrastructure fixtures
2. **Use consistent naming**: `{app}_settings`, `{app}_scraper`, `{app}_client`
3. **Integration vs Unit**:
   - Integration: Real scenarios, slower, network access
   - Unit: Fast, isolated, mocked dependencies
4. **Settings priority**: `.env.test` > env vars > code defaults
5. **Results storage**: Use `results` fixture to save test data for debugging

## Migration Guide

When migrating existing tests:

1. Move app-specific fixtures to `tests/{type}/{app}/conftest.py`
2. Update fixture names to avoid conflicts (e.g., `test_settings` → `ml_prices_settings`)
3. Update test imports if needed
4. Verify tests still pass: `pytest tests/`

## Examples

### Integration Test

```python
# tests/integration/ml_prices/scrapers/test_search.py
def test_search_products(ml_scraper, results):
    products = ml_scraper.search("smartphone", max_pages=1)
    
    results.store("test_search_products", {
        "products": products,
        "count": len(products)
    })
    
    assert len(products) > 0
```

### Unit Test

```python
# tests/unit/ml_prices/scrapers/test_parser.py
def test_parse_price(ml_prices_settings):
    parser = PriceParser(ml_prices_settings)
    result = parser.parse("R$ 1.234,56")
    
    assert result == 1234.56
```

## Troubleshooting

### Fixture Not Found

- Check fixture name matches between conftest and test
- Verify conftest.py is in correct location
- Ensure `__init__.py` exists in all test directories

### Settings Not Loading

- Check `.env.test` file location (`config/.env.test`)
- Verify environment variable prefix matches settings class
- Check `Config.env_prefix` in settings class

### Browser Issues

- Set `PLAYWRIGHT_HEADLESS=false` to see browser
- Check browser launch args in root `conftest.py`
- Verify Playwright installation: `playwright install chromium`
