# agent/core.py
status: integrado
fontes: qabot/agent/core.py
atualizado: 2026-06-02
 
Loop ReAct. `run_agent(project_path)` chama o LLM (gemini-2.5-flash-lite),
parseia JSON {thought, action, action_input} ou {thought, final_answer},
despacha via `_dispatch` e itera (máx. 10). Tem retry com sleep 60s em 429.
 
`TOOLS`/`_dispatch` expõem: list_files, read_file, write_file, run_command,
parse_coverage, detect_api_endpoints, test_api_endpoint.
 
Lacuna-chave: importa parse_coverage/run_command do runner, mas NÃO importa
parse_pytest_failures, analyzer nem report. Ver [[_estado-de-integracao]].
