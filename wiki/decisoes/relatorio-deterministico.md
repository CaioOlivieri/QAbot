# Relatório como passo determinístico
status: implementada
fontes: wiki/raw/layer0-pytest-run.txt
atualizado: 2026-06-09
 
## Decisão implementada (Layer 0, 2026-06-09)
`generate_report` roda SEMPRE no fim de `run_agent` (core.py), consumindo
achados estruturados acumulados ao longo do loop via Findings — em vez de ser
uma tool que o LLM escolhe (ou não) chamar.
 
Relatório é escrito em reports/qa_report.md.
 
## Assinatura
generate_report(project_path, coverage_before, coverage_after,
                ast_bugs, dynamic_bugs, api_results) -> str
- coverage_*  <- parse_coverage
- ast_bugs    <- analyze_project_ast
- dynamic_bugs<- parse_pytest_failures
- api_results <- test_api_endpoint
