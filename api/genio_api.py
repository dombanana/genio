#!/usr/bin/env python3
"""API do Gênio do Capacho.

Roda atrás do nginx em genio.dombanana.tech/api. Só biblioteca padrão do Python
mais o PyMySQL (pacote python3-pymysql do Ubuntu).

Fase 1: tapetes publicados para o cartão com QR Code.
  - o vendedor publica um tapete (POST /api/tapetes, com a chave de publicação);
  - cada tapete tem um código fixo; cada publicação vira uma nova versão;
  - o cliente abre /t/<código> e a página busca a versão mais nova em /api/t/<código>.

Configuração por variáveis de ambiente (arquivo /etc/genio/env, só o root lê):
  GENIO_DB_HOST, GENIO_DB_USER, GENIO_DB_PASS, GENIO_DB_NAME  (MariaDB)
  GENIO_SQLITE  (caminho de um arquivo SQLite, só para teste local)
  GENIO_CHAVE   (chave de publicação dos vendedores)
  GENIO_PORT    (porta local, padrão 8110)
"""
import base64, hmac, json, os, secrets, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = int(os.environ.get("GENIO_PORT", "8110"))
CHAVE = os.environ.get("GENIO_CHAVE", "")
MAX_BODY = 6 * 1024 * 1024          # prévia JPEG + desenho
ALFA = "23456789abcdefghjkmnpqrstuvwxyz"  # sem 0/o/1/l/i, fácil de ler

# ---------- banco ----------
_lock = threading.Lock()
if os.environ.get("GENIO_SQLITE"):
    import sqlite3
    _conn = sqlite3.connect(os.environ["GENIO_SQLITE"], check_same_thread=False)
    PH = "?"
    def _cur():
        return _conn.cursor()
    def _commit():
        _conn.commit()
    BLOB, TXT, AUTO = "BLOB", "TEXT", "INTEGER PRIMARY KEY AUTOINCREMENT"
else:
    import pymysql
    _conn = None
    PH = "%s"
    def _connect():
        return pymysql.connect(host=os.environ.get("GENIO_DB_HOST", "localhost"), user=os.environ["GENIO_DB_USER"],
                               password=os.environ["GENIO_DB_PASS"], database=os.environ.get("GENIO_DB_NAME", "genio"),
                               charset="utf8mb4", autocommit=False)
    def _cur():
        global _conn
        if _conn is None:
            _conn = _connect()
        try:
            _conn.ping(reconnect=True)
        except Exception:
            _conn = _connect()
        return _conn.cursor()
    def _commit():
        _conn.commit()
    BLOB, TXT, AUTO = "MEDIUMBLOB", "MEDIUMTEXT", "BIGINT PRIMARY KEY AUTO_INCREMENT"

def q(sql, args=(), one=False, commit=False):
    sql = sql.replace("?", PH)
    with _lock:
        c = _cur()
        c.execute(sql, args)
        rows = c.fetchall() if c.description else None
        if commit:
            _commit()
        c.close()
    if rows is None:
        return None
    return (rows[0] if rows else None) if one else rows

def migrar():
    q(f"""CREATE TABLE IF NOT EXISTS tapetes_publicados (
        codigo VARCHAR(12) PRIMARY KEY,
        id_local VARCHAR(64) NOT NULL UNIQUE,
        nome VARCHAR(160) NOT NULL,
        largura_cm INT NOT NULL, altura_cm INT NOT NULL,
        versao INT NOT NULL,
        orcamento VARCHAR(40), vendedor VARCHAR(120), empresa VARCHAR(160), contato VARCHAR(200),
        ativo INT NOT NULL DEFAULT 1,
        aberturas INT NOT NULL DEFAULT 0, ultima_abertura VARCHAR(30),
        criado VARCHAR(30) NOT NULL, atualizado VARCHAR(30) NOT NULL)""", commit=True)
    q(f"""CREATE TABLE IF NOT EXISTS tapete_versoes (
        id {AUTO},
        codigo VARCHAR(12) NOT NULL,
        versao INT NOT NULL,
        largura_cm INT NOT NULL, altura_cm INT NOT NULL,
        desenho {TXT} NOT NULL,
        previa {BLOB},
        criado VARCHAR(30) NOT NULL)""", commit=True)
    try:
        q("CREATE INDEX idx_versoes_codigo ON tapete_versoes (codigo, versao)", commit=True)
    except Exception:
        pass

agora = lambda: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

def novo_codigo():
    for _ in range(20):
        c = "".join(secrets.choice(ALFA) for _ in range(8))
        if not q("SELECT 1 FROM tapetes_publicados WHERE codigo=?", (c,), one=True):
            return c
    raise RuntimeError("sem código livre")

def jpeg_de(data_url):
    if not data_url:
        return None
    if "," in data_url:
        head, data_url = data_url.split(",", 1)
        if "image/jpeg" not in head:
            raise ValueError("a prévia precisa ser JPEG")
    b = base64.b64decode(data_url)
    if b[:3] != b"\xff\xd8\xff":
        raise ValueError("a prévia precisa ser JPEG")
    return b

def publicar(d):
    id_local = str(d.get("id_local") or "")[:64]
    nome = str(d.get("nome") or "Tapete")[:160]
    w, h = int(d.get("largura_cm") or 0), int(d.get("altura_cm") or 0)
    desenho = d.get("desenho")
    if not id_local or not (10 <= w <= 1000) or not (10 <= h <= 1000) or not isinstance(desenho, dict):
        raise ValueError("faltam dados do tapete")
    prev = jpeg_de(d.get("previa"))
    extra = [str(d.get(k) or "")[:n] for k, n in (("orcamento", 40), ("vendedor", 120), ("empresa", 160), ("contato", 200))]
    t = agora()
    row = q("SELECT codigo, versao FROM tapetes_publicados WHERE id_local=?", (id_local,), one=True)
    if row:
        codigo, versao = row[0], row[1] + 1
        q("UPDATE tapetes_publicados SET nome=?, largura_cm=?, altura_cm=?, versao=?, orcamento=?, vendedor=?, empresa=?, contato=?, ativo=1, atualizado=? WHERE codigo=?",
          (nome, w, h, versao, *extra, t, codigo), commit=True)
    else:
        codigo, versao = novo_codigo(), 1
        q("INSERT INTO tapetes_publicados (codigo, id_local, nome, largura_cm, altura_cm, versao, orcamento, vendedor, empresa, contato, criado, atualizado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
          (codigo, id_local, nome, w, h, versao, *extra, t, t), commit=True)
    q("INSERT INTO tapete_versoes (codigo, versao, largura_cm, altura_cm, desenho, previa, criado) VALUES (?,?,?,?,?,?,?)",
      (codigo, versao, w, h, json.dumps(desenho, ensure_ascii=False), prev, t), commit=True)
    return {"codigo": codigo, "versao": versao, "link": f"/t/{codigo}"}

def ler(codigo, contar=True):
    row = q("SELECT codigo, nome, largura_cm, altura_cm, versao, empresa, contato, ativo, atualizado, aberturas FROM tapetes_publicados WHERE codigo=?", (codigo,), one=True)
    if not row or not row[7]:
        return None
    v = q("SELECT desenho FROM tapete_versoes WHERE codigo=? AND versao=?", (codigo, row[4]), one=True)
    if contar:
        q("UPDATE tapetes_publicados SET aberturas=aberturas+1, ultima_abertura=? WHERE codigo=?", (agora(), codigo), commit=True)
    return {"codigo": row[0], "nome": row[1], "largura_cm": row[2], "altura_cm": row[3], "versao": row[4], "empresa": row[5], "contato": row[6],
            "atualizado": row[8], "desenho": json.loads(v[0]) if v else None, "previa": f"/api/t/{row[0]}/previa.jpg?v={row[4]}"}

def previa(codigo):
    row = q("SELECT v.previa FROM tapetes_publicados p JOIN tapete_versoes v ON v.codigo=p.codigo AND v.versao=p.versao WHERE p.codigo=? AND p.ativo=1", (codigo,), one=True)
    return row[0] if row and row[0] else None

def status(codigos):
    out = {}
    for c in codigos[:200]:
        row = q("SELECT versao, aberturas, ultima_abertura FROM tapetes_publicados WHERE codigo=?", (c,), one=True)
        if row:
            out[c] = {"versao": row[0], "aberturas": row[1], "ultima_abertura": row[2]}
    return out

# ---------- HTTP ----------
def codigo_ok(c):
    return 4 <= len(c) <= 12 and all(ch in ALFA for ch in c)

class H(BaseHTTPRequestHandler):
    server_version = "genio-api/1"

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def _send(self, code, obj=None, body=None, ctype="application/json; charset=utf-8", cache="no-store"):
        if body is None:
            body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _erro(self, code, msg):
        self._send(code, {"erro": msg})

    def _autorizado(self):
        k = self.headers.get("X-Genio-Chave", "")
        return bool(CHAVE) and hmac.compare_digest(k.encode(), CHAVE.encode())

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("tamanho inválido")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            if p == "/api/saude":
                q("SELECT 1", one=True)
                return self._send(200, {"ok": True, "banco": True, "hora": agora()})
            parts = p.split("/")
            if len(parts) == 4 and parts[1:3] == ["api", "t"] and codigo_ok(parts[3]):
                d = ler(parts[3])
                return self._send(200, d) if d else self._erro(404, "tapete não encontrado")
            if len(parts) == 5 and parts[1:3] == ["api", "t"] and parts[4] == "previa.jpg" and codigo_ok(parts[3]):
                b = previa(parts[3])
                return self._send(200, body=b, ctype="image/jpeg", cache="public, max-age=86400") if b else self._erro(404, "sem prévia")
            return self._erro(404, "não encontrado")
        except Exception as e:
            sys.stderr.write("erro GET %r\n" % e)
            return self._erro(500, "erro no servidor")
    do_HEAD = do_GET

    def do_POST(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            if p in ("/api/tapetes", "/api/status"):
                if not self._autorizado():
                    return self._erro(401, "chave de publicação inválida")
                d = self._json()
                if p == "/api/tapetes":
                    return self._send(200, publicar(d))
                return self._send(200, status([c for c in d.get("codigos", []) if isinstance(c, str) and codigo_ok(c)]))
            return self._erro(404, "não encontrado")
        except ValueError as e:
            return self._erro(400, str(e))
        except Exception as e:
            sys.stderr.write("erro POST %r\n" % e)
            return self._erro(500, "erro no servidor")

def main():
    migrar()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    sys.stderr.write(f"genio-api ouvindo em 127.0.0.1:{PORT}\n")
    srv.serve_forever()

if __name__ == "__main__":
    main()
