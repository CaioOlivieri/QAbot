# Convenções de teste
status: verificado
fontes: qabot/tests/test_tools.py (24 testes)
atualizado: 2026-06-02
 
- pytest (não unittest). Funções `test_<unidade>_<comportamento>() -> None`.
- Nomes descritivos do comportamento (ex.: test_parse_coverage_excludes_total).
- Sem I/O real: mock via unittest.mock (patch, mock_open, MagicMock);
  httpx mockado em qabot.tools.api.httpx.request.
- Cobrir happy path, edge e erro (o prompt do agente exige o mesmo).
- Estrutura arrange-act-assert implícita (sem comentários AAA).
- pytest config: addopts="--cov=qabot --cov-report=term-missing".
