"""GênIO · busca automática de logotipo (decisão do dono, 09/11: sempre buscar; o vendedor aprova).

Para cada loja de uma zona sem logotipo na ficha do servidor:
  1. usa o que a captação já achou (lacunas.logoOriginal, melhor opção);
  2. senão, pesquisa de imagens "<nome> logo <bairro>" (Serper) e pega a primeira que parece marca
     (quadrada ou larga, pequena, de página com o nome da loja).
Grava na ficha: logos=[{src:/api/arq/…, auto:true, fonte, legenda}], aprovacao="pendente".
Nada é tratado nem gerado antes da aprovação. Roda ao fim da captação e sob pedido do admin.
"""
import base64, json, os, re, sys, time, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import dados as DADOS

def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode())

def _palavras(nome):
    STOP = {"de", "da", "do", "das", "dos", "e", "a", "o", "ltda", "me", "sao", "paulo", "loja", "comercio", "casa"}
    return [p for p in _norm(nome).split() if len(p) > 2 and p not in STOP]

def _data_url(mime, raw):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()

def candidato_captacao(zona, slug):
    try:
        f = json.load(open(os.path.join(RAIZ, "dados", "captacao", zona, "clientes", slug + ".json")))
    except Exception:
        return None
    lo = (f.get("lacunas") or {}).get("logoOriginal") or {}
    if lo.get("estado") != "encontrado" or not lo.get("valor"):
        return None
    arq = os.path.join(RAIZ, "dados", "captacao", zona, lo["valor"])
    if not os.path.exists(arq):
        return None
    ext = arq.rsplit(".", 1)[-1].lower(); mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return {"src": _data_url(mime, open(arq, "rb").read()), "fonte": "captação", "legenda": lo.get("nome") or "Captação", "nota": lo.get("nota_conf")}

def candidato_pesquisa(api, nome, bairro):
    r = api.busca_imagens(f"{nome} logo {bairro}".strip())
    imgs = r.get("imagens") or []
    pal = _palavras(nome)
    def pontos(i):
        p = 0
        t = _norm((i.get("titulo") or "") + " " + (i.get("fonte") or "") + " " + (i.get("pagina") or ""))
        p += sum(2 for w in pal if w in t)
        if re.search(r"logo|marca|brand|perfil|instagram|facebook", t): p += 2
        w, h = i.get("w") or 0, i.get("h") or 0
        if w and h:
            prop = w / h
            if 0.6 <= prop <= 2.6: p += 2
            if max(w, h) <= 1200: p += 1
        return p
    for i in sorted(imgs, key=pontos, reverse=True)[:5]:
        if pontos(i) < 3:
            break
        for u in (i.get("u"), i.get("thumb")):
            try:
                ct, raw = api.proxy_img(u)
                if len(raw) > 2000:
                    return {"src": _data_url(ct, raw), "fonte": "pesquisa", "legenda": (i.get("titulo") or i.get("fonte") or "Pesquisa de imagens")[:80], "url": i.get("pagina") or u}
            except Exception:
                continue
    return None

def rodar(zona, api, limite=None, log=print):
    try:
        lojas = json.load(open(os.path.join(RAIZ, "dados", "captacao", zona, "lojas.json")))["lojas"]
    except Exception as e:
        log(f"zona {zona} sem lojas.json: {e}"); return {"zona": zona, "erro": "sem lojas"}
    feitas = pesquisas = 0
    for l in lojas:
        if limite and feitas >= limite:
            break
        slug = l["slug"]
        f = DADOS.cliente_ler(slug) or {"k": (l.get("nome") or "").lower(), "nome": l.get("nome"), "slug": slug, "logos": [], "arquivo": [], "criado": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if (f.get("logos") or []) or (f.get("manual") or {}).get("editado"):
            continue
        c = candidato_captacao(zona, slug)
        if not c:
            bairro = ((l.get("endereco") or "").split(" · ")[1:] or [zona.replace("-", " ")])[0]
            try:
                c = candidato_pesquisa(api, l.get("nome") or slug, bairro); pesquisas += 1
            except Exception as e:
                log(f"{slug}: pesquisa falhou: {e}"); c = None
        if not c:
            continue
        f["logos"] = [{"id": "auto" + str(int(time.time() * 1000))[-8:], "src": c["src"], "nome": "Logotipo · automático", "origem": c["fonte"], "legenda": c.get("legenda"), "url": c.get("url"), "auto": True}]
        f["aprovacao"] = "pendente"; f["logoAutoEm"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        DADOS.cliente_gravar(slug, f, "busca automática")
        feitas += 1
    log(f"logos automáticos {zona}: {feitas} lojas ({pesquisas} pesquisas)")
    return {"zona": zona, "feitas": feitas, "pesquisas": pesquisas}

if __name__ == "__main__":
    import genio_api as api
    for z in sys.argv[1:] or ["zona-cerealista"]:
        print(rodar(z, api))
