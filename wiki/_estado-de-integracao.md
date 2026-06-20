# Estado de Integração
status: verificado
fontes: qabot/agent/core.py, qabot/agent/prompts.py (lidos do repo, branch main)
atualizado: 2026-06-15
 
Verdade única sobre o que o agente realmente usa. README/AGENT.md divergem disto.
 
| Capacidade            | Função(ões)                          | No _dispatch? | No prompt? | Status            |
| --------------------- | ------------------------------------ | ------------- | ---------- | ----------------- |
| Listar/ler/escrever   | list_files, read_file, write_file    | sim           | sim        | integrado         |
| Rodar comando         | run_command                          | sim           | sim        | integrado         |
| Parsear cobertura     | parse_coverage                       | sim           | sim        | integrado         |
| Classificar falhas    | parse_pytest_failures                | sim           | sim        | integrado         |
| Bug estático (AST)    | analyze_file_ast/analyze_project_ast | sim           | sim        | integrado         |
| Bug semântico (LLM)   | report_suspected_bug/resolve_suspected_bug | sim     | sim        | implementado      |
| Teste de API          | detect_api_endpoints/test_api_endpoint| sim           | sim        | integrado         |
| Relatório             | generate_report                      | NÃO (não é tool)| NÃO        | integrado         |
 
Costura completa em [[projetos/layer-0-wiring]] (2026-06-09).
`run_agent` agora acumula achados estruturados no loop, chama
`generate_report` no fim e escreve o relatório em
`<project_path>/reports/qa_report.md` (via `_write_report`).
 
## Drift de documentação (corrigido na Layer 0, 2026-06-09)
README.md:
- "What it does" passos 8 (detecta bugs) e 9 (relatório) — agora verdadeiros.
- "Design decisions" descreve "Bug detection in two layers" como ativo — agora verdadeiro.
- "Architecture" agora inclui tools/api.py e tools/analyzer.py na árvore.
AGENT.md:
- "Pending" removido — GitHub Issues são a fonte única de trabalho pendente.
- "Architecture" agora lista todos os 8 módulos com papel de uma linha cada.
- "Knowledge base" adicionado com regras de leitura de wiki antes de mudanças.

## Robustez de JSON (2026-06-15)
`_call_llm` usa `response_mime_type="application/json"` e o parsing inline foi
trocado por `_parse_agent_json` (puro, tolerante a cercas/prosa/vírgula final/
newline literal). Causa raiz dos aborts de JSON resolvida; verificado por
execução real. Detalhe em [[decisoes/json-mode-e-parser-robusto]].

## Detecção semântica — Layer 1.5 (2026-06-19)
report_suspected_bug + resolve_suspected_bug no _dispatch e no prompt;
Findings.suspected_bugs; confirmação por execução (_resolve_suspicion só confirma
se o último run de teste falhou). Confirmados contam no score; suspeitos vão para
"For Review" (fora do score). E2e ao vivo PENDENTE (quota Gemini) — por isso
"implementado", não "verificado". Detalhe em
[[projetos/layer-1-5-deteccao-semantica]].
