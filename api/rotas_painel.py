"""GênIO · painel de acompanhamento por rota (supervisor).

Só LÊ o que já está no servidor: as listas captadas (dados/captacao/<zona>/lojas.json), o estado do dia
(dados/estado/dia.json: visitas, orçamentos, pedidos, voltas), os adesivos e conversas da página da loja (relaciona)
e o dono de cada rota (estado "rotas-donos", que o administrador preenche no painel).
Cada vendedor tem o seu caderno do dia (estado/dia-u<id>.json); o painel soma todos e mostra quem fez o quê em cada rota.
"""
import json, os, time
import dados as DADOS

def _ler(arq):
    try:
        with open(arq, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _lojas(arq):
    d = _ler(arq)
    L = d if isinstance(d, list) else (d or {}).get("lojas") or []
    return [x for x in L if isinstance(x, dict) and x.get("slug")]

def _cadernos():
    """um caderno por vendedor (estado/dia-u<id>.json); o caderno antigo, único (dia.json), só entra se quem o escreveu ainda não tem o próprio"""
    pasta = os.path.join(DADOS.RAIZ_DADOS, "estado"); out = []
    for n in (sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []):
        if n.startswith("dia-u") and n.endswith(".json"):
            d = _ler(os.path.join(pasta, n)) or {}
            out.append({"nome": d.get("por") or n[4:-5], "e": d.get("valor") or {}, "atualizado": d.get("atualizado")})
    ant = _ler(os.path.join(pasta, "dia.json"))
    if ant and not any(c["nome"] == ant.get("por") for c in out):
        out.append({"nome": ant.get("por") or "caderno antigo", "e": ant.get("valor") or {}, "atualizado": ant.get("atualizado")})
    return out

def _conta(e, slugs, hoje):
    feitas = set(e.get("feitas") or []); atend = e.get("atend") or {}; sel = e.get("sel") or {}; ped = e.get("pedidos") or {}; voltas = e.get("voltas") or {}
    vis = {s for s in slugs if s in feitas or (atend.get(s) or {}).get("fim")}
    orc = {s for s in slugs if any((v or {}).get("q", 0) > 0 for v in (sel.get(s) or {}).values())}
    pds = {s for s in slugs if any(h.get("etapa") != "entrada" for h in ((ped.get(s) or {}).get("hist") or []))}
    ent = {s for s in pds if (ped.get(s) or {}).get("etapa") == "entregue"}
    receita = sum(float((ped.get(s) or {}).get("valor") or 0) for s in pds); mensal = 0.0
    for s in pds:
        for v in (sel.get(s) or {}).values():
            if v and v.get("q", 0) > 0 and v.get("servico") and v.get("mensal"):
                mensal += float(v["mensal"])
    vd = sorted(d for d in ((voltas.get(s) or {}).get("data") for s in slugs) if d)
    ult = max([((atend.get(s) or {}).get("fim") or "") for s in slugs] or [""])
    return {"vis": vis, "orc": orc, "pds": pds, "ent": ent, "receita": receita, "mensal": mensal, "voltas": vd, "ult": ult}

def painel(raiz):
    hoje = time.strftime("%Y-%m-%d")
    cad = _cadernos()
    donos = ((_ler(os.path.join(DADOS.RAIZ_DADOS, "estado", "rotas-donos.json")) or {}).get("valor")) or {}
    cods = _ler(os.path.join(DADOS.RAIZ_DADOS, "relaciona", "codigos.json")) or {}
    ades = {}
    for c in cods.values():
        if isinstance(c, dict) and c.get("slug"):
            ades[c["slug"]] = ades.get(c["slug"], 0) + 1
    base = os.path.join(raiz, "dados", "captacao"); rotas = []
    for z in (sorted(os.listdir(base)) if os.path.isdir(base) else []):
        L = _lojas(os.path.join(base, z, "lojas.json"))
        if not L:
            continue
        rec = _ler(os.path.join(raiz, "captacao", "zonas", z + ".json")) or _ler(os.path.join("/var/lib/genio/captacao/zonas", z + ".json")) or {}
        slugs = [x["slug"] for x in L]
        vis, orc, pds, ent, voltas = set(), set(), set(), set(), []; receita = mensal = 0.0; ult = ""; vend = []
        for c in cad:
            r = _conta(c["e"], slugs, hoje)
            vis |= r["vis"]; orc |= r["orc"]; pds |= r["pds"]; ent |= r["ent"]; voltas += r["voltas"]; receita += r["receita"]; mensal += r["mensal"]; ult = max(ult, r["ult"])
            if r["vis"] or r["orc"] or r["pds"]:
                vend.append({"nome": c["nome"], "visitadas": len(r["vis"]), "orcamentos": len(r["orc"]), "pedidos": len(r["pds"]), "receita": round(r["receita"], 2), "mensal": round(r["mensal"], 2)})
        conv = 0; abertas = 0
        for s in slugs:
            if s in ades:
                rr = _ler(os.path.join(DADOS.RAIZ_DADOS, "relaciona", s + ".json")) or {}
                cv = rr.get("conversas") or []
                cv = list(cv.values()) if isinstance(cv, dict) else cv
                conv += len(cv); abertas += sum(1 for x in cv if isinstance(x, dict) and x.get("estado") != "encerrada")
        voltas.sort()
        rotas.append({"zona": z, "nome": (rec.get("nome") or z).split(" (")[0], "bairro": rec.get("bairro") or "", "dono": donos.get(z) or "",
                      "lojas": len(slugs), "visitadas": len(vis), "orcamentos": len(orc), "pedidos": len(pds), "entregues": len(ent),
                      "entregas_pendentes": len(pds) - len(ent), "receita": round(receita, 2), "mensal": round(mensal, 2),
                      "adesivos": sum(1 for s in slugs if s in ades), "conversas": conv, "conversas_abertas": abertas,
                      "voltas_vencidas": sum(1 for d in voltas if d < hoje), "proxima_volta": next((d for d in voltas if d >= hoje), None),
                      "ultima_visita": ult[:16] or None, "vendedores": sorted(vend, key=lambda v: -v["visitadas"])})
    return {"hoje": hoje, "rotas": rotas, "cadernos": [{"nome": c["nome"], "atualizado": c["atualizado"]} for c in cad], "estado_unico": False}
