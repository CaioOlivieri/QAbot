# tools/runner.py
status: parcial
fontes: qabot/tools/runner.py
atualizado: 2026-06-02
 
- run_command(cmd, cwd) -> (retcode, stdout, stderr)  — integrado
- parse_coverage(output) -> dict[modulo, pct]          — integrado
- parse_pytest_failures(output) -> list[dict]          — ORFAO-TOTAL
 
parse_pytest_failures: máquina de estados (SCANNING / IN_FAILURES / IN_TEST),
severidade crítico vs warning conforme a falha origina em arquivo de produção
ou de teste. Existe e é testado, mas não é importado em core.py.
Saída alimenta `dynamic_bugs` de [[componentes/agent-report]].
