#!/usr/bin/env python3
"""API do Gênio do Capacho.

Roda atrás do nginx em genio.dombanana.tech/api. Só biblioteca padrão do Python
mais o PyMySQL (pacote python3-pymysql do Ubuntu).

Fase 1: tapetes publicados para o cartão com QR Code.
Fase 2: contas (administrador e vendedores), login por e-mail e senha, convites, aparelhos por plano
        e pedidos de "quero vender" da página de vendas.
  - o vendedor publica um tapete (POST /api/tapetes, com a chave de publicação);
  - cada tapete tem um código fixo; cada publicação vira uma nova versão;
  - o cliente abre /t/<código> e a página busca a versão mais nova em /api/t/<código>.

Configuração por variáveis de ambiente (arquivo /etc/genio/env, só o root lê):
  GENIO_DB_HOST, GENIO_DB_USER, GENIO_DB_PASS, GENIO_DB_NAME  (MariaDB)
  GENIO_SQLITE  (caminho de um arquivo SQLite, só para teste local)
  GENIO_CHAVE   (chave de publicação dos vendedores)
  GENIO_PORT    (porta local, padrão 8110)
"""
import base64, hashlib, hmac, json, os, re, secrets, subprocess, sys, threading, time
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

def q_insert(sql, args=()):
    sql = sql.replace("?", PH)
    with _lock:
        c = _cur()
        c.execute(sql, args)
        rid = c.lastrowid
        _commit()
        c.close()
    return rid

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
    # contas
    q(f"""CREATE TABLE IF NOT EXISTS contas (
        id {AUTO}, nome VARCHAR(120) NOT NULL, email VARCHAR(190) NOT NULL UNIQUE, senha VARCHAR(200),
        papel VARCHAR(20) NOT NULL, plano VARCHAR(20) NOT NULL, ativo INT NOT NULL DEFAULT 1,
        criado VARCHAR(30) NOT NULL, ultimo_acesso VARCHAR(30))""", commit=True)
    q(f"""CREATE TABLE IF NOT EXISTS aparelhos (
        id {AUTO}, conta_id BIGINT NOT NULL, chave VARCHAR(64) NOT NULL, nome VARCHAR(160),
        ativo INT NOT NULL DEFAULT 1, criado VARCHAR(30) NOT NULL, visto VARCHAR(30))""", commit=True)
    q("""CREATE TABLE IF NOT EXISTS sessoes (
        token VARCHAR(64) PRIMARY KEY, conta_id BIGINT NOT NULL, aparelho_id BIGINT,
        criado VARCHAR(30) NOT NULL, visto VARCHAR(30), expira VARCHAR(30) NOT NULL)""", commit=True)
    q("""CREATE TABLE IF NOT EXISTS convites (
        token VARCHAR(64) PRIMARY KEY, conta_id BIGINT NOT NULL, criado VARCHAR(30) NOT NULL,
        expira VARCHAR(30) NOT NULL, usado VARCHAR(30))""", commit=True)
    q(f"""CREATE TABLE IF NOT EXISTS interesse (
        id {AUTO}, nome VARCHAR(120) NOT NULL, telefone VARCHAR(40) NOT NULL, cidade VARCHAR(120),
        mensagem VARCHAR(600), criado VARCHAR(30) NOT NULL, visto INT NOT NULL DEFAULT 0)""", commit=True)
    for idx in ("CREATE INDEX idx_aparelhos_conta ON aparelhos (conta_id, chave)",
                "CREATE INDEX idx_sessoes_conta ON sessoes (conta_id)"):
        try:
            q(idx, commit=True)
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

# ---------- contas ----------
# Planos: limite de aparelhos ligados à conta (vendedor = aparelho conectado). None = sem limite.
PLANOS = {
    "vendedor":  {"nome": "Vendedor", "aparelhos": 1, "orcamentos": 150},
    "ilimitado": {"nome": "Vendedor Ilimitado", "aparelhos": 1, "orcamentos": None},
    "admin":     {"nome": "Administrador", "aparelhos": None, "orcamentos": None},
}
SESSAO_DIAS = 180
CONVITE_DIAS = 7
EMAIL_OK = re.compile(r"^[^@\s]{1,80}@[^@\s]{1,100}\.[^@\s]{2,20}$")
h64 = lambda t: hashlib.sha256(t.encode()).hexdigest()
quando = lambda dias: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + dias * 86400))

def senha_hash(senha):
    sal = secrets.token_bytes(16)
    d = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, 210000)
    return "pbkdf2$210000$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(d).decode()

def senha_ok(senha, guardada):
    try:
        _, it, sal, d = (guardada or "").split("$")
        x = hashlib.pbkdf2_hmac("sha256", senha.encode(), base64.b64decode(sal), int(it))
        return hmac.compare_digest(x, base64.b64decode(d))
    except Exception:
        return False

def senha_valida(senha):
    if not isinstance(senha, str) or len(senha) < 8 or len(senha) > 200:
        raise ValueError("a senha precisa ter pelo menos 8 caracteres")

# tentativas de login: no máximo 8 por e-mail e 30 por endereço a cada 15 minutos
_tent = {}
def limite(chave, n, janela=900):
    t = time.time()
    L = [x for x in _tent.get(chave, []) if t - x < janela]
    if len(L) >= n:
        _tent[chave] = L
        return False
    L.append(t)
    _tent[chave] = L
    return True

def conta_pub(row):
    cid, nome, email, papel, plano, ativo, criado, ult = row
    return {"id": cid, "nome": nome, "email": email, "papel": papel, "plano": plano, "plano_nome": PLANOS.get(plano, {}).get("nome", plano),
            "ativo": bool(ativo), "criado": criado, "ultimo_acesso": ult}

CONTA_COLS = "id, nome, email, papel, plano, ativo, criado, ultimo_acesso"

def aparelho_registrar(conta_id, plano, chave, nome):
    chave = str(chave or "")[:64]
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", chave):
        raise ValueError("aparelho inválido")
    row = q("SELECT id, ativo FROM aparelhos WHERE conta_id=? AND chave=?", (conta_id, chave), one=True)
    if row and row[1]:
        q("UPDATE aparelhos SET visto=?, nome=? WHERE id=?", (agora(), str(nome or "")[:160], row[0]), commit=True)
        return row[0]
    lim = PLANOS.get(plano, {}).get("aparelhos", 1)
    if lim is not None:
        n = q("SELECT COUNT(*) FROM aparelhos WHERE conta_id=? AND ativo=1", (conta_id,), one=True)[0]
        if n >= lim:
            raise PermissionError(f"o seu plano permite {lim} aparelho{'s' if lim > 1 else ''}. Peça ao administrador para liberar este aparelho.")
    if row:
        q("UPDATE aparelhos SET ativo=1, visto=?, nome=? WHERE id=?", (agora(), str(nome or "")[:160], row[0]), commit=True)
        return row[0]
    return q_insert("INSERT INTO aparelhos (conta_id, chave, nome, ativo, criado, visto) VALUES (?,?,?,1,?,?)",
                    (conta_id, chave, str(nome or "")[:160], agora(), agora()))

def sessao_nova(conta_id, aparelho_id):
    tok = secrets.token_urlsafe(32)
    q("INSERT INTO sessoes (token, conta_id, aparelho_id, criado, visto, expira) VALUES (?,?,?,?,?,?)",
      (h64(tok), conta_id, aparelho_id, agora(), agora(), quando(SESSAO_DIAS)), commit=True)
    q("UPDATE contas SET ultimo_acesso=? WHERE id=?", (agora(), conta_id), commit=True)
    return tok

def sessao_conta(tok):
    if not tok:
        return None
    row = q(f"""SELECT c.id, c.nome, c.email, c.papel, c.plano, c.ativo, c.criado, c.ultimo_acesso, s.expira, s.aparelho_id, a.ativo
               FROM sessoes s JOIN contas c ON c.id=s.conta_id LEFT JOIN aparelhos a ON a.id=s.aparelho_id WHERE s.token=?""", (h64(tok),), one=True)
    if not row or not row[5] or row[8] < agora():
        return None
    if row[9] is not None and not row[10]:          # aparelho desligado pelo administrador
        return None
    c = conta_pub(row[:8])
    c["aparelho_id"] = row[9]
    return c

def entrar(d):
    email = str(d.get("email") or "").strip().lower()
    row = q("SELECT id, senha, papel, plano, ativo FROM contas WHERE email=?", (email,), one=True)
    if not row or not row[1] or not senha_ok(str(d.get("senha") or ""), row[1]):
        raise PermissionError("e-mail ou senha não conferem")
    if not row[4]:
        raise PermissionError("esta conta está desativada. Fale com o administrador.")
    ap = aparelho_registrar(row[0], row[3] if row[2] != "admin" else "admin", d.get("aparelho"), d.get("nome_aparelho"))
    return sessao_nova(row[0], ap)

def convite_novo(conta_id):
    tok = secrets.token_urlsafe(24)
    q("INSERT INTO convites (token, conta_id, criado, expira) VALUES (?,?,?,?)", (h64(tok), conta_id, agora(), quando(CONVITE_DIAS)), commit=True)
    return tok

def convite_ler(tok):
    row = q("""SELECT v.conta_id, v.expira, v.usado, c.nome, c.email, c.ativo FROM convites v JOIN contas c ON c.id=v.conta_id WHERE v.token=?""",
            (h64(str(tok or "")),), one=True)
    if not row or row[2] or row[1] < agora() or not row[5]:
        return None
    return {"conta_id": row[0], "nome": row[3], "email": row[4]}

def convite_usar(tok, d):
    cv = convite_ler(tok)
    if not cv:
        raise ValueError("este convite não vale mais. Peça um novo ao administrador.")
    senha_valida(d.get("senha"))
    q("UPDATE contas SET senha=? WHERE id=?", (senha_hash(d["senha"]), cv["conta_id"]), commit=True)
    q("UPDATE convites SET usado=? WHERE token=?", (agora(), h64(tok)), commit=True)
    q("DELETE FROM sessoes WHERE conta_id=?", (cv["conta_id"],), commit=True)   # senha nova: as sessões antigas saem
    return entrar({"email": cv["email"], "senha": d["senha"], "aparelho": d.get("aparelho"), "nome_aparelho": d.get("nome_aparelho")})

# Primeiro acesso: só enquanto não existe administrador, e só com o código cujo hash está no repositório.
PRIMEIRO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "primeiro_acesso.sha256")
def primeiro_valido(tok):
    if q("SELECT 1 FROM contas WHERE papel='admin'", one=True):
        return False
    try:
        alvo = open(PRIMEIRO).read().strip()
    except Exception:
        return False
    return bool(tok) and hmac.compare_digest(h64(str(tok)), alvo)

def primeiro_usar(d):
    if not primeiro_valido(d.get("c")):
        raise ValueError("este link de primeiro acesso não vale mais")
    nome = str(d.get("nome") or "").strip()[:120]
    email = str(d.get("email") or "").strip().lower()[:190]
    if not nome or not EMAIL_OK.match(email):
        raise ValueError("confira o nome e o e-mail")
    senha_valida(d.get("senha"))
    q_insert("INSERT INTO contas (nome, email, senha, papel, plano, ativo, criado) VALUES (?,?,?,'admin','admin',1,?)",
             (nome, email, senha_hash(d["senha"]), agora()))
    return entrar({"email": email, "senha": d["senha"], "aparelho": d.get("aparelho"), "nome_aparelho": d.get("nome_aparelho")})

def admin_contas():
    out = []
    for row in q(f"SELECT {CONTA_COLS} FROM contas ORDER BY id DESC") or []:
        c = conta_pub(row)
        c["tem_senha"] = bool(q("SELECT 1 FROM contas WHERE id=? AND senha IS NOT NULL", (c["id"],), one=True))
        c["aparelhos"] = [{"id": a[0], "nome": a[1], "criado": a[2], "visto": a[3]}
                          for a in q("SELECT id, nome, criado, visto FROM aparelhos WHERE conta_id=? AND ativo=1 ORDER BY id", (c["id"],)) or []]
        out.append(c)
    return out

def admin_criar(d):
    nome = str(d.get("nome") or "").strip()[:120]
    email = str(d.get("email") or "").strip().lower()[:190]
    plano = str(d.get("plano") or "vendedor")
    papel = "admin" if plano == "admin" else "vendedor"
    if not nome or not EMAIL_OK.match(email):
        raise ValueError("confira o nome e o e-mail")
    if plano not in PLANOS:
        raise ValueError("plano desconhecido")
    if q("SELECT 1 FROM contas WHERE email=?", (email,), one=True):
        raise ValueError("já existe uma conta com este e-mail")
    cid = q_insert("INSERT INTO contas (nome, email, papel, plano, ativo, criado) VALUES (?,?,?,?,1,?)", (nome, email, papel, plano, agora()))
    return {"id": cid, "convite": convite_novo(cid)}

def admin_mudar(cid, d, eu):
    row = q("SELECT id, papel FROM contas WHERE id=?", (cid,), one=True)
    if not row:
        raise ValueError("conta não encontrada")
    if "ativo" in d:
        if cid == eu["id"] and not d["ativo"]:
            raise ValueError("você não pode desativar a própria conta")
        q("UPDATE contas SET ativo=? WHERE id=?", (1 if d["ativo"] else 0, cid), commit=True)
        if not d["ativo"]:
            q("DELETE FROM sessoes WHERE conta_id=?", (cid,), commit=True)
    if "plano" in d:
        if d["plano"] not in PLANOS or d["plano"] == "admin" or row[1] == "admin":
            raise ValueError("plano inválido")
        q("UPDATE contas SET plano=? WHERE id=?", (d["plano"], cid), commit=True)
    return {"ok": True}

def admin_aparelho_tirar(aid):
    q("UPDATE aparelhos SET ativo=0 WHERE id=?", (aid,), commit=True)
    q("DELETE FROM sessoes WHERE aparelho_id=?", (aid,), commit=True)
    return {"ok": True}

def interesse_novo(d, ip):
    nome = str(d.get("nome") or "").strip()[:120]
    tel = re.sub(r"[^0-9+() -]", "", str(d.get("telefone") or ""))[:40].strip()
    if not nome or len(re.sub(r"\D", "", tel)) < 10:
        raise ValueError("informe o nome e um telefone com DDD")
    q_insert("INSERT INTO interesse (nome, telefone, cidade, mensagem, criado) VALUES (?,?,?,?,?)",
             (nome, tel, str(d.get("cidade") or "").strip()[:120], str(d.get("mensagem") or "").strip()[:600], agora()))
    return {"ok": True}

def admin_interesse():
    return [{"id": r[0], "nome": r[1], "telefone": r[2], "cidade": r[3], "mensagem": r[4], "criado": r[5], "visto": bool(r[6])}
            for r in q("SELECT id, nome, telefone, cidade, mensagem, criado, visto FROM interesse ORDER BY id DESC") or []]

# ---------- HTTP ----------
def codigo_ok(c):
    return 4 <= len(c) <= 12 and all(ch in ALFA for ch in c)

# ---------- chaves de serviços externos (Places, Serper, Apify, ZapSign…) ----------
CHAVES_ARQ = os.environ.get("GENIO_CHAVES", "/var/lib/genio/chaves.json")
# ---------- captura de logotipo: imagens do site do cliente, busca de imagens e proxy ----------
from urllib import request as _rq
from urllib.parse import urljoin as _urljoin, parse_qs as _parse_qs, quote as _quote
_UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
def site_imagens(url):
    """Imagens que o site do cliente mostra (cabeçalho primeiro), para o representante marcar o logotipo com o dedo."""
    if not re.match(r"^https?://", url or ""):
        url = "https://" + (url or "")
    html_ = _rq.urlopen(_rq.Request(url, headers=_UA), timeout=20).read(600_000).decode("utf-8", "replace")
    titulo = (re.search(r"<title[^>]*>(.*?)</title>", html_, re.I | re.S) or [None, ""])[1].strip()[:120]
    def srcs(trecho):
        out = []
        for m in re.finditer(r"<img[^>]+>", trecho, re.I):
            t = m.group(0); src = re.search(r'(?:data-src|data-lazy-src|src)=["\']([^"\']+)', t)
            ss = re.search(r'srcset=["\']([^"\']+)', t)
            u = (ss.group(1).split(",")[-1].strip().split(" ")[0] if ss else None) or (src.group(1) if src else None)
            if u and not u.startswith("data:"):
                alt = re.search(r'alt=["\']([^"\']*)', t)
                out.append({"u": _urljoin(url, u), "alt": (alt.group(1) if alt else "")[:60], "logo": bool(re.search(r"logo|marca|brand", t, re.I))})
        return out
    cab = " ".join(re.findall(r"<(?:header|nav)[^>]*>.*?</(?:header|nav)>", html_, re.I | re.S))
    lista = srcs(cab); lista += srcs(html_)
    for m in re.finditer(r'<(?:meta|link)[^>]+(?:property=["\']og:image["\']|rel=["\'][^"\']*icon[^"\']*["\'])[^>]*>', html_, re.I):
        h = re.search(r'(?:content|href)=["\']([^"\']+)', m.group(0))
        if h:
            lista.append({"u": _urljoin(url, h.group(1)), "alt": "ícone / imagem de compartilhamento", "logo": True})
    vistos, out = set(), []
    for it in lista:
        if it["u"] in vistos or re.search(r"\.svg(\?|$)|pixel|tracking|1x1", it["u"], re.I):
            continue
        vistos.add(it["u"]); out.append(it)
        if len(out) >= 60:
            break
    out.sort(key=lambda x: (not x["logo"]))
    return {"url": url, "titulo": titulo, "imagens": out}
def busca_imagens(qtxt):
    k = chaves_ler().get("SERPER_KEY")
    if not k:
        return {"erro": "SERPER_KEY não definida na tela Chaves"}
    body = json.dumps({"q": qtxt, "gl": "br", "hl": "pt-br", "num": 30}).encode()
    r = _rq.urlopen(_rq.Request("https://google.serper.dev/images", data=body, headers={"X-API-KEY": k, "Content-Type": "application/json"}), timeout=25)
    d = json.loads(r.read().decode("utf-8", "replace"))
    return {"q": qtxt, "imagens": [{"u": i.get("imageUrl"), "thumb": i.get("thumbnailUrl") or i.get("imageUrl"), "titulo": (i.get("title") or "")[:80], "fonte": i.get("source") or i.get("domain") or "", "pagina": i.get("link")} for i in d.get("images", []) if i.get("imageUrl")]}
def proxy_img(u):
    if not re.match(r"^https?://", u or ""):
        raise ValueError("endereço inválido")
    r = _rq.urlopen(_rq.Request(u, headers=dict(_UA, Referer="https://www.google.com/")), timeout=25)
    ct = r.headers.get("Content-Type", "application/octet-stream").split(";")[0]
    if not ct.startswith("image/"):
        raise ValueError("não é imagem")
    return ct, r.read(8_000_000)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_DIR = os.path.dirname(CHAVES_ARQ) if os.path.dirname(CHAVES_ARQ) else "/var/lib/genio"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import dados as DADOS; import mostra as MOSTRA  # fichas, notas e estado do app: fonte única no servidor
MAX_FICHA = 60 * 1024 * 1024  # ficha com artes em base64 (vira arquivos no servidor)
KIT_IDS = {"capacho": "01", "placas": "02", "adesivos": "03", "uniformes": "04", "impressos": "05", "panfleto": "06", "banners": "07", "parede": "08", "brindes": "09", "carimbo": "10",
           "windbanner": "11", "faixa": "12", "folheto": "13", "camiseta": "14", "bone": "15", "avental": "16"}
# setor do app → pasta do kit de 14 setores (o mesmo mapa de app/kits14.js)
SETOR_KIT14 = {"cafeteria": "01_Cafeteria", "restaurante": "02_Restaurante", "bar": "02_Restaurante", "padaria": "03_Padaria", "clínica/consultório": "04_Clinica",
    "estética": "05_Estetica", "salão/barbearia": "06_Salao", "escritório/imobiliária": "07_Imobiliaria", "loja de roupas/calçados": "08_Loja_Roupas",
    "floricultura/presentes": "08_Loja_Roupas", "pet": "09_Pet_Shop", "farmácia": "10_Farmacia", "ótica": "10_Farmacia", "academia/estúdio": "11_Academia",
    "autopeças/oficina": "12_Autopecas", "celular/assistência": "13_Escritorio", "escola/curso": "13_Escritorio", "cereais/empório": "14_Mercado",
    "mercado/hortifruti": "14_Mercado", "embalagens/utilidades": "14_Mercado", "comércio": "14_Mercado"}
def disco_uso():
    """quanto o GênIO ocupa no disco da VPS (só leitura): disco inteiro e cada pasta de dados, em MB"""
    import shutil
    def tam(raiz):
        t, n = 0, 0
        for dp, _, fs in os.walk(raiz):
            for f in fs:
                try:
                    t += os.path.getsize(os.path.join(dp, f)); n += 1
                except OSError:
                    pass
        return round(t / 1048576, 1), n
    u = shutil.disk_usage("/"); pastas = {}
    for nome, cam in (("dados", DADOS.RAIZ_DADOS), ("renderizacoes_kits", os.path.join(ESTADO_DIR, "kits")), ("estado", ESTADO_DIR), ("codigo", RAIZ)):
        if os.path.isdir(cam):
            mb, n = tam(cam); pastas[nome] = {"caminho": cam, "mb": mb, "arquivos": n}
    if os.path.isdir(DADOS.RAIZ_DADOS):
        for sub in sorted(os.listdir(DADOS.RAIZ_DADOS)):
            c = os.path.join(DADOS.RAIZ_DADOS, sub)
            if os.path.isdir(c):
                mb, n = tam(c); pastas["dados/" + sub] = {"mb": mb, "arquivos": n}
    return {"disco_total_gb": round(u.total / 1e9, 1), "disco_usado_gb": round(u.used / 1e9, 1), "disco_livre_gb": round(u.free / 1e9, 1), "pastas": pastas}

def peca_provar(d):
    """Provar a peça na foto: recorte da peça, troca de cor (mantém a luz) e posição da logo pelas medidas da peça.
    A foto e o recorte ficam em cache pelo id; trocar a cor manda só {id, cor}."""
    import numpy as np, cv2
    sys.path.insert(0, os.path.join(RAIZ, "api", "kits")); import provar
    pasta = os.path.join(ESTADO_DIR, "provas"); os.makedirs(pasta, exist_ok=True)
    peca = d.get("peca") if d.get("peca") in provar.REGRA else "camiseta"
    pid = re.sub(r"[^a-f0-9]", "", str(d.get("id") or ""))[:24]
    if d.get("foto"):
        raw = base64.b64decode(str(d["foto"]).split(",", 1)[-1]); pid = hashlib.sha256(raw).hexdigest()[:24]
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("foto ilegível")
        k = min(1.0, 1600 / max(img.shape[:2])); img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else img
        cv2.imwrite(os.path.join(pasta, pid + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    img = cv2.imread(os.path.join(pasta, pid + ".jpg"))
    if img is None:
        raise ValueError("foto não encontrada: mande de novo")
    ponto = d.get("ponto") if isinstance(d.get("ponto"), list) and len(d["ponto"]) == 2 else None
    try:
        tol = max(0.4, min(2.5, float(d.get("tol") or 1.0)))
    except (TypeError, ValueError):
        tol = 1.0
    mp = os.path.join(pasta, f"{pid}.{peca}.png")
    if ponto or d.get("tol") is not None or not os.path.exists(mp):
        m = provar.recortar(img, ponto, tol)
        if m is None:
            raise ValueError("não achei a peça: toque em cima dela")
        cv2.imwrite(mp, m)
    m = cv2.imread(mp, cv2.IMREAD_GRAYSCALE); med = provar.medir(m, peca)
    cor = d.get("cor") if re.match(r"^#[0-9a-fA-F]{6}$", d.get("cor") or "") else None
    out = provar.tingir(img, m, cor) if cor else img
    ok, jpg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 86])
    r = {"id": pid, "peca": peca, "w": int(img.shape[1]), "h": int(img.shape[0]), "medidas": med, "jpg": "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()}
    if d.get("camada"):   # provador com ferramentas: foto original + recorte (máscara) para a cor ser aplicada e corrigida no aparelho
        ok2, png = cv2.imencode(".png", m)
        r["mascara"] = "data:image/png;base64," + base64.b64encode(png.tobytes()).decode()
    return r

# ---- Mostraí: arquivos da loja e pesquisa de imagem dentro da programação (o código do Mostraí é a chave; só leitura da ficha)
def mostra_arquivos(token):
    """imagens ligadas à loja (logotipos, fachada, produtos, arquivo, artes e provas) para escolher a foto de uma tela"""
    est = MOSTRA.ler(token)
    if not est:
        raise FileNotFoundError
    f = DADOS.cliente_ler(est["slug"]) or {}
    out, vistos = [], set()
    def add(src, tag):
        if isinstance(src, str) and src and src not in vistos and src not in (f.get("descartadas") or []):
            vistos.add(src); out.append({"tag": tag, "src": src})
    m = f.get("manual") or {}
    add(m.get("tratado"), "Logotipo tratado")
    for x in f.get("logos") or []:
        add(x.get("src"), "Logotipo")
    add((f.get("fachada") or {}).get("src"), "Fachada")
    for x in f.get("produtos") or []:
        add(x.get("src"), "Produto")
    for x in f.get("arquivo") or []:
        add(x.get("src"), "Arquivo")
    for k, a in (f.get("artes") or {}).items():
        if isinstance(a, dict):
            add(a.get("contexto") or a.get("png"), "Arte · " + k.split("~")[0])
            for pr in a.get("provas") or []:
                add((pr or {}).get("src"), "Prova · " + k.split("~")[0])
    return out[:80]

def mostra_arquivo_bytes(token, i):
    """bytes da i-ésima imagem da loja (para a miniatura e para virar foto da tela)"""
    lista = mostra_arquivos(token)
    if not (0 <= i < len(lista)):
        raise FileNotFoundError
    src = lista[i]["src"]
    if src.startswith("data:image/"):
        cab, b64 = src.split(",", 1); return cab[5:].split(";")[0], base64.b64decode(b64)
    if src.startswith("/api/arq/"):
        pt = src.split("?")[0].split("/")
        return DADOS.arquivo(pt[3], pt[4], pt[5])
    if src.startswith("http"):
        return proxy_img(src)
    rel = src.split("?")[0].lstrip("/")
    cam = os.path.realpath(os.path.join(RAIZ, rel))
    if not cam.startswith(os.path.realpath(os.path.join(RAIZ, "dados")) + os.sep) and not cam.startswith(os.path.realpath(os.path.join(RAIZ, "brand")) + os.sep):
        raise ValueError("caminho inválido")
    ext = cam.rsplit(".", 1)[-1].lower()
    with open(cam, "rb") as fh:
        return {"png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg"), fh.read()

def mostra_foto_de(token, d):
    """foto de uma tela a partir de um arquivo da loja ({arquivo: i}) ou de uma imagem da pesquisa ({url}); vira JPEG de até 1080 px"""
    import numpy as np, cv2
    if d.get("arquivo") is not None:
        _, raw = mostra_arquivo_bytes(token, int(d["arquivo"]))
    else:
        _, raw = proxy_img(str(d.get("url") or ""))
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("imagem ilegível")
    if img.ndim == 3 and img.shape[2] == 4:   # PNG com transparência: fundo branco
        a = img[..., 3:4].astype(np.float32) / 255; img = (img[..., :3].astype(np.float32) * a + 255 * (1 - a)).astype(np.uint8)
    elif img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    k = min(1.0, 1080 / max(img.shape[:2])); img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else img
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 84])
    return MOSTRA.foto_gravar(token, "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode(), d.get("tela"))

def kit_aplicar(d):
    """Contextualização: a arte feita no editor (PNG transparente, base64) aplicada na capa calibrada do kit do setor."""
    import hashlib, tempfile
    sys.path.insert(0, os.path.join(RAIZ, "api", "kits")); import aplicar, gerar_kit
    setor_app = d.get("setor") or ""
    if os.path.isdir(os.path.join(RAIZ, "brand", "kits14")):
        kit = SETOR_KIT14.get(setor_app) or SETOR_KIT14.get(setor_app.split("/")[0] if setor_app else "", "14_Mercado"); ref = False
    else:
        kit, ref = gerar_kit.kit_para(setor_app.split("/")[0])
    pid = KIT_IDS.get(d.get("produto"), d.get("produto")); png = d.get("png") or ""
    if png.startswith("/api/arq/"):
        _, col, ident, nome = png.split("/")[2:6]
        raw = DADOS.arquivo(col, ident, nome)[1]
    else:
        if "," in png[:40]:
            png = png.split(",", 1)[1]
        raw = base64.b64decode(png)
    if len(raw) > 6_000_000:
        raise ValueError("arte grande demais")
    material = d.get("material") if re.match(r"^#[0-9a-fA-F]{6}$", d.get("material") or "") else None
    # carimbo: as marcas do kit (PAGO, RECEBIDO, data, redondo com a marca) + o carimbo grande da empresa, cada uma na sua folha
    if pid == "10" and os.path.isdir(os.path.join(RAIZ, "brand", "kits14")):
        _, P10, _img = aplicar.carregar(kit, "10")
        if P10.get("carimbos"):
            slug = re.sub(r"[^a-z0-9-]", "", str(d.get("slug") or ""))[:80]; ficha = {}
            try:
                ficha = (DADOS.cliente_ler(slug) if slug else {}) or {}
            except Exception:
                ficha = {}
            nome = str(d.get("nome") or (ficha or {}).get("nome") or "")[:40]; logo_raw = None
            src = ((ficha or {}).get("manual") or {}).get("tratado") or ""
            if src.startswith("/api/arq/"):
                try:
                    _, col, ident, nm = src.split("/")[2:6]; logo_raw = DADOS.arquivo(col, ident, nm)[1]
                except Exception:
                    logo_raw = None
            hoje = time.strftime("%Y-%m-%d")
            campos = d.get("campos") if isinstance(d.get("campos"), dict) else None
            if campos:
                campos = {k: str(campos.get(k) or "")[:80] for k in ("nome", "razao", "cnpj", "endereco", "tel")}
            h = hashlib.sha256(raw + (logo_raw or b"") + f"|{kit}|10|{nome}|{hoje}|{json.dumps(campos, sort_keys=True)}|carimbo3".encode()).hexdigest()[:20]
            pasta = os.path.join(ESTADO_DIR, "kits"); os.makedirs(pasta, exist_ok=True); saida = os.path.join(pasta, h + ".jpg")
            if not os.path.exists(saida):
                tmps = []
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        f.write(raw); tmps.append(f.name)
                    lp = None
                    if logo_raw:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                            f.write(logo_raw); lp = f.name; tmps.append(lp)
                    aplicar.carimbar(kit, tmps[0], saida, nome, lp, campos=campos)
                finally:
                    for t in tmps:
                        try: os.remove(t)
                        except Exception: pass
            return {"kit": kit, "produto": "10", "referencia": False, "jpg": "data:image/jpeg;base64," + base64.b64encode(open(saida, "rb").read()).decode()}
    tam = None
    try:
        if d.get("w_cm") and d.get("h_cm"):
            tam = (max(5.0, min(1000.0, float(d["w_cm"]))), max(5.0, min(1000.0, float(d["h_cm"]))))
    except (TypeError, ValueError):
        tam = None
    h = hashlib.sha256(raw + f"|{kit}|{pid}|{material}|{tam}|k14v8".encode()).hexdigest()[:20]
    pasta = os.path.join(ESTADO_DIR, "kits"); os.makedirs(pasta, exist_ok=True); saida = os.path.join(pasta, h + ".jpg")
    if not os.path.exists(saida):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(raw); tmp = f.name
        try:
            aplicar.aplicar(kit, pid, tmp, saida, material, None, 1.0, cheio=True, tamanho_cm=tam)
        finally:
            try: os.remove(tmp)
            except Exception: pass
    return {"kit": kit, "produto": pid, "referencia": ref, "jpg": "data:image/jpeg;base64," + base64.b64encode(open(saida, "rb").read()).decode()}

def fundo_da_marca(img):
    """Cor do fundo da arte original: a cor que domina a moldura da imagem (3% de cada lado). Fundo transparente
    ou moldura sem cor dominante (foto) → None. Devolve (hex, parte da moldura com essa cor)."""
    import numpy as np
    h, w = img.shape[:2]; b = max(2, int(min(h, w) * 0.03))
    mold = np.concatenate([img[:b].reshape(-1, 4), img[-b:].reshape(-1, 4), img[:, :b].reshape(-1, 4), img[:, -b:].reshape(-1, 4)])
    opaco = mold[mold[:, 3] > 200][:, :3].astype(np.int32)
    if len(opaco) < 0.6 * len(mold):
        return None, 0.0
    q = (opaco // 16); chave = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, cont = np.unique(chave, return_counts=True); top = vals[np.argmax(cont)]
    sel = opaco[chave == top]; conf = float(len(sel) / len(mold))
    if conf < 0.45:
        return None, round(conf, 2)
    bgr = np.median(sel, axis=0)
    return "#%02x%02x%02x" % (int(bgr[2]), int(bgr[1]), int(bgr[0])), round(conf, 2)

def marca_preparar(d):
    """Passada 1 (grátis): fundo removido (rembg, se instalado) + camadas por cor (k-means OpenCV) para o representante corrigir no editor."""
    import numpy as np, cv2
    png = (d.get("png") or ""); png = png.split(",", 1)[1] if "," in png[:40] else png
    raw = np.frombuffer(base64.b64decode(png), np.uint8); img = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("imagem inválida")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    h, w = img.shape[:2]; esc = min(1.0, 1400 / max(h, w))
    if esc < 1:
        img = cv2.resize(img, (int(w * esc), int(h * esc)), interpolation=cv2.INTER_AREA); h, w = img.shape[:2]
    fundo_hex, fundo_conf = fundo_da_marca(img)   # cor do fundo da arte antes do recorte (vira a cor base dos produtos)
    sem_fundo = None
    try:
        from rembg import remove
        out = remove(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)); out = np.array(out)
        if out.ndim == 3 and out.shape[2] == 4 and (out[..., 3] > 10).mean() > 0.02:
            img = cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA); sem_fundo = True
    except Exception:
        pass
    if not sem_fundo:  # sem rembg: fundo = cor dominante das bordas, removido por tolerância
        borda = np.concatenate([img[0, :, :3], img[-1, :, :3], img[:, 0, :3], img[:, -1, :3]]).astype(np.float32)
        cor = np.median(borda, axis=0); dist = np.linalg.norm(img[..., :3].astype(np.float32) - cor, axis=2)
        if (dist < 40).mean() > 0.25:
            img[..., 3] = np.where(dist < 40, 0, img[..., 3]); sem_fundo = "borda"
    alfa = img[..., 3] > 20; px = img[..., :3][alfa].astype(np.float32)
    camadas, cores = [], []
    if len(px) > 50:
        k = 5; amostra = px[np.random.RandomState(1).choice(len(px), min(len(px), 20000), replace=False)]
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
        _, _, centros = cv2.kmeans(amostra, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        # junta centros parecidos (ΔRGB < 40)
        cs = []
        for c in centros:
            if all(np.linalg.norm(c - x) >= 40 for x in cs):
                cs.append(c)
        cs = np.array(cs, np.float32)
        rot = np.argmin(np.linalg.norm(px[:, None, :] - cs[None, :, :], axis=2), axis=1)
        idx = np.zeros((h, w), np.int32) - 1; idx[alfa] = rot
        for i, c in enumerate(cs):
            m = idx == i; area = int(m.sum())
            if area < 0.03 * alfa.sum():
                continue
            cam = np.zeros_like(img); cam[m] = img[m]
            ok, buf = cv2.imencode(".png", cam); hexc = "#%02x%02x%02x" % (int(c[2]), int(c[1]), int(c[0]))
            cores.append({"hex": hexc, "area": round(area / alfa.sum() * 100)})
            camadas.append({"nome": "Cor", "hex": hexc, "area": cores[-1]["area"], "png": "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()})
        camadas.sort(key=lambda x: -x["area"]); cores.sort(key=lambda x: -x["area"])
    ok, buf = cv2.imencode(".png", img)
    return {"sem_fundo": "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode(), "fundo_removido_por": sem_fundo or None, "fundo_hex": fundo_hex, "fundo_conf": fundo_conf, "cores": cores, "camadas": camadas, "largura": w, "altura": h}

def ia_fundo(d):
    """Fundo/composição por IA para cartão, flyer e banner — só a composição (a marca e os textos ficam como camadas por cima).
    Gemini primeiro (chave já gravada), OpenAI como opção. Registra cada geração em /var/lib/genio/ia.log."""
    prompt = (d.get("prompt") or "").strip()[:1500]
    if not prompt:
        raise ValueError("prompt vazio")
    w, h = max(1, int(d.get("w") or 1), ), max(1, int(d.get("h") or 1))
    razoes = {"1:1": 1, "3:4": 3/4, "4:3": 4/3, "9:16": 9/16, "16:9": 16/9, "2:3": 2/3, "3:2": 3/2, "4:5": 4/5, "5:4": 5/4, "21:9": 21/9}
    ar = min(razoes, key=lambda k: abs(razoes[k] - w / h))
    K = chaves_ler(); erros = []
    prompt_full = prompt + " Sem texto, sem letras, sem logotipos, sem marcas d'água; imagem de fundo limpa, com área de respiro para aplicar uma marca por cima. Alta qualidade, impressão gráfica."
    if K.get("GEMINI_KEY"):
        modelos = ["gemini-2.5-flash-image"]
        try:  # modelos de imagem realmente disponíveis para esta chave (a lista muda; o Google aposenta nomes)
            r = _rq.urlopen(_rq.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": K["GEMINI_KEY"]}), timeout=20)
            lst = json.loads(r.read().decode("utf-8", "replace")).get("models", [])
            disp = [m["name"].split("/", 1)[1] for m in lst if "image" in m.get("name", "") and "generateContent" in (m.get("supportedGenerationMethods") or [])]
            if disp:
                modelos = sorted(disp, key=lambda n: (("preview" in n), n), reverse=True)[:3]
        except Exception:
            pass
        for modelo in modelos:
            try:
                body = json.dumps({"contents": [{"parts": [{"text": prompt_full}]}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ar}}}).encode()
                r = _rq.urlopen(_rq.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent", data=body, headers={"x-goog-api-key": K["GEMINI_KEY"], "Content-Type": "application/json"}), timeout=90)
                j = json.loads(r.read().decode("utf-8", "replace"))
                for part in (((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []):
                    if part.get("inlineData", {}).get("data"):
                        mt = part["inlineData"].get("mimeType", "image/png")
                        with open(os.path.join(ESTADO_DIR, "ia.log"), "a") as f:
                            f.write(f"{dt_now()} gemini {modelo} {ar} {prompt[:80]!r}\n")
                        return {"png": f"data:{mt};base64," + part["inlineData"]["data"], "provedor": modelo, "aspecto": ar}
                erros.append(f"{modelo}: sem imagem na resposta")
            except Exception as e:
                msg = str(e)
                try: msg = e.read().decode("utf-8", "replace")[:160]
                except Exception: pass
                erros.append(f"{modelo}: {msg[:160]}")
                if "429" in msg:
                    break
    if K.get("OPENAI_KEY"):
        size = "1536x1024" if w > h else ("1024x1536" if h > w else "1024x1024")
        try:
            body = json.dumps({"model": "gpt-image-1", "prompt": prompt_full, "size": size, "n": 1, "quality": d.get("qualidade") or "medium"}).encode()
            r = _rq.urlopen(_rq.Request("https://api.openai.com/v1/images/generations", data=body, headers={"Authorization": "Bearer " + K["OPENAI_KEY"], "Content-Type": "application/json"}), timeout=120)
            j = json.loads(r.read().decode("utf-8", "replace")); b64 = (j.get("data") or [{}])[0].get("b64_json")
            if b64:
                with open(os.path.join(ESTADO_DIR, "ia.log"), "a") as f:
                    f.write(f"{dt_now()} openai gpt-image-1 {size} {prompt[:80]!r}\n")
                return {"png": "data:image/png;base64," + b64, "provedor": "gpt-image-1", "aspecto": size}
            erros.append("openai: sem imagem")
        except Exception as e:
            msg = str(e)
            try: msg = e.read().decode("utf-8", "replace")[:160]
            except Exception: pass
            erros.append("openai: " + msg[:160])
    raise ValueError(" · ".join(erros) or "nenhuma chave de IA (Gemini/OpenAI) gravada")
def dt_now():
    import datetime; return datetime.datetime.now().isoformat(timespec="seconds")

CHAVES_NOMES = ["GOOGLE_PLACES_KEY", "SERPER_KEY", "APIFY_TOKEN", "ZAPSIGN_TOKEN", "ASAAS_TOKEN", "OPENAI_KEY", "GEMINI_KEY", "GOOGLE_MAPS_KEY",
                "MELHORENVIO_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "ML_APP_ID", "ML_SECRET"]
def chaves_ler():
    try:
        with open(CHAVES_ARQ) as f:
            return json.load(f)
    except Exception:
        return {}
def chaves_estado():
    c = chaves_ler()
    return [{"nome": n, "definida": bool(c.get(n)), "fim": (c.get(n) or "")[-4:]} for n in CHAVES_NOMES]
def chaves_gravar(d):
    c = chaves_ler()
    for n in CHAVES_NOMES:
        v = d.get(n)
        if v is None:
            continue
        v = str(v).strip()
        if v == "":
            c.pop(n, None)
        elif re.fullmatch(r"[A-Za-z0-9_\-\.:$=/+]{8,400}", v):
            c[n] = v
        else:
            raise ValueError(f"{n}: valor inválido")
    os.makedirs(os.path.dirname(CHAVES_ARQ), exist_ok=True)
    tmp = CHAVES_ARQ + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CHAVES_ARQ)
    return chaves_estado()

class H(BaseHTTPRequestHandler):
    server_version = "genio-api/1"

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def _send(self, code, obj=None, body=None, ctype="application/json; charset=utf-8", cache="no-store", cookie=None):
        if body is None:
            body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        if cookie is not None:
            seg = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            idade = SESSAO_DIAS * 86400 if cookie else 0
            self.send_header("Set-Cookie", f"genio_s={cookie}; Path=/; Max-Age={idade}; HttpOnly; SameSite=Lax{seg}")
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

    def _tok(self):
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == "genio_s":
                return v
        return None

    def _eu(self):
        return sessao_conta(self._tok())

    def _ip(self):
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def _origem_ok(self):
        o = self.headers.get("Origin")
        return not o or urlparse(o).netloc == (self.headers.get("Host") or "")

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("tamanho inválido")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            if p == "/api/mapa":
                return self._send(200, {"google": chaves_ler().get("GOOGLE_MAPS_KEY") or ""})
            if p == "/api/saude":
                q("SELECT 1", one=True)
                return self._send(200, {"ok": True, "banco": True, "hora": agora()})
            if p == "/api/eu":
                eu = self._eu()
                if not eu:
                    return self._erro(401, "entre com a sua conta")
                return self._send(200, dict(eu, planos=PLANOS))
            if p in ("/api/site/imagens", "/api/imagens/busca", "/api/img"):
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                qs = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                try:
                    if p == "/api/site/imagens":
                        return self._send(200, site_imagens(qs.get("url", "")))
                    if p == "/api/imagens/busca":
                        return self._send(200, busca_imagens(qs.get("q", "")))
                    ct, dados = proxy_img(qs.get("u", ""))
                    return self._send(200, body=dados, ctype=ct, cache="public, max-age=86400")
                except Exception as e:
                    return self._erro(502, "não consegui abrir: " + str(e)[:120])
            if p.startswith("/api/mostra/"):
                partes = p.split("/")   # /api/mostra/<token>[/logo.ext]
                try:
                    if len(partes) == 5 and partes[4].startswith(("logo.", "foto.", "foto-")):
                        ct, raw = MOSTRA.logo(partes[3], partes[4])
                        return self._send(200, body=raw, ctype=ct, cache="public, max-age=600")
                    if len(partes) == 5 and partes[4] == "arquivos":
                        return self._send(200, {"itens": [{"i": i, "tag": x["tag"]} for i, x in enumerate(mostra_arquivos(partes[3]))]})
                    if len(partes) == 6 and partes[4] == "arquivo" and partes[5].isdigit():
                        ct, raw = mostra_arquivo_bytes(partes[3], int(partes[5]))
                        return self._send(200, body=raw, ctype=ct, cache="private, max-age=600")
                    if len(partes) == 5 and partes[4] == "busca":
                        if not MOSTRA.ler(partes[3]):
                            return self._erro(404, "este Mostraí não existe")
                        qb = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                        return self._send(200, busca_imagens(qb.get("q", "")[:120]))
                    if len(partes) == 5 and partes[4] == "mensagens":
                        est = MOSTRA.ler(partes[3])
                        if not est:
                            return self._erro(404, "este Mostraí não existe")
                        return self._send(200, {"mensagens": [{"de": m["de"], "texto": m["texto"], "em": m["em"]} for m in DADOS.mensagens_ler(est["slug"])][-50:]})
                    est = MOSTRA.ler(partes[3]) if len(partes) == 4 else None
                    if not est:
                        return self._erro(404, "este Mostraí não existe")
                    qs = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                    if qs.get("v") and str(est.get("v")) == qs["v"]:
                        return self._send(200, {"v": est["v"], "igual": True})
                    return self._send(200, MOSTRA.publico(est))
                except (ValueError, FileNotFoundError):
                    return self._erro(404, "este Mostraí não existe")
            if p.startswith("/api/arq/"):
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                partes = p.split("/")
                if len(partes) != 6:
                    return self._erro(404, "arquivo não existe")
                try:
                    ct, raw = DADOS.arquivo(partes[3], partes[4], partes[5])
                except (FileNotFoundError, ValueError):
                    return self._erro(404, "arquivo não existe")
                return self._send(200, body=raw, ctype=ct, cache="private, max-age=31536000, immutable")
            if p == "/api/clientes" or p.startswith("/api/clientes/") or p == "/api/notas" or p.startswith("/api/estado/") or p == "/api/dados/resumo" or p.startswith("/api/mensagens"):
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                try:
                    if p == "/api/clientes":
                        qs = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                        slugs = set(qs["slugs"].split(",")) if qs.get("slugs") else None
                        return self._send(200, {"clientes": DADOS.clientes_listar(slugs)})
                    if p.startswith("/api/clientes/"):
                        f = DADOS.cliente_ler(p.split("/")[3])
                        return self._send(200, f) if f else self._erro(404, "sem ficha")
                    if p == "/api/notas":
                        return self._send(200, {"notas": DADOS.notas_listar()})
                    if p == "/api/mensagens":
                        return self._send(200, {"conversas": DADOS.mensagens_resumo()})
                    if p.startswith("/api/mensagens/"):
                        return self._send(200, {"mensagens": DADOS.mensagens_ler(p.split("/")[3])})
                    if p == "/api/dados/resumo":
                        return self._send(200, DADOS.resumo())
                    e = DADOS.estado_ler(p.split("/")[3])
                    return self._send(200, e if e else {"valor": None})
                except ValueError as e:
                    return self._erro(400, str(e))
            if p == "/api/convite":
                qs = dict(x.split("=", 1) for x in (urlparse(self.path).query or "").split("&") if "=" in x)
                if qs.get("p"):
                    return self._send(200, {"primeiro": True}) if primeiro_valido(qs["p"]) else self._erro(404, "este link de primeiro acesso não vale mais")
                cv = convite_ler(qs.get("c"))
                return self._send(200, {"nome": cv["nome"], "email": cv["email"]}) if cv else self._erro(404, "este convite não vale mais. Peça um novo ao administrador.")
            if p.startswith("/api/admin/"):
                eu = self._eu()
                if not eu or eu["papel"] != "admin":
                    return self._erro(403, "só o administrador")
                if p == "/api/admin/contas":
                    return self._send(200, {"contas": admin_contas(), "planos": PLANOS})
                if p == "/api/admin/disco":
                    return self._send(200, disco_uso())
                if p == "/api/admin/interesse":
                    return self._send(200, {"interesse": admin_interesse()})
                if p == "/api/admin/chaves":
                    return self._send(200, {"chaves": chaves_estado()})
                if p == "/api/admin/logos-auto":
                    # dispara a busca automática de logotipo da zona (em segundo plano); ?zona=
                    qs = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                    zona = re.sub(r"[^a-z0-9-]", "", qs.get("zona") or ""); 
                    if not zona:
                        return self._erro(400, "zona?")
                    import logos_auto, importlib; importlib.reload(logos_auto)
                    me = sys.modules[__name__]; res = {}
                    # zona=todas: todas as listas já captadas (cada pasta de dados/captacao com lojas.json), uma depois da outra
                    pasta_cap = os.path.join(RAIZ, "dados", "captacao")
                    zonas = sorted(z for z in os.listdir(pasta_cap) if os.path.exists(os.path.join(pasta_cap, z, "lojas.json"))) if zona == "todas" else [zona]
                    arq_est = os.path.join(ESTADO_DIR, f"logos_auto-{zona}.json")
                    json.dump({"andamento": True, "zonas": zonas, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(arq_est, "w"))
                    def _job():
                        for z in zonas:
                            try: r = logos_auto.rodar(z, me, log=lambda t: sys.stderr.write(t + "\n"))
                            except Exception as e: r = {"zona": z, "erro": str(e)}
                            if zona == "todas":
                                res.setdefault("zonas_feitas", []).append(r); json.dump({"andamento": True, **res}, open(arq_est, "w"))
                            else:
                                res.update(r)
                        res["fim"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        json.dump(res, open(arq_est, "w"))
                    threading.Thread(target=_job, daemon=True).start()
                    return self._send(200, {"ok": True, "zona": zona, "resultado_em": f"/api/admin/logos-auto/estado?zona={zona}"})
                if p == "/api/admin/logos-auto/estado":
                    qs = {k: v[0] for k, v in _parse_qs(urlparse(self.path).query or "").items()}
                    try:
                        return self._send(200, json.load(open(os.path.join(ESTADO_DIR, "logos_auto-" + re.sub(r"[^a-z0-9-]", "", qs.get("zona") or "") + ".json"))))
                    except Exception:
                        return self._send(200, {"andamento": True})
                if p == "/api/admin/atividade":
                    # rastro das contextualizações (cache em /var/lib/genio/kits, um arquivo por arte aplicada); as fichas ficam no aparelho
                    import datetime as _dt
                    pasta = os.path.join(ESTADO_DIR, "kits"); arqs = []
                    try:
                        for n in os.listdir(pasta):
                            st = os.stat(os.path.join(pasta, n)); arqs.append(st.st_mtime)
                    except Exception:
                        pass
                    arqs.sort(); agora = time.time(); fmt = lambda t: _dt.datetime.fromtimestamp(t).strftime("%d/%m %H:%M")
                    horas = {}
                    for t in arqs:
                        if agora - t < 48 * 3600:
                            k = _dt.datetime.fromtimestamp(t).strftime("%d/%m %Hh"); horas[k] = horas.get(k, 0) + 1
                    return self._send(200, {"total": len(arqs), "ultima": fmt(arqs[-1]) if arqs else None, "ultimas_2h": sum(1 for t in arqs if agora - t < 7200), "ultimas_24h": sum(1 for t in arqs if agora - t < 86400), "por_hora_48h": horas})
                if p == "/api/admin/esteira":
                    out = {}
                    for n in ("esteira.log", "apt.log"):
                        try:
                            with open("/var/lib/genio/" + n) as f:
                                out[n] = f.read()[-4000:]
                        except Exception as e:
                            out[n] = ""
                    try:
                        out["python"] = subprocess.run([sys.executable, "-c", "import cv2,skimage,PIL;print(cv2.__version__)"], capture_output=True, text=True, timeout=20).stdout.strip() or "sem cv2/skimage"
                    except Exception as e:
                        out["python"] = str(e)[:100]
                    try:  # ferramentas da versão limpa
                        out["ferramentas"] = subprocess.run([sys.executable, "-c", "import importlib,shutil;m={n:bool(importlib.util.find_spec(n)) for n in ('vtracer','rembg','realesrgan','torch')};m.update({'inkscape':bool(shutil.which('inkscape')),'gs':bool(shutil.which('gs'))});print(m)"], capture_output=True, text=True, timeout=20).stdout.strip()
                        out["marcadores"] = {n: os.path.exists("/var/lib/genio/" + n) for n in ("pacotes3.ok", "pacotes3.rodando", "realesrgan.ok")}
                    except Exception as e:
                        out["ferramentas"] = str(e)[:100]
                    return self._send(200, out)
                if p == "/api/admin/captacao":
                    est = {}
                    for n in ("quota", "padrao", "pedido"):
                        try:
                            est[n] = json.load(open(f"/var/lib/genio/captacao/{n}.json"))
                        except Exception:
                            est[n] = None
                    zonas = sorted(f[:-5] for f in os.listdir(os.path.join(os.path.dirname(__file__), "..", "captacao", "zonas")) if f.endswith(".json"))
                    return self._send(200, {"zonas": zonas, "quota": est["quota"] or {}, "padrao": est["padrao"] or {}, "pedido": est["pedido"]})
                return self._erro(404, "não encontrado")
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

    def _json_grande(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_FICHA:
            raise ValueError("tamanho inválido")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_PUT(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            if p.startswith("/api/mostra/") and p.endswith("/foto") and len(p.split("/")) == 5:   # foto principal da tela
                try:
                    j = self._json_grande()
                    if j.get("arquivo") is not None or j.get("url"):
                        return self._send(200, mostra_foto_de(p.split("/")[3], j))
                    return self._send(200, MOSTRA.foto_gravar(p.split("/")[3], j.get("foto"), j.get("tela")))
                except FileNotFoundError:
                    return self._erro(404, "este Mostraí não existe")
                except ValueError as e:
                    return self._erro(400, str(e))
            if p.startswith("/api/mostra/") and p.endswith("/mensagem") and len(p.split("/")) == 5:   # cliente → atendimento
                try:
                    est = MOSTRA.ler(p.split("/")[3])
                    if not est:
                        raise FileNotFoundError
                    return self._send(200, DADOS.mensagem_gravar(est["slug"], "cliente", self._json().get("texto"), "Mostraí"))
                except FileNotFoundError:
                    return self._erro(404, "este Mostraí não existe")
                except ValueError as e:
                    return self._erro(400, str(e))
            if p.startswith("/api/mostra/") and len(p.split("/")) == 4:   # programação do cliente: o código é a chave
                try:
                    return self._send(200, MOSTRA.publico(MOSTRA.gravar(p.split("/")[3], self._json())))
                except (ValueError, FileNotFoundError):
                    return self._erro(404, "este Mostraí não existe")
            eu = self._eu()
            if not eu:
                return self._erro(401, "entre com a sua conta")
            if not self._origem_ok():
                return self._erro(403, "origem")
            partes = p.split("/")
            if p.startswith("/api/clientes/") and len(partes) == 4:
                return self._send(200, DADOS.cliente_gravar(partes[3], self._json_grande(), eu["nome"]))
            if p.startswith("/api/notas/") and len(partes) == 4:
                return self._send(200, DADOS.nota_gravar(partes[3], self._json_grande(), eu["nome"]))
            if p.startswith("/api/estado/") and len(partes) == 4:
                return self._send(200, {"valor": DADOS.estado_gravar(partes[3], self._json_grande().get("valor"), eu["nome"])})
            if p.startswith("/api/mensagens/") and len(partes) == 5 and partes[4] == "lidas":
                return self._send(200, DADOS.mensagens_lidas(partes[3]))
            if p.startswith("/api/mensagens/") and len(partes) == 4:   # resposta do atendimento (aparece para o cliente no painel dele)
                return self._send(200, DADOS.mensagem_gravar(partes[3], "genio", self._json().get("texto"), "app", eu["nome"]))
            return self._erro(404, "não existe")
        except ValueError as e:
            return self._erro(400, str(e))
        except Exception as e:
            return self._erro(500, "erro: " + str(e)[:200])

    def do_DELETE(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            eu = self._eu()
            if not eu:
                return self._erro(401, "entre com a sua conta")
            if not self._origem_ok():
                return self._erro(403, "origem")
            partes = p.split("/")
            if p.startswith("/api/notas/") and len(partes) == 4:
                DADOS.nota_apagar(partes[3]); return self._send(200, {"ok": True})
            if p.startswith("/api/clientes/") and len(partes) == 4 and eu["papel"] == "admin":
                DADOS.cliente_apagar(partes[3]); return self._send(200, {"ok": True})
            return self._erro(404, "não existe")
        except ValueError as e:
            return self._erro(400, str(e))

    def do_POST(self):
        p = urlparse(self.path).path.rstrip("/")
        try:
            if p == "/api/ia/fundo":
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                try:
                    return self._send(200, ia_fundo(self._json()))
                except Exception as e:
                    return self._erro(502, "IA: " + str(e)[:400])
            if p == "/api/marca/preparar":
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                try:
                    return self._send(200, marca_preparar(self._json()))
                except Exception as e:
                    return self._erro(500, "preparo falhou: " + str(e)[:160])
            if p == "/api/mostra":   # acionar o Mostraí de uma loja (vendedor logado) → links
                eu = self._eu()
                if not eu:
                    return self._erro(401, "entre com a sua conta")
                d = self._json(); slug = d.get("slug") or ""
                try:
                    ficha = DADOS.cliente_ler(slug) or {"k": slug, "nome": (d.get("loja") or {}).get("nome") or slug, "slug": slug, "logos": [], "arquivo": []}
                    est = MOSTRA.criar(slug, ficha, d.get("loja") or {}, eu["nome"])
                    ficha["mostra"] = {"token": est["token"], "criado": est["criado"]}
                    DADOS.cliente_gravar(slug, ficha, eu["nome"])
                    return self._send(200, {"token": est["token"], "tela": f"/mostra.html?c={est['token']}", "programacao": f"/programacao.html?c={est['token']}", "estado": est})
                except Exception as e:
                    return self._erro(500, "Mostraí: " + str(e)[:200])
            if p == "/api/provar":
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                try:
                    return self._send(200, peca_provar(self._json_grande()))
                except Exception as e:
                    return self._erro(500, "provar: " + str(e)[:160])
            if p == "/api/kit/aplicar":
                if not self._eu():
                    return self._erro(401, "entre com a sua conta")
                try:
                    return self._send(200, kit_aplicar(self._json()))
                except Exception as e:
                    return self._erro(500, "contextualização falhou: " + str(e)[:160])
            if p == "/api/correcoes":
                # correções de imagem feitas no aparelho (trocada, ajustada, apagada, errada) — alimentam a captação
                if not self._origem_ok():
                    return self._erro(403, "origem não permitida")
                d = self._json()
                itens = [x for x in (d.get("correcoes") or []) if isinstance(x, dict)][:200]
                os.makedirs("/var/lib/genio/captacao", exist_ok=True)
                with open("/var/lib/genio/captacao/correcoes.jsonl", "a") as f:
                    for x in itens:
                        f.write(json.dumps({k: (str(v)[:300] if isinstance(v, str) else v) for k, v in x.items() if k != "dados"}, ensure_ascii=False) + "\n")
                return self._send(200, {"ok": True, "recebidas": len(itens)})
            if p in ("/api/entrar", "/api/sair", "/api/convite", "/api/primeiro", "/api/interesse") or p.startswith("/api/admin/"):
                if not self._origem_ok():
                    return self._erro(403, "origem não permitida")
                if p == "/api/sair":
                    t = self._tok()
                    if t:
                        q("DELETE FROM sessoes WHERE token=?", (h64(t),), commit=True)
                    return self._send(200, {"ok": True}, cookie="")
                d = self._json()
                if p == "/api/entrar":
                    email = str(d.get("email") or "").strip().lower()
                    if not limite("e:" + email, 8) or not limite("i:" + self._ip(), 30):
                        return self._erro(429, "muitas tentativas. Espere 15 minutos e tente de novo.")
                    try:
                        return self._send(200, {"ok": True}, cookie=entrar(d))
                    except PermissionError as e:
                        return self._erro(403, str(e))
                if p == "/api/convite":
                    if not limite("i:" + self._ip(), 30):
                        return self._erro(429, "muitas tentativas. Espere 15 minutos.")
                    try:
                        return self._send(200, {"ok": True}, cookie=convite_usar(d.get("c"), d))
                    except PermissionError as e:
                        return self._erro(403, str(e))
                if p == "/api/primeiro":
                    if not limite("i:" + self._ip(), 30):
                        return self._erro(429, "muitas tentativas. Espere 15 minutos.")
                    return self._send(200, {"ok": True}, cookie=primeiro_usar(d))
                if p == "/api/interesse":
                    if not limite("q:" + self._ip(), 5, 3600):
                        return self._erro(429, "recebemos os seus dados. Já já entramos em contato.")
                    return self._send(200, interesse_novo(d, self._ip()))
                eu = self._eu()
                if not eu or eu["papel"] != "admin":
                    return self._erro(403, "só o administrador")
                parts = p.split("/")
                if p == "/api/admin/contas":
                    r = admin_criar(d)
                    return self._send(200, r)
                if len(parts) == 5 and parts[3] == "contas" and parts[4].isdigit():
                    return self._send(200, admin_mudar(int(parts[4]), d, eu))
                if len(parts) == 6 and parts[3] == "contas" and parts[4].isdigit() and parts[5] == "convite":
                    if not q("SELECT 1 FROM contas WHERE id=?", (int(parts[4]),), one=True):
                        return self._erro(404, "conta não encontrada")
                    return self._send(200, {"convite": convite_novo(int(parts[4]))})
                if len(parts) == 6 and parts[3] == "aparelhos" and parts[4].isdigit() and parts[5] == "tirar":
                    return self._send(200, admin_aparelho_tirar(int(parts[4])))
                if p == "/api/admin/interesse/visto":
                    q("UPDATE interesse SET visto=1", commit=True)
                    return self._send(200, {"ok": True})
                if p == "/api/admin/chaves":
                    return self._send(200, {"chaves": chaves_gravar(d)})
                if p == "/api/admin/captacao":
                    zona = re.sub(r"[^a-z0-9-]", "", str(d.get("zona") or ""))
                    if not zona:
                        return self._erro(400, "zona?")
                    ped = {"zona": zona, "limite": max(1, min(100, int(d.get("limite") or 50))), "refazer": bool(d.get("refazer")), "nonce": "admin-" + str(int(time.time()))}
                    os.makedirs("/var/lib/genio/captacao", exist_ok=True)
                    json.dump(ped, open("/var/lib/genio/captacao/pedido.json", "w"))
                    pad = {}
                    try:
                        pad = json.load(open("/var/lib/genio/captacao/padrao.json"))
                    except Exception:
                        pass
                    pad["zona"] = zona; json.dump(pad, open("/var/lib/genio/captacao/padrao.json", "w"))
                    return self._send(200, {"ok": True, "pedido": ped})
                return self._erro(404, "não encontrado")
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
# reinício 2026-11-09 (aplicador)
