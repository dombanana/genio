"""GênIO · Relacionamento com o cliente (página da loja pelo QR do balcão + conversa com o gerente).

/var/lib/genio/dados/relaciona/codigos.json        {"GA-0001": {"slug": ..., "ativado": ..., "por": ...}}
/var/lib/genio/dados/relaciona/<slug>.json         loja (dados públicos), respostas prontas, conversas, aparelhos
/var/lib/genio/dados/relaciona/<slug>/logo.<ext>   logotipo público da página

Regras combinadas com o dono (24/11/2026):
- o QR do balcão abre direto a conversa com o gerente; a conversa fica no nosso sistema (o cliente não precisa de conta);
- toda primeira mensagem recebe na hora a resposta pronta da loja, conforme o assunto;
- a conversa se encerra de quatro jeitos, e todos levam ao MESMO convite para o Google:
    elogio (logo depois da resposta), gerente marca "resolvido", cliente diz que está tudo certo,
    ou duas horas sem o cliente responder à última mensagem da loja;
- se o cliente voltar a escrever, a conversa reabre (o relacionamento continua);
- o convite é igual para todos: mesma frase, mesmo botão. Nada de brinde ou desconto em troca de avaliação.
"""
import hashlib, json, os, re, secrets, threading, time
import dados as DADOS

PASTA = os.path.join(DADOS.RAIZ_DADOS, "relaciona")
CODIGO = re.compile(r"^GA-\d{4}$")
ASSUNTOS = {"elogio": "Elogio", "sugestao": "Sugestão", "reclamacao": "Reclamação", "duvida": "Dúvida"}
SILENCIO_FIM = 2 * 3600   # duas horas sem o cliente responder à loja encerram a conversa (decisão do dono)
RESPOSTAS_PADRAO = {
    "elogio": "Que alegria ler isso! Muito obrigado por contar. Vamos passar para toda a equipe.",
    "sugestao": "Obrigado pela sugestão! O gerente vai ler com atenção e responde por aqui.",
    "reclamacao": "Sentimos muito. O gerente recebeu agora a sua mensagem e vai responder por aqui.",
    "duvida": "Recebemos a sua dúvida. O gerente responde por aqui em seguida.",
}
CONVITE = "Obrigado por conversar com a gente. Se quiser, conte também no Google."
_lock = threading.Lock()

def _agora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def _ts(s):
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0

def _h(tok):
    return hashlib.sha256(("rel|" + str(tok)).encode()).hexdigest()[:32]

def _arq(slug):
    return os.path.join(PASTA, DADOS.valida_slug(slug) + ".json")

def _codigos():
    return DADOS._ler_json(os.path.join(PASTA, "codigos.json")) or {}

def ler(slug):
    return DADOS._ler_json(_arq(slug))

def _gravar(slug, obj):
    DADOS._escrever_json(_arq(slug), obj)

# ---------- dados públicos da loja (vêm da captação + ficha) ----------
def loja_captacao(raiz, slug):
    """o registro da loja nas zonas captadas (nome, endereço, telefone, place_id, horário, mapa)"""
    base = os.path.join(raiz, "dados", "captacao")
    if os.path.isdir(base):
        for z in sorted(os.listdir(base)):
            f = os.path.join(base, z, "lojas.json")
            try:
                for l in json.load(open(f, encoding="utf-8")).get("lojas", []):
                    if l.get("slug") == slug:
                        return dict(l, zona=z)
            except Exception:
                continue
    return {}

def _logo_publico(ficha, slug):
    src = ((ficha.get("manual") or {}).get("tratado")) or (((ficha.get("logos") or [{}])[0]).get("src"))
    if not src or not src.startswith("/api/arq/"):
        return None
    try:
        _, _, col, ident, nome = src.split("/")[1:6]
        mime, raw = DADOS.arquivo(col, ident, nome)
    except Exception:
        return None
    ext = nome.rsplit(".", 1)[-1]
    pasta = os.path.join(PASTA, slug); os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        if f.startswith("logo."):
            os.remove(os.path.join(pasta, f))
    with open(os.path.join(pasta, "logo." + ext), "wb") as f:
        f.write(raw)
    return f"/api/loja/{slug}/logo.{ext}?v={int(time.time())}"

def _nome_loja(nome):
    return re.sub(r"\s*[-–|·]\s*(São Paulo|SP|Ipiranga|Cambuci|Aclimação).*$", "", str(nome or "")).strip() or str(nome or "")

def preparar_loja(raiz, slug, ficha, loja_app=None):
    """monta (ou atualiza) os dados públicos da página da loja"""
    l = loja_captacao(raiz, slug) or {}
    la = loja_app or {}
    tel = re.sub(r"\D", "", str(l.get("tel") or la.get("tel") or ""))
    if tel.startswith("55") and len(tel) in (12, 13):
        tel = tel[2:]
    pub = {"slug": slug, "nome": _nome_loja(ficha.get("nome") or l.get("nome") or la.get("nome") or slug),
           "setor": l.get("setor") or la.get("setor") or ficha.get("setor") or "",
           "endereco": (l.get("endereco") or la.get("endereco") or "").split(" · ")[0],
           "tel": tel, "whats": len(tel) == 11 and tel[2] == "9",
           "place_id": l.get("place_id") or la.get("place_id") or "", "maps": l.get("maps") or la.get("maps") or "",
           "horario": l.get("horario") or la.get("horario") or "",
           "logo": _logo_publico(ficha, slug), "mostra": (ficha.get("mostra") or {}).get("token") or ""}
    return pub

# ---------- QR numerado ----------
def ativar(raiz, codigo, slug, ficha, loja_app, por):
    codigo = str(codigo or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"GA\d{4}", codigo):
        codigo = "GA-" + codigo[2:]
    if not CODIGO.match(codigo):
        raise ValueError("código do adesivo inválido (formato GA-0001)")
    DADOS.valida_slug(slug)
    with _lock:
        cods = _codigos()
        ja = cods.get(codigo)
        if ja and ja.get("slug") != slug:
            raise PermissionError(f"o adesivo {codigo} já está ligado a outra loja")
        cods[codigo] = {"slug": slug, "ativado": _agora(), "por": por}
        DADOS._escrever_json(os.path.join(PASTA, "codigos.json"), cods)
        est = ler(slug) or {"slug": slug, "criado": _agora(), "respostas": dict(RESPOSTAS_PADRAO), "conversas": {}, "aparelhos": {}}
        est["loja"] = preparar_loja(raiz, slug, ficha, loja_app)
        est["codigos"] = sorted(set((est.get("codigos") or []) + [codigo]))
        _gravar(slug, est)
    return {"codigo": codigo, "slug": slug, "pagina": f"/q.html?c={codigo}", "loja": est["loja"]}

def desativar(codigo, slug):
    with _lock:
        cods = _codigos()
        if (cods.get(codigo) or {}).get("slug") != slug:
            raise ValueError("este adesivo não é desta loja")
        cods.pop(codigo, None)
        DADOS._escrever_json(os.path.join(PASTA, "codigos.json"), cods)
        est = ler(slug)
        if est:
            est["codigos"] = [c for c in est.get("codigos") or [] if c != codigo]
            _gravar(slug, est)
    return {"ok": True}

def slug_do_codigo(codigo):
    return (_codigos().get(str(codigo or "").upper()) or {}).get("slug")

# ---------- encerramento e convite ----------
def _link_google(est):
    pid = (est.get("loja") or {}).get("place_id")
    return f"https://search.google.com/local/writereview?placeid={pid}" if pid else ""

def _encerrar(est, cv, motivo):
    if cv.get("estado") == "encerrada":
        return False
    cv["estado"] = "encerrada"; cv["motivo_fim"] = motivo; cv["encerrada_em"] = _agora()
    if not cv.get("convite"):
        cv["convite"] = _agora()
        cv["msgs"].append({"de": "sistema", "texto": CONVITE, "em": _agora(), "convite": True})
    return True

def _rever(est):
    """encerra as conversas cujo prazo passou (duas horas sem o cliente responder à loja)"""
    mudou = False; t = time.time()
    for cv in (est.get("conversas") or {}).values():
        if cv.get("estado") != "aberta" or not cv.get("msgs"):
            continue
        ult = cv["msgs"][-1]
        if ult.get("de") == "loja" and t - _ts(ult.get("em", "")) >= SILENCIO_FIM:
            mudou = _encerrar(est, cv, "tempo") or mudou
    return mudou

def _cv_pub(est, cv):
    return {"id": cv["id"], "assunto": cv.get("assunto"), "estado": cv.get("estado"), "criada": cv.get("criada"),
            "msgs": [{"de": m["de"], "texto": m["texto"], "em": m["em"], "convite": bool(m.get("convite"))} for m in cv.get("msgs", [])],
            "google": _link_google(est) if cv.get("convite") else ""}

# ---------- lado do cliente da loja (página pública) ----------
def pagina(codigo, tok):
    slug = slug_do_codigo(codigo)
    if not slug:
        return {"ativo": False, "codigo": codigo}
    with _lock:
        est = ler(slug) or {}
        if _rever(est):
            _gravar(slug, est)
        cv = None
        if tok:
            ap = (est.get("aparelhos") or {}).get(_h(tok))
            if ap and ap.get("conversas"):
                cv = (est.get("conversas") or {}).get(ap["conversas"][-1])
    L = est.get("loja") or {}
    cardapio = []
    tok_m = L.get("mostra")
    if not tok_m:   # o Mostraí pode ter sido ligado depois do adesivo
        try:
            tok_m = ((DADOS.cliente_ler(slug) or {}).get("mostra") or {}).get("token")
        except Exception:
            tok_m = None
    if tok_m:
        try:
            import mostra as MOSTRA
            m = MOSTRA.ler(tok_m) or {}
            telas = m.get("telas") or [{"itens": m.get("itens") or []}]
            for t in telas:
                its = [{"nome": i["nome"], "preco": i.get("preco", ""), "desc": i.get("desc", ""), "apartir": i.get("apartir", False)}
                       for i in t.get("itens", []) if i.get("ativo", True) and (i.get("nome") or "").strip()]
                if its:
                    cardapio.append({"titulo": t.get("titulo") or "", "itens": its})
            # só mostra cardápio que a loja programou de verdade (com preço); itens de partida sem preço não entram
            if not any((i.get("preco") or "").strip() for g in cardapio for i in g["itens"]):
                cardapio = []
        except Exception:
            cardapio = []
    return {"ativo": True, "codigo": codigo, "assuntos": ASSUNTOS,
            "loja": {k: L.get(k) for k in ("nome", "setor", "endereco", "tel", "whats", "maps", "horario", "logo")},
            "cardapio": cardapio, "conversa": _cv_pub(est, cv) if cv else None}

def registrar_visita(codigo, tok):
    """o mesmo aparelho lendo o QR em outro dia = o cliente voltou à loja"""
    slug = slug_do_codigo(codigo)
    if not slug or not tok:
        return
    with _lock:
        est = ler(slug)
        if not est:
            return
        ap = est.setdefault("aparelhos", {}).setdefault(_h(tok), {"visitas": [], "conversas": []})
        hoje = time.strftime("%Y-%m-%d")
        if hoje not in ap["visitas"]:
            ap["visitas"] = (ap["visitas"] + [hoje])[-60:]
            _gravar(slug, est)

def cliente_escrever(codigo, tok, d):
    slug = slug_do_codigo(codigo)
    if not slug:
        raise FileNotFoundError
    texto = str(d.get("texto") or "").strip()[:1500]
    if not texto:
        raise ValueError("escreva a sua mensagem")
    with _lock:
        est = ler(slug)
        ap = est.setdefault("aparelhos", {}).setdefault(_h(tok), {"visitas": [time.strftime("%Y-%m-%d")], "conversas": []})
        cv = est["conversas"].get(ap["conversas"][-1]) if ap["conversas"] else None
        if cv is None or d.get("nova"):
            assunto = d.get("assunto") if d.get("assunto") in ASSUNTOS else "duvida"
            cid = "c" + secrets.token_hex(5)
            cv = {"id": cid, "assunto": assunto, "nome": str(d.get("nome") or "").strip()[:40], "criada": _agora(), "estado": "aberta",
                  "msgs": [{"de": "cliente", "texto": texto, "em": _agora()}], "lida_loja": False, "aparelho": _h(tok)}
            est["conversas"][cid] = cv; ap["conversas"].append(cid)
            # resposta pronta da loja, na hora
            cv["msgs"].append({"de": "loja", "texto": (est.get("respostas") or RESPOSTAS_PADRAO).get(assunto) or RESPOSTAS_PADRAO[assunto],
                               "em": _agora(), "auto": True})
            if assunto == "elogio":
                _encerrar(est, cv, "elogio")
        else:
            cv["msgs"].append({"de": "cliente", "texto": texto, "em": _agora()})
            cv["lida_loja"] = False
            if cv.get("estado") == "encerrada":   # o relacionamento continua: a conversa reabre
                cv["estado"] = "aberta"; cv["reaberta"] = _agora()
        _gravar(slug, est)
        return _cv_pub(est, cv)

def cliente_encerrar(codigo, tok):
    slug = slug_do_codigo(codigo)
    if not slug:
        raise FileNotFoundError
    with _lock:
        est = ler(slug)
        ap = (est.get("aparelhos") or {}).get(_h(tok)) or {}
        cv = est["conversas"].get((ap.get("conversas") or [None])[-1])
        if not cv:
            raise ValueError("não há conversa aberta")
        _encerrar(est, cv, "cliente"); _gravar(slug, est)
        return _cv_pub(est, cv)

# ---------- lado da loja (painel do cliente, com telefone + código) ----------
def painel(slug):
    with _lock:
        est = ler(slug)
        if not est:
            return {"ativo": False}
        if _rever(est):
            _gravar(slug, est)
    convs = sorted((est.get("conversas") or {}).values(), key=lambda c: (c.get("estado") != "aberta", -(_ts(c["msgs"][-1]["em"]) if c.get("msgs") else 0)))
    aps = est.get("aparelhos") or {}
    mes = time.strftime("%Y-%m")
    lista = []
    for c in convs[:200]:
        ap = aps.get(c.get("aparelho")) or {}
        lista.append({"id": c["id"], "assunto": c.get("assunto"), "nome": c.get("nome") or "", "estado": c.get("estado"), "criada": c.get("criada"),
                      "motivo_fim": c.get("motivo_fim"), "lida": c.get("lida_loja", True), "excelencia": bool(c.get("excelencia")),
                      "visitas": len(ap.get("visitas") or []), "msgs": c.get("msgs", [])})
    ind = {"abertas": sum(1 for c in convs if c.get("estado") == "aberta"),
           "mes": sum(1 for c in convs if (c.get("criada") or "").startswith(mes)),
           "voltaram": sum(1 for a in aps.values() if len(a.get("visitas") or []) > 1),
           "por_assunto": {k: sum(1 for c in convs if c.get("assunto") == k and (c.get("criada") or "").startswith(mes)) for k in ASSUNTOS}}
    return {"ativo": True, "assuntos": ASSUNTOS, "respostas": est.get("respostas") or RESPOSTAS_PADRAO, "conversas": lista, "indicadores": ind,
            "codigos": est.get("codigos") or [], "google": bool((est.get("loja") or {}).get("place_id"))}

def loja_responder(slug, cid, texto, por):
    texto = str(texto or "").strip()[:1500]
    if not texto:
        raise ValueError("escreva a resposta")
    with _lock:
        est = ler(slug); cv = (est or {}).get("conversas", {}).get(cid)
        if not cv:
            raise FileNotFoundError
        cv["msgs"].append({"de": "loja", "texto": texto, "em": _agora(), "por": por})
        cv["lida_loja"] = True
        _gravar(slug, est)
        return {"ok": True}

def loja_marcar(slug, cid, acao):
    with _lock:
        est = ler(slug); cv = (est or {}).get("conversas", {}).get(cid)
        if not cv:
            raise FileNotFoundError
        if acao == "resolvido":
            _encerrar(est, cv, "resolvido")
        elif acao == "lida":
            cv["lida_loja"] = True
        elif acao == "excelencia":
            cv["excelencia"] = not cv.get("excelencia")
        else:
            raise ValueError("ação inválida")
        _gravar(slug, est)
        return {"ok": True}

def loja_respostas(slug, d):
    with _lock:
        est = ler(slug)
        if not est:
            raise FileNotFoundError
        r = dict(est.get("respostas") or RESPOSTAS_PADRAO)
        for k in ASSUNTOS:
            if isinstance(d.get(k), str) and d[k].strip():
                r[k] = d[k].strip()[:400]
        est["respostas"] = r; _gravar(slug, est)
        return r

def logo(slug, nome):
    DADOS.valida_slug(slug)
    if not re.match(r"^logo\.[a-z0-9]{1,5}$", nome or ""):
        raise ValueError("caminho inválido")
    ext = nome.rsplit(".", 1)[1]
    mime = {v: k for k, v in DADOS.EXT.items()}.get(ext, "application/octet-stream")
    with open(os.path.join(PASTA, slug, nome), "rb") as f:
        return mime, f.read()

def resumo_vendedor(slug):
    """o que o vendedor vê na loja: adesivos ligados e números do relacionamento"""
    est = ler(slug)
    if not est:
        return {"codigos": []}
    p = painel(slug)
    return {"codigos": est.get("codigos") or [], "indicadores": p.get("indicadores"), "google": p.get("google")}
