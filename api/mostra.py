"""GênIO · Mostra Aí — tela (TV Box / celular) + programação (painel do cliente), tudo no servidor.

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

# itens de partida por setor (sem preço: o cliente preenche na programação)
EXEMPLOS = {
    "padaria": ["Pão francês", "Pão de queijo", "Croissant", "Bolo do dia", "Café coado", "Pão na chapa + café"],
    "restaurante": ["Prato do dia", "Executivo", "Marmitex", "Salada", "Sobremesa", "Suco natural"],
    "bar": ["Chope", "Cerveja long neck", "Caipirinha", "Porção de fritas", "Porção da casa", "Refrigerante"],
    "cafeteria": ["Expresso", "Cappuccino", "Café coado", "Pão de queijo", "Bolo da casa", "Chocolate quente"],
    "salão/barbearia": ["Corte", "Barba", "Corte + barba", "Escova", "Coloração", "Manicure"],
    "pet": ["Banho", "Banho e tosa", "Tosa higiênica", "Corte de unhas", "Hidratação", "Ração (kg)"],
    "clínica/consultório": ["Consulta", "Retorno", "Avaliação", "Procedimento", "Exame", "Pacote"],
    "academia/estúdio": ["Plano mensal", "Plano trimestral", "Plano anual", "Aula avulsa", "Personal (hora)", "Avaliação física"],
    "ótica": ["Armação", "Óculos de sol", "Lente simples", "Lente multifocal", "Lente de contato", "Ajuste e limpeza"],
    "mercado/hortifruti": ["Oferta do dia", "Frutas (kg)", "Verduras", "Carnes (kg)", "Ovos (dúzia)", "Pão"],
    "cereais/empório": ["Arroz (kg)", "Feijão (kg)", "Castanhas (100 g)", "Temperos (100 g)", "Farinhas (kg)", "Café (250 g)"],
}
PADRAO_EXEMPLOS = ["Item 1", "Item 2", "Item 3", "Item 4"]

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
    """copia o logotipo tratado (ou o primeiro salvo) da ficha para a pasta pública do Mostra Aí"""
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
    """cria (ou devolve) o Mostra Aí da loja; o token fica na ficha (ficha['mostra'])"""
    tok = (ficha.get("mostra") or {}).get("token")
    est = ler(tok) if tok and TOKEN.match(tok) else None
    if not est:
        tok = "".join(secrets.choice(ALFA) for _ in range(10))
        setor = (loja or {}).get("setor") or ficha.get("setor") or "comércio"
        exemplos = EXEMPLOS.get(setor) or EXEMPLOS.get(setor.split("/")[0]) or PADRAO_EXEMPLOS
        cores = [c.get("hex") for c in ((ficha.get("manual") or {}).get("cores") or []) if c.get("hex")]
        est = {"token": tok, "slug": slug, "nome": ficha.get("nome") or (loja or {}).get("nome") or slug, "setor": setor,
               "titulo": "Cardápio" if setor in ("padaria", "restaurante", "bar", "cafeteria") else "Nossos serviços",
               "aviso": "", "cores": cores[:4], "logo": None, "v": 1, "criado": time.strftime("%Y-%m-%dT%H:%M:%S"), "por": por,
               "itens": [{"id": f"i{i+1}", "nome": n, "preco": "", "destaque": i == 0, "ativo": True} for i, n in enumerate(exemplos)]}
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
                          "desc": str(it.get("desc") or "")[:90], "destaque": bool(it.get("destaque")), "ativo": it.get("ativo", True) is not False})
        est["itens"] = itens
    for k, n in (("titulo", 40), ("aviso", 140)):
        if k in mud:
            est[k] = str(mud[k] or "")[:n]
    if isinstance(mud.get("tema"), str) and mud["tema"] in ("claro", "escuro", "auto"):
        est["tema"] = mud["tema"]
    est["v"] = int(est.get("v") or 1) + 1; est["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _escrever(token, est)
    return est

def logo(token, nome):
    if not TOKEN.match(token or "") or not re.match(r"^logo\.[a-z0-9]{1,5}$", nome or ""):
        raise ValueError("caminho inválido")
    ext = nome.rsplit(".", 1)[1]
    mime = {v: k for k, v in DADOS.EXT.items()}.get(ext, "application/octet-stream")
    with open(os.path.join(PASTA, token, nome), "rb") as f:
        return mime, f.read()
