# Layer 1.5 — Detecção semântica (hipótese verificável)
status: verificado
atualizado: 2026-06-23

## Implementação (2026-06-19, PR #21)
Entregue em core.py / report.py / prompts.py:
- `Findings.suspected_bugs`; actions `report_suspected_bug` e
  `resolve_suspected_bug` no `_dispatch` e no prompt.
- Portão D3 (`_resolve_suspicion`): confirma só quando o último run de teste
  capturado falhou de verdade (`parse_pytest_failures`); senão descarta.
  Suspeita sem execução fica "suspected".
- report.py: seção "Semantic Bugs (confirmed)" entra no score; "For Review"
  (suspected) fica FORA do score; discarded não aparece.
- Prompt: o agente detecta e reporta, NUNCA conserta o código-fonte (escopo da
  vaga: identificar/documentar bugs, não corrigir).
- Testes: mecanismo com FakeLLM (test_agent.py) + isolamento de score
  (test_report.py). 52 testes, CI verde.

VERIFICADO e2e (2026-06-23): run ao vivo limpo com `QABOT_MODEL=gemini-2.5-flash`
contra `~/Projetos/qabot_target` (fixture: `is_even` invertido vs docstring,
`last_index` off-by-one). O agente detectou ambos, escreveu testes
`*_intended_behavior` que FALHARAM, e `_resolve_suspicion` os promoveu a
`confirmed` — SEM tocar no `ops.py` (`git diff` vazio). Relatório do alvo lista os
2 sob "Semantic Bugs (confirmed by execution)"; "For Review" vazio. Evidência em
[[raw/issue9-e2e-run]]. Destravado por: prompt afirmando comportamento intended
(PR #26), modelo configurável (PR #27), retry 503/429 (PR #25), tool-error (PR #28).

Bugs semânticos que a AST não enxerga (off-by-one, condição de borda invertida,
código que contradiz a docstring, argumentos trocados) detectados via LLM —
mas como HIPÓTESE, nunca como veredito.

## Princípio inegociável
Achado de LLM é inferência. Pela regra de [[_schema]], inferência não vira
afirmação. Logo, o pipeline é:

1. LLM levanta suspeita sobre um trecho (arquivo, linha, descrição do bug).
2. O agente escreve um teste que FALHA se o bug for real.
3. Roda o teste. Saída salva em raw/ (do projeto-alvo, via run_command).
4. Só então o achado é promovido: suspeito -> confirmado (teste falhou,
   bug existe) ou descartado (teste passou, hipótese refutada).

Achado nunca confirmado por execução permanece "suspeito" no relatório.

## Dois tiers no relatório — nunca fundidos
- AST (determinístico)        -> seção "Bugs detectados", entra no score.
- LLM confirmado por execução -> mesma seção, marcado como semântico.
- LLM suspeito (não testado)  -> seção própria "Para revisão", FORA do score.
Fundir tiers de confiança distinta no mesmo número seria mentir sobre
procedência — o anti-padrão que este projeto existe para combater.

## Arquitetura (pontos de encaixe, já previstos na Layer 0)
- Findings ganha campo suspected_bugs (e confirmação muda dict do achado).
- generate_report ganha parâmetro novo + _section_suspected.
- Preferir capturar suspeitas do raciocínio que o loop JÁ faz ao ler arquivos,
  em vez de tool nova de varredura arquivo-a-arquivo (custo de quota).

## Riscos
- Quota Gemini free tier: varredura semântica multiplica chamadas. Medir antes.
- Não-determinismo: achados flaky; test_agent.py só testa o mecanismo
  (promoção/descarte), nunca o conteúdo dos achados.
- Falso positivo do LLM gerando teste errado: o teste também precisa provar
  que falha quando deveria (regra já existente em [[_schema]]).

## Posição no roadmap
Depois de [[projetos/layer-1-test-agent-ci]]. Não bloqueia nem altera a
Layer 0 (costura entregue sem esta camada; README descreve só AST até aqui
existir).

