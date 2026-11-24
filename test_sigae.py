"""Testes do SIGAE (seção 7 do enunciado). Execute: python test_sigae.py
Para guardar como evidência:  python test_sigae.py > evidencias_testes.txt
Sem unittest/random: asserts simples e gerador pseudoaleatório próprio (LCG), reprodutível.
"""
import time

from sistema import SIGAE, ErroSistema
from structures import AVL


def ok(cond, texto):
    assert cond, "FALHOU: " + texto
    print("  ok -", texto)


def erra(fn, *args):
    try:
        fn(*args)
    except ErroSistema:
        return True
    return False


def t1_ordem_de_chamada():
    print("Teste 1 - pacientes fora de ordem cronológica, prioridades repetidas")
    s = SIGAE()
    s.cadastrar_medico("Dra. Teste", "CRM-1")
    for nome, risco, chegada in (("A", 3, 100), ("B", 1, 300), ("C", 3, 50), ("D", 1, 300), ("E", 5, 10)):
        s.cadastrar_paciente(nome, risco, chegada)
    cron = [p.nome for _, p in s.por_chegada.em_ordem()]
    ok(cron == ["E", "C", "A", "B", "D"], "ordem cronológica = %s" % cron)
    ordem = []
    while True:
        try:
            a = s.chamar_proximo()
        except ErroSistema:
            break
        ordem.append(a.paciente_nome)
        s.concluir(a.id)
    ok(ordem == ["B", "D", "C", "A", "E"],
       "ordem efetiva de chamada = %s (risco > chegada; empate: chegada, depois ID)" % ordem)
    ok(s.verificar() == [], "invariantes consistentes")


def t2_empates_de_medicos():
    print("Teste 2 - três médicos com o mesmo total: todos os desempates")
    s = SIGAE()
    m1, m2, m3 = (s.cadastrar_medico("M%d" % i, "CRM-%d" % i) for i in (1, 2, 3))
    for i in range(6):
        s.cadastrar_paciente("P%d" % i, 3, i)
    a = [s.chamar_proximo() for _ in range(3)]
    ok([x.medico_id for x in a] == [m1.id, m2.id, m3.id], "ninguém recebeu antes -> menor ID primeiro")
    for i in (2, 0, 1):                                   # conclusão fora de ordem
        s.concluir(a[i].id)
    b = [s.chamar_proximo() for _ in range(3)]
    ok([x.medico_id for x in b] == [m1.id, m2.id, m3.id],
       "mesmo total (1 cada) -> quem está há mais tempo sem receber paciente, não quem liberou antes")
    ok(s.verificar() == [], "invariantes consistentes")


def t3_distribuicao_de_carga():
    print("Teste 3 - chamadas simultâneas, indisponíveis, menor carga")
    s = SIGAE()
    m1, m2, m3 = (s.cadastrar_medico("M%d" % i, "CRM-%d" % i) for i in (1, 2, 3))
    s.alterar_disponibilidade(m2.id, "Indisponível")
    s.alterar_disponibilidade(m3.id, "Indisponível")
    for i in range(5):
        s.cadastrar_paciente("P%d" % i, 3, i)
    for _ in range(2):
        s.concluir(s.chamar_proximo().id)
    ok(m1.concluidas == 2 and m2.concluidas == 0 and m3.concluidas == 0, "só M1 atendeu (2 consultas)")
    s.alterar_disponibilidade(m2.id, "Disponível")
    s.alterar_disponibilidade(m3.id, "Disponível")
    a = [s.chamar_proximo() for _ in range(3)]
    ok([x.medico_id for x in a] == [m2.id, m3.id, m1.id], "menos carregados primeiro; M1 (2 consultas) por último")
    ok(erra(s.alterar_disponibilidade, m1.id, "Indisponível"), "médico em atendimento não pode ficar indisponível")
    ok(s.verificar() == [], "invariantes consistentes")

    s = SIGAE()
    ms = [s.cadastrar_medico("M%d" % i, "CRM-%d" % i) for i in (1, 2, 3)]
    for i in range(30):
        s.cadastrar_paciente("P%d" % i, 1 + i % 5, i)
    x = 7
    for _ in range(10):
        ativos = [s.chamar_proximo() for _ in range(3)]
        ok_busy = all(m.situacao == "Em atendimento" for m in ms)
        assert ok_busy and erra(s.chamar_proximo), "médico ocupado não pode ser escalado"
        for _ in range(3):                                 # conclui em ordem pseudoaleatória
            x = (x * 1103515245 + 12345) % 2147483648
            s.concluir(ativos.pop(x % len(ativos)).id)
    ok([m.concluidas for m in ms] == [10, 10, 10], "30 consultas -> 10 por médico; ocupado nunca escalado de novo")
    ok(s.verificar() == [], "invariantes consistentes")


def t4_sem_medico_disponivel():
    print("Teste 4 - sem médico disponível a fila não perde ninguém")
    s = SIGAE()
    p = s.cadastrar_paciente("Zé", 1, 1)
    ok(erra(s.chamar_proximo), "chamada sem médico é recusada")
    ok(p.situacao == "Aguardando" and len(s.fila) == 1, "paciente continua aguardando na fila")
    m = s.cadastrar_medico("M", "CRM-1")
    s.alterar_disponibilidade(m.id, "Indisponível")
    ok(erra(s.chamar_proximo) and len(s.fila) == 1, "médico indisponível também não é escalado")
    s.alterar_disponibilidade(m.id, "Disponível")
    ok(s.chamar_proximo().paciente_id == p.id, "voltando a ficar disponível, o paciente é chamado")


def t5_cancelar_desfazer_reclassificar():
    print("Teste 5 - cancelamento, desfazimento e reclassificação")
    s = SIGAE()
    m1, m2 = s.cadastrar_medico("M1", "CRM-1"), s.cadastrar_medico("M2", "CRM-2")
    p1, p2 = s.cadastrar_paciente("P1", 1, 10), s.cadastrar_paciente("P2", 2, 5)
    a = s.chamar_proximo()
    ok(a.paciente_id == p1.id and a.medico_id == m1.id, "P1 (risco 1) é chamado com M1")
    s.desfazer_chamada(a.id)
    ok(p1.situacao == "Aguardando" and m1.concluidas == 0 and m1.situacao == "Disponível",
       "desfazer: paciente volta à fila, médico livre, contador intacto")
    a2 = s.chamar_proximo()
    ok(a2.paciente_id == p1.id and a2.medico_id == m1.id, "mantém prioridade e o 'tempo sem receber' do médico")
    s.cancelar_paciente(p1.id)
    ok(p1.situacao == "Cancelado" and m1.concluidas == 0 and m1.situacao == "Disponível",
       "cancelar em atendimento não conta como consulta e libera o médico")
    ok(erra(s.cancelar_paciente, p1.id), "cancelar duas vezes é recusado")
    p3 = s.cadastrar_paciente("P3", 5, 1)
    s.reclassificar(p3.id, 1)
    ok(s.chamar_proximo().paciente_id == p3.id, "reclassificado (5->1, chegada mais antiga) passa à frente de P2")
    ok(len(s.pacientes) == 3 and len(s.por_chegada) == 3, "sem duplicação nem registros órfãos")
    ok(s.verificar() == [], "invariantes consistentes")


def t6_estresse_com_invariantes():
    print("Teste 6 - 3000 operações aleatórias (reprodutíveis), invariantes após cada uma")
    s = SIGAE()
    meds = [s.cadastrar_medico("M%d" % i, "CRM-%d" % i) for i in range(4)]
    x = 12345

    def rnd(n):
        nonlocal x
        x = (x * 1103515245 + 12345) % 2147483648
        return (x >> 8) % n

    for _ in range(3000):
        op = rnd(7)
        try:
            if op == 0:
                s.cadastrar_paciente("P", 1 + rnd(5), rnd(1000))
            elif op == 1:
                s.reclassificar(1001 + rnd(s._pid - 1000), 1 + rnd(5))
            elif op == 2:
                s.cancelar_paciente(1001 + rnd(s._pid - 1000))
            elif op == 3:
                s.chamar_proximo()
            elif op == 4 and s._aid:
                s.concluir(1 + rnd(s._aid))
            elif op == 5 and s._aid:
                s.desfazer_chamada(1 + rnd(s._aid))
            elif op == 6:
                m = meds[rnd(4)]
                s.alterar_disponibilidade(m.id, "Indisponível" if m.situacao == "Disponível" else "Disponível")
        except ErroSistema:
            pass
        erros = s.verificar()
        assert erros == [], "invariante violada: %s" % erros
    total = s._pid - 1000
    ok(len(s.pacientes) == len(s.por_chegada) == total == sum(s.cont_p), "%d pacientes, nenhum duplicado ou órfão" % total)
    ok(sum(m.concluidas for m in meds) == len(s.concluidos), "consultas concluídas batem com o histórico")
    print("  situação final:", s.painel()["aguardando"], "aguardando,", s.painel()["em_atendimento"], "em atendimento")


def t7_casos_adversos():
    print("Teste 7 - casos adversos para as estruturas escolhidas")
    n = 20000
    t = time.time()
    a = AVL()
    for i in range(n):                                     # IDs ordenados: pior caso de uma BST simples
        a.inserir(i, i)
    h, dt = a.altura(), time.time() - t
    ok(h <= 1.45 * (n + 2).bit_length(), "AVL com %d chaves ordenadas: altura %d (BST simples teria %d); %.2fs" % (n, h, n, dt))
    ok(all(a.buscar(i) == i for i in range(0, n, 97)) and a.valida() == [], "buscas corretas e árvore válida")
    for i in range(0, n, 2):
        a.remover(i)
    ok(len(a) == n // 2 and a.valida() == [] and a.buscar(2) is None and a.buscar(3) == 3,
       "remoção de metade das chaves mantém balanceamento")

    t = time.time()
    s = SIGAE()
    s.cadastrar_medico("M", "CRM-1")
    N = 5000
    for i in range(N):                                     # mesma prioridade, chegadas ordenadas (muito empate)
        s.cadastrar_paciente("P", 5, i)
    for i in range(N):                                     # muitas atualizações
        s.reclassificar(1001 + (i * 37) % N, 1 + i % 5)
    ok(s.verificar() == [], "%d pacientes + %d reclassificações: estruturas consistentes" % (N, N))
    anterior, cont = None, 0
    while len(s.fila):
        a = s.chamar_proximo()
        p = s.pacientes.buscar(a.paciente_id)
        chave = (p.risco, p.chegada, p.id)
        assert anterior is None or anterior <= chave, "ordem de chamada quebrada"
        anterior, cont = chave, cont + 1
        s.concluir(a.id)
    ok(cont == N, "%d chamadas em ordem não decrescente de (risco, chegada, ID); %.2fs" % (cont, time.time() - t))


if __name__ == "__main__":
    for teste in (t1_ordem_de_chamada, t2_empates_de_medicos, t3_distribuicao_de_carga,
                  t4_sem_medico_disponivel, t5_cancelar_desfazer_reclassificar,
                  t6_estresse_com_invariantes, t7_casos_adversos):
        teste()
    print("\nTODOS OS TESTES PASSARAM")
