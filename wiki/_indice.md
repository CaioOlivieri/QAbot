# Índice — QAbot
 
Mapa de navegação. Comece por [[_estado-de-integracao]] — é o que o README
deveria refletir e hoje não reflete.
 
Stack (de pyproject.toml): Python >=3.13; google-genai, python-dotenv;
dev: pytest, pytest-cov, ruff. Modelo: gemini-2.5-flash-lite. API via httpx.
 
## Estado / meta
- [[_estado-de-integracao]] — tabela tool-por-tool: integrado vs órfão
 
## Decisões
- [[decisoes/escopo-do-agente]]            (rascunho)
- [[decisoes/relatorio-deterministico]]    (proposta, NÃO implementada)
- [[decisoes/react-unico-vs-multiagente]]  (aberta)
 
## Componentes
- [[componentes/agent-core]]      integrado
- [[componentes/agent-prompts]]   integrado (lista só 5 tools — lacuna)
- [[componentes/agent-report]]    orfao-total
- [[componentes/tools-fs]]        integrado
- [[componentes/tools-runner]]    parcial (parse_pytest_failures órfão)
- [[componentes/tools-api]]       orfao-na-pratica
- [[componentes/tools-analyzer]]  orfao-total
 
## Padrões
- [[padroes/convencoes-de-teste]]
- [[padroes/workflow-git]]
- [[padroes/harness-handoff]]
 
## Projetos (roadmap)
- [[projetos/layer-0-wiring]]
- [[projetos/layer-1-test-agent-ci]]
- [[projetos/layer-2-github-integration]]
- [[projetos/layer-3-state-persistence]]
