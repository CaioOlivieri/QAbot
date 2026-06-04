# tools/analyzer.py
status: orfao-total
fontes: qabot/tools/analyzer.py
atualizado: 2026-06-02
 
Análise estática via AST:
- analyze_file_ast(filepath) -> list[dict]
- analyze_project_ast(project_path) -> list[dict]
Detecta (verificado pelos testes): bare except, except amplo e handler
silencioso. NÃO é importado em core.py — nenhum bug estático é detectado em
runtime hoje. Saída alimenta `ast_bugs` de [[componentes/agent-report]].
 
Nota: AGENT.md menciona "AST + LLM semantic"; o código atual implementa só a
parte AST. A camada semântica via LLM não existe ainda — não documentar como se
existisse.
