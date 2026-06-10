# Estado de Integração
status: verificado
fontes: qabot/agent/core.py, qabot/agent/prompts.py (lidos do repo, branch main)
atualizado: 2026-06-09
 
Verdade única sobre o que o agente realmente usa. README/AGENT.md divergem disto.
 
| Capacidade            | Função(ões)                          | No _dispatch? | No prompt? | Status            |
| --------------------- | ------------------------------------ | ------------- | ---------- | ----------------- |
| Listar/ler/escrever   | list_files, read_file, write_file    | sim           | sim        | integrado         |
| Rodar comando         | run_command                          | sim           | sim        | integrado         |
| Parsear cobertura     | parse_coverage                       | sim           | sim        | integrado         |
| Classificar falhas    | parse_pytest_failures                | sim           | sim        | integrado         |
| Bug estático (AST)    | analyze_file_ast/analyze_project_ast | sim           | sim        | integrado         |
| Teste de API          | detect_api_endpoints/test_api_endpoint| sim           | sim        | integrado         |
| Relatório             | generate_report                      | NÃO (não é tool)| NÃO        | integrado         |
 
Costura completa em [[projetos/layer-0-wiring]] (2026-06-09).
`run_agent` agora acumula achados estruturados no loop, chama
`generate_report` no fim e escreve `reports/qa_report.md` em disco.
 
## Drift de documentação (corrigido na Layer 0, 2026-06-09)
README.md:
- "What it does" passos 8 (detecta bugs) e 9 (relatório) — agora verdadeiros.
- "Design decisions" descreve "Bug detection in two layers" como ativo — agora verdadeiro.
- "Architecture" agora inclui tools/api.py e tools/analyzer.py na árvore.
AGENT.md:
- "Pending" removido — GitHub Issues são a fonte única de trabalho pendente.
- "Architecture" agora lista todos os 8 módulos com papel de uma linha cada.
- "Knowledge base" adicionado com regras de leitura de wiki antes de mudanças.
