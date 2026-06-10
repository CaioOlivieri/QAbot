# Schema da Wiki — QAbot
 
Regras de como esta wiki funciona. O agente lê isto antes de escrever.
 
## Camadas
- raw/       Fontes brutas e imutáveis (saídas de execução, dumps). Nunca editar.
- 00_inbox/  Material recém-jogado, ainda não processado em páginas.
- demais     Páginas curadas, uma entidade/tópico por arquivo, em kebab-case.md.
 
## Cabeçalho de cada página
    status: <ver lista no rodapé>
    fontes: [[raw/...]]   # de onde veio o conteúdo, quando aplicável
    atualizado: AAAA-MM-DD
 
## Regra de disciplina de QA (núcleo do QAbot)
O QAbot — e esta wiki sobre ele — só afirma resultado de teste, cobertura
ou comportamento de código com base em SAÍDA REAL de execução salva em raw/,
nunca por inferência.
- Um teste "que deveria passar" NÃO é um teste que passa.
- Página de resultado só vira `status: verificado` após execução logada.
- Teste gerado só é válido depois de provar que FALHA quando deveria falhar.
Isto é a institucionalização da falha já vivida: o harness (OpenCode/DeepSeek)
reportou sucesso falso sem aplicar a correção. Desconfie por padrão.
 
## Operações (mentalidade Karpathy)
- ingest: processa algo de 00_inbox/ ou raw/, cria/atualiza páginas e linka.
- query:  responde lendo só as páginas relevantes (nunca a wiki toda).
- lint:   aponta links quebrados, contradições, rascunhos antigos e — específico
          aqui — divergência entre o status declarado e o que o core.py importa.
 
## Status válidos
integrado | orfao-na-pratica | orfao-total | proposta | aberta | rascunho | verificado
