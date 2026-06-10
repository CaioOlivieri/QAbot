# tools/analyzer.py
status: integrado
fontes: qabot/tools/analyzer.py
atualizado: 2026-06-09
 
Análise estática via AST:
- analyze_file_ast(filepath) -> list[dict]
- analyze_project_ast(project_path) -> list[dict]
Detecta (verificado pelos testes): bare except, except amplo e handler
silencioso. Importado e exposto em core.py via analyze_project_ast.
Saída alimenta `ast_bugs` do relatório.
 
Nota: AGENT.md menciona "AST + LLM semantic"; o código atual implementa só a
parte AST. A camada semântica via LLM não existe ainda — não documentar como se
existisse.
