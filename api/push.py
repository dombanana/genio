"""GênIO · aviso no celular do lojista (notificação do próprio painel, sem WhatsApp e sem custo).

/var/lib/genio/dados/push/vapid.json     chave do servidor (criada na primeira vez; nunca sai do servidor)
/var/lib/genio/dados/push/<slug>.json    aparelhos do lojista que pediram aviso (só o endereço de entrega do navegador)

Como funciona: o lojista toca em "Avisar neste celular" no painel; o navegador dele entrega um endereço; quando chega
mensagem de cliente ou horário novo, o servidor "toca a campainha" nesse endereço, sem mandar conteúdo nenhum.
O celular então pergunta ao painel o que há de novo e mostra a notificação. Nenhum dado do cliente passa pelo serviço de avisos.
Tudo com a biblioteca padrão do Python (assinatura ES256 feita aqui), para não depender de instalar nada no servidor.
"""
import base64, hashlib, hmac, json, os, secrets, threading, time
from urllib import request as _rq, error as _er
from urllib.parse import urlparse
import dados as DADOS

PASTA = os.path.join(DADOS.RAIZ_DADOS, "push")
SITE = "https://genio.dombanana.tech"
# só serviços de aviso conhecidos dos navegadores (o endereço vem do aparelho do lojista: não se chama qualquer site)
HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com", ".notify.windows.com", ".push.apple.com")
MAX_APARELHOS = 6
_lock = threading.Lock()

# ---------- curva P-256 (para a assinatura que os navegadores exigem) ----------
P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
A = P - 3
GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5

def _soma(p1, p2):
    if p1 is None: return p2
    if p2 is None: return p1
    x1, y1 = p1; x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    m = ((3 * x1 * x1 + A) * pow(2 * y1, -1, P)) % P if p1 == p2 else ((y2 - y1) * pow(x2 - x1, -1, P)) % P
    x3 = (m * m - x1 - x2) % P
    return (x3, (m * (x1 - x3) - y1) % P)

def _mult(k, pt):
    r = None
    while k:
        if k & 1:
            r = _soma(r, pt)
        pt = _soma(pt, pt); k >>= 1
    return r

def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def _k_rfc6979(d, h1):
    """número de uso único determinístico (RFC 6979), para nunca repetir e nunca depender de sorteio"""
    x = d.to_bytes(32, "big"); v = b"\x01" * 32; k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest(); v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest(); v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest(); c = int.from_bytes(v, "big")
        if 1 <= c < N:
            return c
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest(); v = hmac.new(k, v, hashlib.sha256).digest()

def assinar_es256(d, msg):
    h1 = hashlib.sha256(msg).digest(); z = int.from_bytes(h1, "big")
    while True:
        k = _k_rfc6979(d, h1); r = _mult(k, (GX, GY))[0] % N
        s = (pow(k, -1, N) * (z + r * d)) % N
        if r and s:
            return r.to_bytes(32, "big") + s.to_bytes(32, "big")
        h1 = hashlib.sha256(h1).digest()

def conferir_es256(pub, msg, sig):
    r = int.from_bytes(sig[:32], "big"); s = int.from_bytes(sig[32:], "big"); z = int.from_bytes(hashlib.sha256(msg).digest(), "big")
    w = pow(s, -1, N); pt = _soma(_mult(z * w % N, (GX, GY)), _mult(r * w % N, pub))
    return pt is not None and pt[0] % N == r

# ---------- chave do servidor ----------
def _vapid():
    arq = os.path.join(PASTA, "vapid.json")
    v = DADOS._ler_json(arq)
    if not v:
        with _lock:
            v = DADOS._ler_json(arq)
            if not v:
                d = secrets.randbelow(N - 1) + 1; x, y = _mult(d, (GX, GY))
                v = {"d": format(d, "064x"), "pub": _b64(b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")), "criada": time.strftime("%Y-%m-%dT%H:%M:%S")}
                os.makedirs(PASTA, exist_ok=True)
                DADOS._escrever_json(arq, v)
                try:
                    os.chmod(arq, 0o600)
                except Exception:
                    pass
    return v

def chave_publica():
    return _vapid()["pub"]

def _jwt(aud):
    v = _vapid()
    cab = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    corpo = _b64(json.dumps({"aud": aud, "exp": int(time.time()) + 12 * 3600, "sub": SITE}, separators=(",", ":")).encode())
    return f"{cab}.{corpo}." + _b64(assinar_es256(int(v["d"], 16), f"{cab}.{corpo}".encode()))

# ---------- aparelhos ----------
def _arq(slug):
    return os.path.join(PASTA, DADOS.valida_slug(slug) + ".json")

def _host_ok(endpoint):
    u = urlparse(str(endpoint or ""))
    h = (u.hostname or "").lower()
    return u.scheme == "https" and len(endpoint) <= 1000 and any(h == x or (x.startswith(".") and h.endswith(x)) for x in HOSTS)

def assinar(slug, endpoint, quem=""):
    if not _host_ok(endpoint):
        raise ValueError("este navegador não entrega avisos por um serviço conhecido")
    with _lock:
        L = DADOS._ler_json(_arq(slug)) or []
        L = [a for a in L if a.get("endpoint") != endpoint]
        L.append({"endpoint": endpoint, "quem": str(quem or "")[:60], "desde": time.strftime("%Y-%m-%dT%H:%M:%S")})
        os.makedirs(PASTA, exist_ok=True)
        DADOS._escrever_json(_arq(slug), L[-MAX_APARELHOS:])
    return len(L[-MAX_APARELHOS:])

def sair(slug, endpoint):
    with _lock:
        L = DADOS._ler_json(_arq(slug)) or []
        N2 = [a for a in L if a.get("endpoint") != endpoint]
        if len(N2) != len(L):
            DADOS._escrever_json(_arq(slug), N2)
    return len(N2)

def aparelhos(slug):
    return len(DADOS._ler_json(_arq(slug)) or [])

def _tocar(endpoint):
    """toca a campainha: aviso sem conteúdo. Devolve o código da resposta (201 = entregue ao serviço)."""
    u = urlparse(endpoint)
    req = _rq.Request(endpoint, data=b"", method="POST", headers={
        "TTL": "86400", "Urgency": "high", "Content-Length": "0",
        "Authorization": f"vapid t={_jwt(u.scheme + '://' + u.netloc)}, k={chave_publica()}"})
    try:
        with _rq.urlopen(req, timeout=12) as r:
            return r.status
    except _er.HTTPError as e:
        return e.code
    except Exception:
        return 0

def _enviar(slug):
    L = DADOS._ler_json(_arq(slug)) or []
    if not L:
        return
    mortos = []
    for a in L:
        cod = _tocar(a["endpoint"])
        if cod in (404, 410):   # o aparelho desligou os avisos ou desinstalou: tira da lista
            mortos.append(a["endpoint"])
    try:
        with open(os.path.join(PASTA, "envios.log"), "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {slug} aparelhos={len(L)} removidos={len(mortos)}\n")
    except Exception:
        pass
    if mortos:
        with _lock:
            DADOS._escrever_json(_arq(slug), [a for a in (DADOS._ler_json(_arq(slug)) or []) if a["endpoint"] not in mortos])

def avisar(slug):
    """chamado quando chega mensagem de cliente ou horário novo; nunca atrasa nem derruba o pedido que o disparou"""
    try:
        if slug and os.path.exists(_arq(slug)):
            threading.Thread(target=_enviar, args=(slug,), daemon=True).start()
    except Exception:
        pass
