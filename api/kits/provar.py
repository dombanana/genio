"""Provar a peça na foto (camiseta, polo, boné, avental), sem inteligência artificial:
1. recorte da peça pela cor, a partir de um ponto (toque do vendedor ou centro do peito), refinado com GrabCut;
2. troca de cor mantendo dobras e sombras (mesma luz da foto, só o tom muda);
3. posição da logo pelas medidas da própria peça: gola, ombros, eixo do corpo e giro dos ombros."""
import cv2
import numpy as np

# posição da estampa em proporção da largura dos ombros (frente da peça)
REGRA = {
    "camiseta":  {"lado": 0.0,  "desce": 0.34, "larg": 0.40},   # centro do peito, abaixo da linha dos ombros
    "uniformes": {"lado": 0.22, "desce": 0.30, "larg": 0.19},   # peito esquerdo de quem veste (direita na foto)
    "avental":   {"lado": 0.0,  "desce": 0.0,  "larg": 0.5},   # peito do avental (30% da altura)
    "bone":      {"lado": 0.0,  "desce": 0.0,  "larg": 0.36},   # painel da frente (32% da altura)
}


def _hex2bgr(h):
    h = h.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)


def recortar(img, ponto=None, tol=1.0):
    """recorte em resolução reduzida (rápido no servidor) e borda devolvida no tamanho da foto"""
    H0, W0 = img.shape[:2]; k = min(1.0, 720 / max(H0, W0))
    peq = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else img
    m = _recortar(peq, ponto, tol)
    if m is None or k == 1:
        return m
    m = cv2.resize(m, (W0, H0), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(m, (5, 5), 0)


def _recortar(img, ponto=None, tol=1.0):
    h, w = img.shape[:2]
    px, py = (int(ponto[0] * w), int(ponto[1] * h)) if ponto else (w // 2, int(h * 0.58))
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    r = max(6, int(min(h, w) * 0.02))
    amostra = lab[max(0, py - r):py + r, max(0, px - r):px + r].reshape(-1, 3)
    L0, a0, b0 = np.median(amostra, axis=0)
    dab = np.hypot(lab[..., 1] - a0, lab[..., 2] - b0)
    neutra = np.hypot(a0 - 128, b0 - 128) < 10   # peça branca/preta/cinza: a luz pesa mais que o tom
    tol_ab, tol_L = (7, 45) if neutra else (14, 70)
    tol_ab, tol_L = tol_ab * tol, tol_L * min(tol, 1.6)   # tolerância de cor escolhida no provador (1 = padrão)
    cand = ((dab < tol_ab) & (np.abs(lab[..., 0] - L0) < tol_L)).astype(np.uint8)
    bordas = cv2.Canny(cv2.cvtColor(cv2.GaussianBlur(img, (3, 3), 0), cv2.COLOR_BGR2GRAY), 50, 130)
    livre = cv2.morphologyEx(cand & (bordas == 0), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lb, st, _ = cv2.connectedComponentsWithStats(livre, connectivity=4)
    alvo = lb[py, px]
    if alvo == 0:   # ponto caiu numa borda: pega o pedaço grande mais perto
        d = cv2.distanceTransform((lb == 0).astype(np.uint8), cv2.DIST_L2, 3)
        ys, xs = np.where(lb > 0)
        if not len(xs):
            return None
        k = np.argmin(np.hypot(xs - px, ys - py)); alvo = lb[ys[k], xs[k]]
    sem = (lb == alvo).astype(np.uint8)
    # costuras, gola e bolso cortam a cor em pedaços: os pedaços vizinhos da mesma cor que não encostam na borda da foto entram
    area0 = int(sem.sum())
    for _ in range(3):
        perto = cv2.dilate(sem, np.ones((9, 9), np.uint8))
        novos = set(np.unique(lb[(perto > 0) & (sem == 0)])) - {0}
        cresceu = False
        for i in novos:
            x, y, bw, bh, ar = st[i]
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1 or ar < 40 or ar > 1.5 * area0:
                continue
            sem[lb == i] = 1; cresceu = True
        if not cresceu:
            break
    # GrabCut: o que cresceu é peça provável; a cor parecida em volta decide a borda
    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    gc[cv2.dilate(sem, np.ones((25, 25), np.uint8)) > 0] = cv2.GC_PR_BGD
    gc[(cv2.dilate(sem, np.ones((9, 9), np.uint8)) > 0) & (cand > 0)] = cv2.GC_PR_FGD
    gc[cv2.erode(sem, np.ones((5, 5), np.uint8)) > 0] = cv2.GC_FGD
    try:
        cv2.grabCut(img, gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_MASK)
        m = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8) * 255
    except cv2.error:
        m = sem * 255
    n, lb, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        alvo = lb[py, px] or (1 + np.argmax(st[1:, 4])); m = (lb == alvo).astype(np.uint8) * 255
    # furos pequenos (estampa já existente, botões, sombra forte) entram na peça
    inv = 255 - m; n2, l2, s2, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n2):
        x, y, bw, bh, ar = s2[i]
        if ar < 0.2 * (m > 0).sum() and x > 0 and y > 0 and x + bw < w and y + bh < h:
            m[l2 == i] = 255
    return cv2.GaussianBlur(m, (5, 5), 0)


def medir(m, peca):
    """gola, ombros, eixo e giro a partir da máscara (vista de frente)"""
    b = m > 128; ys, xs = np.where(b)
    if not len(xs):
        return None
    top, bot = ys.min(), ys.max(); H = bot - top + 1
    linhas = range(top, top + int(H * 0.45))
    # gola: primeira linha (de cima para baixo) em que a peça passa inteira pelo eixo do corpo sem buraco
    eixo0 = int(np.median(xs))
    gola = top
    for y in linhas:
        row = b[y]
        if row[max(0, eixo0 - 2):eixo0 + 3].all():
            gola = y; break
    # ombros: largura um pouco abaixo da gola (antes das mangas abrirem)
    yo = min(bot, gola + int(H * 0.06))
    xr = np.where(b[yo])[0]
    if not len(xr):
        return None
    esq, dir_ = xr.min(), xr.max(); ombro = max(1, dir_ - esq)
    # eixo: meio do peito (média do meio de várias linhas abaixo da gola)
    meios = []
    for y in range(gola, min(bot, gola + int(H * 0.3)), max(1, H // 60)):
        x = np.where(b[y])[0]
        if len(x):
            meios.append((x.min() + x.max()) / 2)
    eixo = float(np.median(meios)) if meios else float(eixo0)
    # giro dos ombros: borda de cima de cada lado da gola
    def borda_sup(x0, x1):
        pts = []
        for x in range(int(x0), int(x1), max(1, int((x1 - x0) / 25))):
            c = np.where(b[:, x])[0]
            if len(c):
                pts.append((x, c.min()))
        return pts
    pe = borda_sup(esq + ombro * 0.08, eixo - ombro * 0.18); pd = borda_sup(eixo + ombro * 0.18, dir_ - ombro * 0.08)
    ang = 0.0
    if len(pe) > 3 and len(pd) > 3:
        ye = np.median([p[1] for p in pe]); yd = np.median([p[1] for p in pd]); xe = np.median([p[0] for p in pe]); xd = np.median([p[0] for p in pd])
        ang = float(np.degrees(np.arctan2(yd - ye, xd - xe)))
        if abs(ang) > 25:
            ang = 0.0
    if peca == "avental":   # avental: a referência é a largura do corpo do avental (a 35% da altura), a estampa no peito
        xb = np.where(b[top + int(H * 0.35)])[0]
        if len(xb):
            ombro = float(np.ptp(xb)); eixo = float((xb.min() + xb.max()) / 2)
        gola = top + int(H * 0.08); ang = 0.0
    if peca == "bone":   # boné: sem gola; a frente é a metade de cima da máscara
        xb = np.where(b[top + int(H * 0.35)])[0]
        gola = top; ombro = float(np.ptp(xb)) if len(xb) else ombro; ang = 0.0
    R = REGRA.get(peca, REGRA["camiseta"])
    # linha dos ombros: borda de cima da peça a ±30% da largura dos ombros (não depende da gola, que pode mostrar as costas)
    def topo_em(x):
        c = np.where(b[:, int(np.clip(x, 0, b.shape[1] - 1))])[0]
        return c.min() if len(c) else None
    te, td = topo_em(eixo - ombro * 0.3), topo_em(eixo + ombro * 0.3)
    linha = float(np.mean([v for v in (te, td) if v is not None])) if (te is not None or td is not None) else float(gola)
    if peca == "avental":
        linha = top + H * 0.30 - ombro * R["desce"]
    if peca == "bone":
        linha = top + H * 0.32 - ombro * R["desce"]
    larg = ombro * R["larg"]; rad = np.radians(ang)
    ux, uy = np.cos(rad), np.sin(rad)          # ao longo dos ombros
    vx, vy = -np.sin(rad), np.cos(rad)         # para baixo, perpendicular
    cx = eixo + ux * ombro * R["lado"] + vx * ombro * R["desce"]
    cy = linha + uy * ombro * R["lado"] + vy * ombro * R["desce"]
    return {"gola": int(gola), "ombro": float(ombro), "eixo": eixo, "ang": ang, "logo": {"cx": float(cx), "cy": float(cy), "w": float(larg), "ang": ang},
            "caixa": [int(xs.min()), int(top), int(xs.max()), int(bot)]}


def tingir(img, m, cor):
    """troca o tom da peça e mantém a luz: L da foto (realçado no meio-tom), a e b da cor nova"""
    alvo = cv2.cvtColor(np.uint8([[_hex2bgr(cor)]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    a = (m.astype(np.float32) / 255)[..., None]
    sel = m > 128
    if not sel.any():
        return img
    Lp = lab[..., 0]; mu = np.median(Lp[sel])
    # a luz da peça vira desvio em volta do L da cor nova (dobras e sombras ficam)
    novoL = np.clip(alvo[0] + (Lp - mu) * (0.85 if alvo[0] > 60 else 0.6), 0, 255)
    out = lab.copy(); out[..., 0] = novoL; out[..., 1] = alvo[1]; out[..., 2] = alvo[2]
    rgb = cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    return (img.astype(np.float32) * (1 - a) + rgb * a).astype(np.uint8)
