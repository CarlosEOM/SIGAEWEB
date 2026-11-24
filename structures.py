"""Estruturas de dados do SIGAE, implementadas do zero.

Nenhum import: sem heapq, bisect, collections, dict como índice, etc.
- AVL: árvore binária de busca auto-balanceada (chave -> valor).
- HeapMin: heap binário de mínimo sobre vetor, com posição guardada no próprio
  objeto (atributo `hpos`), o que permite remover/atualizar qualquer item em O(log n).
"""


# ----------------------------------------------------------------- AVL
class _No:
    __slots__ = ("chave", "valor", "esq", "dir", "h")

    def __init__(self, chave, valor):
        self.chave, self.valor = chave, valor
        self.esq = self.dir = None
        self.h = 1


def _h(n):
    return n.h if n else 0


def _atualiza(n):
    a, b = _h(n.esq), _h(n.dir)
    n.h = 1 + (a if a > b else b)


def _rot_dir(y):
    x = y.esq
    y.esq, x.dir = x.dir, y
    _atualiza(y)
    _atualiza(x)
    return x


def _rot_esq(x):
    y = x.dir
    x.dir, y.esq = y.esq, x
    _atualiza(x)
    _atualiza(y)
    return y


def _balanceia(n):
    _atualiza(n)
    fb = _h(n.esq) - _h(n.dir)
    if fb > 1:                                  # pesado à esquerda
        if _h(n.esq.esq) < _h(n.esq.dir):       # caso esquerda-direita
            n.esq = _rot_esq(n.esq)
        return _rot_dir(n)
    if fb < -1:                                 # pesado à direita
        if _h(n.dir.dir) < _h(n.dir.esq):       # caso direita-esquerda
            n.dir = _rot_dir(n.dir)
        return _rot_esq(n)
    return n


class AVL:
    """Mapa ordenado. Chaves devem ser comparáveis (int, str, tuplas...)."""

    def __init__(self):
        self.raiz = None
        self.tamanho = 0
        self._flag = False

    def __len__(self):
        return self.tamanho

    def inserir(self, chave, valor):
        """True se a chave é nova; False se apenas substituiu o valor. O(log n)."""
        self._flag = False
        self.raiz = self._ins(self.raiz, chave, valor)
        if self._flag:
            self.tamanho += 1
        return self._flag

    def _ins(self, n, chave, valor):
        if n is None:
            self._flag = True
            return _No(chave, valor)
        if chave < n.chave:
            n.esq = self._ins(n.esq, chave, valor)
        elif chave > n.chave:
            n.dir = self._ins(n.dir, chave, valor)
        else:
            n.valor = valor
            return n
        return _balanceia(n)

    def buscar(self, chave):
        """Valor da chave ou None. O(log n) garantido."""
        n = self.raiz
        while n:
            if chave < n.chave:
                n = n.esq
            elif chave > n.chave:
                n = n.dir
            else:
                return n.valor
        return None

    def remover(self, chave):
        """True se removeu. O(log n)."""
        self._flag = False
        self.raiz = self._rem(self.raiz, chave)
        if self._flag:
            self.tamanho -= 1
        return self._flag

    def _rem(self, n, chave):
        if n is None:
            return None
        if chave < n.chave:
            n.esq = self._rem(n.esq, chave)
        elif chave > n.chave:
            n.dir = self._rem(n.dir, chave)
        else:
            if n.esq is None or n.dir is None:
                self._flag = True
                return n.esq or n.dir
            s = n.dir                           # sucessor in-order
            while s.esq:
                s = s.esq
            n.chave, n.valor = s.chave, s.valor
            n.dir = self._rem(n.dir, s.chave)
        return _balanceia(n)

    def em_ordem(self):
        """Gera (chave, valor) em ordem crescente de chave. O(n) total."""
        pilha, n = [], self.raiz
        while pilha or n:
            while n:
                pilha.append(n)
                n = n.esq
            n = pilha.pop()
            yield n.chave, n.valor
            n = n.dir

    def altura(self):
        return _h(self.raiz)

    def valida(self):
        """Confere ordenação, alturas, balanceamento e tamanho. Lista de erros."""
        erros = []

        def rec(n):
            if n is None:
                return 0
            a, b = rec(n.esq), rec(n.dir)
            if abs(a - b) > 1:
                erros.append("árvore desbalanceada")
            if n.h != 1 + max(a, b):
                erros.append("altura armazenada incorreta")
            return 1 + max(a, b)

        rec(self.raiz)
        ant, cont = None, 0
        for k, _ in self.em_ordem():
            if ant is not None and not ant < k:
                erros.append("chaves fora de ordem")
            ant, cont = k, cont + 1
        if cont != self.tamanho:
            erros.append("tamanho divergente")
        return erros


# ---------------------------------------------------------------- Heap
class HeapMin:
    """Heap de mínimo. `chave(item)` devolve uma tupla; menor tupla sai primeiro.

    Todo item inserido precisa aceitar o atributo `hpos` (posição no vetor).
    Se a chave de um item mudar, chame `atualizar(item)`.
    """

    def __init__(self, chave):
        self.v = []
        self.chave = chave

    def __len__(self):
        return len(self.v)

    def topo(self):
        """Menor item sem remover. O(1)."""
        return self.v[0] if self.v else None

    def inserir(self, x):
        x.hpos = len(self.v)
        self.v.append(x)
        self._sobe(x.hpos)

    def extrair(self):
        """Remove e devolve o menor item. O(log n)."""
        if not self.v:
            return None
        x = self.v[0]
        self.remover(x)
        return x

    def remover(self, x):
        """Remove um item arbitrário usando x.hpos. O(log n)."""
        i = x.hpos
        if i < 0 or i >= len(self.v) or self.v[i] is not x:
            return False
        ultimo = self.v.pop()
        x.hpos = -1
        if i < len(self.v):
            self.v[i] = ultimo
            ultimo.hpos = i
            self._sobe(i)
            self._desce(ultimo.hpos)
        return True

    def atualizar(self, x):
        """Reposiciona x após mudança de chave. O(log n)."""
        self._sobe(x.hpos)
        self._desce(x.hpos)

    def _troca(self, i, j):
        v = self.v
        v[i], v[j] = v[j], v[i]
        v[i].hpos, v[j].hpos = i, j

    def _sobe(self, i):
        v, ch = self.v, self.chave
        while i > 0:
            p = (i - 1) // 2
            if ch(v[i]) < ch(v[p]):
                self._troca(i, p)
                i = p
            else:
                break

    def _desce(self, i):
        v, ch, n = self.v, self.chave, len(self.v)
        while True:
            e, d, m = 2 * i + 1, 2 * i + 2, i
            if e < n and ch(v[e]) < ch(v[m]):
                m = e
            if d < n and ch(v[d]) < ch(v[m]):
                m = d
            if m == i:
                break
            self._troca(i, m)
            i = m

    def valida(self):
        erros = []
        for i, x in enumerate(self.v):
            if x.hpos != i:
                erros.append("posição (hpos) incorreta")
            if i > 0 and self.chave(x) < self.chave(self.v[(i - 1) // 2]):
                erros.append("propriedade de heap violada")
        return erros
