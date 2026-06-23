# Estado de Integração
status: verificado
fontes: qabot/agent/core.py, qabot/agent/prompts.py (lidos do repo, branch main)
atualizado: 2026-06-23
 
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

## Endurecimento de segurança & faxina de qualidade (PR #23, 2026-06-23)
Passada de manutenibilidade (rebase-merge, 9 commits). Única mudança de
comportamento *wired*: `write_file` agora é **contido** na fronteira de confiança
do `_dispatch` — `_resolve_write_path` recusa caminho que escape do `project_path`
ou que não seja arquivo de teste (`test_*.py`, `*_test.py`, `conftest.py`). Antes
aceitava qualquer caminho; a regra "só cria teste, nunca edita fonte" vivia só no
prompt e não era imposta. Também corrige caminho relativo que resolvia contra o
CWD do processo, não o projeto-alvo. O prompt passou a declarar a restrição.

Demais commits são internos, sem mudança de wiring: dedup das seções do relatório
(`_by_severity` + `_section_suspicions`), `detect_api_endpoints` reusa
`list_files`, acumulação de Findings extraída para `_accumulate_findings` (pura,
testável), código morto removido (backports.zoneinfo, parâmetro `rel`) e rede de
testes nova para as linhas do relatório e o entrypoint CLI.

Verificado por execução real: [[raw/pr23-quality-cleanup-checks]] — ruff format e
check limpos, 63 testes, cobertura total 90% (era 80%). CI verde no PR #23 (merged).
