"""
Constants for auction end analytics UI.
"""

# Competition level labels
COMPETITION_LEVEL_LABELS = {
    "low": "Baixa (1 participante classificado)",
    "medium": "Média (2-3 participantes)",
    "high": "Alta (4+ participantes)",
}

# Proposal status labels
PROPOSAL_STATUS_LABELS = {
    "Classificada": "Classificada",
    "Recusada - Valor Insuficiente": "Recusada (Valor Insuficiente)",
    "Desclassificada - Sanções CEIS": "Desclassificada (Sanções CEIS)",
    "Unknown": "Desconhecido",
}

# Bid status labels
BID_STATUS_LABELS = {
    "Vencedor": "Vencedor",
    "Perdedor": "Perdedor",
    "Empatado": "Empatado",
    "Recusado - Valor não Obedece a Faixa de Incremento": "Recusado (Faixa de Incremento)",
    "Unknown": "Desconhecido",
}

# Page configuration (if used standalone)
PAGE_TITLE = "Auction End Analytics"
PAGE_ICON = "📊"
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"

# Default values
DEFAULT_MAX_PAGES = None  # None = process all pages
