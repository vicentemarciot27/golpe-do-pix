# Max Bid UI - Interface Streamlit

Interface web para calcular o lance máximo em leilões da Receita Federal.

## Como usar

### Opção 1: Via Python
```bash
# No diretório raiz do projeto
python -m streamlit run apps/max_bid/ui/__main__.py
```

### Opção 2: Via script helper
```bash
# No diretório raiz do projeto
python apps/max_bid/ui/run.py
```

### Opção 3: Via PowerShell (Windows)
```powershell
# No diretório raiz do projeto
.\venv\Scripts\Activate.ps1
streamlit run apps/max_bid/ui/__main__.py
```

## Funcionalidades

### 🔧 Configurações (Sidebar)

#### Simples Nacional
- **Fixed**: Usa taxa padrão de 4% (primeira faixa)
- **Variable**: Calcula taxa baseada na receita dos últimos 12 meses (faixas progressivas)
- **Custom Fixed**: Permite definir taxa e dedução personalizadas

#### NCM (Impostos)
- **Fixed**: Usa taxas padrão (IPI: 20%, II: 20%, ICMS: 18%, CBS: 9.2%, IBS: 8.8%)
- **Variable**: Busca taxas específicas por código NCM (quando implementado)
- **Custom Fixed**: Permite definir todas as taxas manualmente

### 📝 Parâmetros do Item

#### Venda (Mercado Livre)
- **Preço Médio ML**: Preço médio de venda do produto no Mercado Livre
- **Taxa ML**: Comissão do Mercado Livre (padrão 19%, pode variar de 10% a 19%)
- **Buffer de Risco de Venda**: Margem de segurança para reembolsos e perdas (padrão 10%)

#### Margem e Receita
- **Margem Bruta**: Margem de lucro desejada (padrão 30%)
- **Receita 12 meses**: Receita dos últimos 12 meses (usado no modo Variable do Simples Nacional)

#### Produto
- **Código NCM**: Código NCM do produto (use "0" para valores default)
- **Quantidade**: Quantidade de itens no lote
- **Buffer de Risco de Custo**: Margem de segurança para custos imprevistos (padrão 5%)

### 📊 Resultados

#### Métricas Principais
- **Lance Máximo**: Valor máximo que você deve ofertar
- **Receita Esperada**: Receita esperada após ajustes de risco
- **Lucro Bruto**: Lucro esperado e margem percentual

#### Detalhamento
- **Impostos NCM**: Alíquotas e valores em reais de cada imposto (IPI, II, ICMS, CBS, IBS)
- **Simples Nacional**: Taxa efetiva e valor calculado
- **Breakdown Completo**: Fórmula detalhada e resumo de todos os custos

## Fórmula de Cálculo

```
Receita Esperada = Preço ML × Quantidade × (1 - Buffer Venda)

Numerador = Receita Esperada × (1 - Margem - Simples Nacional - Taxa ML)

Denominador = (1 + IPI + II + ICMS + CBS + IBS) × (1 + Buffer Custo)

Lance Máximo = Numerador / Denominador
```

## Exemplos de Uso

### Exemplo 1: Cálculo Básico (Fixed)
- Preço ML: R$ 1.000,00
- Modo: Fixed (ambos)
- Margem: 30%
- Resultado: Lance Máximo ≈ R$ 275,00

### Exemplo 2: Com Receita Variable
- Preço ML: R$ 5.000,00
- Receita 12 meses: R$ 300.000,00
- Modo Simples Nacional: Variable (faixa 2)
- Resultado: Taxa efetiva ≈ 7.3% ao invés de 4%

### Exemplo 3: Custom Fixed
- Defina suas próprias taxas de impostos
- Útil para simulações e análises de sensibilidade

## Arquitetura

A UI segue a arquitetura hexagonal do projeto:

```
UI (Streamlit)
    ↓
MaxBidCalculator (Service)
    ↓
Calculators (SimplesNacional + NCM)
    ↓
Storages (via Ports/Adapters)
```

### Dependências
- `streamlit`: Interface web
- `MaxBidCalculator`: Lógica de cálculo
- `LocalNCMStorage`: Armazenamento em memória de taxas NCM
- `LocalRevenueStorage`: Armazenamento em memória de dados de receita

## Troubleshooting

### Erro: ModuleNotFoundError
Certifique-se de estar executando do diretório raiz do projeto e que o venv está ativado.

### Erro: Port already in use
Use uma porta diferente:
```bash
streamlit run apps/max_bid/ui/__main__.py --server.port=8502
```

### Valores estranhos no resultado
Verifique se:
- Todas as taxas estão em porcentagem (serão divididas por 100 internamente)
- A margem não é muito alta para o preço de venda
- O buffer de risco não está muito alto

