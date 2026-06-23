# tools/fs.py
status: integrado
fontes: qabot/tools/fs.py
atualizado: 2026-06-23
 
list_files, read_file, write_file. write_file cria diretórios (os.makedirs
exist_ok=True). Todas as três no _dispatch e no system prompt.

Nota (PR #23): write_file é um primitivo puro; a contenção (só arquivos de teste,
dentro do projeto) é imposta a montante por `_resolve_write_path` no `_dispatch`
([[componentes/agent-core]]), não aqui.
