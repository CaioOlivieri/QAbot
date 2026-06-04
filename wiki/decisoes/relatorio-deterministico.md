# Relatório como passo determinístico
status: proposta
 
## Proposta (de sessão anterior, NÃO implementada)
`generate_report` deve rodar SEMPRE no fim de `run_agent`, consumindo achados
estruturados acumulados ao longo do loop — em vez de ser uma tool que o LLM
escolhe (ou não) chamar.
 
## Realidade atual (verificada)
`generate_report` não é importado nem chamado em core.py. `run_agent` retorna
texto livre do LLM. Logo: proposta pendente, não decisão tomada.
 
## Assinatura que o report exige (define o que a costura precisa produzir)
generate_report(project_path, coverage_before, coverage_after,
                ast_bugs, dynamic_bugs, api_results) -> str
- coverage_*  <- parse_coverage
- ast_bugs    <- analyze_project_ast
- dynamic_bugs<- parse_pytest_failures
- api_results <- test_api_endpoint
