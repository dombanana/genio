"""GênIO · painel de acompanhamento por rota (supervisor).

Só LÊ o que já está no servidor: as listas captadas (dados/captacao/<zona>/lojas.json), o estado do dia
(dados/estado/dia.json: visitas, orçamentos, pedidos, voltas), os adesivos e conversas da página da loja (relaciona)
e o dono de cada rota (estado "rotas-donos", que o administrador preenche no painel).
Hoje o estado do dia é um só para todos os vendedores: enquanto for assim, os números são da equipe inteira, não por pessoa.
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

def painel(raiz):
    hoje = time.strftime("%Y-%m-%d")
    est = (_ler(os.path.join(DADOS.RAIZ_DADOS, "estado", "dia.json")) or {})
    e = est.get("valor") or {}
    donos = ((_ler(os.path.join(DADOS.RAIZ_DADOS, "estado", "rotas-donos.json")) or {}).get("valor")) or {}
    feitas = set(e.get("feitas") or [])
    atend = e.get("atend") or {}; sel = e.get("sel") or {}; ped = e.get("pedidos") or {}; voltas = e.get("voltas") or {}
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
        rec = _ler(os.path.join(raiz, "captacao", "zonas", z + ".json")) or {}
        slugs = [x["slug"] for x in L]
        vis = [s for s in slugs if s in feitas or (atend.get(s) or {}).get("fim")]
        orc = [s for s in slugs if any((v or {}).get("q", 0) > 0 for v in (sel.get(s) or {}).values())]
        pds = [s for s in slugs if any(h.get("etapa") != "entrada" for h in ((ped.get(s) or {}).get("hist") or []))]
        entregues = [s for s in pds if (ped.get(s) or {}).get("etapa") == "entregue"]
        receita = sum(float((ped.get(s) or {}).get("valor") or 0) for s in pds)
        mensal = 0.0
        for s in pds:
            for v in (sel.get(s) or {}).values():
                if v and v.get("q", 0) > 0 and v.get("servico") and v.get("mensal"):
                    mensal += float(v["mensal"])
        conv = 0; abertas = 0
        for s in slugs:
            if s in ades:
                r = _ler(os.path.join(DADOS.RAIZ_DADOS, "relaciona", s + ".json")) or {}
                cv = r.get("conversas") or []
                cv = list(cv.values()) if isinstance(cv, dict) else cv
                conv += len(cv); abertas += sum(1 for x in cv if isinstance(x, dict) and x.get("estado") != "encerrada")
        vd = [(voltas.get(s) or {}).get("data") for s in slugs]; vd = sorted(d for d in vd if d)
        ult = [((atend.get(s) or {}).get("fim") or "") for s in slugs]; ult = max(ult) if ult else ""
        rotas.append({"zona": z, "nome": rec.get("nome") or z, "bairro": rec.get("bairro") or "", "dono": donos.get(z) or "",
                      "lojas": len(slugs), "visitadas": len(vis), "orcamentos": len(orc), "pedidos": len(pds), "entregues": len(entregues),
                      "entregas_pendentes": len(pds) - len(entregues), "receita": round(receita, 2), "mensal": round(mensal, 2),
                      "adesivos": sum(1 for s in slugs if s in ades), "conversas": conv, "conversas_abertas": abertas,
                      "voltas_vencidas": sum(1 for d in vd if d < hoje), "proxima_volta": next((d for d in vd if d >= hoje), None),
                      "ultima_visita": ult[:16] or None})
    return {"hoje": hoje, "rotas": rotas, "estado_atualizado": est.get("atualizado"), "estado_por": est.get("por"),
            "estado_unico": True, "receitas_na_fila": sorted(f[:-5] for f in os.listdir(os.path.join(raiz, "captacao", "zonas")) if f.endswith(".json")) if os.path.isdir(os.path.join(raiz, "captacao", "zonas")) else []}
