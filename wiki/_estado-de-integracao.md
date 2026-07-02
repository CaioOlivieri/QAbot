# Estado de Integração
status: verificado
fontes: qabot/agent/core.py, qabot/agent/prompts.py (lidos do repo, branch main)
atualizado: 2026-07-02 (tabela de capacidades revalidada contra core.py atual;
ver nova seção "#30–#65" abaixo para o que foi adicionado desde 2026-06-23)
 
Verdade única sobre o que o agente realmente usa. README/AGENT.md divergem disto.
 
| Capacidade            | Função(ões)                          | No _dispatch? | No prompt? | Status            |
| --------------------- | ------------------------------------ | ------------- | ---------- | ----------------- |
| Listar/ler/escrever   | list_files, read_file, write_file    | sim           | sim        | integrado         |
| Rodar comando         | run_command                          | sim           | sim        | integrado         |
| Parsear cobertura     | parse_coverage                       | sim           | sim        | integrado         |
| Classificar falhas    | parse_pytest_failures                | sim           | sim        | integrado         |
| Bug estático (AST)    | analyze_file_ast/analyze_project_ast | sim           | sim        | integrado         |
| Bug semântico (LLM)   | report_suspected_bug/resolve_suspected_bug | sim     | sim        | implementado      |
| Teste de API          | detect_api_endpoints/test_api_endpoint| sim           | sim        | integrado         |
| Relatório             | generate_report                      | NÃO (não é tool)| NÃO        | integrado         |
 
Costura completa em [[projetos/layer-0-wiring]] (2026-06-09).
`run_agent` agora acumula achados estruturados no loop, chama
`generate_report` no fim e escreve o relatório em
`<project_path>/reports/qa_report.md` (via `_write_report`).
 
## Drift de documentação (corrigido na Layer 0, 2026-06-09)
README.md:
- "What it does" passos 8 (detecta bugs) e 9 (relatório) — agora verdadeiros.
- "Design decisions" descreve "Bug detection in two layers" como ativo — agora verdadeiro.
- "Architecture" agora inclui tools/api.py e tools/analyzer.py na árvore.
AGENT.md:
- "Pending" removido — GitHub Issues são a fonte única de trabalho pendente.
- "Architecture" agora lista todos os 8 módulos com papel de uma linha cada.
- "Knowledge base" adicionado com regras de leitura de wiki antes de mudanças.

## Robustez de JSON (2026-06-15)
`_call_llm` usa `response_mime_type="application/json"` e o parsing inline foi
trocado por `_parse_agent_json` (puro, tolerante a cercas/prosa/vírgula final/
newline literal). Causa raiz dos aborts de JSON resolvida; verificado por
execução real. Detalhe em [[decisoes/json-mode-e-parser-robusto]].

## Detecção semântica — Layer 1.5 (2026-06-19)
report_suspected_bug + resolve_suspected_bug no _dispatch e no prompt;
Findings.suspected_bugs; confirmação por execução (_resolve_suspicion só confirma
se o último run de teste falhou). Confirmados contam no score; suspeitos vão para
"For Review" (fora do score). E2e ao vivo PENDENTE (quota Gemini) — por isso
"implementado", não "verificado". Detalhe em
[[projetos/layer-1-5-deteccao-semantica]].

## Endurecimento de segurança & faxina de qualidade (PR #23, 2026-06-23)
Passada de manutenibilidade (rebase-merge, 9 commits). Única mudança de
comportamento *wired*: `write_file` agora é **contido** na fronteira de confiança
do `_dispatch` — `_resolve_write_path` recusa caminho que escape do `project_path`
ou que não seja arquivo de teste (`test_*.py`, `*_test.py`, `conftest.py`). Antes
aceitava qualquer caminho; a regra "só cria teste, nunca edita fonte" vivia só no
prompt e não era imposta. Também corrige caminho relativo que resolvia contra o
CWD do processo, não o projeto-alvo. O prompt passou a declarar a restrição.

Demais commits são internos, sem mudança de wiring: dedup das seções do relatório
(`_by_severity` + `_section_suspicions`), `detect_api_endpoints` reusa
`list_files`, acumulação de Findings extraída para `_accumulate_findings` (pura,
testável), código morto removido (backports.zoneinfo, parâmetro `rel`) e rede de
testes nova para as linhas do relatório e o entrypoint CLI.

Verificado por execução real: [[raw/pr23-quality-cleanup-checks]] — ruff format e
check limpos, 63 testes, cobertura total 90% (era 80%). CI verde no PR #23 (merged).

## Layers 3a–3c, segurança, CI e agnosticismo de provider (#30–#65, 2026-06-25 a 2026-07-02)

Tudo abaixo é paralelo ao loop ReAct documentado na tabela do topo — nenhum destes
itens mexeu em `_dispatch` nem no prompt, por isso a tabela de capacidades continua
válida sem alteração. Fatos abaixo verificados por leitura do código-fonte atual
(`main`) + `git log --grep='closes #'` nesta sessão de revisão de manutenibilidade;
sem evidência nova arquivada em `wiki/raw/` para estes itens (exceto #65, ver nota),
então status "integrado" — não "verificado" no sentido estrito desta wiki (comparar
com a seção Layer 1.5 acima, que já distingue os dois níveis).

- **#30 Layer 3a** (`8b05adf`) — `qabot/state.py`: ledger persistente
  (`reports/qabot_state.json`) + diff run-over-run.
- **#36–#39 endurecimento de segurança** (`faf90f9`, `59b9361`, `580ed0d`,
  `b6e7752`) — sandbox de `read_file`, timeout de `run_command`, guard SSRF +
  rede opt-in, `THREAT_MODEL.md`.
- **#31 Layer 3b** (`5438b2b`) — `qabot/agent/exports.py` (SARIF/JUnit/Cobertura)
  + scorecard/gate/thresholds em `report.py`.
- **#32 Layer 3c** (`b1eec13`) — `qabot/agent/reconcile.py` +
  `qabot/tools/github.py`: DRE / escape rate de defeitos de produção.
- **#33 CI** (`30a6033`) — `.github/workflows/qa-gate.yml`: gate `smoke`
  (LLM-free, roda em PR) + `regression` (LLM completo, agendado).
- **#34 notificações** (`d8a4d83`) — `qabot/notify.py`: Slack + comentário de PR.
- **#46 DRE — sinais mais fortes** (`5148326`) — `fix_file_refs` + ancoragem
  temporal (`qa_observation_start` / `catchable`).
- **#47 SSRF — fecha DNS-rebinding** (`9925e19`) — resolve e fixa o IP validado
  antes de conectar.
- **#48 fix 503/429** (`fff365c`) — reseta o contador de retry de 503 quando um
  429 intervém.
- **#49 coverage.xml real** (`1eb0ac5`) — `write_exports` grava o XML
  line-level do coverage.py quando disponível, em vez de um resumo sintético.
- **#50 LLM agnóstico de provider** (`58d2053`) — novo `qabot/agent/llm.py`:
  `LLMProvider` Protocol + Gemini/OpenAI-compatible/Anthropic via `QABOT_PROVIDER`.
- **#56 SZZ provenance** (`459bcd3`) — novo `qabot/tools/git_blame.py`: blame do
  commit de fix para localizar o commit que introduziu o bug (algoritmo SZZ).
- **#65 fix da persistência do trend em CI** (`c2107f0`, sessão atual) — o passo
  "Persist defect trend" nunca commitava (`reports/` era gitignored e
  `git diff --quiet` num arquivo untracked sempre saía 0, então o passo sempre
  imprimia "No trend change." antes de chegar no commit). `.gitignore` agora
  excetua `reports/qabot_state.json`; o passo faz stage-then-diff do índice em
  vez do worktree. **Confirmado ao vivo nesta sessão**: disparo manual via
  `workflow_dispatch` (run `28564393016`) produziu o primeiro commit de trend da
  história do repo (`5c7c1b5`, `create mode 100644 reports/qabot_state.json`) —
  evidência não arquivada como transcript em `wiki/raw/` nesta passada.
