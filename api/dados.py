"""GênIO · dados do app no servidor (fonte única).

Fichas de cliente, notas e estado compartilhado moram aqui, em /var/lib/genio/dados/:
  clientes/<slug>.json      ficha (logotipos, manual, artes, produtos…)
  clientes/<slug>/<hash>.ext imagens da ficha (data: URLs viram arquivos; o JSON guarda /api/arq/<slug>/<hash>.ext)
  notas/<id>.json + notas/<id>/…  notas (áudio, vídeo, foto)
  estado/<chave>.json       estado compartilhado (dia da rota, pedidos, avulsos, fornecedores, ocorrências)
O aparelho não guarda nada: lê e grava sempre aqui.
"""
import base64, hashlib, json, os, re, tempfile, time

RAIZ_DADOS = os.environ.get("GENIO_DADOS", "/var/lib/genio/dados")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg",
       "audio/webm": "weba", "audio/mp4": "m4a", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/wav": "wav",
       "video/webm": "webm", "video/mp4": "mp4"}

def _pasta(*p):
    d = os.path.join(RAIZ_DADOS, *p); os.makedirs(d, exist_ok=True); return d

def _escrever_json(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(caminho), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, caminho)

def _ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def valida_slug(s):
    if not isinstance(s, str) or not SLUG.match(s):
        raise ValueError("identificador inválido")
    return s

def desidratar(obj, colecao, ident):
    """Troca data: URLs grandes por arquivos em <colecao>/<ident>/<hash>.<ext>; devolve o objeto com URLs /api/arq/…"""
    pasta = None
    def guardar(s):
        nonlocal pasta
        m = re.match(r"^data:([\w/+.-]+);base64,(.*)$", s, re.S)
        if not m:
            return s
        mime, b64 = m.group(1), m.group(2)
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return s
        ext = EXT.get(mime.split(";")[0], "bin")
        h = hashlib.sha256(raw).hexdigest()[:24]
        if pasta is None:
            pasta = _pasta(colecao, ident)
        arq = os.path.join(pasta, f"{h}.{ext}")
        if not os.path.exists(arq):
            fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            os.replace(tmp, arq)
        return f"/api/arq/{colecao}/{ident}/{h}.{ext}"
    def anda(x):
        if isinstance(x, str):
            return guardar(x) if (len(x) > 256 and x.startswith("data:")) else x
        if isinstance(x, list):
            return [anda(v) for v in x]
        if isinstance(x, dict):
            return {k: anda(v) for k, v in x.items()}
        return x
    return anda(obj)

def arquivos_referidos(obj, acc=None):
    acc = set() if acc is None else acc
    if isinstance(obj, str):
        if obj.startswith("/api/arq/"):
            acc.add(obj)
    elif isinstance(obj, list):
        for v in obj: arquivos_referidos(v, acc)
    elif isinstance(obj, dict):
        for v in obj.values(): arquivos_referidos(v, acc)
    return acc

def _limpar_orfaos(colecao, ident, obj):
    """Apaga arquivos da pasta que a ficha não referencia mais (artes refeitas, logotipos trocados)."""
    pasta = os.path.join(RAIZ_DADOS, colecao, ident)
    if not os.path.isdir(pasta):
        return
    usados = {u.rsplit("/", 1)[1] for u in arquivos_referidos(obj)}
    for n in os.listdir(pasta):
        if n not in usados and not n.endswith(".tmp"):
            try: os.remove(os.path.join(pasta, n))
            except OSError: pass

# ---------- clientes
def cliente_ler(slug):
    return _ler_json(os.path.join(RAIZ_DADOS, "clientes", valida_slug(slug) + ".json"))

def cliente_gravar(slug, ficha, por=None):
    valida_slug(slug)
    if not isinstance(ficha, dict):
        raise ValueError("ficha inválida")
    ficha = desidratar(ficha, "clientes", slug)
    ficha["slug"] = slug; ficha["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S"); ficha["por"] = por
    _escrever_json(os.path.join(_pasta("clientes"), slug + ".json"), ficha)
    _limpar_orfaos("clientes", slug, ficha)
    return ficha

def clientes_listar(slugs=None):
    pasta = os.path.join(RAIZ_DADOS, "clientes")
    if not os.path.isdir(pasta):
        return []
    out = []
    for n in sorted(os.listdir(pasta)):
        if not n.endswith(".json"):
            continue
        s = n[:-5]
        if slugs is not None and s not in slugs:
            continue
        f = _ler_json(os.path.join(pasta, n))
        if f: out.append(f)
    return out

def cliente_apagar(slug):
    valida_slug(slug)
    try: os.remove(os.path.join(RAIZ_DADOS, "clientes", slug + ".json"))
    except FileNotFoundError: pass
    _limpar_orfaos("clientes", slug, {})

# ---------- notas
def notas_listar():
    pasta = os.path.join(RAIZ_DADOS, "notas")
    if not os.path.isdir(pasta):
        return []
    out = [_ler_json(os.path.join(pasta, n)) for n in os.listdir(pasta) if n.endswith(".json")]
    return sorted([x for x in out if x], key=lambda x: x.get("em", ""), reverse=True)

def nota_gravar(ident, nota, por=None):
    valida_slug(ident)
    nota = desidratar(nota, "notas", ident); nota["id"] = ident; nota["por"] = por
    _escrever_json(os.path.join(_pasta("notas"), ident + ".json"), nota)
    return nota

def nota_apagar(ident):
    valida_slug(ident)
    try: os.remove(os.path.join(RAIZ_DADOS, "notas", ident + ".json"))
    except FileNotFoundError: pass
    _limpar_orfaos("notas", ident, {})

# ---------- estado compartilhado (chave → JSON)
def estado_ler(chave):
    return _ler_json(os.path.join(RAIZ_DADOS, "estado", valida_slug(chave) + ".json"))

def estado_gravar(chave, valor, por=None):
    valida_slug(chave)
    _escrever_json(os.path.join(_pasta("estado"), chave + ".json"), {"valor": valor, "atualizado": time.strftime("%Y-%m-%dT%H:%M:%S"), "por": por})
    return valor

# ---------- arquivos
def arquivo(colecao, ident, nome):
    if colecao not in ("clientes", "notas") or not SLUG.match(ident or "") or not re.match(r"^[0-9a-f]{24}\.[a-z0-9]{1,5}$", nome or ""):
        raise ValueError("caminho inválido")
    caminho = os.path.join(RAIZ_DADOS, colecao, ident, nome)
    ext = nome.rsplit(".", 1)[1]
    mime = {v: k for k, v in EXT.items()}.get(ext, "application/octet-stream")
    with open(caminho, "rb") as f:
        return mime, f.read()

# ---- mensagens do cliente (painel do cliente / Mostraí; e-mail quando ligado): uma conversa por cliente
def _arq_msg(slug):
    return os.path.join(_pasta("mensagens"), valida_slug(slug) + ".json")

def mensagens_ler(slug):
    return _ler_json(_arq_msg(slug)) or []

def mensagem_gravar(slug, de, texto, canal="", por=None):
    texto = str(texto or "").strip()[:2000]
    if not texto:
        raise ValueError("mensagem vazia")
    lista = mensagens_ler(slug)
    m = {"id": "m" + str(int(time.time() * 1000)), "de": "cliente" if de == "cliente" else "genio", "texto": texto,
         "canal": str(canal or "")[:30], "por": por, "em": time.strftime("%Y-%m-%dT%H:%M:%S"), "lida": de != "cliente"}
    lista.append(m); _escrever_json(_arq_msg(slug), lista[-500:])
    return m

# painel do cliente: escolhas e pedido do cliente num arquivo próprio da loja (o vendedor regrava a ficha inteira; aqui não há atropelo)
def _arq_painel(slug):
    return os.path.join(_pasta("painel"), valida_slug(slug) + ".json")

def painel_cliente_ler(slug):
    return _ler_json(_arq_painel(slug)) or {}

def painel_cliente_gravar(slug, obj):
    obj = dict(obj or {}); obj["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever_json(_arq_painel(slug), obj)
    return obj

def mensagens_lidas(slug):
    lista = mensagens_ler(slug)
    for m in lista:
        m["lida"] = True
    _escrever_json(_arq_msg(slug), lista)
    return {"ok": True}

def mensagens_resumo():
    """não lidas por cliente (para o sino de Clientes) e a última mensagem de cada conversa"""
    pasta = _pasta("mensagens"); out = {}
    for n in os.listdir(pasta):
        if not n.endswith(".json"):
            continue
        lista = _ler_json(os.path.join(pasta, n)) or []
        if lista:
            out[n[:-5]] = {"nao_lidas": sum(1 for m in lista if not m.get("lida")), "ultima": lista[-1]}
    return out

def resumo():
    cl = clientes_listar()
    return {"clientes": len(cl), "com_logotipo": sum(1 for c in cl if (c.get("manual") or {}).get("tratado")),
            "com_artes": sum(1 for c in cl if c.get("artes")), "notas": len(notas_listar()),
            "ultima_gravacao": max([c.get("atualizado", "") for c in cl] or [""])}
