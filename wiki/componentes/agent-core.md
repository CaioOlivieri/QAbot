# agent/core.py
status: integrado
fontes: qabot/agent/core.py
atualizado: 2026-06-19
 
Loop ReAct. `run_agent(project_path)` chama o LLM (gemini-2.5-flash-lite),
parseia JSON {thought, action, action_input} ou {thought, final_answer},
despacha via `_dispatch` e itera (máx. 25). Tem retry com sleep 60s em 429.
 
`_dispatch` expõe: list_files, read_file, write_file, run_command,
parse_coverage, detect_api_endpoints, test_api_endpoint, parse_pytest_failures,
analyze_project_ast.
 
Acumula achados estruturados (Findings) durante o loop e chama
generate_report no fim, escrevendo o relatório em
<project_path>/reports/qa_report.md (via _write_report).

Layer 1.5: as actions report_suspected_bug/resolve_suspected_bug alimentam
Findings.suspected_bugs; _resolve_suspicion confirma só se o último run de teste
capturado falhou (parse_pytest_failures), senão descarta.
