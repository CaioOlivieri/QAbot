# agent/prompts.py
status: integrado
fontes: qabot/agent/prompts.py
atualizado: 2026-06-23
 
SYSTEM_PROMPT define o loop ReAct e as regras de geração de teste
(pytest, mockar I/O, nomes descritivos, "never fabricate behavior", alvo 80%).
 
"Available tools" lista todos os 9 tools: list_files, read_file, write_file,
run_command, parse_coverage, detect_api_endpoints, test_api_endpoint,
parse_pytest_failures, analyze_project_ast. Inclui seção "Workflow guidance"
com ordem recomendada de uso.

PR #23: a descrição de write_file no prompt agora declara a restrição — cria
arquivo de teste (test_*.py/*_test.py/conftest.py) dentro do projeto; qualquer
outro caminho é recusado. Alinha o prompt à contenção imposta no _dispatch
([[componentes/agent-core]]).
