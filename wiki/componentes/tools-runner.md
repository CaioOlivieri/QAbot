# tools/runner.py
status: integrado
fontes: qabot/tools/runner.py
atualizado: 2026-06-09
 
- run_command(cmd, cwd) -> (retcode, stdout, stderr)  — integrado
- parse_coverage(output) -> dict[modulo, pct]          — integrado
- parse_pytest_failures(output) -> list[dict]          — integrado
 
parse_pytest_failures: máquina de estados (SCANNING / IN_FAILURES / IN_TEST),
severidade crítico vs warning conforme a falha origina em arquivo de produção
ou de teste. Importado e exposto em core.py, alimenta `dynamic_bugs` do
relatório.
