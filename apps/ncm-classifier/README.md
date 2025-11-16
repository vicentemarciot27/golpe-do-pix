# NCM Classifier

Classificador que converte descrições de produtos no código NCM correspondente.

## Características
- Utiliza LLMs para interpretar textos livres e sugerir o NCM mais provável.
- Pode combinar regras heurísticas do `shared` para validar o resultado.
- Expõe a classificação para consumo direto por `rfb-ncm` e outros serviços.

## Roadmap curto
- Definir dataset inicial para few-shot prompting.
- Implementar métricas de confiança e explicabilidade no retorno.
