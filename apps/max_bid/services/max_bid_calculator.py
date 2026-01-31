from apps.max_bid.services.ncm_calculator import NcmCalculator
from apps.max_bid.services.simples_nacional_calculator import SimplesNacionalCalculator
from shared.domain.auction.value_objects import (
    MaxBidItemCalculationInput,
    MaxBidItemCalculationOutput,
)


class MaxBidCalculator:
    def __init__(
        self,
        simples_nacional_calculator: SimplesNacionalCalculator,
        ncm_calculator: NcmCalculator,
    ):
        self.simples_nacional_calculator = simples_nacional_calculator
        self.ncm_calculator = ncm_calculator

    def calculate_max_bid_item(
        self, input: MaxBidItemCalculationInput
    ) -> MaxBidItemCalculationOutput:
        """
        Calcula o max bid para um item na Receita Federal.

        Args:
            input: Input para cálculo do max bid para um item.
                .ml_price_avg: Preço médio do item no mercado livre.
                .sales_risk_buffer_rate: Taxa de desconto para segurança com relação à receita esperada
                .revenue_last_12months: Receita líquida dos últimos 12 meses.
                .ml_fee: Taxa de comissionamento do Mercado Livre.
                .target_net_margin: Margem líquida desejada (lucro líquido / receita).
                .ncm: NCM do item.
                .cost_risk_buffer_rate: Taxa de desconto para segurança com relação aos custos.
                .qty_item: Quantidade de itens.
        """
        # 1 Calcular receita esperada ajustada
        expected_rev = (
            input.ml_price_avg * input.qty_item * (1 - input.sales_risk_buffer_rate)
        )

        # 2 Calcular taxa de Simples Nacional
        simples_nacional_tax = self.simples_nacional_calculator.calculate(
            input.revenue_last_12months
        )
        simples_nacional_tax_effective_rate = (
            simples_nacional_tax.calculate_effective_rate(input.revenue_last_12months)
        )

        # 3 Calcular alíquotas de NCM
        ncm_tax_rates = self.ncm_calculator.calculate(input.ncm)

        # 4.1 Calcular numerador (reserva margem líquida desejada + impostos + taxa ML)
        numerator = expected_rev * (
            1
            - input.target_net_margin
            - simples_nacional_tax_effective_rate
            - input.ml_fee
        )

        # 4.2 Calcular denominador
        denominator = (
            1
            + ncm_tax_rates.ipi
            + ncm_tax_rates.ii
            + ncm_tax_rates.icms
            + ncm_tax_rates.cbs
            + ncm_tax_rates.ibs
        ) * (1 + input.cost_risk_buffer_rate)

        # 4.3 Calcular max bid item
        max_bid_item = numerator / denominator if denominator != 0 else 0

        # 4.4 Calcular ncm taxes total
        total_ncm_taxes = max_bid_item * (
            ncm_tax_rates.ipi
            + ncm_tax_rates.ii
            + ncm_tax_rates.icms
            + ncm_tax_rates.cbs
            + ncm_tax_rates.ibs
        )

        max_bid_item_calculation_output = MaxBidItemCalculationOutput(
            expected_rev=expected_rev,
            simples_nacional_tax_rate=simples_nacional_tax.rate,
            simples_nacional_tax_deducao=simples_nacional_tax.deducao,
            simples_nacional_tax_effective_rate=simples_nacional_tax_effective_rate,
            ncm_tax_rates=ncm_tax_rates,
            ncm_taxes_total=total_ncm_taxes,
            numerator=numerator,
            denominator=denominator,
            max_bid_item=max_bid_item,
        )

        return max_bid_item_calculation_output

    def calculate_max_bid_lote(self, inputs: list[MaxBidItemCalculationInput]) -> float:
        """Calcula o lance máximo total para um lote com múltiplos itens"""
        max_bid_items = [self.calculate_max_bid_item(input) for input in inputs]
        return sum(max_bid_item.max_bid_item for max_bid_item in max_bid_items)
