# Índice — QAbot
 
Mapa de navegação. Comece por [[_estado-de-integracao]] — é o que o README
deveria refletir e hoje não reflete.
 
Stack (de pyproject.toml): Python >=3.13; google-genai, python-dotenv;
dev: pytest, pytest-cov, ruff. Modelo: gemini-2.5-flash-lite. API via httpx.
 
## Estado / meta
- [[_estado-de-integracao]] — tabela tool-por-tool: integrado vs órfão
 
## Decisões
- [[decisoes/escopo-do-agente]]            (rascunho)
- [[decisoes/relatorio-deterministico]]    (implementada)
- [[decisoes/react-unico-vs-multiagente]]  (aberta)
 
## Componentes
- [[componentes/agent-core]]      integrado
- [[componentes/agent-prompts]]   integrado
- [[componentes/agent-report]]    integrado
- [[componentes/tools-fs]]        integrado
- [[componentes/tools-runner]]    integrado
- [[componentes/tools-api]]       integrado
- [[componentes/tools-analyzer]]  integrado
 
## Padrões
- [[padroes/convencoes-de-teste]]
- [[padroes/workflow-git]]
- [[padroes/harness-handoff]]
 
## Projetos (roadmap)
- [[projetos/layer-0-wiring]]
- [[projetos/layer-1-test-agent-ci]]
- [[projetos/layer-1-5-deteccao-semantica]]  (proposta)
- [[projetos/layer-2-github-integration]]
- [[projetos/layer-3-state-persistence]]
