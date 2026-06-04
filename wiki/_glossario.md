# Glossário — QAbot
status: verificado
 
## órfão
Componente construído e testado, mas não conectado ao loop do agente. Subtipos:
orfao-total (nem importado) e orfao-na-pratica (no _dispatch, fora do prompt).
 
## ReAct
Loop "Reason + Act": o LLM alterna pensamento (thought) e ação (action/tool).
 
## cobertura (coverage)
% de linhas/módulos exercidos por testes. Alvo do projeto: >=80% por módulo.
 
## bug estático vs dinâmico
Estático: achado por AST sem rodar o código (analyzer.py). Dinâmico: achado por
falha de execução do pytest (parse_pytest_failures).
 
## flaky test
Teste que passa/falha de forma não determinística. (a documentar quando surgir)
