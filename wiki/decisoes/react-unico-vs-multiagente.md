# ReAct único vs. multi-agente
status: aberta
 
Decisão em aberto, sem desfecho registrado.
 
## Opção A — manter ReAct single-loop (atual)
Simples, já funciona, fácil de testar. Risco: o LLM perde o fio em tarefas
longas e não orquestra bem múltiplas capacidades.
 
## Opção B — sugestão do Gemini: multi-agente + MCP + RAG + roteamento
Pipeline fragmentado (ex.: agente de commits/PRs, gerador, executor, relator).
Promete escala e menos perda de contexto. Custo: complexidade, e MCP de GitHub
hoje indisponível na interface web do Claude (blocker de OAuth/GitHub App).
 
## Observação honesta
Antes de trocar de arquitetura, a Layer 0 (costurar o que já existe) entrega a
maior parte do valor com risco baixo. Decidir A vs B depois da costura.
