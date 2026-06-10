# agent/report.py
status: integrado
fontes: qabot/agent/report.py, wiki/raw/layer0-pytest-run.txt
atualizado: 2026-06-09
 
`generate_report(...) -> str` (markdown puro) + helpers privados
(_section_coverage, _section_ast_bugs, _section_dynamic_bugs, _section_api,
_compute_score). Score = 40% cobertura + 40% bugs + 20% API
(bug_score = 100 - 10/crítico - 3/warning; api_score = % aprovados).
 
Chamado deterministicamente no fim de run_agent (core.py). Escreve
reports/qa_report.md em disco. Consome as saídas de parse_coverage,
analyze_project_ast, parse_pytest_failures e test_api_endpoint via Findings.
