import json,re,sys,math,glob
# junta resultados do Google Places de um centro, tira franquias/redes, ordena como roteiro de ida e volta e propõe setor + produtos
FRANQ=re.compile(r"\b(drogasil|droga ?raia|drogaria s[aã]o paulo|pague menos|ultrafarma|drogal|nissei|panvel|mcdonald|burger king|subway|habib|starbucks|cacau show|kopenhagen|brasil cacau|botic[aá]rio|natura|petz|cobasi|petlove|smart ?fit|bluefit|bio ?ritmo|magazine luiza|casas bahia|renner|riachuelo|c&a|americanas|[oó]ticas? (carol|diniz)|chilli beans|havaianas|spoleto|china in box|domino|pizza hut|giraffas|bob's|outback|oakberry|bradesco|ita[uú]|santander|caixa econ|banco do brasil|correios|lot[eé]rica|kumon|wizard|fisk|ccaa|\bcna\b|yes idiomas|carrefour|p[aã]o de a[çc][uú]car|assa[ií]|hirota|sonda|swift|vivara|hering|lupo|centauro|leroy|telhanorte|kfc|popeyes|rei do mate|casa do p[aã]o de queijo|chiquinho|yogoberry|kalunga|pernambucanas|marisa|zara|arezzo|melissa|ri happy|pbkids|pure pilates|resolv sa[uú]de|oral ?sin|sulminas|odontocompany|sorridents|wiz|cvc|localiza|movida|vivo|claro|tim|oi\b|unidas|ipiranga posto|shell|br mania|am ?pm|oxxo|mercado dia|dia %|extra|minuto p[aã]o|sodi[eê]|the body shop|quem disse|cia ?athletica|hortifruti|oba\b|st ?marche|natural da terra|y[aá]zigi|red balloon|kidstok|brandili|ecc english|cultura inglesa|minds|wise up|skill|microlins|prepara|oral ?unic|odontoclinic|sorriso|uniodonto|amor sa[uú]de|dr\.? ?consulta|clube de autores)\b",re.I)
SETOR=[("padaria",["bakery","confectionery","pastry","cake","candy","dessert"]),("restaurante",["restaurant","snack","diner","hamburger","fast_food","pizza","food"]),("bar",["bar","pub","night_club"]),("cafeteria",["cafe","coffee"]),
 ("salão/barbearia",["barber","hair","beauty","nail","spa","massage"]),("pet",["pet","veterinary"]),("clínica/consultório",["dentist","dental","doctor","medical","physio","health"]),("academia/estúdio",["gym","fitness","pilates","yoga"]),
 ("ótica",["optician","eyewear","ÓTICA","otica"]),("loja de roupas/calçados",["clothing","shoe","fashion","apparel"]),("floricultura/presentes",["florist","gift","home_goods","toy","stationery","furniture"]),("mercado/hortifruti",["grocery","supermarket","butcher","market","convenience","liquor"]),
 ("celular/assistência",["electronics","cell_phone","phone","repair"]),("escritório/imobiliária",["real_estate","accounting","lawyer","insurance","finance"]),("escola/curso",["school","language","education","tutor","child_care"])]
PROD={"padaria":"capacho · adesivo de vitrine · cardápio de parede","restaurante":"capacho · cardápio de parede · Mostraí","bar":"capacho · cardápio · banner","cafeteria":"capacho · cardápio de parede · Mostraí","salão/barbearia":"capacho · adesivo de vitrine · cartões","pet":"capacho · placa · adesivo de vitrine","clínica/consultório":"placa de recepção · cartões · capacho","academia/estúdio":"placa · adesivo de parede · uniformes","ótica":"adesivo de vitrine · placa · cartões","loja de roupas/calçados":"adesivo de vitrine · banner · capacho","floricultura/presentes":"adesivo de vitrine · cartões · capacho","mercado/hortifruti":"banner · placa · capacho","celular/assistência":"adesivo de vitrine · placa · cartões","escritório/imobiliária":"placa de recepção · cartões · capacho","escola/curso":"placa · adesivo de parede · uniformes","comércio":"capacho · placa · cartões"}
def setor(p):
    t=(" ".join(p.get("types",[]))+" "+p["name"]).lower()
    # nome manda primeiro (barbearia, ótica, pilates, academia), depois os tipos do Google
    for pal,s in [("barbear","salão/barbearia"),("barber","salão/barbearia"),("salão","salão/barbearia"),("salao","salão/barbearia"),("cabele","salão/barbearia"),("ótica","ótica"),("otica","ótica"),("pilates","academia/estúdio"),("academia","academia/estúdio"),("crossfit","academia/estúdio"),("studio","academia/estúdio"),("pet","pet"),("odonto","clínica/consultório"),("clínica","clínica/consultório"),("clinica","clínica/consultório"),("padaria","padaria"),("panific","padaria"),("confeit","padaria"),("doceria","padaria"),("cafeteria","cafeteria"),("café","cafeteria"),("floric","floricultura/presentes"),("flores","floricultura/presentes"),("papelaria","floricultura/presentes"),("imobili","escritório/imobiliária"),("contab","escritório/imobiliária"),("escola","escola/curso"),("colégio","escola/curso"),("colegio","escola/curso"),("idiomas","escola/curso"),("celular","celular/assistência"),("assist","celular/assistência"),("lanch","restaurante"),("restaur","restaurante"),("pizza","restaurante"),("bar ","bar"),("boteco","bar"),("modas","loja de roupas/calçados"),("calçad","loja de roupas/calçados")]:
        if pal in p["name"].lower(): return s
    for s,ks in SETOR:
        if any(k.lower() in t for k in ks): return s
    return "comércio"
def num(addr):
    m=re.search(r",\s*(\d+)",addr or ""); return int(m.group(1)) if m else 0
def rua(addr):
    return (addr or "").split(",")[0].strip()
def montar(nome,arqs,eixo,base):
    seen={};
    for a in arqs:
        for p in json.load(open(a))["places"]:
            if p["place_id"] in seen or FRANQ.search(p["name"]): continue
            d=math.hypot((p["latitude"]-base[0])*111,(p["longitude"]-base[1])*102)
            if d>2.2: continue
            seen[p["place_id"]]=p
    L=[]
    for p in seen.values():
        s=setor(p);L.append({"nome":p["name"],"setor":s,"rua":rua(p.get("address")),"numero":num(p.get("address")),"endereco":(p.get("address") or "").split(" - ")[0],"tel":p.get("phone_number",""),"lat":p["latitude"],"lng":p["longitude"],"nota":p.get("rating"),"aval":p.get("rating_count"),"produtos":PROD[s],"place_id":p["place_id"]})
    # roteiro: escolhe as 50 mais perto do eixo/base e monta um caminho de vizinho mais próximo saindo da base;
    # as 25 primeiras são o dia 1 (ida), as 25 seguintes o dia 2 (volta) — o caminho fecha perto de onde começou
    def km(a,b):return math.hypot((a[0]-b[0])*111,(a[1]-b[1])*102)
    for x in L:x["_d"]=km((x["lat"],x["lng"]),base)-(0.6 if any(e.lower() in x["rua"].lower() for e in eixo) else 0)
    cand=sorted(L,key=lambda x:x["_d"])[:50];resto=[x for x in L if x not in cand]
    rota=[];cur=base;pool=cand[:]
    while pool:
        nx=min(pool,key=lambda x:km((x["lat"],x["lng"]),cur));pool.remove(nx);rota.append(nx);cur=(nx["lat"],nx["lng"])
    half=(len(rota)+1)//2;dia1=rota[:half];dia2=rota[half:]
    for i,x in enumerate(dia1):x["dia"]=1;x["ordem"]=i+1
    for i,x in enumerate(dia2):x["dia"]=2;x["ordem"]=i+1
    for x in resto:x["dia"]=0;x["ordem"]=0
    for x in L:x.pop("_d",None)
    sobra=resto
    out={"centro":nome,"base":base,"lojas":dia1+dia2+sobra}
    json.dump(out,open(f"/tmp/claude-0/-home-claude/e28c1937-d9ee-5e6c-8c03-3286a94c4195/scratchpad/rotas/{nome}.json","w"),ensure_ascii=False,indent=0)
    print(nome,"lojas",len(L),"dia1",len(dia1),"dia2",len(dia2),"sobra",len(sobra));
    from collections import Counter;print(Counter(x["setor"] for x in L).most_common())
if __name__=="__main__":
    montar(sys.argv[1],sys.argv[4:],sys.argv[2].split("|"),tuple(map(float,sys.argv[3].split(","))))
