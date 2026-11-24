"""Servidor do SIGAE WEB. Execute: python server.py  ->  http://127.0.0.1:8000

Usa apenas a biblioteca padrão do Python para falar HTTP (http.server) e JSON.
Toda a lógica e todas as estruturas de dados estão em sistema.py / structures.py.
O servidor atende uma requisição por vez, então as operações são naturalmente serializadas.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from sistema import SIGAE, SIT_P, ErroSistema, converter_hora, popular_demo

S = SIGAE()
PASTA = os.path.dirname(os.path.abspath(__file__))


def _id(txt):
    if not txt.isdigit():
        raise ErroSistema("ID inválido.")
    return int(txt)


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            raise ErroSistema("JSON inválido.")

    def _tratar(self, metodo):
        caminho, _, qs = self.path.partition("?")
        partes = [x for x in caminho.split("/") if x]
        try:
            if metodo == "GET" and not partes:
                with open(os.path.join(PASTA, "index.html"), "rb") as f:
                    return self._enviar(200, f.read(), "text/html; charset=utf-8")
            if partes[:1] != ["api"]:
                return self._enviar(404, {"erro": "Não encontrado."})
            self._enviar(200, self._rota(metodo, partes[1:], qs))
        except ErroSistema as e:
            self._enviar(400, {"erro": str(e)})
        except Exception as e:  # noqa
            self._enviar(500, {"erro": "Erro interno: %s" % e})

    def _rota(self, m, p, qs):
        if m == "GET":
            if p == ["painel"]:
                return S.painel()
            if p == ["pacientes"]:
                sit = SIT_P[int(qs[2:])] if qs.startswith("s=") and qs[2:].isdigit() and int(qs[2:]) < 4 else None
                return [x.json() for x in S.listar_pacientes(sit)]
            if len(p) == 2 and p[0] == "pacientes":
                return S.buscar_paciente(_id(p[1])).json()
            if p == ["medicos"]:
                return [x.json() for x in S.listar_medicos()]
            if p == ["atendimentos"]:
                return [x.json() for x in S.listar_atendimentos()]
            if p == ["historico"]:
                return S.historico()
        else:
            b = self._corpo()
            if p == ["pacientes"]:
                return S.cadastrar_paciente(b.get("nome"), b.get("risco"), converter_hora(b.get("chegada"))).json()
            if len(p) == 3 and p[0] == "pacientes" and p[2] == "reclassificar":
                return S.reclassificar(_id(p[1]), b.get("risco")).json()
            if len(p) == 3 and p[0] == "pacientes" and p[2] == "cancelar":
                return S.cancelar_paciente(_id(p[1])).json()
            if p == ["medicos"]:
                return S.cadastrar_medico(b.get("nome"), b.get("crm")).json()
            if len(p) == 3 and p[0] == "medicos" and p[2] == "disponibilidade":
                return S.alterar_disponibilidade(_id(p[1]), b.get("situacao")).json()
            if p == ["chamar"]:
                try:
                    n = int(b.get("quantidade", 1))
                except (TypeError, ValueError):
                    raise ErroSistema("Quantidade inválida.")
                feitas, motivo = S.chamar_varios(max(1, min(n, 50)))
                txt = "%d chamada(s) realizada(s)." % len(feitas)
                return {"atendimentos": [a.json() for a in feitas],
                        "motivo": txt + (" Parou: " + motivo if motivo else "")}
            if len(p) == 3 and p[0] == "atendimentos" and p[2] == "concluir":
                return S.concluir(_id(p[1])).json()
            if len(p) == 3 and p[0] == "atendimentos" and p[2] == "desfazer":
                return S.desfazer_chamada(_id(p[1])).json()
            if p == ["demo"]:
                if len(S.medicos) or len(S.pacientes):
                    raise ErroSistema("Os dados de demonstração só carregam com o sistema vazio.")
                popular_demo(S)
                return {"motivo": "Dados fictícios carregados."}
        raise ErroSistema("Rota inexistente.")

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")


if __name__ == "__main__":
    print("SIGAE WEB em http://127.0.0.1:8000  (Ctrl+C para sair)")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
