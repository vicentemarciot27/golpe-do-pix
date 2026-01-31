from typing import Protocol

from shared.domain.auction.value_objects import NcmMode, NcmTaxRates
from shared.ports.auction_storage import NCMStorage


class NcmCalculator(Protocol):
    """Interface para cálculo de impostos por NCM"""

    def calculate(self, ncm: str) -> NcmTaxRates: ...


class FixedNcmCalculator(NcmCalculator):
    """Modo fixed: busca taxas default do storage (NCM=0)"""

    def __init__(self, ncm_storage: NCMStorage):
        self.ncm_storage = ncm_storage

    def calculate(self, ncm: str) -> NcmTaxRates:
        return self.ncm_storage.get_default_tax_rates()


class CustomFixedNcmCalculator(NcmCalculator):
    """Modo fixed: busca taxas customizadas a partir de input do usuário"""

    def __init__(self, custom_rates: NcmTaxRates):
        self.custom_rates = custom_rates

    def calculate(self, ncm: str) -> NcmTaxRates:
        return self.custom_rates


class VariableNcmCalculator(NcmCalculator):
    """Modo prod: busca taxas específicas por NCM"""

    def __init__(self, ncm_storage: NCMStorage):
        self.ncm_storage = ncm_storage

    def calculate(self, ncm: str) -> NcmTaxRates:
        return self.ncm_storage.get_tax_rates_by_ncm(ncm)


class NcmCalculatorFactory:
    def __init__(self, ncm_storage: NCMStorage):
        self.ncm_storage = ncm_storage

    def create(self, mode: NcmMode, custom_rates: NcmTaxRates = None) -> NcmCalculator:
        if mode == NcmMode.FIXED:
            return FixedNcmCalculator(self.ncm_storage)
        elif mode == NcmMode.VARIABLE:
            return VariableNcmCalculator(self.ncm_storage)
        elif mode == NcmMode.CUSTOM_FIXED:
            return CustomFixedNcmCalculator(custom_rates)
        else:
            raise ValueError(f"Invalid mode: {mode}")
