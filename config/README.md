# Config

Centraliza variáveis de ambiente, templates de `.env` e presets de deploy.

## Guia rápido
- Use este diretório para documentar valores padrão e segredos esperados.
- Cada serviço deve declarar aqui quais chaves precisa antes de subir.

## Dependency Injection Pattern

Este projeto utiliza **injeção de dependências** para configurações, permitindo diferentes ambientes (produção, testes, desenvolvimento) sem acoplamento a variáveis globais.

### Como funciona

#### 1. Definição de Settings

Cada serviço define suas configurações usando `pydantic_settings.BaseSettings`:

```python
# config/ml_prices/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings

class MLPricesSettings(BaseSettings):
    pages_to_scrape: int = Field(default=3, ge=1)
    headless: bool = Field(default=True)
    page_load_timeout: int = Field(default=40, ge=1)
    explicit_wait: int = Field(default=20, ge=1)
    
    class Config:
        env_prefix = "ML_PRICES_"
        env_file_encoding = "utf-8"

def get_settings(env_file: Optional[str] = None) -> MLPricesSettings:
    """
    Return a settings instance from the specified env file.
    
    Args:
        env_file: Path to .env file. If None, uses 'config/.env'
    """
    if env_file is None:
        env_file = "config/.env"
    return MLPricesSettings(_env_file=env_file)
```

#### 2. Uso em Classes (Recomendado)

Classes recebem settings via construtor:

```python
# apps/ml_prices/scrapers/playwright.py
class MercadoLivreScraper:
    def __init__(self, settings: MLPricesSettings):
        self.settings = settings
    
    def scrape(self, termo: str) -> List[Produto]:
        # Usa self.settings.pages_to_scrape, etc.
        ...
```

#### 3. Instanciação em Diferentes Ambientes

**Produção:**
```python
from config.ml_prices.settings import get_settings
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper

settings = get_settings()  # usa config/.env
scraper = MercadoLivreScraper(settings)
produtos = scraper.scrape("smartphone", max_pages=3)
```

**Testes:**
```python
from config.ml_prices.settings import get_settings
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper

test_settings = get_settings("config/.env.test")
scraper = MercadoLivreScraper(test_settings)
produtos = scraper.scrape("smartphone", max_pages=1)
```

**Customizado (sem arquivo .env):**
```python
from config.ml_prices.settings import MLPricesSettings
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper

custom_settings = MLPricesSettings(
    pages_to_scrape=1,
    headless=True,
    page_load_timeout=10,
    explicit_wait=5,
)
scraper = MercadoLivreScraper(custom_settings)
```

#### 4. Fixtures para Testes

Use fixtures do pytest para reutilizar configurações:

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def test_settings() -> MLPricesSettings:
    """Settings configuradas para testes."""
    try:
        return get_settings("config/.env.test")
    except Exception:
        return MLPricesSettings(
            pages_to_scrape=1,
            headless=True,
            page_load_timeout=30,
            explicit_wait=15,
        )

@pytest.fixture
def test_scraper(test_settings: MLPricesSettings) -> MercadoLivreScraper:
    """Scraper configurado para testes."""
    return MercadoLivreScraper(test_settings)
```

**Uso nos testes:**
```python
def test_scraping_with_custom_settings(test_scraper):
    produtos = test_scraper.scrape("notebook", max_pages=1)
    assert len(produtos) > 0
```

### Estrutura de Arquivos .env

```
config/
├── .env              # Produção (não commitado)
├── .env.test         # Testes (pode ser commitado)
├── .env.example      # Template (commitado)
└── ml_prices/
    └── settings.py
```

**Exemplo de .env:**
```bash
ML_PRICES_PAGES_TO_SCRAPE=3
ML_PRICES_HEADLESS=true
ML_PRICES_PAGE_LOAD_TIMEOUT=40
ML_PRICES_EXPLICIT_WAIT=20
```

**Exemplo de .env.test:**
```bash
ML_PRICES_PAGES_TO_SCRAPE=1
ML_PRICES_HEADLESS=true
ML_PRICES_PAGE_LOAD_TIMEOUT=20
ML_PRICES_EXPLICIT_WAIT=10
```