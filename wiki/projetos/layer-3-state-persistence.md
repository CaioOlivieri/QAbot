# Layer 3 — Persistência de estado
status: 3a entregue · 3b/3c abertas
atualizado: 2026-06-24

Tracking prod-vs-QA entre execuções (o agente antes era stateless/one-shot).
É AQUI que mora o "conhecimento sobre os códigos-alvo" — runtime, NÃO esta wiki.
Esta wiki documenta o desenvolvimento do QAbot; os achados sobre projetos
testados são saída persistida do produto.

## 3a — ledger + diff (entregue, issue #30)

Módulo `qabot/state.py`. Estado por-alvo em `<projeto>/reports/qabot_state.json`,
gravado pelo `run_agent` no fim de cada execução.

### Esquema do `qabot_state.json`
```jsonc
{
  "version": 1,
  "target": "/abs/path/do/projeto",
  "runs": [
    {
      "run_id": "r1",
      "timestamp": "2026-06-24T18:30:00Z",   // UTC
      "commit_sha": "abc123" ,               // HEAD do alvo, ou null se não for git
      "coverage": { "ops.py": 92.0 },        // cobertura final da execução
      "findings": [
        {
          "fingerprint": "static:ops.py:10:mutable_default",
          "source": "static" ,               // static | dynamic | semantic
          "file": "ops.py",
          "line": 10,
          "category": "mutable_default",
          "severity": "warning",
          "description": "...",
          "status": "new"                    // new | regressed | existing
        }
      ]
    }
  ]
}
```

### Identidade estável (fingerprint)
`source:file:line:category` — o que casa um defeito entre execuções. `severity` e
`description` podem mudar sem perder a identidade. Origens:
- `static`  → bug do AST, categoria = `category` do analyzer.
- `dynamic` → falha de pytest, categoria = `error_type`.
- `semantic` → suspeita confirmada por execução (apenas `status == "confirmed"`;
  suspeitas não verificadas/descartadas nunca entram no ledger).

### Diff run-over-run
Comparado contra a execução anterior **e** o histórico completo:
- `new`       — fingerprint nunca visto em nenhuma execução anterior.
- `regressed` — já visto antes, ausente na execução anterior, voltou agora.
- `resolved`  — presente na execução anterior, ausente agora.
- `coverage`  — média antes/depois + delta.

`summarize_diff` imprime uma linha no fim do run. Funções de diff/normalização são
puras (sem I/O), testadas em `tests/test_state.py`. O **report** consome o diff
desde a 3b (#31).

## 3b — report profissional (entregue, #31)
`report.py` consome o diff do ledger: scorecard com **score + seta de tendência**
(vs o `quality` persistido no run anterior), **gate PASS/FAIL** (coverage > 80%,
0 novos críticos) com motivos, seção **"Changes Since Last Run"** e metadados do run
(run_id/timestamp/commit/thresholds). Exports machine-readable em
`qabot/agent/exports.py`, gravados ao lado do `qa_report.md`: `qa.sarif` (SARIF
2.1.0, achados estáticos → annotations do GitHub), `qa-results.xml` (JUnit: gate +
defeitos) e `coverage.xml` (Cobertura, resumo por módulo). O `run_agent` registra o
run **antes** de gerar o report; o `record_run` persiste os `scores` por run para a
tendência.

## 3c — reconciliação prod-vs-QA (entregue, #32)
Critical defect escape rate / DRE — a métrica-título da vaga. Adapter
`qabot/tools/github.py` (opt-in via `QABOT_PROD_REPO`, paginado, token só-leitura do
env, host fixo `api.github.com`) ingere issues `bug`/`production` como
`reconcile.ProductionBug`. `qabot/agent/reconcile.py` (puro) calcula:
- **headline por contagem**: `escape_rate = D_crit / (E_crit + D_crit)`, DRE = inverso,
  em janela configurável (`QABOT_DRE_WINDOW_DAYS`, default 90 — Capers Jones; ISBSG 30).
  Um defeito em produção é escape **por definição** (não precisa de matching).
- **diagnóstico secundário** `detection_breakdown` (stack-trace da issue → flagado /
  não-detectado / unmatched). KPI no report ligado ao gate, com saúde vs o mínimo
  profissional de 95% (Jones). Fonte e confounders documentados.

### Sinais mais fortes (issue #46, implementado)

Dois sinais deferidos do #32 para evitar scope creep, agora entregues:
- **enriquecimento por fix-commit** — para um bug crítico fechado sem ref de texto, o
  adapter resolve o commit que fechou a issue (evento "closed by" na timeline) e usa os
  arquivos `.py` que ele alterou como segundo sinal de atribuição (`ProductionBug.fix_file_refs`),
  com fallback para o texto. Reduz o balde `unmatched`. Chamadas extras opt-in, graciosas
  e limitadas (`max_fix_lookups`).
- **âncora temporal** — `qa_observation_start` + `catchable` só contam um escape se o bug
  foi reportado depois de QA ter analisado um commit registrado (`commit_sha` no ledger),
  refletindo defeitos que QA teve chance real de pegar.

A âncora é um proxy leve de *proveniência de defeito*. A versão rigorosa identifica o
commit introdutor do bug via `git blame` nas linhas do fix — o **algoritmo SZZ** (Jacek
Śliwerski, Thomas Zimmermann & Andreas Zeller, *"When Do Changes Induce Fixes?"*, MSR
2005), deixado como follow-up.

## Security hardening (issue #39)

Documented the trust boundary and all runtime controls in [THREAT_MODEL.md](../../THREAT_MODEL.md).

Hardening set:
- #36 — read sandbox (`_contain_in_root` / `_resolve_read_path`)
- #37 — SSRF defence / opt-in network (`_ssrf_reason` + `QABOT_ALLOW_NETWORK`)
- #38 — command timeout (`DEFAULT_COMMAND_TIMEOUT = 120 s`)
- #39 — this documentation
