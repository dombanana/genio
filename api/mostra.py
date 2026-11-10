"""GênIO · Mostraí — tela (TV Box / celular) + programação (painel do cliente), tudo no servidor.

/var/lib/genio/dados/mostra/<token>.json  estado: itens, título, aviso, cores, logo, versão
/var/lib/genio/dados/mostra/<token>/logo.<ext>
A tela lê (GET público, por token); a programação grava (PUT público, por token). Cada gravação sobe a versão;
a tela consulta a cada poucos segundos e redesenha quando a versão muda.
"""
import json, os, re, secrets, tempfile, time
import dados as DADOS

ALFA = "23456789abcdefghjkmnpqrstuvwxyz"
TOKEN = re.compile(r"^[a-z0-9]{8,16}$")
PASTA = os.path.join(DADOS.RAIZ_DADOS, "mostra")

# 14 segmentos do pacote Mostraí (brand/mostrai): título, itens de partida, rótulo do destaque e paleta de referência.
# Valores do pacote são fictícios: não entram. O lojista preenche os preços na programação.
SEGMENTOS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mostrai_segmentos.json"), encoding="utf-8"))
SETOR_SEG = {"cafeteria": "01_Cafeteria", "restaurante": "02_Restaurante", "bar": "02_Restaurante", "padaria": "03_Padaria", "clínica/consultório": "04_Clinica",
    "estética": "05_Estetica", "salão/barbearia": "06_Salao", "escritório/imobiliária": "07_Imobiliaria", "loja de roupas/calçados": "08_Loja_Roupas",
    "floricultura/presentes": "08_Loja_Roupas", "pet": "09_Pet_Shop", "farmácia": "10_Farmacia", "ótica": "10_Farmacia", "academia/estúdio": "11_Academia",
    "autopeças/oficina": "12_Autopecas", "celular/assistência": "13_Escritorio", "escola/curso": "13_Escritorio", "cereais/empório": "14_Mercado",
    "mercado/hortifruti": "14_Mercado", "embalagens/utilidades": "14_Mercado", "comércio": "14_Mercado"}

def segmento(setor):
    setor = setor or ""
    return SETOR_SEG.get(setor) or SETOR_SEG.get(setor.split("/")[0]) or "14_Mercado"

def _destaque(d):
    d = d if isinstance(d, dict) else {}
    ate = str(d.get("ate") or "")[:10]
    return {"rotulo": str(d.get("rotulo") or "")[:28], "texto": str(d.get("texto") or "")[:60], "valor": str(d.get("valor") or "")[:22],
            "ate": ate if re.match(r"^\d{4}-\d{2}-\d{2}$", ate) else ""}

def _arq(token):
    return os.path.join(PASTA, token + ".json")

def _escrever(token, obj):
    os.makedirs(PASTA, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=PASTA, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, _arq(token))

def ler(token):
    if not TOKEN.match(token or ""):
        raise ValueError("código inválido")
    try:
        return json.load(open(_arq(token), encoding="utf-8"))
    except FileNotFoundError:
        return None

def _logo_da_ficha(ficha, token):
    """copia o logotipo tratado (ou o primeiro salvo) da ficha para a pasta pública do Mostraí"""
    src = ((ficha.get("manual") or {}).get("tratado")) or (((ficha.get("logos") or [{}])[0]).get("src"))
    if not src or not src.startswith("/api/arq/"):
        return None
    try:
        _, _, col, ident, nome = src.split("/")[1:6]
        mime, raw = DADOS.arquivo(col, ident, nome)
    except Exception:
        return None
    ext = nome.rsplit(".", 1)[-1]
    pasta = os.path.join(PASTA, token); os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "logo." + ext), "wb") as f:
        f.write(raw)
    return f"/api/mostra/{token}/logo.{ext}"

def criar(slug, ficha, loja, por=None):
    """cria (ou devolve) o Mostraí da loja; o token fica na ficha (ficha['mostra'])"""
    tok = (ficha.get("mostra") or {}).get("token")
    est = ler(tok) if tok and TOKEN.match(tok) else None
    if not est:
        tok = "".join(secrets.choice(ALFA) for _ in range(10))
        setor = (loja or {}).get("setor") or ficha.get("setor") or "comércio"
        seg = segmento(setor); G = SEGMENTOS[seg]
        cores = [c.get("hex") for c in ((ficha.get("manual") or {}).get("cores") or []) if c.get("hex")]
        est = {"token": tok, "slug": slug, "nome": ficha.get("nome") or (loja or {}).get("nome") or slug, "setor": setor, "segmento": seg,
               "rotulo": G["rotulo"], "titulo": G["titulo"], "aviso": "", "cores": cores[:4], "paleta": G["paleta"], "logo": None, "foto": None, "giro": 0,
               "v": 1, "criado": time.strftime("%Y-%m-%dT%H:%M:%S"), "por": por,
               "destaque": {"rotulo": G["destaque_rotulo"], "texto": "", "valor": "", "ate": ""},
               "itens": [{"id": f"i{i+1}", "nome": n, "preco": "", "desc": "", "ativo": True} for i, n in enumerate(G["itens"])]}
    # segmento conferido na visita mudou e o lojista ainda não lançou preço: a tela acompanha o segmento certo
    seg_novo = segmento((loja or {}).get("setor") or est.get("setor"))
    if est.get("segmento") != seg_novo and not any((i.get("preco") or "").strip() for i in est.get("itens", [])) and not (est.get("destaque") or {}).get("valor"):
        G = SEGMENTOS[seg_novo]
        est.update({"segmento": seg_novo, "setor": (loja or {}).get("setor") or est.get("setor"), "rotulo": G["rotulo"], "titulo": G["titulo"], "paleta": G["paleta"],
                    "destaque": {"rotulo": G["destaque_rotulo"], "texto": "", "valor": "", "ate": ""},
                    "itens": [{"id": f"i{i+1}", "nome": n, "preco": "", "desc": "", "ativo": True} for i, n in enumerate(G["itens"])]})
        est["v"] = int(est.get("v") or 1) + 1
    if not est.get("segmento"):   # telas criadas antes do pacote de 14 segmentos
        seg = segmento(est.get("setor")); G = SEGMENTOS[seg]
        est.update({"segmento": seg, "rotulo": G["rotulo"], "paleta": G["paleta"]})
        est.setdefault("destaque", {"rotulo": G["destaque_rotulo"], "texto": "", "valor": "", "ate": ""})
        if est.get("titulo") in ("Cardápio", "Nossos serviços", "", None):
            est["titulo"] = G["titulo"]
    est["logo"] = _logo_da_ficha(ficha, tok) or est.get("logo")
    if not est.get("cores"):
        est["cores"] = [c.get("hex") for c in ((ficha.get("manual") or {}).get("cores") or []) if c.get("hex")][:4]
    _escrever(tok, est)
    return est

def gravar(token, mud):
    """programação do cliente: só os campos editáveis; sobe a versão"""
    est = ler(token)
    if not est:
        raise FileNotFoundError
    if isinstance(mud.get("itens"), list):
        itens = []
        for i, it in enumerate(mud["itens"][:60]):
            if not isinstance(it, dict):
                continue
            itens.append({"id": re.sub(r"[^a-z0-9]", "", str(it.get("id") or f"i{i+1}"))[:16] or f"i{i+1}",
                          "nome": str(it.get("nome") or "")[:60], "preco": str(it.get("preco") or "")[:20],
                          "desc": str(it.get("desc") or "")[:40], "ativo": it.get("ativo", True) is not False})
        est["itens"] = itens
    for k, n in (("titulo", 40), ("aviso", 140)):
        if k in mud:
            est[k] = str(mud[k] or "")[:n]
    if "destaque" in mud:
        est["destaque"] = _destaque(mud["destaque"])
    if mud.get("giro") in (0, 90, 270):
        est["giro"] = mud["giro"]
    if mud.get("foto") is None and "foto" in mud:
        est["foto"] = None
    est["v"] = int(est.get("v") or 1) + 1; est["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever(token, est)
    return est

def foto_gravar(token, data_url):
    """foto principal da tela (JPEG já reduzido no aparelho de quem envia); fica no servidor"""
    import base64
    est = ler(token)
    if not est:
        raise FileNotFoundError
    m = re.match(r"^data:image/(jpeg|png|webp);base64,(.+)$", data_url or "", re.S)
    if not m:
        raise ValueError("imagem inválida")
    raw = base64.b64decode(m.group(2)); ext = {"jpeg": "jpg"}.get(m.group(1), m.group(1))
    if len(raw) > 4_000_000:
        raise ValueError("foto grande demais")
    pasta = os.path.join(PASTA, token); os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        if f.startswith("foto."):
            os.remove(os.path.join(pasta, f))
    with open(os.path.join(pasta, "foto." + ext), "wb") as f:
        f.write(raw)
    est["v"] = int(est.get("v") or 1) + 1; est["foto"] = f"/api/mostra/{token}/foto.{ext}?v={est['v']}"; est["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever(token, est)
    return est

def logo(token, nome):
    if not TOKEN.match(token or "") or not re.match(r"^(logo|foto)\.[a-z0-9]{1,5}$", nome or ""):
        raise ValueError("caminho inválido")
    ext = nome.rsplit(".", 1)[1]
    mime = {v: k for k, v in DADOS.EXT.items()}.get(ext, "application/octet-stream")
    with open(os.path.join(PASTA, token, nome), "rb") as f:
        return mime, f.read()
