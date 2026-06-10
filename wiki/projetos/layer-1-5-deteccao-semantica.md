# Layer 1.5 — Detecção semântica (hipótese verificável)
status: proposta
atualizado: 2026-06-09

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

