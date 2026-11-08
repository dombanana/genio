#!/usr/bin/env python3
"""Captação GenIO — roda na VPS (serviço genio-captacao), sem IA.

Entrada : captacao/zonas/<zona>.json (consultas, centro, raio, base) e api/captacao.run ({"zona","limite"}).
Chaves  : /var/lib/genio/chaves.json (tela Chaves do admin) ou variáveis de ambiente.
Saída   : dados/captacao/<zona>/  (servido em https://genio.dombanana.tech/dados/captacao/<zona>/)
            places.json      tudo que o Places devolveu (cache 7 dias)
            lojas.json       lojas filtradas, com dia/ordem da rota
            clientes/<slug>.json  cadastro no formato das caixinhas (lacunas)
            img/<slug>/      imagens baixadas (logo e local)
            index.html       revisão: caminho percorrido, candidatos, notas, decisões
            visitas.csv / visitas.kml / roteiro.html   exportação para o vendedor
            status.json / log.txt
Regras  : só entra como logo o que a fonte identifica como marca (perfil de rede social, foto do dono no Places,
          imagem repetida em 2+ fontes). Foto de ambiente vai para Local. Dúvida → opções para decidir. Nada inventado.
Cota    : 50 lojas por noite (reserva de 50 para refazer); "limite" no captacao.run manda.
"""
import json, os, re, sys, math, time, hashlib, unicodedata, io, csv, html, subprocess, datetime as dt
from urllib import request, parse, error

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "dados", "captacao")
ESTADO = "/var/lib/genio"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GenIO-captacao/1.0"}
try:
    from PIL import Image
except Exception:
    Image = None

# ---------- chaves ----------
def chaves():
    c = {}
    try:
        c = json.load(open(os.environ.get("GENIO_CHAVES", os.path.join(ESTADO, "chaves.json"))))
    except Exception:
        pass
    for k in ("GOOGLE_PLACES_KEY", "SERPER_KEY", "APIFY_TOKEN"):
        if os.environ.get(k):
            c[k] = os.environ[k]
    return c
K = chaves()

# ---------- utilidades ----------
def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70]
def km(a, b):
    return math.hypot((a[0] - b[0]) * 111, (a[1] - b[1]) * 102)
def http(url, data=None, headers=None, timeout=40, binario=False):
    h = dict(UA); h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode(); h.setdefault("Content-Type", "application/json")
    req = request.Request(url, data=body, headers=h)
    with request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if binario else json.loads(b.decode("utf-8", "replace") or "{}")
def tenta(f, *a, **kw):
    if f is http and "headers" in kw and len(a) == 1:
        a = (a[0], None)
    try:
        return f(*a, **kw)
    except error.HTTPError as e:
        return {"_erro": f"HTTP {e.code} {e.read()[:200].decode('utf-8','replace')}"}
    except Exception as e:
        return {"_erro": str(e)[:200]}
def tel_br(t):
    d = re.sub(r"\D", "", t or ""); d = d[2:] if d.startswith("55") and len(d) > 11 else d
    return f"({d[:2]}) {d[2:-4]}-{d[-4:]}" if len(d) in (10, 11) else (t or "")
def log(pasta, msg):
    linha = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(linha, flush=True)
    with open(os.path.join(pasta, "log.txt"), "a") as f:
        f.write(linha + "\n")
def status(pasta, **kw):
    p = os.path.join(pasta, "status.json")
    try:
        s = json.load(open(p))
    except Exception:
        s = {}
    s.update(kw); s["atualizado"] = dt.datetime.now().isoformat(timespec="seconds")
    json.dump(s, open(p, "w"), ensure_ascii=False, indent=1)

# ---------- filtro de redes / setor (mesmas listas do montar.py) ----------
FRANQ = re.compile(r"\b(drogasil|droga ?raia|drogaria s[aã]o paulo|pague menos|ultrafarma|drogal|nissei|panvel|mcdonald|burger king|subway|habib|starbucks|cacau show|kopenhagen|brasil cacau|botic[aá]rio|natura|petz|cobasi|petlove|smart ?fit|bluefit|bio ?ritmo|magazine luiza|casas bahia|renner|riachuelo|c&a|americanas|[oó]ticas? (carol|diniz)|chilli beans|havaianas|spoleto|china in box|domino|pizza hut|giraffas|bob's|outback|oakberry|bradesco|ita[uú]|santander|caixa econ|banco do brasil|correios|lot[eé]rica|kumon|wizard|fisk|ccaa|\bcna\b|carrefour|p[aã]o de a[çc][uú]car|assa[ií]|hirota|sonda|swift|vivara|hering|lupo|centauro|leroy|telhanorte|kfc|popeyes|rei do mate|casa do p[aã]o de queijo|chiquinho|kalunga|pernambucanas|marisa|zara|arezzo|melissa|ri happy|pbkids|cvc|localiza|movida|vivo|claro|tim|unidas|shell|am ?pm|oxxo|dia %|extra|minuto p[aã]o|sodi[eê]|hortifruti|oba\b|st ?marche|natural da terra|cultura inglesa|wise up|mercad[aã]o|mercado municipal)\b", re.I)
ENDERECO_COMO_NOME = re.compile(r"^(r\.|rua|av\.?|avenida|al\.|alameda|tv\.|travessa|pç\.|praça|lj\.?|loja)\s.*\d", re.I)
TIPOS_FORA = {"lodging", "atm", "bank", "parking", "transit_station", "bus_station", "subway_station", "church", "school", "hospital", "government_office", "post_office", "police", "gas_station", "car_rental", "insurance_agency", "real_estate_agency", "lawyer", "university", "local_government_office", "courthouse", "embassy", "cemetery", "park", "tourist_attraction", "museum"}
SETORES = [("padaria", ["bakery", "confectionery", "pastry", "cake", "candy", "dessert", "padaria", "panific", "confeit", "doceria"]), ("restaurante", ["restaurant", "snack", "diner", "hamburger", "fast_food", "pizza", "lanch", "restaur"]), ("bar", [r"\bbar\b", r"\bpub\b", "boteco"]), ("cafeteria", ["cafe", "coffee", "café"]),
           ("salão/barbearia", ["barber", "hair", "beauty", "nail", "spa", "barbear", "salão", "salao", "cabele"]), ("pet", [r"\bpet\b", r"pet ?shop", "veterinary", "veterin"]), ("clínica/consultório", ["dentist", "dental", "doctor", "medical", "physio", "odonto", "clínica", "clinica"]), ("academia/estúdio", ["gym", "fitness", "pilates", "yoga", "academia", "crossfit"]),
           ("ótica", ["optician", "eyewear", "ótica", "otica"]), ("loja de roupas/calçados", ["clothing", "shoe", "fashion", "apparel", "modas", "calçad"]), ("floricultura/presentes", ["florist", "gift", "home_goods", "toy", "stationery", "floric", "papelaria"]),
           ("cereais/empório", ["health_food", "grocery", "cereal", "emp[óo]rio", "gr[ãa]os", "armaz[ée]m", "temper", "especiar", "castanh", "natura"]), ("mercado/hortifruti", ["supermarket", "butcher", "market", "convenience", "liquor", "casa de carnes", "açougue", "acougue"]),
           ("embalagens/utilidades", ["embalag", "descart", "utilidad", "panela", "utens", "sacaria"]), ("celular/assistência", ["electronics", "cell_phone", "phone", "repair", "celular", "assist"]), ("escritório/imobiliária", ["accounting", "contab", "imobili"]), ("escola/curso", ["language", "education", "tutor", "idiomas", "curso"])]
PROD = {"padaria": "capacho · adesivo de vitrine · cardápio de parede", "restaurante": "capacho · cardápio de parede · Mostra Aí", "bar": "capacho · cardápio · banner", "cafeteria": "capacho · cardápio de parede · Mostra Aí", "salão/barbearia": "capacho · adesivo de vitrine · cartões", "pet": "capacho · placa · adesivo de vitrine", "clínica/consultório": "placa de recepção · cartões · capacho", "academia/estúdio": "placa · adesivo de parede · uniformes", "ótica": "adesivo de vitrine · placa · cartões", "loja de roupas/calçados": "adesivo de vitrine · banner · capacho", "floricultura/presentes": "adesivo de vitrine · cartões · capacho", "cereais/empório": "capacho (chuva e grão no chão) · placa de preços · adesivo de vitrine", "mercado/hortifruti": "banner · placa · capacho", "embalagens/utilidades": "capacho · banner · placa", "celular/assistência": "adesivo de vitrine · placa · cartões", "escritório/imobiliária": "placa de recepção · cartões · capacho", "escola/curso": "placa · adesivo de parede · uniformes", "comércio": "capacho · placa · cartões"}
def setor(p):
    t = (" ".join(p.get("types", [])) + " " + p["nome"]).lower()
    for s, ks in SETORES:
        if any(re.search(k, t) for k in ks):
            return s
    return "comércio"

# ---------- 1. Places ----------
PL = "https://places.googleapis.com/v1/"
def places_busca(texto, centro, raio):
    out, tok = [], None
    for _ in range(3):
        body = {"textQuery": texto, "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 20,
                "locationBias": {"circle": {"center": {"latitude": centro[0], "longitude": centro[1]}, "radius": raio}}}
        if tok:
            body["pageToken"] = tok
        r = tenta(http, PL + "places:searchText", body, {"X-Goog-Api-Key": K["GOOGLE_PLACES_KEY"],
            "X-Goog-FieldMask": "nextPageToken,places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.types,places.primaryType,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours.weekdayDescriptions,places.googleMapsUri,places.businessStatus"})
        if "_erro" in r:
            return out, r["_erro"]
        out += r.get("places", []); tok = r.get("nextPageToken")
        if not tok:
            break
        time.sleep(1.5)
    return out, None
def places_fotos(pid):
    r = tenta(http, PL + f"places/{pid}", None, {"X-Goog-Api-Key": K["GOOGLE_PLACES_KEY"], "X-Goog-FieldMask": "photos"})
    if "_erro" in r:
        return {"_erro": r["_erro"]}
    return r.get("photos", [])[:5]
def places_foto_bytes(nome, w=900):
    return tenta(http, PL + f"{nome}/media?maxWidthPx={w}&skipHttpRedirect=false&key={K['GOOGLE_PLACES_KEY']}", binario=True)

def places_avaliacoes(pid):
    r = tenta(http, PL + f"places/{pid}", None, {"X-Goog-Api-Key": K["GOOGLE_PLACES_KEY"], "X-Goog-FieldMask": "reviews,rating,userRatingCount"})
    if "_erro" in r:
        return [], r["_erro"]
    out = []
    for v in r.get("reviews", [])[:10]:
        out.append({"nota": v.get("rating"), "texto": (v.get("originalText") or v.get("text") or {}).get("text", ""), "autor": (v.get("authorAttribution") or {}).get("displayName", ""), "quando": v.get("relativePublishTimeDescription", ""), "fonte": "Google"})
    return out, None
def serper_avaliacoes(pid):
    r = serper("reviews", "", placeId=pid, sortBy="lowestRating")
    if "_erro" in r:
        return [], r["_erro"]
    out = []
    for v in (r.get("reviews") or [])[:10]:
        out.append({"nota": v.get("rating"), "texto": v.get("snippet") or v.get("text") or "", "autor": (v.get("user") or {}).get("name", ""), "quando": v.get("date", ""), "fonte": "Google"})
    return out, None
# temas das avaliações que o nosso serviço resolve → argumento pronto para o vendedor
GATILHOS = [
    ("chão sujo / molhado", r"\b(suj[oa]s?|sujeira|imund|poeira|ch[aã]o (molhado|escorregadio|sujo)|piso (molhado|sujo|escorreg)|escorreg|lama|barro|molhad[oa])\b", "capacho", "Clientes já reclamam do chão: o capacho na entrada segura a sujeira e a água da rua antes de entrar."),
    ("difícil de achar / sem identificação", r"\b(dif[ií]cil (de )?(achar|encontrar|localizar)|n[aã]o (achei|encontrei|vi a placa)|sem placa|placa (pequena|apagada|escondida)|escondid[oa]|mal sinalizad)\b", "placa", "Gente passa reto: placa e adesivo de vitrine com a marca resolvem na hora."),
    ("fachada / aparência", r"\b(fachada|aparência|apar[eê]ncia|feio|feia|velh[oa]|descuidad|mal cuidad|bagun[cç]|desorganizad|cai(ndo|ndo aos peda[cç]os))\b", "adesivos", "A primeira impressão está pesando contra: identidade visual na entrada e na vitrine muda isso."),
    ("preço sem placa", r"\b(sem pre[cç]o|pre[cç]o (n[aã]o|sem) (est[aá]|tem) (marcado|exposto)|n[aã]o tem pre[cç]o)\b", "placas", "Reclamação de preço escondido: placa de preços padronizada com a marca."),
    ("atendimento sem identificação", r"\b(n[aã]o sabia quem (era|atendia)|uniforme|funcion[aá]rio[s]? (sem|n[aã]o) identific)\b", "uniformes", "Uniforme com a marca identifica a equipe e passa confiança."),
    ("cheiro / higiene", r"\b(cheiro (ruim|forte|de mofo)|mofo|higiene|insalubr|barat[ao]s?|rato)\b", "capacho", "Higiene aparece nas avaliações: capacho e organização visual da entrada ajudam na percepção de limpeza."),
]
CONTEXTO_LUGAR = r"\b(loja|lugar|local|ambiente|entrada|porta|ch[aã]o|piso|fachada|vitrine|placa|letreiro|banheiro|balc[aã]o|estabelecimento|espa[cç]o|corredor|box|mesa|sal[aã]o|atendimento|funcion[aá]ri)"
def gatilhos(avals):
    """só vira gancho quando a reclamação é sobre o LUGAR (não sobre o produto): a palavra precisa vir perto de loja/entrada/chão/placa…"""
    out = []
    for a in avals:
        t = (a.get("texto") or "").lower()
        for tema, rx, prod, arg in GATILHOS:
            m = re.search(rx, t, re.I)
            if m:
                i = max(0, m.start() - 60); trecho = t[i:m.end() + 60].strip()
                if not re.search(CONTEXTO_LUGAR, t[max(0, m.start() - 80):m.end() + 80], re.I):
                    continue
                out.append({"tema": tema, "produto": prod, "argumento": arg, "trecho": ("…" if i else "") + trecho + "…", "nota": a.get("nota"), "autor": a.get("autor")})
    # um por tema, priorizando notas baixas
    vistos, fim = set(), []
    for g in sorted(out, key=lambda g: (g["nota"] or 5)):
        if g["tema"] not in vistos:
            vistos.add(g["tema"]); fim.append(g)
    return fim
# ---------- 2. Serper ----------
def serper(caminho, q, **kw):
    if not K.get("SERPER_KEY"):
        return {"_erro": "sem SERPER_KEY"}
    body = dict(q=q, gl="br", hl="pt-br", **kw)
    return tenta(http, "https://google.serper.dev/" + caminho, body, {"X-API-KEY": K["SERPER_KEY"]})

# ---------- 3. Apify (Instagram) ----------
def apify_instagram(handle):
    if not K.get("APIFY_TOKEN"):
        return {"_erro": "sem APIFY_TOKEN"}
    url = "https://api.apify.com/v2/acts/apify~instagram-profile-scraper/run-sync-get-dataset-items?timeout=90&token=" + K["APIFY_TOKEN"]
    r = tenta(http, url, {"usernames": [handle]}, timeout=120)
    if isinstance(r, list) and r:
        return r[0]
    return r if isinstance(r, dict) else {"_erro": "vazio"}

# ---------- 4. Receita (grátis) ----------
def receita(cnpj):
    d = re.sub(r"\D", "", cnpj)
    r = tenta(http, f"https://minhareceita.org/{d}")
    if "_erro" in r:
        r = tenta(http, f"https://brasilapi.com.br/api/cnpj/v1/{d}")
    return r

# ---------- imagens ----------
def baixar(url, destino, maxb=6_000_000):
    try:
        req = request.Request(url, headers=dict(UA, Referer="https://www.google.com/"))
        with request.urlopen(req, timeout=25) as r:
            ct = r.headers.get("Content-Type", "")
            if "text/html" in ct:
                return None
            b = r.read(maxb + 1)
        if len(b) > maxb or len(b) < 1500 or not (b[:3] == b"\xff\xd8\xff" or b[:4] == b"\x89PNG" or b[:4] == b"RIFF" or b[:3] == b"GIF"):
            return None
        with open(destino, "wb") as f:
            f.write(b)
        return destino
    except Exception:
        return None
def analisar(caminho):
    """tamanho, proporção, dhash (64 bits) — sem PIL devolve só o tamanho do arquivo"""
    info = {"bytes": os.path.getsize(caminho)}
    if not Image:
        return info
    try:
        im = Image.open(caminho); im.load()
        w, h = im.size; info.update(w=w, h=h, prop=round(w / h, 2))
        g = im.convert("L").resize((9, 8), Image.LANCZOS); px = list(g.getdata())
        bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
        info["dhash"] = "%016x" % int(bits, 2)
        # cores dominantes (para o manual): 5 cores mais frequentes numa versão reduzida
        pq = im.convert("RGB").resize((48, 48)).quantize(colors=6, method=Image.Quantize.MEDIANCUT).convert("RGB")
        cont = {}
        for c in pq.getdata():
            cont[c] = cont.get(c, 0) + 1
        info["cores"] = ["#%02x%02x%02x" % c for c, _ in sorted(cont.items(), key=lambda x: -x[1])[:5]]
        # recorte quadrado com conteúdo centralizado? (logo costuma ser) — fração de pixels iguais à borda
        b = im.convert("RGB").resize((64, 64)); d = list(b.getdata()); borda = d[:64] + d[-64:] + d[::64] + d[63::64]
        from collections import Counter
        cor_b, n = Counter(borda).most_common(1)[0]
        info["fundo_liso"] = round(n / len(borda), 2)
    except Exception as e:
        info["erro"] = str(e)[:80]
    return info
def ham(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")

# ---------- curiosidade do nome (Wikipédia pt; Gemini só se a Wikipédia não tiver) ----------
GENERICAS = {"carnes","carne","acougue","açougue","padaria","emporio","empório","loja","lojas","distribuidora","comercial","industria","indústria","atacado","varejo","alimentos","bebidas","embalagens","utilidades","equipamentos","cosmeticos","cosméticos","suplementos","graos","grãos","cereais","temperos","especiarias","castanhas","frutas","secas","famiglia","familia","família","central","grande","pequeno","pequena","novo","nova","velho","velha","bom","boa","santo","santa","sao","são","casa","mundo","brasil","paulista","paulistana","paulistano","real","nacional","popular","imperial","express","premium","gourmet","delicia","delícia","sabor","sabores","arte","artes","ponto","cantinho","recanto","espaco","espaço","super","mega","hiper","top","plus","mais","best"}
def curiosidade_nome(nome):
    """origem da palavra marcante do nome: Wikipédia só quando o artigo é claramente lugar, sobrenome ou palavra (título exato);
    senão Gemini numa frase; senão vira pergunta para o dono"""
    ts = [t for t in tokens(nome) if len(t) >= 4 and t not in GENERICAS]
    if not ts:
        return None
    ACEITA = re.compile(r"\b(sobrenome|apelido de fam[ií]lia|nome de fam[ií]lia|munic[ií]pio|cidade|comuna|vila|aldeia|bairro|distrito|regi[aã]o|prov[ií]ncia|pa[ií]s|rio|serra|ilha|palavra|termo|express[aã]o|significa|nome pr[oó]prio|prenome|deusa?|mitologia)\b", re.I)
    REJEITA = re.compile(r"(pode referir-se|pode se referir|desambigua|esp[eé]cie|g[eê]nero de|fam[ií]lia [A-Z][a-z]+idae|escola de samba|pintor|cantor|ator|atriz|futebolista|jogador|pol[ií]tico|banda|álbum|filme|telenovela)", re.I)
    for palavra in ts[:3]:
        try:
            r = tenta(http, "https://pt.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch=" + parse.quote(palavra), headers={"User-Agent": "GenIO/1.0 (captacao)"})
            for hit in (r.get("query") or {}).get("search") or []:
                titulo = hit["title"]
                if unicodedata.normalize("NFKD", titulo.split(" (")[0]).encode("ascii", "ignore").decode().lower() != palavra:
                    continue
                r2 = tenta(http, "https://pt.wikipedia.org/api/rest_v1/page/summary/" + parse.quote(titulo.replace(" ", "_")), headers={"User-Agent": "GenIO/1.0 (captacao)"})
                ext = (r2.get("extract") or "").strip()
                if ext and ACEITA.search(ext) and not REJEITA.search(ext):
                    frase = re.split(r"(?<=[.!?])\s", ext)[0][:220]
                    return {"estado": "encontrado", "valor": frase, "origem": "publico", "nota": f"Wikipédia · {titulo}", "palavra": palavra}
        except Exception:
            pass
    palavra = ts[0]
    if K.get("GEMINI_KEY"):
        try:
            body = {"contents": [{"parts": [{"text": f"Em uma frase curta (máx. 30 palavras), em português, qual a origem ou o significado provável da palavra '{palavra}' no nome do comércio '{nome}' (sobrenome, cidade, palavra estrangeira, apelido)? Seja factual. Se não houver base, responda só: sem registro."}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 80}}
            # modelos em ordem de preferência: o Google aposenta versões e a resposta de erro indica a nova
            r, txt = {}, ""
            for modelo in ("gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest"):
                r = tenta(http, f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent", body, {"x-goog-api-key": K["GEMINI_KEY"]})
                txt = ((((r.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text") or "").strip()
                if txt or "404" not in str(r.get("_erro", "")):
                    break
            if txt and "sem registro" not in txt.lower():
                return {"estado": "derivado", "valor": txt[:220], "origem": "derivado", "nota": "Gemini (uma frase; confirmar com o dono)", "palavra": palavra}
            erro_g = r.get("_erro") or ("resposta vazia" if not txt else "sem registro")
        except Exception as e:
            erro_g = str(e)[:120]
    else:
        erro_g = "sem GEMINI_KEY"
    return {"estado": "pendente", "valor": "", "origem": "cliente", "nota": f"origem do nome não encontrada — perguntar ao dono (“{palavra}” é de família ou de lugar?) · {erro_g}", "palavra": palavra}
# ---------- o @ / domínio bate com o nome da loja? ----------
STOP={"natural","temperos","tempero","padaria","cafe","bar","restaurante","barbearia","salao","salão","otica","ótica","pet","farmacia","farmácia","doces","doce","loja","lojas","casa","comercio","comércio","ltda","me","mei","eireli","sa","s/a","e","de","da","do","das","dos","the","zona","cerealista","brás","bras","sao","são","paulo","sp","centro","oficial","store","shop","br","com","www","emporio","empório","distribuidora","produtos","naturais","mercado","mercadao","mercadão"}
def tokens(s_):
    s_ = unicodedata.normalize("NFKD", s_ or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", s_) if len(t) >= 3 and t not in STOP]
def bate_nome(nome, alvo):
    """True se um token significativo do nome da loja aparece no @ ou no domínio (ou o nome colado inteiro)"""
    a = unicodedata.normalize("NFKD", alvo or "").encode("ascii", "ignore").decode().lower()
    a = re.sub(r"[^a-z0-9]", "", a)
    ts = tokens(nome)
    if not ts or not a:
        return False
    if "".join(ts) in a or a in "".join(ts):
        return True
    hits = sum(1 for t in ts if len(t) >= 4 and t in a)
    return hits >= min(2, len([t for t in ts if len(t) >= 4]))  # nome com 2+ palavras: as duas têm de aparecer
def cnpj_ok(c):
    d = re.sub(r"\D", "", c)
    if len(d) != 14 or d == d[0] * 14:
        return False
    def dv(nums, pesos):
        r = sum(int(n) * p for n, p in zip(nums, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]; p2 = [6] + p1
    return d[12] == dv(d[:12], p1) and d[13] == dv(d[:13], p2)
# ---------- notas ----------
def _penalidades():
    """fontes que o vendedor marcou como erradas no aparelho: -8 por marcação (até -30)"""
    pen = {}
    try:
        for linha in open(os.path.join(ESTADO, "captacao", "correcoes.jsonl")):
            x = json.loads(linha)
            if x.get("acao") == "errada" and x.get("fonte"):
                k = str(x["fonte"]).lower()
                for f in ("instagram", "facebook", "linktr", "places", "imprensa", "diretorio"):
                    if f in k:
                        pen[f] = min(30, pen.get(f, 0) + 8)
    except Exception:
        pass
    return pen
PESO_FONTE = {"site-proprio": 70, "instagram-perfil": 70, "facebook-perfil": 65, "places-foto": 45, "serper-instagram": 55, "serper-facebook": 55, "serper-linktree": 60, "serper-diretorio": 40, "serper-imprensa": 25, "serper-outro": 30}
def classificar_fonte(dominio):
    d = (dominio or "").lower()
    if "instagram" in d or "cdninstagram" in d:
        return "serper-instagram"
    if "facebook" in d or "fbsbx" in d or "fbcdn" in d:
        return "serper-facebook"
    if "linktr" in d:
        return "serper-linktree"
    if any(x in d for x in ("baressp", "fresha", "ifood", "tripadvisor", "foursquare", "apontador", "guiamais", "solutudo", "cylex", "wanderboat", "kekanto", "zomato", "goomer", "cardapio", "menuweb", "rappi", "booksy", "trinks", "avaliacoes", "locaisdobrasil", "encontrasp")):
        return "serper-diretorio"
    if any(x in d for x in ("uol", "globo", "r7", "estadao", "folha", "exame", "veja", "istoe", "cnn", "band", "terra", "ig.com", "metropoles")):
        return "serper-imprensa"
    return "serper-outro"

# ---------- cadastro ----------
def E(v, origem="publico", **k):
    return dict(estado="encontrado", valor=v, origem=origem, **k)
def horario_txt(desc):
    if not desc:
        return ""
    mapa = {"Monday": "seg", "Tuesday": "ter", "Wednesday": "qua", "Thursday": "qui", "Friday": "sex", "Saturday": "sáb", "Sunday": "dom", "segunda-feira": "seg", "terça-feira": "ter", "quarta-feira": "qua", "quinta-feira": "qui", "sexta-feira": "sex", "sábado": "sáb", "domingo": "dom"}
    out = []
    for d in desc:
        k, _, v = d.partition(":")
        out.append(f"{mapa.get(k.strip(), k.strip()[:3])} {v.strip().replace('Fechado','fechado').replace('Closed','fechado')}")
    return " · ".join(out)

def identidade(loja, zona, pasta, quota_ok):
    """preenche as caixinhas de uma loja com fontes públicas; devolve (cadastro, custo)"""
    s = loja["slug"]; img_dir = os.path.join(pasta, "img", s); os.makedirs(img_dir, exist_ok=True)
    custo = {"places_detalhe": 0, "places_foto": 0, "serper": 0, "apify": 0, "receita": 0}
    cands, locais, fontes, passos = [], [], ["Google Places"], []
    L = {"nome": E(loja["nome"], fontes=["Google Places"]), "setor": E(loja["setor"]), "endereco": E(loja["endereco"] + " · " + zona["bairro"]),
         "servicos": dict(estado="derivado", valor=PROD.get(loja["setor"], PROD["comércio"]), origem="derivado", nota="produtos sugeridos pelo setor; o cliente confirma")}
    if loja.get("tel"):
        L["tel"] = E(tel_br(loja["tel"]))
    if loja.get("horario"):
        L["horario"] = E(loja["horario"], nota="Google Places")
    if loja.get("site"):
        L["site"] = E(loja["site"])
    if not quota_ok:
        L["logoOriginal"] = {"estado": "pendente", "opcoes": [], "origem": "publico", "nota": "fora da cota desta noite; entra na próxima"}
        return L, custo, passos, fontes, cands, locais
    # --- Places Photos (fotos do perfil do Google: dono + clientes)
    fotos = places_fotos(loja["place_id"]); custo["places_detalhe"] += 1
    erro_fotos = fotos.get("_erro") if isinstance(fotos, dict) else None
    fotos = [] if isinstance(fotos, dict) else fotos
    for i, f in enumerate(fotos):
        b = places_foto_bytes(f["name"]); custo["places_foto"] += 1
        if isinstance(b, (bytes, bytearray)) and len(b) > 1500:
            p = os.path.join(img_dir, f"places-{i+1}.jpg"); open(p, "wb").write(b)
            autor = (f.get("authorAttributions") or [{}])[0].get("displayName", "")
            cands.append(dict(arq=p, fonte="places-foto", legenda=f"Google Places · foto {i+1}" + (f" · por {autor}" if autor else ""), url=loja.get("maps", ""), dono=(slug(autor)[:12] in s or s[:12] in slug(autor))))
    passos.append(f"Places Photos → {len(fotos)} fotos do perfil do Google" + (f" · erro: {erro_fotos}" if erro_fotos else ""))
    # --- avaliações (negativas primeiro) e gatilhos do nosso serviço
    avals, erro_av = places_avaliacoes(loja["place_id"]); custo["places_detalhe"] += 1
    if not avals:
        avals, erro_av2 = serper_avaliacoes(loja["place_id"]); custo["serper"] += 1
        erro_av = (erro_av or "") + (" · serper: " + erro_av2 if erro_av2 else "")
    avals.sort(key=lambda a: (a.get("nota") or 5))
    gat = gatilhos(avals)
    L["avaliacoes"] = {"estado": "encontrado" if avals else "nao", "origem": "publico", "valor": f"{loja.get('nota') or '—'} · {loja.get('aval') or 0} avaliações · {sum(1 for a in avals if (a.get('nota') or 5) <= 3)} negativas entre as {len(avals)} lidas (piores primeiro)", "nota_media": loja.get("nota"), "total": loja.get("aval"), "lista": avals, "gatilhos": gat, "nota": ("nenhuma avaliação lida" + (f" ({erro_av})" if erro_av else "")) if not avals else f"{len(avals)} lidas · {len(gat)} tocam no nosso serviço"}
    passos.append(f"Avaliações → {len(avals)} lidas, {sum(1 for a in avals if (a.get('nota') or 5) <= 3)} negativas, {len(gat)} gatilho(s) do nosso serviço" + (f" · {erro_av}" if erro_av and not avals else ""))
    # --- Serper imagens + web
    q = f'"{loja["nome"]}" {zona["bairro"]} {zona["cidade"]}'
    ri = serper("images", q, num=10); custo["serper"] += 1
    n_img = 0
    for i, it in enumerate((ri.get("images") or [])[:10]):
        url = it.get("imageUrl") or ""
        p = baixar(url, os.path.join(img_dir, f"web-{i+1}" + (".png" if url.lower().split("?")[0].endswith(".png") else ".jpg")))
        if p:
            n_img += 1; dom = it.get("domain") or it.get("source") or it.get("link") or ""
            cl = "site-proprio" if bate_nome(loja["nome"], re.sub(r"^https?://(www\.)?", "", dom).split("/")[0]) else classificar_fonte(dom)
            cands.append(dict(arq=p, fonte=cl, legenda=f"{it.get('source') or it.get('domain','')} · {it.get('title','')[:60]}", url=it.get("link") or url))
    passos.append(f"Google Imagens (Serper) → {len(ri.get('images') or [])} resultados, {n_img} baixadas" + (f" · {ri['_erro']}" if "_erro" in ri else ""))
    rw = serper("search", f'{loja["nome"]} {loja["endereco"]} {zona["cidade"]}', num=10); custo["serper"] += 1
    texto = json.dumps(rw, ensure_ascii=False)
    ig = re.findall(r"instagram\.com/([A-Za-z0-9_.]{3,30})/?", texto)
    ig = [h for h in ig if h.lower() not in ("p", "reel", "explore", "accounts", "stories", "reels")]
    fb = re.findall(r"facebook\.com/([A-Za-z0-9_.\-]{3,60})/?", texto)
    fb = [h for h in fb if h.lower() not in ("profile.php", "pages", "people", "groups", "watch")]
    cnpjs = [c for c in re.findall(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", texto) if cnpj_ok(c)]
    sites = [r.get("link") for r in (rw.get("organic") or []) if r.get("link") and not re.search(r"instagram|facebook|google|ifood|tripadvisor|foursquare|apontador|guiamais|solutudo|cylex|telelistas|econodata|cnpj|wanderboat|fresha|linktr|youtube|olx|mercadolivre|kekanto|yelp", r["link"])]
    passos.append(f"Google Web (Serper) → {len(rw.get('organic') or [])} páginas; instagram {ig[:2] or '—'}; facebook {fb[:1] or '—'}; cnpj {cnpjs[:1] or '—'}")
    ig_ok = [h for h in dict.fromkeys(ig) if bate_nome(loja["nome"], h)]
    fb_ok = [h for h in dict.fromkeys(fb) if bate_nome(loja["nome"], h)]
    ig_dup = [h for h in dict.fromkeys(ig) if h not in ig_ok][:3]
    redes = []
    if ig_ok:
        redes.append("Instagram @" + ig_ok[0]); fontes.append("Instagram")
    if fb_ok:
        redes.append("Facebook /" + fb_ok[0]); fontes.append("Facebook")
    if redes:
        L["redes"] = E(" · ".join(redes), nota="o @ confere com o nome da loja; confirmar na porta")
    elif ig_dup:
        L["redes"] = {"estado": "pendente", "origem": "publico", "valor": "", "opcoes": [{"valor": "@" + h, "legenda": "apareceu na busca, mas o nome não confere", "fonte": "Instagram"} for h in ig_dup], "nota": "nenhum @ que confira com o nome — decidir ou perguntar na porta"}
    else:
        L["redes"] = {"estado": "pendente", "origem": "publico", "valor": "", "nota": "nenhum @ encontrado na busca pública — perguntar na porta"}
    ig = ig_ok
    proprios = [u for u in sites if bate_nome(loja["nome"], re.sub(r"^https?://(www\.)?", "", u).split("/")[0])]
    if proprios and not L.get("site"):
        L["site"] = E(proprios[0], nota="domínio confere com o nome da loja")
    elif sites and not L.get("site"):
        L["site"] = {"estado": "pendente", "origem": "publico", "valor": "", "opcoes": [{"valor": u, "legenda": "página que cita a loja; domínio não confere com o nome", "fonte": "web"} for u in sites[:3]], "nota": "nenhum site com o nome da loja — decidir"}
    elif not L.get("site"):
        L["site"] = {"estado": "nao", "origem": "publico", "valor": "nenhum site próprio encontrado"}
    # --- Apify: foto de perfil do Instagram (a marca como o dono a usa)
    if ig:
        pr = apify_instagram(ig[0]); custo["apify"] += 1
        pic = pr.get("profilePicUrlHD") or pr.get("profilePicUrl") if isinstance(pr, dict) else None
        if pic:
            p = baixar(pic, os.path.join(img_dir, "instagram-perfil.jpg"))
            if p:
                cands.append(dict(arq=p, fonte="instagram-perfil", legenda=f"Foto de perfil · Instagram @{ig[0]}", url=f"https://www.instagram.com/{ig[0]}/"))
        bio = (pr.get("biography") or "").strip() if isinstance(pr, dict) else ""
        if bio:
            if re.search(r"\b(ceo|diretor|diretora|fundador|fundadora|s[oó]cio|propriet[aá]ri[oa]|empres[aá]ri[oa])\b", bio.split("\n")[0], re.I):
                bio = ""  # bio pessoal do dono, não frase da casa
            if bio: L["slogan"] = {"estado": "pendente", "origem": "cliente", "valor": "", "opcoes": [{"valor": bio.split("\n")[0][:80], "legenda": "bio do Instagram", "fonte": "Instagram"}], "nota": "frase que a casa usa; confirmar"}
        if isinstance(pr, dict) and pr.get("externalUrl") and L.get("site", {}).get("estado") != "encontrado":
            L["site"] = E(pr["externalUrl"])
        passos.append(f"Instagram @{ig[0]} (Apify) → " + ("perfil lido" if isinstance(pr, dict) and not pr.get("_erro") else f"falhou: {pr.get('_erro') if isinstance(pr, dict) else pr}"))
    # --- Receita
    cn_ops = []
    for c in list(dict.fromkeys(re.sub(r"\D", "", x) for x in cnpjs))[:3]:
        rc = receita(c); custo["receita"] += 1
        if "_erro" not in rc and (rc.get("razao_social") or rc.get("nome")):
            ab = rc.get("data_inicio_atividade") or rc.get("abertura") or ""
            rz = rc.get("razao_social") or rc.get("nome") or ""
            cn_ops.append({"valor": f"Razão social: {rz} · CNPJ {c}" + (f" · desde {ab}" if ab else ""), "legenda": "Receita Federal", "fonte": "Receita", "bate": bate_nome(loja["nome"], rz)})
    if len(cn_ops) == 1 or (cn_ops and sum(1 for o in cn_ops if o["bate"]) == 1):
        esc_ = next((o for o in cn_ops if o["bate"]), cn_ops[0])
        L["leitura"] = E(esc_["valor"], nota="Receita Federal (minhareceita/BrasilAPI)" + ("" if esc_["bate"] else " · razão social não confere com o nome; confirmar na porta")); fontes.append("Receita Federal")
    elif cn_ops:
        L["leitura"] = {"estado": "pendente", "origem": "publico", "valor": "", "opcoes": cn_ops, "nota": "mais de um CNPJ citado para este nome — decidir"}
    if "leitura" not in L:
        L["leitura"] = {"estado": "pendente", "origem": "publico", "valor": "", "nota": "CNPJ não apareceu em fonte pública aberta"}
    # --- análise das imagens e notas
    for c in cands:
        c.update(analisar(c["arq"]))
        c["rel"] = os.path.relpath(c["arq"], pasta)
    # repetição entre fontes (dhash ≤ 10)
    for c in cands:
        rep = {c["fonte"]}
        for d in cands:
            if d is not c and c.get("dhash") and d.get("dhash") and ham(c["dhash"], d["dhash"]) <= 10:
                rep.add(d["fonte"])
        c["repete"] = len(rep) - 1
    logos, loc = [], []
    for c in cands:
        prop = c.get("prop") or 0
        quadrada = 0.75 <= prop <= 1.35
        liso = (c.get("fundo_liso") or 0) >= 0.6
        nota = PESO_FONTE.get(c["fonte"], 30) - next((v for k, v in PEN.items() if k in c["fonte"]), 0)
        if c["fonte"] in ("instagram-perfil", "facebook-perfil"):
            nota += 15                       # a marca como o dono a usa
        if c.get("dono"):
            nota += 15
        if quadrada:
            nota += 5
        if liso:
            nota += 10
        nota += 12 * min(c["repete"], 3)    # principal = o que mais se repete
        c["nota"] = min(100 if c["repete"] else 85, nota)
        # foto de ambiente: paisagem/retrato grande sem fundo liso e sem ser perfil → Local
        # site próprio: só vira candidato de logo se parecer logo (quadrada com fundo liso, ou "logo" no endereço/legenda); foto de produto vai para Local
        pareceLogo = re.search(r"logo|marca|brand|icon|avatar|perfil", (c.get("url") or "") + " " + (c.get("legenda") or ""), re.I)
        if c["fonte"] in ("instagram-perfil", "facebook-perfil") or (c["fonte"] == "site-proprio" and (quadrada and liso or pareceLogo)) or (quadrada and liso) or c["repete"] >= 2:
            logos.append(c)
        else:
            loc.append(c)
    logos.sort(key=lambda c: -c["nota"])
    if logos and logos[0]["nota"] >= 70:
        top = logos[0]
        L["logoOriginal"] = {"estado": "encontrado", "origem": "publico", "valor": top["rel"], "nome": top["legenda"], "nota_conf": top["nota"],
                             "opcoes": [{"img": c["rel"], "legenda": c["legenda"], "fonte": c["fonte"], "nota": c["nota"]} for c in logos[:4]], "escolhida": 0}
    elif logos and logos[0]["nota"] >= 40:
        L["logoOriginal"] = {"estado": "pendente", "origem": "publico", "valor": "", "nota_conf": logos[0]["nota"],
                             "opcoes": [{"img": c["rel"], "legenda": c["legenda"], "fonte": c["fonte"], "nota": c["nota"]} for c in logos[:4]], "nota": "candidatos com confiança média — decidir"}
    else:
        L["logoOriginal"] = {"estado": "pendente", "origem": "porta", "valor": "", "opcoes": [], "nota": "nenhuma imagem identificada como marca em fonte pública — fotografar a placa na porta"}
    L["fachada"] = {"estado": "pendente" if loc else "pendente", "origem": "porta", "referencias": [c["rel"] for c in loc[:8]],
                    "nota": f"{len(loc)} fotos do local como referência (não são candidatos de logo)" if loc else "nenhuma foto do local em fonte aberta; tirar na porta"}
    if logos and logos[0].get("cores"):
        L["cores"] = dict(estado="derivado", valor=" ".join(logos[0]["cores"]), origem="derivado", nota="cores dominantes da imagem principal; o manual confirma")
    L.setdefault("slogan", {"estado": "pendente", "origem": "cliente", "valor": "", "nota": "nenhum slogan público; perguntar na porta"})
    cn = curiosidade_nome(loja["nome"])
    if cn:
        L["nome_curiosidade"] = cn; passos.append("Curiosidade do nome → " + (cn["valor"][:90] if cn["valor"] else cn["nota"]))
    L.setdefault("sobre", {"estado": "pendente", "origem": "cliente", "valor": "", "nota": "sem texto público sobre a casa"})
    return L, custo, passos, fontes, logos, loc

# ---------- manual de identidade (pipeline sem IA) para logo encontrado ----------
def gerar_manual(slug_, cad_path, logo_path, pasta):
    out = os.path.join(pasta, "manual", slug_)
    try:
        import shutil
        if os.path.exists(os.path.join(out, "manual.html")) and os.path.getmtime(os.path.join(out, "manual.html")) > os.path.getmtime(logo_path):
            return {"estado": "encontrado", "valor": f"manual/{slug_}/manual.html", "origem": "derivado", "nota": "manual já gerado"}
        os.makedirs(out, exist_ok=True)
        r = subprocess.run([sys.executable, "-I", os.path.join(RAIZ, "api", "manual", "pipeline.py"), logo_path, cad_path, out], capture_output=True, text=True, timeout=240)
        if r.returncode != 0:
            return {"estado": "pendente", "valor": "", "origem": "derivado", "nota": "pipeline falhou: " + (r.stderr or r.stdout)[-300:].strip()}
        res = {}
        try:
            res = json.load(open(os.path.join(out, "relatorio.json")))
        except Exception:
            pass
        fid = res.get("fidelidade")
        mn = res.get("minimo_cm"); mn = (mn.get("capacho (8 mm)") if isinstance(mn, dict) else mn)
        return {"estado": "encontrado" if (fid or 0) >= 0.85 else "pendente", "valor": f"manual/{slug_}/manual.html", "origem": "derivado", "fidelidade": fid, "cores": res.get("cores"), "nota": f"fidelidade {round(fid, 2) if fid else '?'} · {res.get('camadas')} cores/camadas" + (f" · menor largura no capacho {round(mn)} cm" if isinstance(mn, (int, float)) and mn > 0 else "") + ("" if (fid or 0) >= 0.85 else " — conferir antes de usar")}
    except Exception as e:
        return {"estado": "pendente", "valor": "", "origem": "derivado", "nota": "manual não gerado: " + str(e)[:160]}
# ---------- rota ----------
def rota(lojas, base, por_dia):
    """vizinho mais próximo + melhoria 2-opt (tira os cruzamentos e os saltos longos)"""
    pool = lojas[:]; cur = base; ordem = []
    while pool:
        nx = min(pool, key=lambda x: km((x["lat"], x["lng"]), cur)); pool.remove(nx); ordem.append(nx); cur = (nx["lat"], nx["lng"])
    P = lambda x: (x["lat"], x["lng"])
    melhorou, passes = True, 0
    while melhorou and passes < 20:
        melhorou = False; passes += 1
        for i in range(0, len(ordem) - 2):
            a = base if i == 0 else P(ordem[i - 1]); b = P(ordem[i])
            for j in range(i + 1, len(ordem) - 1):
                c, d = P(ordem[j]), P(ordem[j + 1])
                if km(a, c) + km(b, d) < km(a, b) + km(c, d) - 1e-6:
                    ordem[i:j + 1] = ordem[i:j + 1][::-1]; melhorou = True; b = P(ordem[i])
    for i, x in enumerate(ordem):
        x["dia"] = i // por_dia + 1; x["ordem"] = i % por_dia + 1
    return ordem

# ---------- exportação ----------
def exportar(zona, lojas, cads, pasta):
    with open(os.path.join(pasta, "visitas.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["dia", "ordem", "nome", "setor", "endereco", "telefone", "nota_google", "avaliacoes", "horario", "logo", "produtos", "lat", "lng", "cadastro"])
        for x in lojas:
            c = cads.get(x["slug"], {}); lg = c.get("lacunas", {}).get("logoOriginal", {})
            w.writerow([x["dia"], x["ordem"], x["nome"], x["setor"], x["endereco"], tel_br(x.get("tel")), x.get("nota"), x.get("aval"), x.get("horario", ""), lg.get("estado", ""), PROD.get(x["setor"], ""), x["lat"], x["lng"], f"clientes/{x['slug']}.json"])
    def pm(x):
        nome = html.escape(f"{x['dia']}.{x['ordem']} {x['nome']}"); desc = html.escape(x["setor"] + " · " + x["endereco"])
        return f"<Placemark><name>{nome}</name><description>{desc}</description><Point><coordinates>{x['lng']},{x['lat']},0</coordinates></Point></Placemark>"
    open(os.path.join(pasta, "visitas.kml"), "w").write('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>' + html.escape(zona["nome"]) + "</name>" + "".join(pm(x) for x in lojas) + "</Document></kml>")
    dias = {}
    for x in lojas:
        dias.setdefault(x["dia"], []).append(x)
    h = ["<!doctype html><html lang=pt-BR><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Roteiro · " + html.escape(zona["nome"]) + "</title>",
         "<style>body{font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;color:#1C1635;background:#FFFEFA}h1{font-size:20px}h2{font-size:16px;margin:18px 0 6px;color:#6933C5}table{border-collapse:collapse;width:100%}td,th{padding:5px 6px;border-bottom:1px solid #D8CCEA;font-size:13px;text-align:left;vertical-align:top}.ok{color:#1F5FA8;font-weight:600}.dec{color:#C8552B;font-weight:600}@media print{h2{page-break-before:always}}</style>",
         f"<h1>Roteiro de visitas · {html.escape(zona['nome'])}</h1><p>{len(lojas)} lojas · {len(dias)} dias · {zona.get('por_dia',25)} por dia · gerado {dt.date.today():%d/%m/%Y}</p>"]
    for d, xs in sorted(dias.items()):
        h.append(f"<h2>Dia {d} · {len(xs)} visitas</h2><table><tr><th>#</th><th>Loja</th><th>Setor · produtos</th><th>Endereço · tel</th><th>Google</th><th>Logo</th></tr>")
        for x in xs:
            lg = cads.get(x["slug"], {}).get("lacunas", {}).get("logoOriginal", {}); st = lg.get("estado", "")
            h.append(f"<tr><td>{x['ordem']}</td><td><b>{html.escape(x['nome'])}</b></td><td>{html.escape(x['setor'])}<br><small>{html.escape(PROD.get(x['setor'],''))}</small></td><td>{html.escape(x['endereco'])}<br><small>{html.escape(tel_br(x.get('tel')))}</small></td><td>{x.get('nota') or '—'} ({x.get('aval') or 0})</td><td class='{'ok' if st=='encontrado' else 'dec'}'>{'pronto' if st=='encontrado' else ('decidir' if lg.get('opcoes') else 'na porta')}</td></tr>")
        h.append("</table>")
    open(os.path.join(pasta, "roteiro.html"), "w").write("".join(h))

def revisao(zona, lojas, cads, detalhes, pasta, resumo):
    esc = html.escape
    css = "body{margin:0;background:#FFFEFA;color:#1C1635;font:15px/1.5 Rubik,system-ui,sans-serif;padding:20px 16px 50px}.w{max-width:1000px;margin:0 auto}h1{font-size:24px;margin:0}h1 i{font-style:normal;color:#6933C5}h2{font-size:18px;margin:26px 0 8px}h3{font-size:16px;margin:18px 0 6px}.sub{color:#6B6578}.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}figure{margin:0;background:#EBE3F5;border-radius:12px;padding:6px}figure img{width:100%;height:150px;object-fit:contain;background:#fff;border-radius:8px;display:block}figcaption{font-size:11px;color:#6B6578;margin-top:4px}table{border-collapse:collapse;width:100%}td{padding:5px 8px;border-bottom:1px solid #D8CCEA;font-size:13px;vertical-align:top}.st{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600;color:#fff;background:#C8552B}.st.encontrado{background:#1F5FA8}.st.derivado{background:#6933C5}.st.nao{background:#8E9391}.st.pendente{background:#E8A33D}.passo{border-left:4px solid #6933C5;padding:5px 12px;margin:6px 0;background:#fff;border-radius:0 10px 10px 0;font-size:14px}.loja{background:#fff;border:1px solid #D8CCEA;border-radius:16px;padding:14px 16px;margin:14px 0}.n{font-weight:700;color:#1F5FA8}.exp a{display:inline-block;margin:4px 8px 4px 0;padding:8px 12px;border-radius:10px;background:#6933C5;color:#fff;text-decoration:none;font-size:14px}"
    h = [f"<!doctype html><html lang=pt-BR><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Captação · {esc(zona['nome'])}</title><style>{css}</style></head><body><div class=w>",
         f"<h1>Captação · <i>{esc(zona['nome'])}</i></h1><p class=sub>{resumo}</p>",
         "<h2>Exportação</h2><div class=exp><a href='visitas.csv'>visitas.csv (planilha)</a><a href='visitas.kml'>visitas.kml (Google Maps / My Maps)</a><a href='roteiro.html'>roteiro.html (imprimir)</a><a href='lojas.json'>lojas.json (sistema)</a><a href='clientes/'>clientes/ (cadastros)</a></div>",
         "<h2>O caminho percorrido</h2>"]
    for p in resumo_passos:
        h.append(f"<div class=passo>{esc(p)}</div>")
    h.append("<h2>Lojas processadas nesta rodada</h2>")
    for x in lojas:
        if x["slug"] not in detalhes:
            continue
        d = detalhes[x["slug"]]; c = cads[x["slug"]]["lacunas"]; lg = c["logoOriginal"]
        h.append(f"<div class=loja><h3>{x['dia']}.{x['ordem']} · {esc(x['nome'])} <span class=sub style='font-weight:400'>· {esc(x['setor'])} · {esc(x['endereco'])} · Google {x.get('nota') or '—'} ({x.get('aval') or 0})</span></h3>")
        for p in d["passos"]:
            h.append(f"<div class=passo>{esc(p)}</div>")
        st = lg["estado"]; tit = "Logo · encontrado" if st == "encontrado" else ("Logo · decidir" if lg.get("opcoes") else "Logo · nenhum candidato")
        h.append(f"<h3>{tit}" + (f" <span class=n>nota {lg.get('nota_conf')}</span>" if lg.get("nota_conf") else "") + "</h3>")
        if lg.get("opcoes"):
            h.append("<div class=g>" + "".join(f"<figure><a href='{esc(o['img'])}' target=_blank><img src='{esc(o['img'])}' loading=lazy></a><figcaption><b>nota {o['nota']}</b> · {esc(o['legenda'])} · <a href='{esc(o['img'])}' target=_blank>abrir ↗</a></figcaption></figure>" for o in lg["opcoes"]) + "</div>")
        else:
            h.append(f"<p class=sub>{esc(lg.get('nota',''))}</p>")
        refs = c.get("fachada", {}).get("referencias") or []
        h.append("<h3>Local (referência; não são candidatos de logo)</h3>")
        h.append("<div class=g>" + "".join(f"<figure><a href='{esc(r)}' target=_blank><img src='{esc(r)}' loading=lazy></a><figcaption><a href='{esc(r)}' target=_blank>abrir ↗</a></figcaption></figure>" for r in refs) + "</div>" if refs else "<p class=sub>nenhuma foto do local em fonte aberta</p>")
        h.append("<h3>Caixinhas</h3><table>")
        for k, v in c.items():
            stv = v["estado"]; lab = "decidir" if stv == "pendente" and v.get("opcoes") else stv
            val = v.get("valor", "") if k != "logoOriginal" else v.get("nome", "")
            if k == "avaliacoes" and v.get("gatilhos"):
                val = str(val) + "<br>" + "<br>".join(f"<b>{esc(g['tema'])}</b> → {esc(g['argumento'])} <i>“{esc(g['trecho'][:140])}”</i>" for g in v["gatilhos"])
                nota = ""; h.append(f"<tr><td>{k}</td><td><span class='st {stv}'>{stv}</span></td><td>{val}</td><td>{esc(v['origem'])}</td></tr>"); continue
            if stv == "pendente" and v.get("opcoes") and k != "logoOriginal":
                val = " · ".join(f"<b>{esc(o.get('valor', ''))}</b> <i>({esc(o['legenda'])})</i>" for o in v["opcoes"])
            else:
                val = esc(str(val))
            nota = f"<div class=sub style='font-size:12px'>{esc(v['nota'])}</div>" if v.get("nota") else ""
            h.append(f"<tr><td>{k}</td><td><span class='st {stv}'>{lab}</span></td><td>{val}{nota}</td><td>{esc(v['origem'])}</td></tr>")
        cu = d["custo"]
        h.append(f"</table><p class=sub>Custo desta loja: Places {cu['places_detalhe']} detalhe + {cu['places_foto']} fotos · Serper {cu['serper']} · Apify {cu['apify']} · Receita {cu['receita']} ≈ R$ {d['reais']:.2f}</p></div>")
    h.append("</div></body></html>")
    open(os.path.join(pasta, "index.html"), "w").write("".join(h))

PEN = _penalidades()
def zona_config(zslug):
    """configuração da zona: arquivo em captacao/zonas/<slug>.json ou, se não houver, montada a partir do ranking
    (centro pelo Places, raio 700 m, consultas por eixo e por perfil) e guardada para as próximas rodadas"""
    for cfgp in (os.path.join(RAIZ, "captacao", "zonas", zslug + ".json"), os.path.join(ESTADO, "captacao", "zonas", zslug + ".json")):
        if os.path.exists(cfgp):
            return json.load(open(cfgp))
    try:
        rk = json.load(open(os.path.join(RAIZ, "captacao", "ranking.json")))
    except Exception:
        return None
    z = next((x for x in rk["zonas"] if x.get("slug") == zslug), None)
    if not z or not K.get("GOOGLE_PLACES_KEY"):
        return None
    nome = z["nome"].split(" (")[0]; eixos = [e.strip() for e in re.split(r"[·,]", z["nome"].split("(")[1].rstrip(")"))] if "(" in z["nome"] else [nome]
    r = tenta(http, PL + "places:searchText", {"textQuery": f"{nome}, São Paulo, SP", "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 1}, {"X-Goog-Api-Key": K["GOOGLE_PLACES_KEY"], "X-Goog-FieldMask": "places.location,places.formattedAddress"})
    loc = ((r.get("places") or [{}])[0].get("location") or {}) if "_erro" not in r else {}
    if not loc:
        return None
    centro = [loc["latitude"], loc["longitude"]]
    setores = [t.strip() for t in re.split(r"[;,]", z.get("perfil", "")) if len(t.strip()) > 3][:4]
    consultas = [f"lojas {e} São Paulo" for e in eixos] + [f"comércio {nome} São Paulo", f"restaurante lanchonete {nome} São Paulo", f"padaria café {nome} São Paulo", f"loja de roupas {nome} São Paulo", f"salão de beleza barbearia {nome} São Paulo", f"pet shop {nome} São Paulo", f"ótica farmácia {nome} São Paulo", f"mercado hortifruti {nome} São Paulo"] + [f"{st} {nome} São Paulo" for st in setores]
    cfg = {"slug": zslug, "nome": z["nome"], "bairro": nome, "cidade": "São Paulo", "centro": centro, "raio_m": 700, "base": centro, "por_dia": 25, "consultas": consultas[:22], "gerada": dt.date.today().isoformat()}
    try:
        os.makedirs(os.path.join(ESTADO, "captacao", "zonas"), exist_ok=True)
        json.dump(cfg, open(os.path.join(ESTADO, "captacao", "zonas", zslug + ".json"), "w"), ensure_ascii=False, indent=1)
    except Exception:
        pass
    return cfg
# ---------- principal ----------
resumo_passos = []
def main():
    # pedido de execução: (a) api/captacao.run pela esteira, (b) /var/lib/genio/captacao/pedido.json pelo admin; cada nonce vale uma vez.
    # Sem pedido novo (rodada da madrugada): zona escolhida no admin ou a do último pedido, 50 lojas, sem refazer.
    os.makedirs(os.path.join(ESTADO, "captacao"), exist_ok=True)
    run, consumidos = {}, {}
    try:
        consumidos = json.load(open(os.path.join(ESTADO, "captacao", "nonces.json")))
    except Exception:
        pass
    for fonte in (os.path.join(ESTADO, "captacao", "pedido.json"), os.path.join(RAIZ, "api", "captacao.run")):
        try:
            r = json.load(open(fonte))
            if r.get("nonce") and r["nonce"] not in consumidos:
                run = r; consumidos[r["nonce"]] = dt.datetime.now().isoformat(timespec="seconds"); break
        except Exception:
            pass
    json.dump(consumidos, open(os.path.join(ESTADO, "captacao", "nonces.json"), "w"))
    try:
        padrao = json.load(open(os.path.join(ESTADO, "captacao", "padrao.json")))
    except Exception:
        padrao = {}
    if run:
        padrao["zona"] = run.get("zona") or padrao.get("zona"); json.dump(padrao, open(os.path.join(ESTADO, "captacao", "padrao.json"), "w"))
    if not run and not (2 <= dt.datetime.now().hour <= 5) and "--forcar" not in sys.argv:
        # serviço iniciado fora da madrugada sem pedido novo (nonce já consumido): não gastar 50 lojas por engano
        print("sem pedido novo; nada a fazer"); return
    zslug = run.get("zona") or padrao.get("zona") or (sys.argv[1] if len(sys.argv) > 1 else "zona-cerealista")
    limite = int(run["limite"]) if run.get("limite") is not None else 50
    zona = zona_config(zslug)
    if not zona:
        pasta = os.path.join(DADOS, zslug); os.makedirs(pasta, exist_ok=True)
        log(pasta, f"zona {zslug} sem configuração e sem entrada no ranking"); status(pasta, fase="erro", erro="zona desconhecida"); return
    pasta = os.path.join(DADOS, zslug); os.makedirs(os.path.join(pasta, "clientes"), exist_ok=True); os.makedirs(os.path.join(pasta, "img"), exist_ok=True)
    status(pasta, fase="inicio", zona=zslug, limite=limite)
    if not K.get("GOOGLE_PLACES_KEY"):
        log(pasta, "sem GOOGLE_PLACES_KEY — grave na tela Chaves do admin"); status(pasta, fase="erro", erro="sem chave Places"); return
    # cota diária
    qp = os.path.join(ESTADO, "captacao", "quota.json")
    try:
        quota = json.load(open(qp))
    except Exception:
        quota = {}
    hoje = str(dt.date.today()); usadas = quota.get(hoje, 0)
    # 1. Places (cache 7 dias)
    pj = os.path.join(pasta, "places.json")
    if os.path.exists(pj) and time.time() - os.path.getmtime(pj) < 7 * 86400:
        brutos = json.load(open(pj)); resumo_passos.append(f"1. Places: {len(brutos)} lugares do cache ({dt.datetime.fromtimestamp(os.path.getmtime(pj)):%d/%m})")
    else:
        vistos = {}; erros = 0
        for i, qtxt in enumerate(zona["consultas"]):
            ps, err = places_busca(qtxt, zona["centro"], zona["raio_m"])
            if err:
                erros += 1; log(pasta, f"places '{qtxt}': {err}")
            for p in ps:
                vistos[p["id"]] = p
            log(pasta, f"places {i+1}/{len(zona['consultas'])} '{qtxt}' → {len(ps)} (acum. {len(vistos)})"); status(pasta, fase="places", consulta=i + 1, lugares=len(vistos))
        brutos = list(vistos.values()); json.dump(brutos, open(pj, "w"), ensure_ascii=False)
        resumo_passos.append(f"1. Places Text Search: {len(zona['consultas'])} consultas → {len(brutos)} lugares distintos" + (f" ({erros} consultas com erro)" if erros else ""))
    # 2. filtro
    lojas = []
    for p in brutos:
        nome = p.get("displayName", {}).get("text", ""); loc = p.get("location", {}); lat, lng = loc.get("latitude"), loc.get("longitude")
        if not nome or lat is None or FRANQ.search(nome) or p.get("businessStatus") not in (None, "OPERATIONAL"):
            continue
        if ENDERECO_COMO_NOME.search(nome):  # "R. Comendador Abdo Schahin, 206 - Lj 62" não é loja, é um ponto sem nome
            continue
        if set(p.get("types", [])) & TIPOS_FORA and not (set(p.get("types", [])) & {"store", "food", "restaurant", "cafe", "bakery"}):
            continue
        if km((lat, lng), zona["centro"]) * 1000 > zona["raio_m"] * 1.3:
            continue
        end = (p.get("formattedAddress") or "").split(" - ")[0]
        x = {"nome": nome, "slug": slug(nome), "place_id": p["id"], "lat": lat, "lng": lng, "endereco": end, "tel": p.get("nationalPhoneNumber", ""), "site": p.get("websiteUri", ""),
             "nota": p.get("rating"), "aval": p.get("userRatingCount"), "types": p.get("types", []), "maps": p.get("googleMapsUri", ""), "horario": horario_txt((p.get("regularOpeningHours") or {}).get("weekdayDescriptions"))}
        x["setor"] = setor(x); lojas.append(x)
    vistos = set(); lojas = [x for x in lojas if not (x["slug"] in vistos or vistos.add(x["slug"]))]
    lojas = rota(lojas, zona["base"], zona.get("por_dia", 25))
    from collections import Counter
    resumo_passos.append(f"2. Filtro (redes, tipos fora do alvo, raio {zona['raio_m']} m) → {len(lojas)} lojas independentes · {len(set(x['dia'] for x in lojas))} dias de visita · setores: " + ", ".join(f"{s} {n}" for s, n in Counter(x['setor'] for x in lojas).most_common(6)))
    json.dump({"zona": zona, "gerado": hoje, "lojas": lojas}, open(os.path.join(pasta, "lojas.json"), "w"), ensure_ascii=False, indent=0)
    # 3. identidade (ordem da rota; pula quem já tem cadastro completo)
    cads, detalhes = {}, {}; feitas = 0; reais = 0.0
    for x in lojas:
        cp = os.path.join(pasta, "clientes", x["slug"] + ".json")
        if os.path.exists(cp):
            cads[x["slug"]] = json.load(open(cp))
            if cads[x["slug"]].get("processado") and not run.get("refazer"):
                continue
        if feitas >= limite or (not run and usadas + feitas >= 50):  # cota de 50/dia só para a rodada automática; pedido explícito vale o limite pedido
            L, custo, passos, fontes, lg, lc = identidade(x, zona, pasta, False)
        else:
            log(pasta, f"identidade {feitas+1}/{limite}: {x['nome']}"); status(pasta, fase="identidade", loja=x["nome"], feitas=feitas)
            L, custo, passos, fontes, lg, lc = identidade(x, zona, pasta, True); feitas += 1
            r = custo["places_detalhe"] * 0.09 + custo["places_foto"] * 0.04 + custo["serper"] * 0.006 + custo["apify"] * 0.03 + custo["receita"] * 0
            reais += r; detalhes[x["slug"]] = {"passos": passos, "custo": custo, "reais": r}
        cads[x["slug"]] = {"nome": x["nome"], "slug": x["slug"], "rota": {"centro": zslug, "dia": x["dia"], "ordem": x["ordem"], "place_id": x["place_id"], "lat": x["lat"], "lng": x["lng"], "nota": x.get("nota"), "aval": x.get("aval")},
                           "coletadoEm": hoje, "fontes": fontes, "processado": x["slug"] in detalhes, "lacunas": L}
        json.dump(cads[x["slug"]], open(cp, "w"), ensure_ascii=False, indent=1)
        if x["slug"] in detalhes and L.get("logoOriginal", {}).get("estado") == "encontrado":
            lp = os.path.join(pasta, L["logoOriginal"]["valor"])
            L["manual"] = gerar_manual(x["slug"], cp, lp, pasta); detalhes[x["slug"]]["passos"].append("Manual de identidade → " + L["manual"]["nota"])
            json.dump(cads[x["slug"]], open(cp, "w"), ensure_ascii=False, indent=1)
    quota[hoje] = usadas + feitas; json.dump(quota, open(qp, "w"))
    json.dump([{"slug": s, "nome": c["nome"], "dia": c["rota"]["dia"], "ordem": c["rota"]["ordem"], "logo": c["lacunas"].get("logoOriginal", {}).get("estado")} for s, c in cads.items()], open(os.path.join(pasta, "clientes", "index.json"), "w"), ensure_ascii=False)
    enc = sum(1 for s in detalhes if cads[s]["lacunas"]["logoOriginal"]["estado"] == "encontrado"); dec = sum(1 for s in detalhes if cads[s]["lacunas"]["logoOriginal"].get("opcoes") and cads[s]["lacunas"]["logoOriginal"]["estado"] != "encontrado")
    resumo_passos.append(f"3. Identidade pública de {feitas} lojas (cota do dia {quota[hoje]}/50{" · pedido manual" if run else ""}): logo encontrado {enc} · decidir {dec} · na porta {feitas-enc-dec} · custo ≈ R$ {reais:.2f}")
    # 4. exportação e revisão
    exportar(zona, lojas, cads, pasta)
    resumo_passos.append("4. Exportado: visitas.csv, visitas.kml, roteiro.html, lojas.json, clientes/*.json")
    revisao(zona, lojas, cads, detalhes, pasta, f"{len(lojas)} lojas · {feitas} processadas nesta rodada · {hoje} · custo da rodada ≈ R$ {reais:.2f}")
    status(pasta, fase="pronto", lojas=len(lojas), processadas=feitas, custo_reais=round(reais, 2)); log(pasta, f"pronto: {len(lojas)} lojas, {feitas} processadas, R$ {reais:.2f}")

if __name__ == "__main__":
    main()
