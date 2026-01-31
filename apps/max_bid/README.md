# Max Bid

Max Bid é o motor que estima o maior lance que ainda vale a pena ofertar ao vender um produto no Mercado Livre.

## Visão geral
- Consolida custos (produto, taxas, logística) e simula margens.
- Calcula o bid teto considerando metas de lucro e competitividade.
- Fornece a recomendação final para ser consumida pelos demais serviços.

## Próximos passos
- Integrar dados de custos vindos de `shared`.
- Expôr a API/CLI básica para ser usada por `ml_prices`.

# Modelo - Somatória de itens individualizados

## Parâmetros de Entrada

### Relacionados ao valor de venda (variáveis "pós-venda")
- ml_price_avg: preço médio do item no mercado livre

- sales_risk_buffer_rate: taxa de desconto que consideraremos para segurança com relação à receita esperada, começar com 10% e depois ajustamos baseado em modelo estatístico que consuma nosso track record de reembolsos, desvalorizações subtas, perdas e avarias. Deixar na db para podermos alterar facilmente.

- revenue_last_12months: receita líquida dos últimos 12 meses, usada para calcular a alíquota efetiva do Simples Nacional. A alíquota efetiva é calculada como: [(revenue_last_12months × aliq_anexo_I) - deducao_anexo_I] / revenue_last_12months, onde aliq_anexo_I e deducao_anexo_I variam de acordo com a tabela abaixo:

        | Faixa       | Receita Bruta em 12 Meses (R$)            | Alíquota | Valor a Deduzir (R$) |
        |-------------|--------------------------------------------|----------|------------------------|
        | 1ª Faixa    | Até 180.000,00                             | 4,00%    | -                      |
        | 2ª Faixa    | De 180.000,01 a 360.000,00                 | 7,30%    | 5.940,00               |
        | 3ª Faixa    | De 360.000,01 a 720.000,00                 | 9,50%    | 13.860,00              |
        | 4ª Faixa    | De 720.000,01 a 1.800.000,00               | 10,70%   | 22.500,00              |
        | 5ª Faixa    | De 1.800.000,01 a 3.600.000,00             | 14,30%   | 87.300,00              |
        | 6ª Faixa    | De 3.600.000,01 a 4.800.000,00             | 19,00%   | 378.000,00             |

    O cálculo utiliza injeção de dependência através do `SimplesNacionalCalculator` (Protocol), com três implementações:
    - **FIXED**: Busca taxa fixa default do `RevenueStorage` (útil para testes/desenvolvimento)
    - **CUSTOM_FIXED**: Usa taxa fixa customizada fornecida pelo usuário (permite simulações sem consultar storage)
    - **VARIABLE**: Consulta faixa progressiva do Anexo I com base em `revenue_last_12months` via `RevenueStorage` (modo produção)

- ml_fee: taxa que fica com mercado livre, considerar 19%, mas deixar no db, de modo que possamos alterar facilmente, pois esse valor pode reduzir de acordo com nosso volume de venda e modo de anúncio no mercado livre, podendo chegar a 10%

- gross_margin: margem que buscamos, deixar de modo que possamos alterar facilmente, considerar como 30% no começo.

### Relacionados ao valor de arrematação (variáveis "pré-venda")
- ncm: código ncm do item, se não for passado como parâmetro, usar 0, como código para fallback; a ideia é o ncm ser usado como chave de consulta na db para obter os % de alíquotas abaixo. O serviço de ncm roda periodicamente para atualizar os dados associados.
    - ipi: alíquota associada ao código ncm
    - ii: alíquota associada ao código ncm
    - icms: alíquota associada ao código ncm
    - cbs: virá efetivamente em 2027, com próxima fase da reforma tributária
    - ibs: virá efetivamente em 2027, com próxima fase da reforma tributária
    - if rfb_ncm=0, ipi=20%, ii=20%, icms=18% , cbs=0%, ibs=0% (deixar em tabela no db, para podermos alterar em lugar unificado de modo fácil)

    O cálculo utiliza injeção de dependência através do `NcmCalculator` (Protocol), com três implementações:
    - **FIXED**: Busca taxas default do `NCMStorage` (NCM=0, útil para testes/desenvolvimento)
    - **CUSTOM_FIXED**: Usa taxas customizadas fornecidas pelo usuário (permite simulações sem consultar storage)
    - **VARIABLE**: Consulta taxas específicas por NCM via `NCMStorage` (modo produção)

- cost_risk_buffer_rate: margem de segurança para eventuais mudanças imprevistas (eventuais taxas e custos extras, decorrentes de mudanças legislativas abruptas)

## Parâmetros de saída
- max_bid_lote: valor máximo de lance razoável para aquele item

## Operação aritmética
### Passos para Cálculo por Item
1. **Calcular Receita Esperada Ajustada (expected_rev)**:  
   expected_rev = ml_price_avg × qty_item × (1 - sales_risk_buffer_rate)

2. **Calcular Taxa de Simples Nacional Efetiva**:
   - Obtenha aliq_anexo_I e deducao_anexo_I da faixa com base em revenue_last_12months.
   - simples_nacional_tax_effective_rate = [(revenue_last_12months × aliq_anexo_I - deducao_anexo_I) / revenue_last_12months]

3. **Obter Alíquotas Pré-Venda (NCM)**:  
   Consulte DB com ncm (ou fallback 0) para ipi, ii, icms, cbs, ibs.

4. **Calcular Lance Máximo por Item (max_bid_item)**:  
   - Defina o numerador (parte pós-venda ajustada pela margem):  
     numerador = expected_rev × (1 - gross_margin - simples_nacional_tax_effective_rate - ml_fee)  
   - Defina o denominador (parte pré-venda com buffer):  
     denominador = (1 + ipi + ii + icms + cbs + ibs) × (1 + cost_risk_buffer_rate)  
   - max_bid_item = numerador / denominador  
     (Isso garante que CMV = [max_bid_item × (1 + ipi + ii + icms + cbs + ibs) × (1 + cost_risk_buffer_rate)] + expected_rev × (simples_nacional_tax_effective_rate + ml_fee) = expected_rev × (1 - gross_margin), isolando max_bid_item.)

### Agregação para o Lote
- max_bid_lote = Σ max_bid_item (para todos itens no lote).

### Implementação Sugerida (Pseudocódigo para Automação)
```python
def calculate_max_bid_item(input: MaxBidItemCalculationInput):
    # Passo 1: Calcular receita esperada ajustada
    expected_rev = input.ml_price_avg * input.qty_item * (1 - input.sales_risk_buffer_rate)
    
    # Passo 2: Calcular taxa de Simples Nacional
    simples_nacional_tax = simples_nacional_calculator.calculate(input.revenue_last_12months)
    simples_nacional_tax_effective_rate = simples_nacional_tax.calculate_effective_rate(input.revenue_last_12months)
    
    # Passo 3: Calcular alíquotas de NCM
    ncm_tax_rates = ncm_calculator.calculate(input.ncm)
    
    # Passo 4: Calcular max_bid_item
    numerador = expected_rev * (1 - input.gross_margin - simples_nacional_tax_effective_rate - input.ml_fee)
    denominador = (1 + ncm_tax_rates.ipi + ncm_tax_rates.ii + ncm_tax_rates.icms + ncm_tax_rates.cbs + ncm_tax_rates.ibs) * (1 + input.cost_risk_buffer_rate)
    max_bid_item = numerador / denominador if denominador != 0 else 0
    
    return max_bid_item

def calculate_max_bid_lote(inputs: list[MaxBidItemCalculationInput]):
    # Para lote: soma dos max_bid de cada item
    max_bid_items = [calculate_max_bid_item(input) for input in inputs]
    return sum(max_bid_item for max_bid_item in max_bid_items)
```


# Aspectos jurídicos

## IBS e CBS
Pesquisar no detalhe para 2026

## PIS e COFINS Importação
Não incidem no caso de arrematação de bens que sofreram pena de perdimento. Fundamentos:
* Item 1.21 "e" da lista de dispensa de contestar e recorrer PGFN
* Ato Declaratório PGFN nº 8/2018 
* Parecer PGFN/CRJ/Nº 1755/2016 
* DOU de 18/06/2018. Seção 1 pág. 55 
* Nota PGFN/CRJ nº 962/2016 