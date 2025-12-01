from shared.domain.auction.value_objects import SimplesNacionalMode
from apps.max_bid.services.simples_nacional_calculator import SimplesNacionalCalculator

class MaxBidCalculator():

  def __init__(self, simples_nacional_calculator: SimplesNacionalCalculator):
    self.simples_nacional_calculator = simples_nacional_calculator

  def calculate(self, ml_price_avg: float, sales_risk_buffer_rate: float, revenue_last_12months: float, ml_fee: float, gross_margin: float, ncm: str, cost_risk_buffer_rate: float, qty_item: int = 1) -> float:
    """
    Calcula o max bid para um item na Receita Federal.

    Args:
      ml_price_avg: Preço médio do item no mercado livre.
      sales_risk_buffer_rate: axa de desconto que consideraremos para segurança com relação à receita esperada, começar com 10%
      revenue_last_12months: Receita líquida dos últimos 12 meses.
      ml_fee: Taxa de comissionamento do Mercado Livre.
      gross_margin: Margem bruta do item.
      ncm: NCM do item.
      cost_risk_buffer_rate: Taxa de desconto que consideraremos para segurança com relação aos custos.
      qty_item: Quantidade de itens.
    """

