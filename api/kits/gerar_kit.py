#!/usr/bin/env python3
"""Gera, para um cliente da captação, as 10 capas do kit de ambiente com a marca dele aplicada.

Uso: gerar_kit.py <pasta_da_zona> <slug> [setor_do_kit]
Entrada: dados/captacao/<zona>/manual/<slug>/marca-cor.svg (saída do pipeline do manual) e relatorio.json (cores).
Saída:  dados/captacao/<zona>/kit/<slug>/<id>.jpg + index.json. Sem IA; determinístico; roda de novo só se a marca mudou.
"""
import json, os, subprocess, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aplicar

KITS = aplicar.KITS
VERSAO = "2"  # muda quando a rotina de aplicação muda → capas são refeitas na próxima rodada
MATERIAL_PADRAO = {"01": "#2B2B2D", "02": "#F4F1EA", "04": "#F4F1EA", "07": "#F4F1EA", "09": None, "05": None, "06": None}

def kit_para(setor):
    """Kit do setor; se ainda não existe, usa o de padaria como ambiente de referência (marcado no index)."""
    s = (setor or "").split("/")[0]
    if os.path.isdir(os.path.join(KITS, s)):
        return s, False
    return "padaria", True

def gerar(pasta_zona, slug, setor=None):
    man = os.path.join(pasta_zona, "manual", slug); svg = os.path.join(man, "marca-cor.svg")
    if not os.path.exists(svg):
        return {"erro": "sem marca-cor.svg (manual ainda não gerado)"}
    out = os.path.join(pasta_zona, "kit", slug); os.makedirs(out, exist_ok=True)
    h = hashlib.sha256(open(svg, "rb").read() + VERSAO.encode()).hexdigest()[:12]
    idx_p = os.path.join(out, "index.json")
    if os.path.exists(idx_p):
        try:
            if json.load(open(idx_p)).get("marca") == h:
                return json.load(open(idx_p))
        except Exception:
            pass
    arte = os.path.join(out, "_arte.png")
    subprocess.run(["rsvg-convert", "-w", "1400", svg, "-o", arte], check=True)
    # versão clara da marca para materiais escuros (capacho preto recebe arte clara — regra de produção)
    branca = None; svg_b = os.path.join(man, "marca-branca.svg")
    if os.path.exists(svg_b):
        branca = os.path.join(out, "_arte_branca.png"); subprocess.run(["rsvg-convert", "-w", "1400", svg_b, "-o", branca], check=True)
    cores = []
    try:
        cores = json.load(open(os.path.join(man, "relatorio.json"))).get("cores", [])
    except Exception:
        pass
    cor_arte = next((c["hex"] for c in sorted(cores, key=lambda c: -c.get("area", 0)) if c.get("hex", "#fff").lower() not in ("#ffffff", "#fff")), "#1C1635")
    kit, referencia = kit_para(setor)
    cal = json.load(open(os.path.join(KITS, kit, "calibracao.json")))
    itens = []
    for pid, P in cal["produtos"].items():
        dest = os.path.join(out, f"{pid}.jpg")
        try:
            mat = MATERIAL_PADRAO.get(pid); escuro = bool(mat) and sum(int(mat[i:i+2], 16) for i in (1, 3, 5)) < 3 * 110
            aplicar.aplicar(kit, pid, branca if (escuro and branca) else arte, dest, mat, cor_arte, 0.8 if pid == "07" else 0.7)
            itens.append({"id": pid, "produto": P["produto"], "arquivo": f"kit/{slug}/{pid}.jpg", "aplicacao": P.get("aplicacao")})
        except Exception as e:
            itens.append({"id": pid, "produto": P["produto"], "erro": str(e)[:200]})
    idx = {"slug": slug, "kit": kit, "ambiente_de_referencia": referencia, "marca": h, "cor_arte": cor_arte, "itens": itens}
    json.dump(idx, open(idx_p, "w"), ensure_ascii=False, indent=1)
    for f in (arte, branca):
        try:
            if f: os.remove(f)
        except Exception:
            pass
    return idx

if __name__ == "__main__":
    print(json.dumps(gerar(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None), ensure_ascii=False)[:600])
