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
puras (sem I/O), testadas em `tests/test_state.py`. O **report** ainda não consome
o diff — isso é a 3b (#31).

## 3b — report profissional (aberta, #31)
Scorecard, tendência, gate PASS/FAIL e exports SARIF/JUnit/coverage, consumindo o
ledger da 3a.

## 3c — reconciliação prod-vs-QA (aberta, #32)
Critical defect escape rate (DRE) via issues do GitHub — a métrica-título da vaga,
também sobre o ledger da 3a.
