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
KITS14 = os.path.join(RAIZ, "brand", "kits14")   # kit de 14 setores (10/11/2026): pares COM/SEM_ARTE calibrados pela diferença

def hex2bgr(h):
    h = h.lstrip("#"); return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)

def carregar(setor, pid):
    base = KITS14 if os.path.isdir(os.path.join(KITS14, setor)) else KITS
    pasta = os.path.join(base, setor); cal = json.load(open(os.path.join(pasta, "calibracao.json")))
    P = cal["produtos"][pid]; arq = os.path.normpath(os.path.join(pasta, P["arquivo"])); img = cv2.imread(arq, cv2.IMREAD_COLOR)
    masc = arq.rsplit(".", 1)[0] + ".mascara.png"   # peça de tecido recortada (uniformes): permite trocar a cor do tecido
    if os.path.exists(masc):
        P = dict(P); P["_mascara"] = masc
    return pasta, P, img

def mascara_material(img, P):
    """Máscara do material cuja cor pode mudar. Plano para superfícies planas; para tecido, a região clara
    e pouco saturada ligada ao plano (mesma peça)."""
    if P.get("_mascara"):
        mm = cv2.imread(P["_mascara"], cv2.IMREAD_GRAYSCALE)
        if mm is not None and mm.shape[:2] == img.shape[:2]:
            return mm
    h, w = img.shape[:2]; m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.array(P["plano"], np.int32)], 255)
    if P.get("material_poly"):
        m[:] = 0; cv2.fillPoly(m, [np.array(P["material_poly"], np.int32)], 255)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m &= ((hsv[..., 1] < 90) & (hsv[..., 2] > 100)).astype(np.uint8) * 255
        return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    if P["superficie"] == "tecido" and P.get("material_bbox"):
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
    s = min(mw / aw, mh / ah, W / aw, H / ah); nw, nh = max(1, int(aw * s)), max(1, int(ah * s))  # nunca maior que o plano
    if cheio:   # arte de sangria (a superfície inteira impressa, borda opaca): cobre o plano todo, sem faixa de papel cru
        al = arte_bgra[..., 3]; borda = np.concatenate([al[:3].ravel(), al[-3:].ravel(), al[:, :3].ravel(), al[:, -3:].ravel()])
        if borda.mean() > 200:
            nw, nh = W, H
    arte = cv2.resize(arte_bgra, (nw, nh), interpolation=cv2.INTER_AREA)
    x0, y0 = (W - nw) // 2, (H - nh) // 2
    if P.get("ancora") == "topo":
        y0 = min(int(H * 0.08), max(0, H - nh))  # arte cheia não pode sair do plano
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
    cor_mat = hex2bgr(material) if (material and (P.get("material_recolor") or P.get("_mascara"))) else None
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
    if P.get("paineis"):   # folheto dobrado com painéis em planos diferentes: cada faixa da arte vai para o seu painel
        n = len(P["paineis"]); H0, W0 = tela.shape[:2]; proj = np.zeros((img.shape[0], img.shape[1], 4), np.uint8)
        for i, q in enumerate(P["paineis"]):
            x0, x1 = int(W0 * i / n), int(W0 * (i + 1) / n); faixa = np.ascontiguousarray(tela[:, x0:x1])
            M = cv2.getPerspectiveTransform(np.float32([[0, 0], [x1 - x0, 0], [x1 - x0, H0], [0, H0]]), np.float32(q))
            w = cv2.warpPerspective(faixa, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            proj = np.where(w[..., 3:4] > proj[..., 3:4], w, proj)
    else:
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

# ---------------------------------------------------------------- carimbos (papéis carimbados)
# Cada foto do kit tem as marcas medidas (calibracao.json → produtos.10.carimbos): o carimbo grande da empresa,
# PAGO, RECEBIDO, a data e o carimbo redondo. Cada marca é desenhada de frente e entra na perspectiva da folha
# em que está, com tinta de carimbo (falha de tinta, borda irregular) multiplicada sobre o papel.
FONTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fontes")
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

def _fonte(tam, negrito=True):
    from PIL import ImageFont
    for f in (os.path.join(FONTES, "DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf"), "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, int(tam))
    return ImageFont.load_default()

def _lados(q):
    q = np.float32(q); w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2; h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    return float(w), float(h)

def _texto_caixa(texto, w, h, borda=True):
    """carimbo retangular: moldura + texto em negrito centralizado, ocupando a caixa"""
    from PIL import Image, ImageDraw
    W, H = int(w * 3), int(h * 3); im = Image.new("L", (W, H), 0); g = ImageDraw.Draw(im)
    lw = max(4, int(H * 0.075))
    if borda:
        g.rectangle([lw // 2, lw // 2, W - lw // 2 - 1, H - lw // 2 - 1], outline=255, width=lw)
    tam = H * 0.62
    while tam > 8:
        f = _fonte(tam); bb = g.textbbox((0, 0), texto, font=f)
        if bb[2] - bb[0] <= W - 4.2 * lw and bb[3] - bb[1] <= H - 3.4 * lw:
            break
        tam *= 0.94
    bb = g.textbbox((0, 0), texto, font=f); g.text(((W - (bb[2] - bb[0])) / 2 - bb[0], (H - (bb[3] - bb[1])) / 2 - bb[1]), texto, font=f, fill=255)
    return np.array(im)

def _redondo(nome, logo_alpha, lado=900):
    """carimbo redondo: dois anéis, o nome da loja em arco no alto e a marca (silhueta do logotipo) no centro"""
    from PIL import Image, ImageDraw
    im = Image.new("L", (lado, lado), 0); g = ImageDraw.Draw(im); c = lado / 2; R = lado * 0.48
    g.ellipse([c - R, c - R, c + R, c + R], outline=255, width=int(lado * 0.022))
    r2 = lado * 0.35; g.ellipse([c - r2, c - r2, c + r2, c + r2], outline=255, width=int(lado * 0.011))
    nome = (nome or "").upper()[:28]
    if nome:
        tam = lado * 0.085; f = _fonte(tam); rt = (R + r2) / 2
        larg = [g.textbbox((0, 0), ch, font=f)[2] for ch in nome]; tot = sum(larg) + tam * 0.12 * (len(nome) - 1)
        lim = np.pi * 0.95   # o nome fica no arco de cima, sem descer pelos lados
        if tot / rt > lim:
            tam = tam * lim * rt / tot; f = _fonte(tam); larg = [g.textbbox((0, 0), ch, font=f)[2] for ch in nome]; tot = sum(larg) + tam * 0.12 * (len(nome) - 1)
        a = -np.pi / 2 - (tot / rt) / 2
        for ch, lw in zip(nome, larg):
            ac = a + (lw / 2) / rt; x, y = c + rt * np.cos(ac), c + rt * np.sin(ac)
            t = Image.new("L", (int(tam * 2), int(tam * 2)), 0); ImageDraw.Draw(t).text((tam, tam), ch, font=f, fill=255, anchor="mm")
            t = t.rotate(-np.degrees(ac) - 90, resample=Image.BICUBIC); im.paste(255, (int(x - t.width / 2), int(y - t.height / 2)), t)
            a += (lw + tam * 0.12) / rt
        for ang in (np.pi * 0.62, np.pi * 0.38):   # duas estrelinhas embaixo
            x, y = c + rt * np.cos(ang), c + rt * np.sin(ang); s = lado * 0.022
            pts = [(x + s * np.cos(np.pi / 2 + k * 4 * np.pi / 5), y - s * np.sin(np.pi / 2 + k * 4 * np.pi / 5)) for k in range(5)]; g.polygon(pts, fill=255)
    if logo_alpha is not None:
        la = logo_alpha; ys, xs = np.where(la > 40)
        if len(xs):
            la = la[ys.min():ys.max() + 1, xs.min():xs.max() + 1]; caixa = r2 * 1.35; k = min(caixa / la.shape[1], caixa * 0.8 / la.shape[0])
            la = cv2.resize(la, (max(1, int(la.shape[1] * k)), max(1, int(la.shape[0] * k))), interpolation=cv2.INTER_AREA)
            arr = np.array(im); y0, x0 = int(c - la.shape[0] / 2), int(c - la.shape[1] / 2); arr[y0:y0 + la.shape[0], x0:x0 + la.shape[1]] = np.maximum(arr[y0:y0 + la.shape[0], x0:x0 + la.shape[1]], la)
            return arr
    sig = "".join(p[0] for p in (nome or "?").split()[:2]) or "?"
    f = _fonte(lado * 0.2); bb = g.textbbox((0, 0), sig, font=f); g.text((c - (bb[2] - bb[0]) / 2 - bb[0], c - (bb[3] - bb[1]) / 2 - bb[1]), sig, font=f, fill=255)
    return np.array(im)

def _empresa(campos, w, h):
    """carimbo da empresa (CNPJ): moldura dupla e as linhas com os dados da loja; o que não se sabe fica "a confirmar" """
    from PIL import Image, ImageDraw
    W, H = int(w * 3), int(h * 3); im = Image.new("L", (W, H), 0); g = ImageDraw.Draw(im)
    lw = max(5, int(H * 0.018)); g.rectangle([lw, lw, W - lw, H - lw], outline=255, width=lw); i2 = lw * 3; g.rectangle([i2, i2, W - i2, H - i2], outline=255, width=max(2, lw // 2))
    cp = campos or {}
    linhas = [((cp.get("nome") or "").upper(), 1.0, True), ((cp.get("razao") or "").strip(), 0.62, True),
              ("CNPJ " + (cp.get("cnpj") or "a confirmar"), 0.56, False), ((cp.get("endereco") or "").strip(), 0.5, False),
              (("Tel. " + cp["tel"]) if cp.get("tel") else "", 0.5, False)]
    linhas = [x for x in linhas if x[0]]
    base = H * 0.15; larg_util = W - 9 * lw
    for _ in range(30):   # o maior tamanho em que todas as linhas cabem
        alt = sum(base * k * 1.32 for _, k, _ in linhas)
        if alt <= H - 10 * lw and all(g.textbbox((0, 0), t, font=_fonte(base * k, n))[2] <= larg_util for t, k, n in linhas):
            break
        base *= 0.93
    y = (H - sum(base * k * 1.32 for _, k, _ in linhas)) / 2
    for t, k, n in linhas:
        f = _fonte(base * k, n); bb = g.textbbox((0, 0), t, font=f); g.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y + (base * k * 1.32 - (bb[3] - bb[1])) / 2 - bb[1]), t, font=f, fill=255); y += base * k * 1.32
    return np.array(im)

def _tinta(alpha, semente):
    """falha de tinta de carimbo: grão, falhas maiores e borda levemente borrada"""
    rs = np.random.RandomState(semente); h, w = alpha.shape
    grao = cv2.GaussianBlur(rs.rand(h, w).astype(np.float32), (0, 0), 1.2); falha = cv2.GaussianBlur(rs.rand(max(2, h // 8), max(2, w // 8)).astype(np.float32), (0, 0), 1.0)
    falha = cv2.resize(falha, (w, h)); m = np.clip((grao * 0.6 + falha * 0.4 - 0.18) * 3.0, 0.35, 1.0)
    return (cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 0.8) * m).clip(0, 255).astype(np.uint8)

def _no_papel(out, alpha, quad, cor, opac=0.9):
    """alpha frontal → perspectiva da folha; tinta multiplicada sobre o papel (a textura do papel aparece)"""
    h, w = alpha.shape; M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(quad))
    a = cv2.warpPerspective(alpha, M, (out.shape[1], out.shape[0]), flags=cv2.INTER_AREA if w > 400 else cv2.INTER_LINEAR).astype(np.float32) / 255 * opac
    tinta = out.astype(np.float32) * (cor[None, None, :] / 255.0)
    return out.astype(np.float32) * (1 - a[..., None]) + tinta * a[..., None]

def carimbar(setor, grande_png, saida, nome=None, logo_png=None, data=None, tinta="#22252E", campos=None):
    pasta, P, img = carregar(setor, "10"); C = P["carimbos"]; cor = hex2bgr(tinta); out = img.copy().astype(np.float32)
    import datetime
    d = data or datetime.date.today(); dtxt = f"{d.day:02d} {MESES[d.month - 1]} {d.year}"
    for k, (tipo, txt) in enumerate((("pago", "PAGO"), ("recebido", "RECEBIDO"), ("data", dtxt))):
        if tipo in C:
            w, h = _lados(C[tipo]); out = _no_papel(out, _tinta(_texto_caixa(txt, w, h), 11 + k), C[tipo], cor)
    if "redondo" in C:
        R = C["redondo"]; la = None
        if logo_png:
            lg = cv2.imread(logo_png, cv2.IMREAD_UNCHANGED)
            if lg is not None:
                cinza = cv2.cvtColor(lg[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32); al = lg[..., 3].astype(np.float32) if lg.ndim == 3 and lg.shape[2] == 4 else np.full(cinza.shape, 255, np.float32)
                escuro = np.clip((215 - cinza) / 110, 0, 1); claro_total = ((al > 128) & (cinza > 170)).mean() / max((al > 128).mean(), 1e-3)
                # logotipo claro (branco) sobre transparente: a forma inteira é tinta; com fundo claro próprio: só o que é escuro
                la = (al if claro_total > 0.85 else al * escuro).clip(0, 255).astype(np.uint8)
        q = np.float32(cv2.boxPoints((tuple(R["centro"]), tuple(R["eixos"]), R["ang"])))
        q = q[np.argsort(q[:, 1])]; q = np.vstack([q[:2][np.argsort(q[:2, 0])], q[2:][np.argsort(q[2:, 0])[::-1]]])
        out = _no_papel(out, _tinta(_redondo(nome, la), 23), q, cor)
    if campos and "grande" in C:
        w, h = _lados(C["grande"]); out = _no_papel(out, _tinta(_empresa(campos, w, h), 31), C["grande"], cor)
    elif grande_png and "grande" in C:
        g = cv2.imread(grande_png, cv2.IMREAD_UNCHANGED)
        if g is not None:
            if g.ndim == 3 and g.shape[2] == 4:
                a = g[..., 3].astype(np.float32) * (1 - cv2.cvtColor(g[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32) / 255 * 0.85)   # o que é escuro e opaco é tinta
            else:
                a = 255 - cv2.cvtColor(g, cv2.COLOR_BGR2GRAY).astype(np.float32)
            a = a.clip(0, 255).astype(np.uint8); ys, xs = np.where(a > 30)
            if len(xs):
                a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            w, h = _lados(C["grande"]); W, H = int(w * 2), int(h * 2); k = min(W / a.shape[1], H / a.shape[0])
            a = cv2.resize(a, (max(1, int(a.shape[1] * k)), max(1, int(a.shape[0] * k))), interpolation=cv2.INTER_AREA)
            tela = np.zeros((H, W), np.uint8); y0, x0 = (H - a.shape[0]) // 2, (W - a.shape[1]) // 2; tela[y0:y0 + a.shape[0], x0:x0 + a.shape[1]] = a
            out = _no_papel(out, _tinta(tela, 31), C["grande"], cor)
    cv2.imwrite(saida, np.clip(out, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return saida

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    if len(args) < 4:
        print(__doc__); sys.exit(1)
    aplicar(args[0], args[1], args[2], args[3], opts.get("material"), opts.get("arte-cor"), float(opts.get("largura", 0.7)))
    print("ok", args[3])
