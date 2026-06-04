# Estado de Integração
status: verificado
fontes: qabot/agent/core.py, qabot/agent/prompts.py (lidos do repo, branch main)
atualizado: 2026-06-02
 
Verdade única sobre o que o agente realmente usa. README/AGENT.md divergem disto.
 
| Capacidade            | Função(ões)                          | No _dispatch? | No prompt? | Status            |
| --------------------- | ------------------------------------ | ------------- | ---------- | ----------------- |
| Listar/ler/escrever   | list_files, read_file, write_file    | sim           | sim        | integrado         |
| Rodar comando         | run_command                          | sim           | sim        | integrado         |
| Parsear cobertura     | parse_coverage                       | sim           | sim        | integrado         |
| Classificar falhas    | parse_pytest_failures                | NÃO           | não        | orfao-total       |
| Bug estático (AST)    | analyze_file_ast/analyze_project_ast | NÃO           | não        | orfao-total       |
| Teste de API          | detect_api_endpoints/test_api_endpoint| sim          | NÃO        | orfao-na-pratica  |
| Relatório             | generate_report                      | NÃO           | não        | orfao-total       |
 
Consequência: `run_agent` devolve o `final_answer` em texto livre do LLM;
nenhum relatório vai pro disco, nenhum bug é detectado pelos mecanismos
construídos para isso. Costura = [[projetos/layer-0-wiring]].
 
## Drift de documentação (corrigir junto da costura)
README.md:
- "What it does" passos 8 (detecta bugs) e 9 (relatório) descritos como se
  existissem — ambos órfãos.
- "Design decisions" descreve "Bug detection in two layers" como ativo — não é.
- "Architecture" omite tools/api.py e tools/analyzer.py da árvore (lista só
  fs.py e runner.py em tools/).
AGENT.md:
- "Pending" lista report.py (#1), test_tools.py (parte do #3) e api.py (#5)
  como pendentes, mas os três já existem. Reais hoje: só test_agent.py
  (resto do #3) e a CI (#4).
- "Architecture" lista só api.py e analyzer.py — visão parcial e desatualizada.
- Viola a própria regra "update this file before changing architecture".
