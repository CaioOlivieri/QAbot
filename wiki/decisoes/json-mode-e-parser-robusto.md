# Robustez de JSON: modo nativo + parser tolerante
status: verificado
fontes: wiki/raw/jsonfix-run-calc.txt
atualizado: 2026-06-15

## Problema
Pós issue #10 (PR #11) o agente ainda abortava em execução real
(`raw/issue10-run-alertavida.txt`): "Aborted: 3 consecutive invalid JSON
responses." O #10 só entregou degradação graciosa; a CAUSA RAIZ continuava —
o LLM (gemini-2.5-flash-lite) emitia JSON inválido, principalmente no
`write_file`, onde o código gerado entra como string com quebras de linha e
aspas que o modelo não escapava.

## Decisão (2 frentes)
1. JSON nativo na origem: `_call_llm` passa
   `response_mime_type="application/json"` no GenerateContentConfig. O Gemini
   passa a serializar JSON válido — sem cercas, sem prosa, escapando newlines
   e aspas dentro de strings. Resolve o write_file-com-código na raiz.
   Sem `response_schema`: `action_input` é polimórfico (str p/ read_file,
   dict p/ write_file/run_command) e a resposta alterna action vs final_answer;
   schema rígido brigaria com o agente. mime_type basta para garantir sintaxe.
2. Parser tolerante como defesa em profundidade: `_parse_agent_json` (puro,
   determinístico) tenta, em ordem: texto cru -> sem cerca markdown ->
   primeiro objeto `{...}` balanceado (respeitando strings/escape, varre todos
   os `{` e ignora chaves de prosa). Cada candidato é tentado com
   `json.loads` strict=True e strict=False (aceita newline literal em string)
   e com vírgula final removida. Falhou tudo -> ValueError -> cai no orçamento
   de retries/abort herdado do #10.

## Verificação (execução real)
`raw/jsonfix-run-calc.txt`: run contra alvo sintético com lacuna de cobertura.
8 iterações incluindo analyze_project_ast, read_file, write_file (código
multilinha) e run_command, terminando em final_answer. **0 ocorrências de
"Invalid JSON"** (antes abortava no iteration 7). Teste gerado pelo agente
saiu íntegro (aspas, newlines, pytest.raises(match=...)).
O ModuleNotFoundError no fim é do layout src/ do alvo, não do qabot nem do JSON.

## Testes
tests/test_agent.py cobre `_parse_agent_json` sem LLM: cercas json/bare,
prosa ao redor, vírgula final, newline literal em string, chaves dentro de
string, chaves de prosa não-JSON, múltiplos objetos, array (rejeita), vazio.

## Pendências relacionadas
Validação contra AlertaVida (alvo do demo) quando estiver local de novo —
substituiria o alvo sintético por execução fim-a-fim canônica.
Ver [[projetos/layer-1-test-agent-ci]].
