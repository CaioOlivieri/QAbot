# Layer 0 — Costura (wiring)
status: aberta
atualizado: 2026-06-02
 
Maior valor, menor risco: ligar o que já existe e está testado. Sem reescrever.
 
Passos (todos verificáveis em [[_estado-de-integracao]]):
1. Adicionar detect_api_endpoints e test_api_endpoint ao system prompt
   ([[componentes/tools-api]]).
2. Importar e usar analyze_project_ast e parse_pytest_failures, acumulando
   achados estruturados durante o loop.
3. Implementar [[decisoes/relatorio-deterministico]]: chamar generate_report
   no fim de run_agent e ESCREVER o markdown em disco.
4. Corrigir o drift de README e AGENT.md para refletir o real.
 
Lembrete de disciplina: cada afirmação do relatório deve vir de execução real
salva em raw/ (ver [[_schema]]).
