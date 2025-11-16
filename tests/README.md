# Tests

Test suite for Golpe do Pix project following pytest conventions.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (fast, isolated)
│   └── ml_prices/
│       └── scrapers/
│           └── playwright.py
└── integration/             # Integration tests (slower, real dependencies)
    └── ml_prices/
        └── scrapers/
            └── playwright.py
```

## Test Organization Rules

- Test folder structure mirrors `apps/` up to the first subdirectory level
- **Maximum nesting**: `tests/unit/ml_prices/scrapers/` ✅
- **Not allowed**: `tests/unit/ml_prices/scrapers/offers/` ❌

## Running Tests

### Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### Run all tests

```bash
pytest
```

### Run only unit tests (fast)

```bash
pytest -m unit
```

### Run only integration tests

```bash
pytest -m integration
```

### Run tests with coverage

```bash
pytest --cov=apps --cov-report=html
```

### Run specific test file

```bash
pytest tests/unit/ml_prices/scrapers/playwright.py
```

### Run specific test

```bash
pytest tests/unit/ml_prices/scrapers/playwright.py::TestProdutoDataclass::test_produto_default_values
```

## Test Markers

Tests are automatically marked based on their location:

- `@pytest.mark.unit` - Unit tests (fast, no external dependencies)
- `@pytest.mark.integration` - Integration tests (slower, real dependencies)
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.requires_network` - Tests requiring internet connection

### Skip slow tests

```bash
pytest -m "not slow"
```

### Skip tests requiring network

```bash
pytest -m "not requires_network"
```

## Results Storage

The `results` fixture saves test data as JSON files for easy validation and debugging.

### Using results in tests

```python
def test_scrape_products(results):
    produtos = scrape_mercadolivre("smartphone", max_pages=1, headless=True)
    
    # Store results as JSON file
    results.store("test_scrape_products", {
        "produtos": produtos,
        "count": len(produtos),
        "search_term": "smartphone",
    })
    
    assert len(produtos) > 0
```

### Viewing results after tests

**Option 1: Interactive viewer (recommended)**

```bash
# Run tests first
pytest

# View results interactively
python view_test_results.py
```

**Option 2: Direct JSON access**

```bash
# Results are saved in tests/results/
ls tests/results/

# View a specific result
cat tests/results/test_scrape_products_20250116_143022.json

# Or use jq for pretty output
cat tests/results/test_scrape_products_20250116_143022.json | jq
```

**Option 3: Python**

```python
import json
from pathlib import Path

# Read latest result
results_dir = Path("tests/results")
latest = max(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

with open(latest) as f:
    data = json.load(f)
    print(f"Found {data['count']} products")
```

**File format**: `{test_name}_{timestamp}.json`

## Fixtures

### Playwright Fixtures (Integration Tests)

- `playwright_instance` - Session-scoped Playwright instance
- `browser` - Session-scoped browser (reused across tests)
- `browser_context` - Function-scoped context (fresh per test)
- `browser_page` - Function-scoped page (fresh per test)

### Helper Fixtures

- `results` - Results storage for validation
- `sample_search_terms` - List of sample search terms
- `ml_base_url` - Mercado Livre base URL
- `ml_search_url` - Mercado Livre search URL pattern

### Example usage

```python
def test_with_browser(browser_page, results):
    """Integration test using real browser."""
    browser_page.goto("https://www.mercadolivre.com.br")
    title = browser_page.title()
    
    results.store("test_with_browser", {"title": title})
    
    assert "Mercado Livre" in title
```

## Writing New Tests

### Unit Tests

- Test individual functions in isolation
- Use mocks for external dependencies
- Should be fast (< 1 second per test)
- No network or file system access

```python
from unittest.mock import Mock

def test_parse_card():
    """Unit test with mocked dependencies."""
    mock_card = Mock()
    mock_card.query_selector.return_value = None
    
    produto = parse_card(mock_card)
    
    assert produto.titulo == "N/A"
```

### Integration Tests

- Test real functionality end-to-end
- Use real dependencies (browser, network)
- Can be slower (acceptable up to 30s per test)
- Store results for validation

```python
def test_real_scraping(results):
    """Integration test with real scraping."""
    produtos = scrape_mercadolivre("notebook", max_pages=1, headless=True)
    
    results.store("test_real_scraping", {
        "produtos": produtos,
        "count": len(produtos),
    })
    
    assert len(produtos) > 0
```

## Best Practices

1. **Use descriptive test names** - `test_scrape_single_page` not `test_1`
2. **One assertion per concept** - Test one thing at a time
3. **Use fixtures** - Reuse setup code via fixtures
4. **Store integration results** - Use `results` fixture for validation
5. **Mark slow tests** - Help others skip slow tests during development
6. **Document complex tests** - Add docstrings explaining what's being tested

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

- Unit tests run on every commit (fast feedback)
- Integration tests run on pull requests (thorough validation)
- Results are stored for analysis and debugging

## Troubleshooting

### Playwright browser not found

```bash
playwright install chromium
```

### Tests timing out

Increase timeout in `config/ml_prices/settings.py`:

```python
page_load_timeout: int = 60  # Increase from 40
explicit_wait: int = 30      # Increase from 20
```

### Network errors in integration tests

Integration tests require internet connection. Skip them if offline:

```bash
pytest -m "not requires_network"
```

