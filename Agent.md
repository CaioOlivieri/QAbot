# AGENT.md — qabot v0.1

> source of truth — atualizar antes do código

---

## 1. propósito

Agente de IA especializado em QA automatizado para projetos Python.
Dado um repositório local, analisa cobertura, gera testes e produz relatório de qualidade.

- **Público-alvo:** startups sem equipe de QA dedicada
- **Motivação:** demonstrar capacidade real para vaga de QA Automation Specialist

---

## 2. interface

```bash
qabot analyze <project_path> [--output <report_path>]
```

- **Entrega:** CLI — terminal first, sem UI
- **Motivo:** integração natural com CI/CD; demo visual no terminal impacta mais em entrevistas

---

## 3. escopo

### dentro do escopo (v0.1)

- [x] analisar codebase Python e mapa de cobertura atual
- [x] identificar módulos com cobertura abaixo de 80%
- [x] gerar testes unitários para gaps identificados
- [x] escrever arquivos de teste no disco
- [x] rodar pytest e validar os testes gerados
- [x] gerar relatório markdown: cobertura antes/depois, bugs encontrados, sugestões

### fora do escopo (v0.1)

- [ ] ~~suporte a outras linguagens (JS, Go, etc.)~~
- [ ] ~~testes de performance ou carga~~
- [ ] ~~interface web ou dashboard~~
- [ ] ~~integração automática com CI/CD~~
- [ ] ~~repositórios remotos (GitHub, GitLab) — apenas path local~~

---

## 4. stack

| item | decisão |
|---|---|
| linguagem | Python 3.13 |
| LLM | Gemini 2.5 Flash via Google AI Studio (free tier) |
| LLM client | google-genai SDK |
| agente | loop ReAct minimal/custom — sem framework |
| testes | pytest + pytest-cov |
| packaging | uv + pyproject.toml |
| CI | GitHub Actions (Ubuntu) |
| linting | ruff |

---

## 5. arquitetura

```
qabot/
├── __main__.py        # entrypoint CLI
├── agent/
│   ├── core.py        # loop ReAct principal
│   ├── tools.py       # ferramentas do agente
│   ├── prompts.py     # system prompt QA specialist
│   └── report.py      # geração do relatório markdown
├── tools/
│   ├── fs.py          # list_files, read_file, write_file
│   └── runner.py      # run_command, parse_coverage
tests/
├── test_tools.py
├── test_agent.py
└── fixtures/
AGENT.md               # este arquivo
pyproject.toml
.env.example           # GEMINI_API_KEY=
```

---

## 6. fluxo do agente

1. recebe `project_path` como input
2. lista arquivos Python e testes existentes
3. executa `pytest --cov` → cobertura atual por módulo
4. lê módulos com gap (<80%) e testes existentes para contexto
5. gera testes para cada gap via LLM
6. escreve arquivos de teste no disco
7. executa `pytest --cov` novamente → cobertura final
8. gera relatório markdown com before/after + bugs encontrados

---

## 7. critérios de sucesso

- cobertura final > 80% no projeto-alvo
- 100% dos testes gerados passando sem intervenção manual
- relatório gerado automaticamente em markdown
- demo funcional no AlertaVida documentada no README

---

## 8. princípios de código

- type hints em tudo — sem exceções
- zero comentários óbvios — código se explica por nomes e tipos
- funções puras onde possível — estado explícito, sem surpresas
- sem framework de agente — loop ReAct implementado do zero
- AGENT.md atualizado antes de qualquer mudança de arquitetura

---

## 9. histórico de mudanças

| data | mudança |
|---|---|
| 2026-05-27 | criação inicial do AGENT.md |