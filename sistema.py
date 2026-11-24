"""Núcleo do SIGAE: regras de negócio sobre as estruturas feitas à mão.

Índices (todos implementados em structures.py):
  pacientes     AVL  id                       -> Paciente    (busca por ID)
  por_chegada   AVL  (chegada, id)            -> Paciente    (ordem cronológica)
  fila          Heap (risco, chegada, id)     -> Paciente    (próximo a ser chamado)
  medicos       AVL  id                       -> Medico
  por_crm       AVL  registro profissional    -> Medico      (impede CRM duplicado)
  livres        Heap (concluídas, última_atribuição, id) -> só médicos Disponíveis
  atendimentos  AVL  id                       -> Atendimento
  concluidos    AVL  (fim, id)                -> Atendimento (histórico)
"""
import time

from structures import AVL, HeapMin

SIT_P = ("Aguardando", "Em atendimento", "Concluído", "Cancelado")
SIT_M = ("Disponível", "Em atendimento", "Indisponível")
NIVEIS = ("Emergência", "Muito urgente", "Urgente", "Pouco urgente", "Não urgente")


class ErroSistema(Exception):
    """Erro de validação/regra de negócio (mensagem exibida ao usuário)."""


def fmt(ts):
    return None if ts is None else time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(ts))


def converter_hora(txt):
    if txt is None or str(txt).strip() == "":
        return None
    if isinstance(txt, (int, float)):
        return float(txt)
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return time.mktime(time.strptime(str(txt).strip(), f))
        except ValueError:
            pass
    raise ErroSistema("Horário de chegada inválido.")


class Paciente:
    def __init__(self, pid, nome, chegada, risco):
        self.id, self.nome, self.chegada, self.risco = pid, nome, chegada, risco
        self.situacao = None
        self.medico_id = None
        self.atend_id = None
        self.hpos = -1

    def json(self):
        return {"id": self.id, "nome": self.nome, "chegada": fmt(self.chegada),
                "risco": self.risco, "nivel": NIVEIS[self.risco - 1],
                "situacao": self.situacao, "medico_id": self.medico_id}


class Medico:
    def __init__(self, mid, nome, crm):
        self.id, self.nome, self.crm = mid, nome, crm
        self.situacao = None
        self.concluidas = 0
        self.ultima_seq = 0        # 0 = nunca recebeu paciente (o mais "antigo" possível)
        self.ultima_hora = None
        self.paciente_id = None
        self.atend_id = None
        self.hpos = -1

    def json(self):
        return {"id": self.id, "nome": self.nome, "crm": self.crm, "situacao": self.situacao,
                "concluidas": self.concluidas, "ultima_hora": fmt(self.ultima_hora),
                "paciente_id": self.paciente_id}


class Atendimento:
    def __init__(self, aid, p, m, inicio):
        self.id = aid
        self.paciente_id, self.paciente_nome = p.id, p.nome
        self.medico_id, self.medico_nome = m.id, m.nome
        self.inicio, self.fim = inicio, None
        self.situacao = "Em andamento"       # Em andamento | Concluído | Cancelado | Desfeito
        self.ant_seq, self.ant_hora = m.ultima_seq, m.ultima_hora   # para desfazer

    def json(self):
        return {"id": self.id, "paciente_id": self.paciente_id, "paciente": self.paciente_nome,
                "medico_id": self.medico_id, "medico": self.medico_nome,
                "inicio": fmt(self.inicio), "fim": fmt(self.fim), "situacao": self.situacao}


class _Cand:
    """Candidato usado só para listar a fila em ordem de chamada sem destruí-la."""
    __slots__ = ("i", "chave", "hpos")

    def __init__(self, i, chave):
        self.i, self.chave, self.hpos = i, chave, -1


class SIGAE:
    def __init__(self):
        self.pacientes = AVL()
        self.por_chegada = AVL()
        self.fila = HeapMin(lambda p: (p.risco, p.chegada, p.id))
        self.medicos = AVL()
        self.por_crm = AVL()
        self.livres = HeapMin(lambda m: (m.concluidas, m.ultima_seq, m.id))
        self.atendimentos = AVL()
        self.concluidos = AVL()
        self._pid, self._mid, self._aid, self._seq = 1000, 2000, 0, 0
        self.cont_p = [0, 0, 0, 0]       # contadores por situação (painel em O(1))
        self.cont_m = [0, 0, 0]

    # ---------------------------------------------------------- auxiliares
    def _set_p(self, p, nova):
        if p.situacao is not None:
            self.cont_p[SIT_P.index(p.situacao)] -= 1
        p.situacao = nova
        self.cont_p[SIT_P.index(nova)] += 1

    def _set_m(self, m, nova):
        if m.situacao is not None:
            self.cont_m[SIT_M.index(m.situacao)] -= 1
        m.situacao = nova
        self.cont_m[SIT_M.index(nova)] += 1

    def _paciente(self, pid):
        p = self.pacientes.buscar(pid)
        if p is None:
            raise ErroSistema("Paciente %s não encontrado." % pid)
        return p

    def _medico(self, mid):
        m = self.medicos.buscar(mid)
        if m is None:
            raise ErroSistema("Médico %s não encontrado." % mid)
        return m

    def _atend(self, aid):
        a = self.atendimentos.buscar(aid)
        if a is None:
            raise ErroSistema("Atendimento %s não encontrado." % aid)
        return a

    def _liberar(self, m):
        m.paciente_id = m.atend_id = None
        self._set_m(m, "Disponível")
        self.livres.inserir(m)

    # ------------------------------------------------------------ pacientes
    def cadastrar_paciente(self, nome, risco, chegada=None):
        nome = (nome or "").strip()
        if not nome:
            raise ErroSistema("Informe o nome do paciente.")
        try:
            risco = int(risco)
        except (TypeError, ValueError):
            raise ErroSistema("Classificação de risco inválida.")
        if not 1 <= risco <= 5:
            raise ErroSistema("A classificação de risco deve ir de 1 a 5.")
        chegada = time.time() if chegada is None else float(chegada)
        self._pid += 1
        p = Paciente(self._pid, nome, chegada, risco)
        self._set_p(p, "Aguardando")
        self.pacientes.inserir(p.id, p)
        self.por_chegada.inserir((p.chegada, p.id), p)
        self.fila.inserir(p)
        return p

    def buscar_paciente(self, pid):
        return self._paciente(pid)

    def reclassificar(self, pid, risco):
        p = self._paciente(pid)
        if p.situacao != "Aguardando":
            raise ErroSistema("Só é possível reclassificar paciente que está aguardando.")
        try:
            risco = int(risco)
        except (TypeError, ValueError):
            raise ErroSistema("Classificação de risco inválida.")
        if not 1 <= risco <= 5:
            raise ErroSistema("A classificação de risco deve ir de 1 a 5.")
        p.risco = risco
        self.fila.atualizar(p)           # mesmo objeto: sem duplicar nem orfanar
        return p

    def cancelar_paciente(self, pid):
        p = self._paciente(pid)
        if p.situacao == "Aguardando":
            self.fila.remover(p)
            self._set_p(p, "Cancelado")
        elif p.situacao == "Em atendimento":
            a = self.atendimentos.buscar(p.atend_id)
            self._encerrar_sem_conclusao(a, "Cancelado")
            self._set_p(p, "Cancelado")
            p.medico_id = p.atend_id = None
        else:
            raise ErroSistema("Paciente já está %s." % p.situacao.lower())
        return p

    # --------------------------------------------------------------- médicos
    def cadastrar_medico(self, nome, crm):
        nome, crm = (nome or "").strip(), (crm or "").strip()
        if not nome or not crm:
            raise ErroSistema("Informe nome e registro profissional (fictício).")
        if self.por_crm.buscar(crm) is not None:
            raise ErroSistema("Registro profissional já cadastrado.")
        self._mid += 1
        m = Medico(self._mid, nome, crm)
        self._set_m(m, "Disponível")
        self.medicos.inserir(m.id, m)
        self.por_crm.inserir(crm, m)
        self.livres.inserir(m)
        return m

    def alterar_disponibilidade(self, mid, nova):
        m = self._medico(mid)
        if nova not in ("Disponível", "Indisponível"):
            raise ErroSistema("Situação inválida.")
        if m.situacao == "Em atendimento":
            raise ErroSistema("Médico em atendimento: conclua ou desfaça a consulta antes.")
        if m.situacao == nova:
            return m
        if nova == "Indisponível":
            self.livres.remover(m)
            self._set_m(m, nova)
        else:
            self._set_m(m, nova)
            self.livres.inserir(m)
        return m

    # ---------------------------------------------------------- atendimentos
    def chamar_proximo(self):
        p = self.fila.topo()
        if p is None:
            raise ErroSistema("Não há pacientes aguardando.")
        m = self.livres.topo()
        if m is None:
            raise ErroSistema("Nenhum médico disponível: o paciente permanece na fila.")
        self.fila.extrair()
        self.livres.extrair()
        self._seq += 1
        self._aid += 1
        a = Atendimento(self._aid, p, m, time.time())
        m.ultima_seq, m.ultima_hora = self._seq, a.inicio
        m.paciente_id, m.atend_id = p.id, a.id
        self._set_m(m, "Em atendimento")
        p.medico_id, p.atend_id = m.id, a.id
        self._set_p(p, "Em atendimento")
        self.atendimentos.inserir(a.id, a)
        return a

    def chamar_varios(self, n):
        feitas, motivo = [], ""
        for _ in range(n):
            try:
                feitas.append(self.chamar_proximo())
            except ErroSistema as e:
                if not feitas:
                    raise
                motivo = str(e)
                break
        return feitas, motivo

    def concluir(self, aid):
        a = self._atend(aid)
        if a.situacao != "Em andamento":
            raise ErroSistema("Este atendimento não está em andamento.")
        a.fim, a.situacao = time.time(), "Concluído"
        self._set_p(self.pacientes.buscar(a.paciente_id), "Concluído")
        m = self.medicos.buscar(a.medico_id)
        m.concluidas += 1                # só aqui o contador sobe
        self._liberar(m)
        self.concluidos.inserir((a.fim, a.id), a)
        return a

    def desfazer_chamada(self, aid):
        """Paciente volta à fila com a mesma prioridade; médico fica livre e não conta."""
        a = self._atend(aid)
        if a.situacao != "Em andamento":
            raise ErroSistema("Este atendimento não está em andamento.")
        p = self.pacientes.buscar(a.paciente_id)
        self._encerrar_sem_conclusao(a, "Desfeito")
        p.medico_id = p.atend_id = None
        self._set_p(p, "Aguardando")
        self.fila.inserir(p)
        return a

    def _encerrar_sem_conclusao(self, a, situacao):
        a.fim, a.situacao = time.time(), situacao
        m = self.medicos.buscar(a.medico_id)
        m.ultima_seq, m.ultima_hora = a.ant_seq, a.ant_hora   # não houve atendimento
        self._liberar(m)

    # ------------------------------------------------------------ consultas
    def listar_pacientes(self, situacao=None):
        """Em ordem de chegada (percurso em ordem da AVL por (chegada, id))."""
        return [p for _, p in self.por_chegada.em_ordem()
                if situacao is None or p.situacao == situacao]

    def listar_medicos(self):
        return [m for _, m in self.medicos.em_ordem()]

    def listar_atendimentos(self):
        return [a for _, a in self.atendimentos.em_ordem()]

    def historico(self):
        conc = [a.json() for _, a in self.concluidos.em_ordem()]
        return {"concluidos": conc,
                "por_medico": [{"id": m.id, "nome": m.nome, "concluidas": m.concluidas}
                               for m in self.listar_medicos()]}

    def ordem_chamada(self, k=10):
        """Primeiros k da fila em ordem de chamada, sem alterar a fila. O(k log k)."""
        v, chave = self.fila.v, self.fila.chave
        if not v:
            return []
        aux = HeapMin(lambda c: c.chave)
        aux.inserir(_Cand(0, chave(v[0])))
        saida = []
        while len(aux) and len(saida) < k:
            c = aux.extrair()
            saida.append(v[c.i])
            for j in (2 * c.i + 1, 2 * c.i + 2):
                if j < len(v):
                    aux.inserir(_Cand(j, chave(v[j])))
        return saida

    def painel(self):
        prox = self.fila.topo()
        return {"aguardando": self.cont_p[0], "em_atendimento": self.cont_p[1],
                "concluidos": self.cont_p[2], "cancelados": self.cont_p[3],
                "total_pacientes": len(self.pacientes),
                "medicos_total": len(self.medicos),
                "medicos_disponiveis": self.cont_m[0], "medicos_ocupados": self.cont_m[1],
                "medicos_indisponiveis": self.cont_m[2],
                "proximo": prox.json() if prox else None,
                "ordem": [p.json() for p in self.ordem_chamada(10)],
                "altura_pacientes": self.pacientes.altura(),
                "altura_chegada": self.por_chegada.altura(),
                "altura_medicos": self.medicos.altura()}

    # ---------------------------------------------------------- verificação
    def verificar(self):
        """Confere TODAS as invariantes entre índices e estados. [] = consistente."""
        e = []
        for nome, est in (("pacientes", self.pacientes), ("por_chegada", self.por_chegada),
                          ("medicos", self.medicos), ("por_crm", self.por_crm),
                          ("atendimentos", self.atendimentos), ("concluidos", self.concluidos),
                          ("fila", self.fila), ("livres", self.livres)):
            e += [nome + ": " + x for x in est.valida()]
        if len(self.pacientes) != len(self.por_chegada):
            e.append("índices de paciente com tamanhos diferentes")
        cp = [0, 0, 0, 0]
        for _, p in self.pacientes.em_ordem():
            cp[SIT_P.index(p.situacao)] += 1
            if (p.situacao == "Aguardando") != (p.hpos >= 0):
                e.append("paciente %s: fila inconsistente" % p.id)
            if self.por_chegada.buscar((p.chegada, p.id)) is not p:
                e.append("paciente %s: ausente do índice de chegada" % p.id)
            if p.situacao == "Em atendimento":
                m = self.medicos.buscar(p.medico_id)
                if m is None or m.paciente_id != p.id or m.situacao != "Em atendimento":
                    e.append("paciente %s: vínculo com médico inconsistente" % p.id)
        if cp != self.cont_p:
            e.append("contadores de pacientes divergem")
        cm, soma = [0, 0, 0], 0
        for _, m in self.medicos.em_ordem():
            cm[SIT_M.index(m.situacao)] += 1
            soma += m.concluidas
            if (m.situacao == "Disponível") != (m.hpos >= 0):
                e.append("médico %s: heap de livres inconsistente" % m.id)
            if m.situacao == "Em atendimento":
                p = self.pacientes.buscar(m.paciente_id)
                if p is None or p.medico_id != m.id or p.situacao != "Em atendimento":
                    e.append("médico %s: vínculo com paciente inconsistente" % m.id)
        if cm != self.cont_m:
            e.append("contadores de médicos divergem")
        if soma != len(self.concluidos) or soma != cp[2]:
            e.append("concluídos divergem do contador dos médicos")
        return e


def popular_demo(s):
    """Dados fictícios para demonstração (chegadas fora de ordem de propósito)."""
    for nome, crm in (("Dra. Mariana Costa", "CRM-0001"), ("Dr. André Ribeiro", "CRM-0002"),
                      ("Dra. Beatriz Lima", "CRM-0003"), ("Dr. Martin Garrido", "CRM-0004")):
        s.cadastrar_medico(nome, crm)
    agora = time.time()
    for nome, risco, min_atras in (("Ana", 3, 20), ("Bruno", 1, 5), ("Carla", 3, 45),
                                   ("Diego", 5, 60), ("Elisa", 2, 30), ("Fábio", 1, 5),
                                   ("Gabriela", 4, 10), ("Hugo", 2, 50)):
        s.cadastrar_paciente(nome, risco, agora - min_atras * 60)
