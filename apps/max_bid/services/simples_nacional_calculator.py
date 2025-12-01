from typing import Protocol
from shared.domain.auction.value_objects import SimplesNacionalMode, SimplesNacionalTax
from shared.ports.auction_storage import RevenueStorage

class SimplesNacionalCalculator(Protocol):
    """Interface para cálculo de Simples Nacional"""
    def calculate(self, revenue_last_12months: float) -> float:
        ...

class FixedSimplesNacionalCalculator(SimplesNacionalCalculator):
    """Modo fixed: busca taxa fixa default do storage"""
    
    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def calculate(self, revenue_last_12months: float) -> float:
        if revenue_last_12months < 0:
            raise ValueError("Revenue cannot be negative")
        
        tax_info = self.revenue_storage.get_fixed_simples_nacional_tax()
        return tax_info.rate

class VariableSimplesNacionalCalculator(SimplesNacionalCalculator):
    """Modo prod: consulta faixa progressiva do Simples Nacional"""
    
    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def calculate(self, revenue_last_12months: float) -> float:
        if revenue_last_12months < 0:
            raise ValueError("Revenue cannot be negative")
        
        tax_info = self.revenue_storage.get_simples_nacional_tax(revenue_last_12months)
        return tax_info.calculate_effective_rate(revenue_last_12months)

class SimplesNacionalCalculatorFactory:
    """Factory para criar calculadora apropriada"""
    
    def __init__(self, revenue_storage: RevenueStorage):
        self.revenue_storage = revenue_storage

    def create(self, mode: SimplesNacionalMode) -> SimplesNacionalCalculator:
        if mode == SimplesNacionalMode.FIXED:
            return FixedSimplesNacionalCalculator(self.revenue_storage)
        elif mode == SimplesNacionalMode.VARIABLE:
            return VariableSimplesNacionalCalculator(self.revenue_storage)
        else: raise ValueError(f"Invalid mode: {mode}")
