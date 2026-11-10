#!/usr/bin/env python3
"""Calibração dos kits de 14 setores a partir dos pares COM_ARTE/SEM_ARTE.
A diferença entre as duas fotos marca exatamente onde a arte de demonstração foi aplicada; o quadrilátero
dessa região é o plano de impressão. Saída: calibracao.json por setor, no formato que api/kits/aplicar.py lê.
Uso: calibrar14.py <pasta GenIO_Kits_14_Setores> <saida> [--debug pasta]"""
import json, os, sys, hashlib
import numpy as np, cv2

ORDEM = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16"]
# regras por produto (Guia + REGRAS_MONTAGEM): como a arte entra naquela superfície
REGRA = {
    "01": dict(produto="Capacho", superficie="fibra", material_recolor=True, aplicacao="impressao_total", fundo_arte="cor_material", borda_px=14, margem=0.06),
    "02": dict(produto="Placa", superficie="rigida", material_recolor=True, aplicacao="impressao_total", oclusoes="parafusos"),
    "03": dict(produto="Adesivo de vitrine", superficie="vidro", material_recolor=False, aplicacao="vinil_recortado"),
    "04": dict(produto="Uniforme polo", superficie="tecido", material_recolor=False, aplicacao="bordado_peito"),
    "05": dict(produto="Cartão de visita", superficie="papel", material_recolor=False, aplicacao="impressao_total"),
    "06": dict(produto="Flyer", superficie="papel", material_recolor=False, aplicacao="impressao_total"),
    "07": dict(produto="Banner retrátil", superficie="lona", material_recolor=False, aplicacao="impressao_total", ancora="topo"),
    "08": dict(produto="Adesivo de parede", superficie="parede", material_recolor=False, aplicacao="vinil_recortado"),
    "09": dict(produto="Ecobag", superficie="tecido", material_recolor=False, aplicacao="serigrafia"),
    "10": dict(produto="Papéis carimbados", superficie="papel", material_recolor=False, aplicacao="impressao_carimbo"),
    "11": dict(produto="Wind banner", superficie="tecido", material_recolor=True, aplicacao="impressao_total", fundo_arte="cor_material"),
    "12": dict(produto="Faixa horizontal", superficie="lona", material_recolor=False, aplicacao="impressao_total"),
    "13": dict(produto="Folheto promocional", superficie="papel", material_recolor=False, aplicacao="impressao_total"),
    "14": dict(produto="Camiseta", superficie="tecido", material_recolor=False, aplicacao="serigrafia"),
    "15": dict(produto="Boné", superficie="tecido", material_recolor=False, aplicacao="bordado_peito"),
    "16": dict(produto="Avental", superficie="tecido", material_recolor=False, aplicacao="serigrafia"),
}
# produtos em que a diferença é a arte inteira (plano = região toda) × produtos em que só o logotipo difere (plano = caixa do logo)
QUAD = {"01", "02", "05", "06", "07", "11", "12", "13"}  # 03 e 08 (vinil) usam caixa; têxteis usam caixa do logotipo

def ordenar(pts):
    pts = np.array(pts, np.float32); c = pts.mean(0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0]); o = pts[np.argsort(ang)]   # sentido horário na imagem (y para baixo)
    i0 = int(np.argmin(o.sum(1)))                                                    # começa no canto mais perto do topo-esquerdo
    return np.roll(o, -i0, axis=0)

def alinhar(a, b):
    """pares que saíram deslocados: desloca COM para casar com SEM (correlação de fase)"""
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32); gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), resp = cv2.phaseCorrelate(gb, ga)
    if abs(dx) < 1.5 and abs(dy) < 1.5:
        return a, (0, 0)
    if abs(dx) > 120 or abs(dy) > 120:
        return a, None
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    return cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), borderMode=cv2.BORDER_REPLICATE), (round(dx, 1), round(dy, 1))

def mascara_diff(a, b, lim=18, fecha=25):
    ga = cv2.GaussianBlur(a, (5, 5), 0).astype(np.int16); gb = cv2.GaussianBlur(b, (5, 5), 0).astype(np.int16)
    d = np.abs(ga - gb).max(2).astype(np.uint8)
    m = (d > lim).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((fecha, fecha), np.uint8))
    return m

def maior_regiao(m, minimo=0.002):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    H, W = m.shape; areas = st[1:, cv2.CC_STAT_AREA]; i = 1 + int(np.argmax(areas))
    if areas.max() < H * W * minimo:
        return None
    # junta regiões grandes vizinhas (arte em várias peças: título + lista) → envelope convexo
    grandes = [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > areas.max() * 0.08]
    sel = np.isin(lab, grandes).astype(np.uint8) * 255
    return sel

def quad_de(mask, modo):
    pts = cv2.findNonZero(mask)
    if pts is None:
        return None
    hull = cv2.convexHull(pts)
    if modo == "quad":
        peri = cv2.arcLength(hull, True)
        for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
            ap = cv2.approxPolyDP(hull, eps * peri, True)
            if len(ap) == 4:
                return ordenar(ap.reshape(-1, 2)), "quadrilatero"
        r = cv2.minAreaRect(hull); return ordenar(cv2.boxPoints(r)), "retangulo_minimo"
    x, y, w, h = cv2.boundingRect(hull)
    return ordenar([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]), "caixa"

SUPERF = {"01", "05", "06", "07", "11", "12", "13"}   # arte cobre a superfície inteira: refina pela cor da própria superfície na foto neutra

def refinar_superficie(sem, reg, pid):
    """COM e SEM foram geradas em separado: sombra, folhagem e reflexo mudam fora do produto. A superfície do produto tem
    cor uniforme na foto neutra: semente = mediana da cor no miolo da diferença; máscara = pixels parecidos, ligados ao miolo."""
    H, W = sem.shape[:2]
    miolo = cv2.erode(reg, np.ones((31, 31), np.uint8))
    if cv2.countNonZero(miolo) < 500:
        miolo = cv2.erode(reg, np.ones((11, 11), np.uint8))
    if cv2.countNonZero(miolo) < 200:
        return None
    lab = cv2.cvtColor(cv2.GaussianBlur(sem, (7, 7), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    semente = np.median(lab[miolo > 0], axis=0)
    d = np.linalg.norm(lab - semente, axis=2); areg = cv2.countNonZero(reg) / (H * W)
    for tol in (14, 18, 24):
        m = (d < tol).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
        n, cc, st, _ = cv2.connectedComponentsWithStats(m)
        ids = set(np.unique(cc[miolo > 0])) - {0}
        if not ids:
            continue
        i = max(ids, key=lambda k: st[k, cv2.CC_STAT_AREA])
        sup = (cc == i).astype(np.uint8) * 255
        ab = cv2.morphologyEx(sup, cv2.MORPH_OPEN, np.ones((41, 41), np.uint8))   # corta vazamentos finos (rejunte, sombra)
        n2, cc2, st2, _ = cv2.connectedComponentsWithStats(ab)
        if n2 > 1:
            sup = (cc2 == 1 + int(np.argmax(st2[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255
        a = cv2.countNonZero(sup) / (H * W)
        if a < areg * 0.3 or a > 0.7:
            continue
        x, y, w, h = cv2.boundingRect(sup)
        if w >= W - 4 and h >= H - 4:   # vazou para o fundo
            continue
        return sup
    return None

def calibrar_par(com_p, sem_p, pid):
    com = cv2.imread(com_p); sem = cv2.imread(sem_p)
    if com is None or sem is None or com.shape != sem.shape:
        return None, "par inválido"
    H, W = sem.shape[:2]; textil = pid in {"04", "09", "14", "15", "16"}
    com2, desloc = alinhar(com, sem)
    tentativas = []
    for lim, fecha in ((18, 25), (12, 25), (8, 17), (28, 25), (40, 25)):
        m = mascara_diff(com2, sem, lim, fecha); reg = maior_regiao(m, 0.0008)
        if reg is None:
            continue
        q, como = quad_de(reg, "quad" if pid in QUAD else "caixa")
        area = float(cv2.contourArea(q.astype(np.float32))) / (H * W)
        cheio = float((reg > 0).mean())
        tentativas.append((lim, q, como, area, cheio))
        ok = (0.0008 <= area <= (0.12 if textil else 0.8)) and (cheio / max(area, 1e-6) > (0.45 if pid in QUAD else 0.25))  # região compacta, não a foto inteira
        if ok and pid in SUPERF:
            sup = refinar_superficie(sem, reg, pid)
            if sup is not None:
                q2, como2 = quad_de(sup, "quad"); a2 = float(cv2.contourArea(q2.astype(np.float32))) / (H * W)
                return {"plano": [[int(round(x)), int(round(y))] for x, y in q2], "modo": como2 + "+superficie", "area_rel": round(a2, 4), "px": [W, H], "limiar": lim, "deslocamento": desloc, "qualidade": "ok"}, None
        if ok:
            return {"plano": [[int(round(x)), int(round(y))] for x, y in q], "modo": como, "area_rel": round(area, 4), "px": [W, H], "limiar": lim, "deslocamento": desloc, "qualidade": "ok"}, None
    if tentativas:
        lim, q, como, area, cheio = min(tentativas, key=lambda t: abs(t[3] - (0.03 if textil else 0.25)))
        return {"plano": [[int(round(x)), int(round(y))] for x, y in q], "modo": como, "area_rel": round(area, 4), "px": [W, H], "limiar": lim, "deslocamento": desloc, "qualidade": "duvidosa"}, None
    return None, "sem diferença"

def main():
    raiz, saida = sys.argv[1], sys.argv[2]; debug = None
    if "--debug" in sys.argv:
        debug = sys.argv[sys.argv.index("--debug") + 1]; os.makedirs(debug, exist_ok=True)
    reaprov = json.load(open(os.path.join(raiz, "REAPROVEITAMENTO.json"))).get("itens", {})
    setores = sorted(d for d in os.listdir(raiz) if d[:2].isdigit() and d != "00_Bases_Compartilhadas")
    resumo = {}
    for s in setores + ["00_Bases_Compartilhadas"]:
        pasta = os.path.join(raiz, s, "Fotos_Produtos") if s != "00_Bases_Compartilhadas" else os.path.join(raiz, s)
        cal = {"setor": s, "versao_kit": 2, "calibrado_em": "2026-11-10", "metodo": "diferença COM_ARTE×SEM_ARTE (medida nas fotos do kit, não estimada)", "unidade": "px na imagem original 1536x1024", "ordem_cantos": "topo-esq, topo-dir, inf-dir, inf-esq", "produtos": {}}
        for pid in ORDEM:
            nomes = [n for n in os.listdir(os.path.join(pasta, "SEM_ARTE")) if n.startswith(pid + "_")]
            if not nomes:
                continue
            arq = nomes[0]; sem_p = os.path.join(pasta, "SEM_ARTE", arq); com_p = os.path.join(pasta, "COM_ARTE", arq)
            if not os.path.exists(com_p):
                continue
            r, erro = calibrar_par(com_p, sem_p, pid)
            ent = dict(REGRA[pid]); ent.update({"arquivo": "SEM_ARTE/" + arq, "demo": "COM_ARTE/" + arq, "sha256_base": hashlib.sha256(open(sem_p, "rb").read()).hexdigest()})
            origem = reaprov.get(f"{s}_{pid}_{arq.split('_',1)[1].rsplit('.',1)[0]}") or reaprov.get(f"{s}_{arq.rsplit('.',1)[0]}")
            if origem:
                ent["origem"] = origem.get("setor_origem"); ent["modo_reaproveitamento"] = origem.get("modo")
            if r:
                ent.update(r)
            else:
                ent["erro"] = erro
            cal["produtos"][pid] = ent
            if debug and r:
                im = cv2.imread(sem_p); cv2.polylines(im, [np.array(r["plano"], np.int32)], True, (0, 0, 255), 4)
                for i, (x, y) in enumerate(r["plano"]):
                    cv2.putText(im, str(i), (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                cv2.imwrite(os.path.join(debug, f"{s}_{arq}"), cv2.resize(im, (768, 512)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        os.makedirs(os.path.join(saida, s), exist_ok=True)
        json.dump(cal, open(os.path.join(saida, s, "calibracao.json"), "w"), ensure_ascii=False, indent=1)
        resumo[s] = {pid: (p.get("modo"), p.get("area_rel")) if "plano" in p else p.get("erro") for pid, p in cal["produtos"].items()}
    json.dump(resumo, open(os.path.join(saida, "resumo_calibracao.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(resumo, ensure_ascii=False)[:3000])

if __name__ == "__main__":
    main()
