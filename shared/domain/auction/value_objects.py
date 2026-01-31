from dataclasses import dataclass
from enum import Enum

class NcmMode(Enum):
    FIXED = "fixed"
    VARIABLE = "variable"
    CUSTOM_FIXED = "custom_fixed"

class SimplesNacionalMode(Enum):
    FIXED = "fixed"
    VARIABLE = "variable"
    CUSTOM_FIXED = "custom_fixed"

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
class NcmTaxesInReais:
    ipi: float
    ii: float
    icms: float
    cbs: float
    ibs: float
    total: float

@dataclass(frozen=True)
class SimplesNacionalTax:
    rate: float
    deducao: float

    def calculate_effective_rate(self, revenue_last_12months: float) -> float:
        """Calcula alíquota efetiva: (RBT12 * Aliq - PD) / RBT12"""
        # Se não há dedução, a taxa efetiva é sempre igual à taxa nominal
        if self.deducao == 0:
            return self.rate

        # Se há dedução mas receita é zero, não é possível calcular taxa efetiva
        if revenue_last_12months == 0:
            raise ValueError("Revenue last 12 months cannot be zero since there is a deduction")

        # Fórmula progressiva: (RBT12 * Aliq - PD) / RBT12
        return (revenue_last_12months * self.rate - self.deducao) / revenue_last_12months

@dataclass(frozen=True)
class MaxBidItemCalculationInput:
    ml_price_avg: float
    sales_risk_buffer_rate: float
    revenue_last_12months: float
    ml_fee: float
    target_net_margin: float  # Margem líquida desejada (após CMV, despesas operacionais e impostos)
    ncm: str
    cost_risk_buffer_rate: float
    qty_item: int = 1

@dataclass(frozen=True)
class MaxBidItemCalculationOutput:
    expected_rev: float
    simples_nacional_tax_rate: float
    simples_nacional_tax_deducao: float
    simples_nacional_tax_effective_rate: float
    ncm_tax_rates: NcmTaxRates
    ncm_taxes_total: float
    numerator: float
    denominator: float
    max_bid_item: float
