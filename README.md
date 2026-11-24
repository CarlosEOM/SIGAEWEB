# SIGAE WEB — Sistema Inteligente de Gerenciamento de Atendimentos de Emergência

Trabalho Final de Estrutura de Dados Avançados (8,0 pontos). Simulação acadêmica, apenas dados fictícios.

## Como executar

```
python server.py            # abre em http://127.0.0.1:8000
python test_sigae.py        # testes (use "> evidencias_testes.txt" para guardar a evidência)
```

Requer apenas Python 3.8+. **Nenhuma biblioteca externa.** Do Python padrão usamos somente
`http.server` e `json` (servir a página e a API), `os` (caminho do arquivo) e `time` (horário).
Nenhuma delas implementa estrutura de dados: **AVL e Heap foram escritos à mão** em `structures.py`
(sem `heapq`, `bisect`, `collections` ou `dict` como índice). Listas do Python aparecem apenas como
vetor interno do heap e para montar respostas JSON.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `structures.py` | `AVL` (com rotações) e `HeapMin` (com posição guardada no objeto) |
| `sistema.py` | regras de negócio, índices e `verificar()` (checa todas as invariantes) |
| `server.py` | API JSON + entrega da página |
| `index.html` | interface (painel, pacientes, médicos, atendimentos, histórico) |
| `test_sigae.py` | testes da seção 7 do enunciado |

## Decisões de estruturas

Notação: n = pacientes, m = médicos. Todas as complexidades abaixo são de pior caso, salvo indicação.

### 1. Busca por identificador → **AVL** (chave: ID)

- **Operações predominantes:** busca por ID (consultas, reclassificar, cancelar, concluir) e inserção no cadastro.
- **Custo:** inserir, buscar, remover e atualizar O(log n) *garantido* (altura ≤ 1,44·log₂ n).
- **Manutenção:** rotações O(1); no máximo uma rotação (simples ou dupla) por inserção e até O(log n) na remoção.
- **Empates:** não há; ID é único.
- **Descartadas:**
  - *BST simples:* IDs são gerados em sequência crescente, que é exatamente o pior caso — degenera em lista, O(n). No teste 7, 20.000 IDs ordenados dão altura 15 na AVL contra 20.000 numa BST simples.
  - *Tabela hash:* O(1) médio, mas O(n) no pior caso (colisões), exige redimensionamento O(n) e não percorre em ordem.
  - *Rubro-Negra:* mesma complexidade assintótica; a AVL é mais rigidamente balanceada (buscas um pouco mais rápidas, e o sistema consulta mais do que altera) e é mais curta de implementar e explicar.

### 2. Organização por chegada → **AVL** (chave: `(horário de chegada, ID)`)

- **Operações predominantes:** inserir paciente (inclusive com chegada fora de ordem), remover/consultar e **percorrer em ordem cronológica**.
- **Custo:** inserir e remover O(log n); percurso em ordem completo O(n), sem ordenar depois.
- **Empates:** a tupla já resolve — mesmo horário, menor ID primeiro.
- **Manutenção:** a chegada nunca muda, então a reclassificação não mexe nesta árvore.
- **Descartadas:** *vetor/lista ordenada* (inserir fora de ordem é O(n)); *lista encadeada* (inserir ordenado e remover são O(n)); *heap* (não percorre em ordem sem esvaziá-lo, O(n log n)).

### 3. Prioridade dos pacientes → **Heap binário de mínimo** (chave: `(risco, chegada, ID)`)

- **Operações predominantes:** escolher o próximo paciente (a cada chamada), inserir, cancelar e reclassificar.
- **Custo:** consultar o próximo O(1); inserir e extrair O(log n); **remover ou reclassificar um paciente qualquer O(log n)**, porque cada paciente guarda sua posição no vetor (`hpos`), sem busca linear.
- **Empates:** a própria chave: mesmo risco → menor horário de chegada → menor ID (regra do enunciado).
- **Manutenção:** reclassificar muda a chave do mesmo objeto e reposiciona (sobe/desce) — sem duplicar nem deixar órfão.
- **Descartadas:** *lista ordenada* (inserção O(n)); *fila FIFO simples* (ignora o risco); *cinco filas, uma por risco* (funciona, mas ordenar por chegada dentro de cada fila e reclassificar exigiriam outra estrutura ordenada); *AVL* (também O(log n), mas o mínimo custa O(log n) em vez de O(1) e tem mais overhead).

### 4. Distribuição de médicos → **Heap binário de mínimo só com médicos Disponíveis** (chave: `(consultas concluídas, ordem da última atribuição, ID)`)

- **Operações predominantes:** escolher o médico elegível com menor carga (a cada chamada); entrar/sair do conjunto quando conclui, é desfeito/cancelado ou muda a disponibilidade.
- **Custo:** escolher O(1), retirar O(log m), devolver O(log m), remover um médico específico O(log m) (via `hpos`).
- **Empates:** menos consultas concluídas → quem está há mais tempo sem receber paciente (menor `ultima_seq`, contador lógico; quem nunca recebeu tem 0) → menor ID.
- **Por que só os disponíveis:** um médico ocupado ou indisponível *não está no heap*, então é impossível escalá-lo — a regra vale por construção, não por checagem.
- **Descartadas:** *varrer a lista de médicos* a cada chamada (O(m) e fácil de errar nos desempates); *AVL por carga* (mais complexa, sem ganho para o perfil de uso).

### Estruturas auxiliares

- `AVL` por **registro profissional** (impede CRM duplicado, O(log m)); `AVL` de **médicos** por ID; `AVL` de **atendimentos** por ID; `AVL` de **concluídos** por `(fim, ID)` (histórico em ordem de conclusão).
- **Contadores por situação** atualizados a cada mudança de estado: painel em O(1).
- `ordem_chamada(k)`: lista os k primeiros da fila **sem alterá-la** percorrendo o heap com um heap auxiliar de candidatos, O(k log k).

## Regras de negócio e decisões onde o enunciado deixa margem

- Chamada: o paciente de maior prioridade vai para o médico disponível com **menos consultas concluídas**; empate pelo tempo sem receber e depois pelo ID. Sem médico disponível, **a chamada é recusada e o paciente continua na fila**.
- O contador do médico **só sobe ao concluir**. Cancelar ou desfazer antes disso não conta.
- **Desfazer chamada:** o paciente volta à fila com a mesma chave (mesma prioridade e chegada); o médico fica livre e **recupera a "última atribuição" anterior**, pois não houve atendimento.
- **Cancelar paciente em atendimento:** paciente Cancelado, médico liberado, mesma restauração.
- Reclassificar só vale para paciente *Aguardando*. Médico *Em atendimento* não pode virar *Indisponível*.
- O formulário aceita **horário de chegada opcional**, necessário para testar inserção fora de ordem cronológica.
- Requisições são atendidas uma por vez, então não há condição de corrida; "chamadas simultâneas" significam vários médicos atendendo ao mesmo tempo.

## Evidências de testes (`python test_sigae.py`)

| # | O que demonstra (seção 7) |
|---|---|
| 1 | Pacientes fora de ordem cronológica, prioridades repetidas e ordem efetiva de chamada |
| 2 | Três médicos com o mesmo total: todos os desempates |
| 3 | Chamadas simultâneas, conclusões, médicos indisponíveis, carga distribuída (30 consultas → 10 por médico) |
| 4 | Sem médico disponível: ninguém sai da fila |
| 5 | Cancelamento, desfazimento e reclassificação sem duplicar nem criar órfãos |
| 6 | 3.000 operações pseudoaleatórias, com `verificar()` após cada uma |
| 7 | Casos adversos: IDs ordenados, muitos empates, 5.000 atualizações; altura e tempos observados |

`verificar()` confere: propriedades da AVL e do heap, fila ⇔ pacientes *Aguardando*, heap de livres ⇔ médicos *Disponível*, vínculos paciente–médico, contadores e soma de consultas concluídas.

## Roteiro sugerido para a defesa

1. Mostrar `structures.py` e explicar rotações da AVL e o papel do `hpos` no heap.
2. Justificar cada escolha com a tabela acima, incluindo a alternativa descartada.
3. Rodar `test_sigae.py` e mostrar o caso adverso (altura 15 vs 20.000).
4. Perguntas prováveis: *por que não hash?* (pior caso e ordem); *como reclassifica em O(log n)?* (`hpos`); *e se dois médicos empatarem?* (`ultima_seq`, depois ID); *o que acontece se desfizer a chamada?* (restaura chave e última atribuição).
