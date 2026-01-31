"""
Max Bid Calculator - Home Page
Entry point for the Streamlit application
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.max_bid.ui import constants

# Page config
st.set_page_config(
    page_title=constants.PAGE_TITLE,
    page_icon=constants.PAGE_ICON,
    layout=constants.LAYOUT,
    initial_sidebar_state=constants.SIDEBAR_STATE,
)

# Home page
st.title("💰 Max Bid Calculator")
st.markdown("### Bem-vindo ao Calculador de Lance Máximo!")

st.markdown("""
Este aplicativo ajuda você a calcular o lance máximo para leilões da Receita Federal,
considerando todas as variáveis tributárias e de mercado.

#### 📦 Modos Disponíveis:

**1. Lote (Múltiplos Itens)** - *Recomendado*
- Calcule o lance para um lote completo com vários itens
- Visualize o breakdown individual de cada item
- Obtenha o total consolidado do lote

**2. Item Único**
- Calcule o lance para um item específico
- Análise detalhada de custos e margens

👈 **Selecione uma opção no menu lateral para começar!**
""")

st.markdown("---")

# Features overview
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    #### ✨ Funcionalidades
    
    - 🔒 **Fixed Mode**: Usa taxas padrão
    - 📊 **Variable Mode**: Calcula por faixa de receita
    - ✏️ **Custom Mode**: Defina suas próprias taxas
    - 💰 **Cálculo Preciso**: Considera todos os impostos
    - 📈 **Margem Configurável**: Defina sua margem desejada
    """)

with col2:
    st.markdown("""
    #### 🎯 Impostos Considerados
    
    - **Simples Nacional**: Taxa progressiva ou fixa
    - **IPI**: Imposto sobre Produtos Industrializados
    - **II**: Imposto de Importação
    - **ICMS**: Imposto sobre Circulação de Mercadorias
    - **CBS/IBS**: Novos impostos da Reforma Tributária
    """)

st.markdown("---")

# Quick start guide
with st.expander("📚 Guia Rápido", expanded=False):
    st.markdown("""
    ### Como Usar:
    
    1. **Escolha o modo** (Lote ou Item Único) no menu lateral
    2. **Configure os impostos** (Fixed, Variable ou Custom)
    3. **Preencha os parâmetros**:
       - Preço médio no Mercado Livre
       - Margem líquida desejada (lucro após todos os custos)
       - Receita dos últimos 12 meses (0 é o valor padrão para valores default)
       - Código NCM do produto (0 é o valor padrão para valores default)
    4. **Clique em Calcular** e veja o resultado!
    
    ### Dicas:
    
    - Use **Fixed Mode** para cálculos rápidos com valores padrão
    - Use **Variable Mode** para precisão baseada na sua receita real ou no NCM específico do item (será feita uma busca no banco de dados. Caso não encontre, será enviada uma mensagem de erro.)
    - Use **Custom Mode** para cenários específicos
    
    ### ⚠️ Sobre Margens e Lucros:
    
    O cálculo distingue corretamente:
    - **Lucro Bruto** = Receita - CMV (Lance + Impostos NCM)
    - **Lucro Operacional** = Lucro Bruto - Despesas Operacionais (Taxa ML)
    - **Lucro Líquido** = Lucro Operacional - Impostos sobre Receita (Simples Nacional)
    
    A **Margem Líquida Desejada** é o que você quer ganhar no final. A **Margem Real** 
    geralmente é maior devido aos **buffers de segurança**, que reduzem seu lance!
    """)

# Footer
st.markdown("---")
st.markdown(
    """
<div style='text-align: center; color: gray; font-size: 0.9em;'>
    <p>Max Bid Calculator - Golpe do Pix</p>
    <p>Calcule lances inteligentes considerando todas as variáveis tributárias e de mercado</p>
</div>
""",
    unsafe_allow_html=True,
)


if __name__ == "__main__":
    pass
