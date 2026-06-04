# Workflow Git
status: verificado
atualizado: 2026-06-02
 
- Uma branch por issue: feature branch -> checks locais -> push -> PR -> merge na main.
- Commit semântico, um por issue: `feat(scope): descrição closes #N`.
- `ruff format .` e `ruff check .` antes de todo commit; `pytest` deve passar.
- Caio prefere comandos Git crus antes de atalhos de Makefile.
- Review: Claude lê arquivos por URL raw do GitHub em vez de copy-paste.
