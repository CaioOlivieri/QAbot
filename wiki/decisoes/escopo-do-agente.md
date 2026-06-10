# Escopo do agente
status: rascunho
 
## O que faz hoje (verificado no código)
Agente ReAct single-loop (máx. 10 iterações) que, sobre um projeto Python local:
lista arquivos, roda comandos, parseia cobertura, lê/escreve arquivos, e encerra
com um resumo em texto livre. Stateless e one-shot.
 
## O que NÃO faz (verificado) 
- Não persiste estado entre execuções (sem tracking prod-vs-QA).
- Não integra com Git/GitHub.
- Não usa de fato analyzer, parse_pytest_failures, teste de API nem report.
 
## Fronteira normativa — CONFIRMAR COM O CAIO
O "o que ele deliberadamente não deve fazer" (limites de escopo do portfólio)
ainda não foi definido. Preencher após decisão.
