# agent/report.py
status: orfao-total
fontes: qabot/agent/report.py
atualizado: 2026-06-02
 
`generate_report(...) -> str` (markdown puro) + helpers privados
(_section_coverage, _section_ast_bugs, _section_dynamic_bugs, _section_api,
_compute_score). Score = 40% cobertura + 40% bugs + 20% API
(bug_score = 100 - 10/crítico - 3/warning; api_score = % aprovados).
 
Construído e testado, mas nunca chamado por core.py. É o ponto de convergência:
sua assinatura consome exatamente as saídas dos outros órfãos. Ver
[[decisoes/relatorio-deterministico]] e [[projetos/layer-0-wiring]].
