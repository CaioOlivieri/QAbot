# Layer 0 — Costura (wiring)
status: concluída
atualizado: 2026-06-09
 
Maior valor, menor risco: ligar o que já existe e está testado. Sem reescrever.
 
Passos executados (verificados em [[raw/layer0-pytest-run.txt]] e
[[_estado-de-integracao]]):
1. detect_api_endpoints e test_api_endpoint adicionados ao system prompt
   e à seção "Workflow guidance".
2. analyze_project_ast e parse_pytest_failures importados em core.py,
   expostos no _dispatch e prompt; achados acumulados em Findings.
3. generate_report chamado deterministicamente no fim de run_agent;
   relatório escrito em reports/qa_report.md.
4. Drift de README.md e AGENT.md corrigido.
 
Lembrete de disciplina: cada afirmação do relatório deve vir de execução real
salva em raw/ (ver [[_schema]]).
