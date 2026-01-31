"""
Shared constants for Max Bid Calculator UI
"""

# Page configuration
PAGE_TITLE = "Max Bid Calculator"
PAGE_ICON = "💰"
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"

# Mode display names
SIMPLES_NACIONAL_MODE_LABELS = {
    "fixed": "🔒 Fixed (Taxa padrão 4%)",
    "variable": "📊 Variable (Faixa progressiva)",
    "custom_fixed": "✏️ Custom Fixed (Taxa personalizada)",
}

NCM_MODE_LABELS = {
    "fixed": "🔒 Fixed (Taxas padrão)",
    "variable": "📊 Variable (Por NCM específico)",
    "custom_fixed": "✏️ Custom Fixed (Taxas personalizadas)",
}

# Default values
DEFAULT_ML_PRICE = 1000.0
DEFAULT_ML_FEE = 0.19
DEFAULT_SALES_RISK_BUFFER = 0.10
DEFAULT_TARGET_NET_MARGIN = 0.30
DEFAULT_COST_RISK_BUFFER = 0.05
DEFAULT_REVENUE_12M = 0.0
DEFAULT_NCM = "0"
DEFAULT_QTY = 1

# Input constraints
MIN_PERCENTAGE = 0.0
MAX_PERCENTAGE = 100.0
MIN_PRICE = 0.0
MIN_QTY = 1
