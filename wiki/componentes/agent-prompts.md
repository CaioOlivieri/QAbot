# agent/prompts.py
status: integrado
fontes: qabot/agent/prompts.py
atualizado: 2026-06-02
 
SYSTEM_PROMPT define o loop ReAct e as regras de geração de teste
(pytest, mockar I/O, nomes descritivos, "never fabricate behavior", alvo 80%).
 
Lacuna: a seção "Available tools" lista APENAS list_files, read_file,
write_file, run_command, parse_coverage. detect_api_endpoints e
test_api_endpoint estão no _dispatch mas ausentes aqui — por isso o LLM
nunca os chama (orfao-na-pratica). Ver [[componentes/tools-api]].
