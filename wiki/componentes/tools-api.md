# tools/api.py
status: integrado
fontes: qabot/tools/api.py
atualizado: 2026-06-09
 
- detect_api_endpoints(project_path) -> list[str]
- test_api_endpoint(url, method, expected_status) -> dict  (usa httpx)
 
Ambas estão no TOOLS, no _dispatch de core.py E na seção "Available tools"
do system prompt. O LLM pode chamá-las. Saída alimenta `api_results`
do relatório.
