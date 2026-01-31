"""
Value objects for auction end domain.
"""

from dataclasses import dataclass
from enum import Enum


class ProposalStatus(Enum):
    """Status of a proposal in the auction."""
    CLASSIFICADA = "Classificada"
    RECUSADA_VALOR_INSUFICIENTE = "Recusada - Valor Insuficiente"
    DESCLASSIFICADA_SANCOES_CEIS = "Desclassificada - Sanções CEIS"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "ProposalStatus":
        """Parse status from PDF string."""
        value_clean = value.strip()
        for status in cls:
            if status.value.lower() == value_clean.lower():
                return status
        if "classificada" in value_clean.lower() and "des" not in value_clean.lower():
            return cls.CLASSIFICADA
        if "insuficiente" in value_clean.lower():
            return cls.RECUSADA_VALOR_INSUFICIENTE
        if "sanções" in value_clean.lower() or "ceis" in value_clean.lower():
            return cls.DESCLASSIFICADA_SANCOES_CEIS
        return cls.UNKNOWN


class BidStatus(Enum):
    """Status of a bid in the history."""
    VENCEDOR = "Vencedor"
    PERDEDOR = "Perdedor"
    EMPATADO = "Empatado"
    RECUSADO_FAIXA_INCREMENTO = "Recusado - Valor não Obedece a Faixa de Incremento"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "BidStatus":
        """Parse status from PDF string."""
        value_clean = value.strip().lower()
        if "vencedor" in value_clean:
            return cls.VENCEDOR
        if "perdedor" in value_clean:
            return cls.PERDEDOR
        if "empatado" in value_clean:
            return cls.EMPATADO
        if "faixa" in value_clean or "incremento" in value_clean:
            return cls.RECUSADO_FAIXA_INCREMENTO
        return cls.UNKNOWN


@dataclass(frozen=True)
class WinnerInfo:
    """Information about the auction winner."""
    cnpj_cpf: str  # e.g., "60.530.186/0001-12"
    name: str  # e.g., "XP MONEY INFORMATICA E SERVICOS LTDA"

    @classmethod
    def from_string(cls, value: str) -> "WinnerInfo | None":
        """Parse winner info from PDF string like '60.530.186/0001-12 - XP MONEY...'"""
        if not value or value.strip() == "-":
            return None
        parts = value.split(" - ", 1)
        if len(parts) == 2:
            return cls(cnpj_cpf=parts[0].strip(), name=parts[1].strip())
        return cls(cnpj_cpf=value.strip(), name="")
