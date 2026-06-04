# tools/api.py
status: orfao-na-pratica
fontes: qabot/tools/api.py
atualizado: 2026-06-02
 
- detect_api_endpoints(project_path) -> list[str]
- test_api_endpoint(url, method, expected_status) -> dict  (usa httpx)
 
Ambas estão no TOOLS e no _dispatch de core.py, MAS ausentes da seção
"Available tools" do system prompt — então o LLM nunca decide chamá-las.
Correção barata: adicionar as duas ao prompt. Saída alimenta `api_results`
de [[componentes/agent-report]].
