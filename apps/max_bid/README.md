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

- seles_risk_buffer_rate: taxa de desconto que consideraremos para segurança com relação à receita esperada, começar com 10% e depois ajustamos baseado em modelo estatístico que consuma nosso track record de reembolsos, desvalorizações subtas, perdas e avarias. Deixar na db para podermos alterar facilmente.

- sn_mode ("fixed" ou "varialbe") e aliqsn. 
    - If sn_mode=fixed, aliqsn=4% (mínimo do anexo I da lcp 123, para faturamento de até BRL 15k/mês, deixar esse valor salvo no db para conseguirmos alterar mais facilmente, como no caso dos valores para ncm=0)
    - If sn_mode=varialbe, então aliqsn[1] = fcst_rev * {[ (revenue_last_12months * aliq_anexo_I) - deducao_anexo_I] / revenue_last_12months}
        [1] -> aliqsn dependerá do faturamento esperado para o próximo mês (fcst_rev), precisaremos de um bom histórico de vendas e modelo estatístico para prever bem isso. aliq_anexo_I e deducao_anexo_I variam de acordo com a tabela abaixo:

        | Faixa       | Receita Bruta em 12 Meses (R$)            | Alíquota | Valor a Deduzir (R$) |
        |-------------|--------------------------------------------|----------|------------------------|
        | 1ª Faixa    | Até 180.000,00                             | 4,00%    | -                      |
        | 2ª Faixa    | De 180.000,01 a 360.000,00                 | 7,30%    | 5.940,00               |
        | 3ª Faixa    | De 360.000,01 a 720.000,00                 | 9,50%    | 13.860,00              |
        | 4ª Faixa    | De 720.000,01 a 1.800.000,00               | 10,70%   | 22.500,00              |
        | 5ª Faixa    | De 1.800.000,01 a 3.600.000,00             | 14,30%   | 87.300,00              |
        | 6ª Faixa    | De 3.600.000,01 a 4.800.000,00             | 19,00%   | 378.000,00             |

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

- cost_risk_buffer_rate: margem de segurança para eventuais mudanças imprevistas (eventuais taxas e custos extras, decorrentes de mudanças legislativas abruptas)

## Parâmetros de saída
- max_bid_lote: valor máximo de lance razoável para aquele item

## Operação aritmética
### Passos para Cálculo por Item
1. **Calcular Receita Esperada Ajustada (expected_rev)**:  
   expected_rev = ml_price_avg × (1 - sales_risk_buffer_rate)  
   (Se o item tiver quantidade qty_item >1, multiplique: expected_rev = ml_price_avg × qty_item × (1 - sales_risk_buffer_rate). Assuma qty_item=1 se não especificado.)

2. **Determinar aliqsn**:  
   - Se sn_mode = "fixed": aliqsn = 0.04  
   - Se sn_mode = "varialbe":  
     - Obtenha aliq_anexo_I e deducao_anexo_I da faixa com base em revenue_last_12months.  
     - aliqsn = [(revenue_last_12months × aliq_anexo_I - deducao_anexo_I) / revenue_last_12months]  
     (Isso é a alíquota efetiva %)

3. **Obter Alíquotas Pré-Venda**:  
   Consulte DB com ncm (ou fallback 0) para ipi, ii, icms, cbs, ibs.

4. **Calcular Lance Máximo por Item (max_bid_item)**:  
   - Defina o numerador (parte pós-venda ajustada pela margem):  
     numerador = expected_rev × (1 - gross_margin - aliqsn - ml_fee)  
   - Defina o denominador (parte pré-venda com buffer):  
     denominador = (1 + ipi + ii + icms + cbs + ibs) × (1 + cost_risk_buffer_rate)  
   - max_bid_item = numerador / denominador  
     (Isso garante que CMV = [max_bid_item × (1 + ipi + ii + icms + cbs + ibs) × (1 + cost_risk_buffer_rate)] + expected_rev × (aliqsn + ml_fee) = expected_rev × (1 - gross_margin), isolando max_bid_item.)

### Agregação para o Lote
- max_bid_lote = Σ max_bid_item (para todos itens no lote).

### Implementação Sugerida (Pseudocódigo para Automação)
```python
def calculate_max_bid_item(ml_price_avg, sales_risk_buffer_rate, sn_mode, revenue_last_12months, ml_fee, gross_margin, ncm, cost_risk_buffer_rate, qty_item=1):
    # Passo 1: Expected Rev
    expected_rev = ml_price_avg * qty_item * (1 - sales_risk_buffer_rate)
    
    # Passo 2: aliqsn
    if sn_mode == "fixed":
        aliqsn = 0.04
    elif sn_mode == "varialbe":
        # Determinar faixa (implemente lookup na tabela do DB com base em revenue_last_12months diretamente)
        aliq_anexo_I, deducao_anexo_I = get_faixa_from_db(revenue_last_12months)
        aliqsn = (revenue_last_12months * aliq_anexo_I - deducao_anexo_I) / revenue_last_12months if revenue_last_12months != 0 else 0
    
    # Passo 3: Alíquotas pré (consulta DB)
    ipi, ii, icms, cbs, ibs = get_aliquotas_from_db(ncm)
    
    # Passo 4: max_bid_item
    numerador = expected_rev * (1 - gross_margin - aliqsn - ml_fee)
    denominador = (1 + ipi + ii + icms + cbs + ibs) * (1 + cost_risk_buffer_rate)
    max_bid_item = numerador / denominador if denominador != 0 else 0
    
    return max_bid_item

# Para lote: max_bid_lote = sum(calculate_max_bid_item(...) for item in lote_itens)
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