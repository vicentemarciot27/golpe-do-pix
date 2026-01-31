from typing import Protocol

from shared.domain.auction.value_objects import SimplesNacionalMode, SimplesNacionalTax
from shared.ports.auction_storage import RevenueStorage


class SimplesNacionalCalculator(Protocol):
    """Interface para cálculo de Simples Nacional"""

    def calculate(self, revenue_last_12months: float) -> SimplesNacionalTax:
        """Retorna SimplesNacionalTax com rate, deducao e método calculate_effective_rate"""
        ...


class FixedSimplesNacionalCalculator(SimplesNacionalCalculator):
    """Modo fixed: busca taxa fixa default do storage"""

    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def calculate(self, revenue_last_12months: float) -> SimplesNacionalTax:
        if revenue_last_12months < 0:
            raise ValueError("Revenue cannot be negative")

        return self.revenue_storage.get_fixed_simples_nacional_tax()


class CustomFixedSimplesNacionalCalculator(SimplesNacionalCalculator):
    """Modo fixed: busca taxa fixa customizada a partir de input do usuário"""

    def __init__(self, simples_nacional_tax: SimplesNacionalTax):
        self.simples_nacional_tax = simples_nacional_tax

    def calculate(self, revenue_last_12months: float) -> SimplesNacionalTax:
        if revenue_last_12months < 0:
            raise ValueError("Revenue cannot be negative")

        return self.simples_nacional_tax


class VariableSimplesNacionalCalculator(SimplesNacionalCalculator):
    """Modo prod: consulta faixa progressiva do Simples Nacional"""

    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def calculate(self, revenue_last_12months: float) -> SimplesNacionalTax:
        if revenue_last_12months < 0:
            raise ValueError("Revenue cannot be negative")

        return self.revenue_storage.get_simples_nacional_tax(revenue_last_12months)


class SimplesNacionalCalculatorFactory:
    """Factory para criar calculadora apropriada"""

    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def create(
        self, mode: SimplesNacionalMode, simples_nacional_tax: SimplesNacionalTax = None
    ) -> SimplesNacionalCalculator:
        if mode == SimplesNacionalMode.FIXED:
            return FixedSimplesNacionalCalculator(self.revenue_storage)
        elif mode == SimplesNacionalMode.VARIABLE:
            return VariableSimplesNacionalCalculator(self.revenue_storage)
        elif mode == SimplesNacionalMode.CUSTOM_FIXED:
            return CustomFixedSimplesNacionalCalculator(simples_nacional_tax)
        else:
            raise ValueError(f"Invalid mode: {mode}")
