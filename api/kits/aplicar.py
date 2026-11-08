#!/usr/bin/env python3
"""GênIO · kits de ambiente por setor — aplicação determinística de cor e arte.

Uso: aplicar.py <setor> <id_produto> <arte.png> <saida.jpg> [--material=#hex] [--arte-cor=#hex] [--largura=0.7]

Rotina (Guia_Kit): carregar base + calibração → recolorir só o material autorizado → encaixar a arte
proporcionalmente no plano frontal (contain, com margem) → transformar para a perspectiva da foto →
aplicar textura e luz da própria foto → repor oclusões → exportar. Sem IA, mesmo resultado sempre.
"""
import json, os, sys
import numpy as np, cv2

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KITS = os.path.join(RAIZ, "brand", "kits")

def hex2bgr(h):
    h = h.lstrip("#"); return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)

def carregar(setor, pid):
    pasta = os.path.join(KITS, setor); cal = json.load(open(os.path.join(pasta, "calibracao.json")))
    P = cal["produtos"][pid]; img = cv2.imread(os.path.join(pasta, P["arquivo"]), cv2.IMREAD_COLOR)
    return pasta, P, img

def mascara_material(img, P):
    """Máscara do material cuja cor pode mudar. Plano para superfícies planas; para tecido, a região clara
    e pouco saturada ligada ao plano (mesma peça)."""
    h, w = img.shape[:2]; m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.array(P["plano"], np.int32)], 255)
    if P.get("material_poly"):
        m[:] = 0; cv2.fillPoly(m, [np.array(P["material_poly"], np.int32)], 255)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m &= ((hsv[..., 1] < 90) & (hsv[..., 2] > 100)).astype(np.uint8) * 255
        return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    if P["superficie"] == "tecido":
        # GrabCut dentro da caixa do material (calibrada), semeado pelo plano de impressão; depois só a parte clara e pouco saturada
        x0, y0, x1, y1 = P["material_bbox"]
        gc = np.full((h, w), cv2.GC_BGD, np.uint8); gc[y0:y1, x0:x1] = cv2.GC_PR_FGD
        gc[m > 0] = cv2.GC_FGD
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(img, gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
        fg = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8) * 255
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        claro = ((hsv[..., 1] < 80) & (hsv[..., 2] > 120)).astype(np.uint8) * 255
        m = cv2.morphologyEx(fg & claro, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab = cv2.connectedComponents(m); ids = set(np.unique(lab[cv2.erode(np.where(lab > 0, 255, 0).astype(np.uint8) & (np.isin(lab, list(set(np.unique(lab[np.array(cv2.fillPoly(np.zeros((h, w), np.uint8), [np.array(P["plano"], np.int32)], 255)) > 0])) - {0})) * 255).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0])) - {0}
        if ids:
            m = np.isin(lab, list(ids)).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return m

def recolorir(img, mask, cor_bgr):
    """Troca a cor do material preservando luz, sombra e textura: trabalha em Lab, substitui a/b e
    reescala L em torno da média do material (tinta branca em material escuro continua visível)."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    alvo = cv2.cvtColor(np.uint8([[cor_bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    sel = mask > 0
    if not sel.any():
        return img
    Lm = lab[..., 0][sel].mean()
    L = lab[..., 0]; Ln = np.clip(alvo[0] + (L - Lm) * (0.85 if alvo[0] < 128 else 1.0), 0, 255)
    out = lab.copy(); a = mask.astype(np.float32) / 255.0
    out[..., 0] = L * (1 - a) + Ln * a; out[..., 1] = lab[..., 1] * (1 - a) + alvo[1] * a; out[..., 2] = lab[..., 2] * (1 - a) + alvo[2] * a
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

def layout_frontal(arte_bgra, P, largura_rel=0.7, cor_fundo=None, cheio=False):
    """Plano frontal do produto em pixels (sem perspectiva): proporção física quando conhecida; a arte entra
    em 'contain' ocupando largura_rel da largura útil, centralizada; margem de segurança 6%."""
    prop = P.get("proporcao_fisica"); plano = np.array(P["plano"], np.float32)
    if prop:
        W, H = 1200, int(1200 * prop[1] / prop[0])
    else:  # proporção do próprio plano na foto (média dos lados)
        wl = (np.linalg.norm(plano[1] - plano[0]) + np.linalg.norm(plano[2] - plano[3])) / 2
        hl = (np.linalg.norm(plano[3] - plano[0]) + np.linalg.norm(plano[2] - plano[1])) / 2
        W, H = 1200, max(200, int(1200 * hl / wl))
    tela = np.zeros((H, W, 4), np.uint8)
    if cor_fundo is not None:
        tela[..., :3] = cor_fundo.astype(np.uint8); tela[..., 3] = 255
    ah, aw = arte_bgra.shape[:2]; mw, mh = (W, H) if cheio else (W * 0.88 * largura_rel, H * 0.88)
    s = min(mw / aw, mh / ah); nw, nh = max(1, int(aw * s)), max(1, int(ah * s))
    arte = cv2.resize(arte_bgra, (nw, nh), interpolation=cv2.INTER_AREA)
    x0, y0 = (W - nw) // 2, (H - nh) // 2
    if P.get("ancora") == "topo":
        y0 = int(H * 0.08)
    if P.get("aplicacao") == "impressao_carimbo":  # 4×6 cm no terço esquerdo da folha
        x0, y0 = int(W * 0.12), int(H * 0.18); nw, nh = min(nw, W - x0), min(nh, H - y0); arte = arte[:nh, :nw]
    a = arte[..., 3:4].astype(np.float32) / 255
    reg = tela[y0:y0 + nh, x0:x0 + nw]
    reg[..., :3] = (arte[..., :3] * a + reg[..., :3] * (1 - a)).astype(np.uint8)
    reg[..., 3] = np.maximum(reg[..., 3], arte[..., 3])
    return tela

def projetar(tela, P, shape):
    H, W = tela.shape[:2]; src = np.float32([[0, 0], [W, 0], [W, H], [0, H]]); dst = np.float32(P["plano"])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(tela, M, (shape[1], shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

def mapa_de_luz(img, mask):
    """Luz e textura da própria foto, normalizadas pela média do material: a impressão herda sombra e grão."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sel = mask > 0; med = g[sel].mean() if sel.any() else g.mean()
    return np.clip(g / max(med, 1), 0.25, 1.6)

def oclusoes(img, P):
    """Elementos que ficam na frente da aplicação: parafusos/standoffs = pequenos pontos muito claros e
    neutros dentro do plano (especular do aço). Devolve máscara para repor a foto original."""
    h, w = img.shape[:2]; m = np.zeros((h, w), np.uint8)
    if P.get("oclusoes") == "parafusos":
        plano = np.zeros((h, w), np.uint8); cv2.fillPoly(plano, [np.array(P["plano"], np.int32)], 255)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # aço: contraste local alto (borda escura + brilho) em área pequena
        lap = cv2.Laplacian(cv2.GaussianBlur(g, (5, 5), 0), cv2.CV_32F); forte = (np.abs(lap) > 18).astype(np.uint8) * 255
        forte = cv2.morphologyEx(forte & plano, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(forte)
        for i in range(1, n):
            x, y, bw, bh, area = st[i]
            if 80 < area < 4000 and 0.6 < bw / max(bh, 1) < 1.6 and max(bw, bh) < 70:
                cv2.circle(m, (int(cen[i][0]), int(cen[i][1])), int(max(bw, bh) * 0.62) + 3, 255, -1)
    return m

def aplicar(setor, pid, arte_path, saida, material=None, arte_cor=None, largura=0.7, cheio=False):
    pasta, P, img = carregar(setor, pid)
    arte = cv2.imread(arte_path, cv2.IMREAD_UNCHANGED)
    if arte is None:
        raise SystemExit("arte não encontrada: " + arte_path)
    if arte.shape[2] == 3:
        arte = cv2.cvtColor(arte, cv2.COLOR_BGR2BGRA)
    # recorta as margens transparentes: a proporção da arte é a do desenho, não a da prancheta
    ys, xs = np.where(arte[..., 3] > 8)
    if len(xs) > 10 and not cheio:
        arte = arte[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    base = img.copy()
    mmat = mascara_material(img, P)
    cor_mat = hex2bgr(material) if (material and P.get("material_recolor")) else None
    if cor_mat is not None:
        base = recolorir(base, mmat, cor_mat)
    aplic = P.get("aplicacao")
    if aplic in ("vinil_recortado", "impressao_carimbo", "bordado_peito", "serigrafia") and not cheio:
        # arte monocromática: só a forma (alpha) importa; a cor vem do vinil/tinta/linha
        cor = hex2bgr(arte_cor or "#1C1635")
        mono = np.zeros_like(arte); mono[..., :3] = cor; mono[..., 3] = arte[..., 3]
        if aplic == "impressao_carimbo":  # carimbo não imprime chapado: leve falha de tinta
            ruido = (np.random.RandomState(7).rand(*arte.shape[:2]) > 0.08).astype(np.uint8)
            mono[..., 3] = (arte[..., 3] * ruido).astype(np.uint8)
        arte = mono
    fundo = cor_mat if (aplic == "impressao_total" and P.get("fundo_arte") == "cor_material" and cor_mat is not None) else None
    if aplic == "impressao_carimbo":
        largura = min(largura, 0.32)
    tela = layout_frontal(arte, P, largura, fundo, cheio)
    proj = projetar(tela, P, img.shape)
    a = (proj[..., 3].astype(np.float32) / 255.0)
    if aplic == "vinil_recortado" and P["superficie"] == "vidro":
        a *= 0.9  # reflexo do vidro continua passando um pouco
    luz = mapa_de_luz(img, mmat)
    cor_proj = proj[..., :3].astype(np.float32) * luz[..., None]
    out = base.astype(np.float32) * (1 - a[..., None]) + np.clip(cor_proj, 0, 255) * a[..., None]
    oc = oclusoes(img, P)
    if oc.any():
        k = (oc.astype(np.float32) / 255.0)[..., None]; out = out * (1 - k) + img.astype(np.float32) * k
    out = np.clip(out, 0, 255).astype(np.uint8)
    cv2.imwrite(saida, out, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return saida

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    if len(args) < 4:
        print(__doc__); sys.exit(1)
    aplicar(args[0], args[1], args[2], args[3], opts.get("material"), opts.get("arte-cor"), float(opts.get("largura", 0.7)))
    print("ok", args[3])
