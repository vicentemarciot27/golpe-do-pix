from shared.ports.auction_storage import NCMStorage, RevenueStorage
from shared.domain.auction.value_objects import NcmTaxRates, SimplesNacionalTax
import logging

class LocalNCMStorage(NCMStorage):
    """Adapter local para armazenamento de taxas NCM em memória"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Taxas padrão (NCM=0) - valores default
        self.default_rates = NcmTaxRates(
            ipi=0.20,
            ii=0.20,
            icms=0.18,
            cbs=0.092,
            ibs=0.088
        )
        # Dicionário para armazenar taxas específicas por NCM
        self.ncm_rates: dict[str, NcmTaxRates] = {}
    
    def get_tax_rates_by_ncm(self, ncm: str) -> NcmTaxRates:
        """Retorna taxas para NCM específico ou default se não encontrado"""
        return self.ncm_rates.get(ncm, self.default_rates)
    
    def get_default_tax_rates(self) -> NcmTaxRates:
        """Retorna taxas default"""
        return self.default_rates
    
    def add_ncm_tax_rates(self, ncm: str, rates: NcmTaxRates) -> None:
        """Adiciona taxas para um NCM específico"""
        self.ncm_rates[ncm] = rates


class LocalRevenueStorage(RevenueStorage):
    """Adapter local para armazenamento de receita em memória"""
    
    def __init__(self, revenue_last_12months: float = 0.0):
        self.logger = logging.getLogger(__name__)
        self._revenue_last_12months = revenue_last_12months
        
        # Tabela de faixas progressivas do Simples Nacional (Comércio - Anexo I)
        # Baseado na Lei Complementar 123/2006
        self.simples_brackets = [
            # (limite_superior, aliquota, deducao)
            (180_000.00, 0.04, 0.0),           # Até 180k: 4%
            (360_000.00, 0.073, 5_940.00),     # 180k - 360k
            (720_000.00, 0.095, 13_860.00),    # 360k - 720k
            (1_800_000.00, 0.107, 22_500.00),  # 720k - 1.8M
            (3_600_000.00, 0.143, 87_300.00),  # 1.8M - 3.6M
            (4_800_000.00, 0.19, 378_000.00),  # 3.6M - 4.8M
        ]
        
        self.default_simples_nacional_tax = SimplesNacionalTax(rate=0.04, deducao=0.0)
    
    def get_revenue_last_12months(self) -> float:
        """Retorna receita dos últimos 12 meses"""
        return self._revenue_last_12months
    
    def set_revenue_last_12months(self, revenue: float) -> None:
        """Define receita dos últimos 12 meses"""
        if revenue < 0:
            raise ValueError("Revenue cannot be negative")
        self._revenue_last_12months = revenue
    
    def get_simples_nacional_tax(self, revenue_last_12months: float) -> SimplesNacionalTax:
        """Retorna taxa do Simples Nacional baseada na receita"""
        # Se receita é 0, retorna taxa default (modo fixed)
        if revenue_last_12months == 0.0:
            return self.default_tax
        
        # Busca faixa apropriada
        for limite, aliquota, deducao in self.simples_brackets:
            if revenue_last_12months <= limite:
                return SimplesNacionalTax(rate=aliquota, deducao=deducao)
        
        # Acima do limite do Simples Nacional
        raise ValueError(f"Revenue {revenue_last_12months} exceeds Simples Nacional limit")

    def get_fixed_simples_nacional_tax(self) -> SimplesNacionalTax:
        """Retorna taxa fixa default"""
        return self.default_tax

