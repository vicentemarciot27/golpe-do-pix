#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pytest root configuration and shared fixtures.
This file contains only infrastructure fixtures that are app-agnostic.
App-specific fixtures should be defined in their respective conftest.py files.
"""

import sys
from pathlib import Path
from typing import Generator, Any

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# =========================
# RESULTS STORAGE
# =========================
import json
from datetime import datetime


class TestResultsStorage:
    """
    Stores test results as JSON files for easy validation and debugging.
    Results are saved to tests/results/ directory.
    """
    
    def __init__(self):
        self.results_dir = ROOT_DIR / "tests" / "results"
        self.results_dir.mkdir(exist_ok=True)
        self._last_test_name = ""
    
    def store(self, test_name: str, data: Any) -> None:
        """Store test results as JSON file."""
        self._last_test_name = test_name
        
        # Create safe filename from test name
        safe_name = test_name.replace("::", "_").replace("/", "_").replace("\\", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        # Convert data to JSON-serializable format
        json_data = self._make_serializable(data)
        json_data["_metadata"] = {
            "test_name": test_name,
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat()
        }
        
        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved: {filepath.name}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format."""
        if hasattr(obj, "__dict__"):
            # Dataclass or object with __dict__
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    def get_last_test_name(self) -> str:
        """Get the name of the last test that stored results."""
        return self._last_test_name


# Global results storage instance
_results_storage = TestResultsStorage()


@pytest.fixture(scope="function")
def results() -> TestResultsStorage:
    """
    Function-scoped fixture for storing test results as JSON files.
    
    Usage in tests:
        def test_something(results):
            data = scrape_mercadolivre("smartphone", max_pages=1, headless=True)
            results.store("test_something", {
                "produtos": data,
                "count": len(data)
            })
            assert len(data) > 0
    
    Results are saved to: tests/results/{test_name}_{timestamp}.json
    """
    yield _results_storage


# =========================
# PLAYWRIGHT FIXTURES
# =========================
@pytest.fixture(scope="session")
def playwright_instance():
    """
    Session-scoped Playwright instance.
    Reuses the same Playwright instance across all tests for efficiency.
    """
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance) -> Generator[Browser, None, None]:
    """
    Session-scoped browser instance.
    Launches browser once and reuses it across tests.
    Defaults to headless=True for CI/CD compatibility.
    Override in app-specific conftest if needed.
    """
    import os
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    
    browser = playwright_instance.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,1024",
            "--disable-blink-features=AutomationControlled",
        ]
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def browser_context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """
    Function-scoped browser context.
    Creates a fresh context for each test to ensure isolation.
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 1024},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def browser_page(browser_context: BrowserContext) -> Generator[Page, None, None]:
    """
    Function-scoped browser page.
    Creates a fresh page for each test.
    """
    page = browser_context.new_page()
    yield page
    page.close()


# =========================
# PYTEST HOOKS
# =========================
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_network: mark test as requiring network access"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (for pytest-asyncio compatibility)"
    )


def pytest_sessionstart(session):
    """Print all configurations when test session starts."""
    import os
    
    print("\n" + "=" * 80)
    print("🚀 PYTEST CONFIGURATION - Root conftest.py")
    print("=" * 80)
    
    # Print environment info
    print(f"\n🌍 ENVIRONMENT:")
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true")
    print(f"   • PLAYWRIGHT_HEADLESS: {headless} {'← Browser hidden' if headless == 'true' else '← Browser visible'}")
    
    # Print available fixtures (root level only)
    print(f"\n🔧 ROOT-LEVEL FIXTURES (app-agnostic):")
    fixtures_info = [
        ("playwright_instance", "Session-scoped Playwright instance"),
        ("browser", "Session-scoped browser instance"),
        ("browser_context", "Function-scoped browser context"),
        ("browser_page", "Function-scoped browser page"),
        ("results", "TestResultsStorage for saving test results"),
    ]
    for name, desc in fixtures_info:
        print(f"   • {name}: {desc}")
    
    print(f"\n   ℹ️  App-specific fixtures are defined in tests/{{integration|unit}}/{{app_name}}/conftest.py")
    
    # Print configured markers
    print(f"\n🏷️  CONFIGURED MARKERS:")
    markers_info = [
        ("e2e", "End-to-end tests (auto-marked for tests/e2e/)"),
        ("integration", "Integration tests (auto-marked for tests/integration/)"),
        ("unit", "Unit tests (auto-marked for tests/unit/)"),
        ("slow", "Slow running tests"),
        ("requires_network", "Tests requiring network access"),
        ("asyncio", "Async tests"),
    ]
    for marker, desc in markers_info:
        print(f"   • {marker}: {desc}")
    
    # Print results directory
    print(f"\n💾 RESULTS STORAGE:")
    results_dir = ROOT_DIR / "tests" / "results"
    print(f"   • Directory: {results_dir}")
    print(f"   • Exists: {results_dir.exists()}")
    
    # Print project structure info
    print(f"\n📁 PROJECT STRUCTURE:")
    print(f"   • Root: {ROOT_DIR}")
    print(f"   • Tests: {ROOT_DIR / 'tests'}")
    print(f"   • Python path includes project root: {str(ROOT_DIR) in sys.path}")
    
    print("\n" + "=" * 80)
    print("✅ Root configuration loaded successfully")
    print("=" * 80 + "\n")


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location.
    - tests/e2e/* -> e2e, requires_network, slow
    - tests/integration/* -> integration, requires_network, slow
    - tests/unit/* -> unit
    """
    for item in items:
        # Get test file path relative to tests directory
        test_path = Path(item.fspath).relative_to(ROOT_DIR / "tests")
        
        # Auto-mark e2e tests
        if test_path.parts[0] == "e2e":
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.requires_network)
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark integration tests
        elif test_path.parts[0] == "integration":
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.requires_network)
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark unit tests
        elif test_path.parts[0] == "unit":
            item.add_marker(pytest.mark.unit)




# =========================
# NOTE: App-specific fixtures have been moved to their respective conftest files:
# - tests/integration/ml_prices/conftest.py
# - tests/unit/ml_prices/conftest.py
# - tests/integration/max_bid/conftest.py
# - etc.
# =========================
