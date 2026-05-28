# AGENT.md — qabot v0.1

> source of truth — atualizar antes do código

---

## 1. propósito

Agente de IA especializado em QA automatizado para projetos Python.
Dado um repositório local, analisa cobertura, gera testes, detecta bugs e produz relatório de qualidade.

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
- [ ] detectar bugs críticos antes da produção
- [ ] gerar relatório markdown: cobertura antes/depois, bugs encontrados, sugestões

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
| LLM | Gemini 2.5 Flash Lite via Google AI Studio (free tier) |
| LLM client | google-genai SDK |
| agente | loop ReAct minimal/custom — sem framework |
| testes | pytest + pytest-cov |
| packaging | uv + pyproject.toml |
| CI | GitHub Actions (Ubuntu) — pendente |
| linting | ruff |

---

## 5. arquitetura

```
qabot/
├── __main__.py        # entrypoint CLI ✓
├── agent/
│   ├── core.py        # loop ReAct principal ✓
│   ├── prompts.py     # system prompt QA specialist ✓
│   └── report.py      # geração do relatório markdown ✗ pendente
└── tools/
    ├── fs.py          # list_files, read_file, write_file ✓
    └── runner.py      # run_command, parse_coverage ✓
tests/
├── test_tools.py      ✗ pendente
├── test_agent.py      ✗ pendente
└── fixtures/          ✗ pendente
AGENT.md
pyproject.toml
README.md
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
8. detecta bugs críticos — falhas de asserção, edge cases não cobertos, exceções silenciosas
9. gera relatório markdown com before/after + bugs encontrados

---

## 7. critérios de sucesso

- cobertura final > 80% no projeto-alvo
- 100% dos testes gerados passando sem intervenção manual
- 100% dos bugs críticos detectados antes da produção
- relatório markdown gerado automaticamente
- demo funcional no AlertaVida documentada no README

---

## 8. detecção de bugs — estratégia

A detecção de bugs será feita em duas camadas:

**Camada 1 — estática (via LLM):**
O agente lê cada módulo com gap de cobertura e analisa o código em busca de:
- exceções silenciosas (`except: pass`)
- edge cases sem tratamento (divisão por zero, None não verificado)
- invariantes violadas

**Camada 2 — dinâmica (via pytest):**
Testes gerados que falham ao rodar revelam bugs reais.
O agente classifica falhas como bugs críticos quando envolvem:
- dados corrompidos
- exceções não tratadas em produção
- comportamento divergente entre o código e sua documentação

Resultado: lista de bugs no relatório final com severidade e localização.

---

## 9. pendências por prioridade

| prioridade | item |
|---|---|
| 1 | `agent/report.py` — geração do relatório markdown |
| 2 | detecção de bugs — implementar camadas 1 e 2 |
| 3 | `tests/test_tools.py` — testes unitários das tools |
| 4 | `tests/test_agent.py` — testes do loop ReAct |
| 5 | GitHub Actions CI |

---

## 10. princípios de código

- type hints em tudo — sem exceções
- zero comentários óbvios — código se explica por nomes e tipos
- funções puras onde possível — estado explícito, sem surpresas
- sem framework de agente — loop ReAct implementado do zero
- AGENT.md atualizado antes de qualquer mudança de arquitetura

---

## 11. histórico de mudanças

| data | mudança |
|---|---|
| 2026-05-27 | criação inicial do AGENT.md |
| 2026-05-27 | implementação do loop ReAct, tools de filesystem e execução |
| 2026-05-27 | entrypoint CLI, system prompt, tratamento de rate limit |
| 2026-05-27 | atualização: detecção de bugs adicionada ao escopo, pendências mapeadas, arquitetura corrigida com status real de cada arquivo |