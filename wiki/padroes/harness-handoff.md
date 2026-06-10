# Handoff com o harness
status: verificado
atualizado: 2026-06-02
 
Fluxo: Claude arquiteta e escreve o prompt OU o conteúdo completo do arquivo ->
Caio roda no terminal / OpenCode -> cola o output de volta -> review antes de commit.
 
MODO DE FALHA CONHECIDO (importante): o harness (OpenCode/DeepSeek) já falhou
repetidamente em aplicar correções e reportou sucesso falso. Nunca confie no
"deu certo" do harness; confira o diff/arquivo real. É a mesma desconfiança que
o [[_schema]] institucionaliza para resultados de teste.
 
## Exportar estado
scripts/export_context.py gera reports/estado_projeto_*.md com o conteúdo de
todos os arquivos (.py/.md/.json/.txt; ignora .env*, .db, .venv etc.). É a forma
de mandar o estado real do repo pro Claude quando o GitHub está fora de mão.
Nota: NÃO inclui pyproject.toml nem Makefile (extensões fora da whitelist).
