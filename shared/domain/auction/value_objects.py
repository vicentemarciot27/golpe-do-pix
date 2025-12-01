from dataclasses import dataclass
from enum import Enum

class NcmMode(Enum):
    FIXED = "fixed"
    VARIABLE = "variable"

class SimplesNacionalMode(Enum):
    FIXED = "fixed"
    VARIABLE = "variable"

@dataclass(frozen=True)  # frozen=True garante imutabilidade, o que significa que o objeto não pode ser modificado depois de criado
class NcmTaxRates:
    ipi: float
    ii: float
    icms: float
    cbs: float
    ibs: float
    
    def __post_init__(self):
        for field_name in ['ipi', 'ii', 'icms', 'cbs', 'ibs']:
            value = getattr(self, field_name)
            if not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be between 0 and 1")

@dataclass(frozen=True)
class SimplesNacionalTax:
    rate: float
    deducao: float
    
    def calculate_effective_rate(self, revenue_12months: float) -> float:
        """Calcula alíquota efetiva: (RBT12 * Aliq - PD) / RBT12"""
        if revenue_12months == 0:
            return 0
        return (revenue_12months * self.rate - self.deducao) / revenue_12months