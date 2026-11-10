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

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MODELOS = ("lista", "sem-foto", "vitrine", "combo")

def _item(it, i):
    return {"id": re.sub(r"[^a-z0-9]", "", str(it.get("id") or f"i{i+1}"))[:16] or f"i{i+1}",
            "nome": str(it.get("nome") or "")[:60], "preco": str(it.get("preco") or "")[:20],
            "desc": str(it.get("desc") or "")[:40], "apartir": it.get("apartir") is True, "ativo": it.get("ativo", True) is not False}

def _telas(lista, antigas, token):
    """telas do carrossel: cada uma com modelo, foto própria e os seus itens (o preço ligado àquela foto)"""
    fotos = {t.get("id"): t.get("foto") for t in (antigas or [])}
    out = []
    for k, t in enumerate(lista[:20]):
        if not isinstance(t, dict):
            continue
        tid = re.sub(r"[^a-z0-9]", "", str(t.get("id") or f"t{k+1}"))[:16] or f"t{k+1}"
        itens = [_item(it, i) for i, it in enumerate((t.get("itens") or [])[:12]) if isinstance(it, dict)]
        # foto: só as desta tela guardadas no servidor; sem o campo, fica a que já estava; null tira
        f = t.get("foto")
        foto = f if isinstance(f, str) and f.startswith(f"/api/mostra/{token}/") else (None if ("foto" in t and f is None) else fotos.get(tid))
        out.append({"id": tid, "modelo": t.get("modelo") if t.get("modelo") in MODELOS else "lista", "foto": foto, "itens": itens})
    return out

def _estilo(e, ant):
    e = e if isinstance(e, dict) else {}; out = dict(ant or {})
    if e.get("fonte") in ("moderna", "elegante", "impacto"): out["fonte"] = e["fonte"]
    if e.get("tamanho") in ("auto", "P", "M", "G"): out["tamanho"] = e["tamanho"]
    if e.get("logo_pos") in ("centro", "esquerda", "canto"): out["logo_pos"] = e["logo_pos"]
    if e.get("logo_tam") in ("P", "M", "G"): out["logo_tam"] = e["logo_tam"]
    if isinstance(e.get("rodape"), bool): out["rodape"] = e["rodape"]
    if e.get("combo") in ("todas", "nenhuma"): out["combo"] = e["combo"]
    try:
        if e.get("tempo") is not None: out["tempo"] = max(5, min(60, int(e["tempo"])))
    except (TypeError, ValueError):
        pass
    if isinstance(e.get("cores"), dict):
        out["cores"] = {k: (v if HEX.match(str(v or "")) else "") for k, v in e["cores"].items() if k in ("fundo", "faixa", "destaque", "texto")}
    return out

def publico(est):
    """o que a tela e a programação recebem: o estado + o que o ramo sugere (complemento certo e itens de partida)"""
    G = SEGMENTOS.get(est.get("segmento") or "") or {}
    return {**est, "complemento": G.get("complemento") or {"rotulo": "Complemento", "exemplo": ""}, "sugestoes": G.get("sugestoes") or []}

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
    if isinstance(mud.get("telas"), list):
        est["telas"] = _telas(mud["telas"], est.get("telas"), token)
        est["itens"] = [it for t in est["telas"] for it in t["itens"]]
    elif isinstance(mud.get("itens"), list):
        est["itens"] = [_item(it, i) for i, it in enumerate(mud["itens"][:60]) if isinstance(it, dict)]
    if "estilo" in mud:
        est["estilo"] = _estilo(mud["estilo"], est.get("estilo"))
    for k, n in (("titulo", 40), ("aviso", 70)):
        if k in mud:
            est[k] = str(mud[k] or "")[:n]
    if "destaque" in mud:
        est["destaque"] = _destaque(mud["destaque"])
    if mud.get("giro") in (0, 90, 270):
        est["giro"] = mud["giro"]
    # diagramação: formato da TV (auto/retrato/paisagem), tamanho em polegadas (0 = não informado) e itens por tela (0 = automático)
    if mud.get("formato") in ("auto", "retrato", "paisagem"):
        est["formato"] = mud["formato"]
    if mud.get("polegadas") in (0, 32, 43, 50, 55, 65, 75, 85):
        est["polegadas"] = mud["polegadas"]
    if mud.get("linhas") in (0, 4, 5, 6, 8, 10):
        est["linhas"] = mud["linhas"]
    if mud.get("foto") is None and "foto" in mud:
        est["foto"] = None
    est["v"] = int(est.get("v") or 1) + 1; est["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever(token, est)
    return est

def foto_gravar(token, data_url, tela=None):
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
    tela = re.sub(r"[^a-z0-9]", "", str(tela or ""))[:16]
    alvo = next((t for t in (est.get("telas") or []) if t.get("id") == tela), None) if tela else None
    base = f"foto-{tela}" if alvo else "foto"
    pasta = os.path.join(PASTA, token); os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        if f.startswith(base + "."):
            os.remove(os.path.join(pasta, f))
    with open(os.path.join(pasta, base + "." + ext), "wb") as f:
        f.write(raw)
    est["v"] = int(est.get("v") or 1) + 1; url = f"/api/mostra/{token}/{base}.{ext}?v={est['v']}"
    if alvo:
        alvo["foto"] = url
    else:
        est["foto"] = url
    est["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever(token, est)
    return est

def logo(token, nome):
    if not TOKEN.match(token or "") or not re.match(r"^(logo|foto|foto-[a-z0-9]{1,16})\.[a-z0-9]{1,5}$", nome or ""):
        raise ValueError("caminho inválido")
    ext = nome.rsplit(".", 1)[1]
    mime = {v: k for k, v in DADOS.EXT.items()}.get(ext, "application/octet-stream")
    with open(os.path.join(PASTA, token, nome), "rb") as f:
        return mime, f.read()
