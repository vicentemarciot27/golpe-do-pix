# RFB NCM

API que retorna dados tributários dos produtos a partir da pesquisa na base da Receita Federal.

## Estado do MVP
- Enquanto a integração oficial não fica pronta, respondemos com um padrão configurável.
- O fallback é controlado via `config`, permitindo ajustar alíquotas padrão rapidamente.

## Próximas etapas
- Implementar o conector real para a base da Receita.
- Ajustar o schema compartilhado em `shared` para incluir regras fiscais por NCM.
