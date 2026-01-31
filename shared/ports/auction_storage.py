from abc import ABC, abstractmethod
from shared.domain.auction.value_objects import NcmTaxRates, SimplesNacionalTax

class NCMStorage(ABC):
    @abstractmethod
    def get_tax_rates_by_ncm(self, ncm: str) -> NcmTaxRates:
        """Retorna alíquotas IPI, II, ICMS, CBS, IBS para um NCM"""
        pass
    
    @abstractmethod
    def get_default_tax_rates(self) -> NcmTaxRates:
        """Retorna alíquotas default (ncm=0)"""
        pass

class RevenueStorage(ABC):
    @abstractmethod
    def get_revenue_last_12months(self) -> float:
        pass
    
    @abstractmethod
    def get_simples_nacional_tax(self, revenue_last_12months: float) -> SimplesNacionalTax:
        pass

    @abstractmethod
    def get_fixed_simples_nacional_tax(self) -> SimplesNacionalTax:
        pass