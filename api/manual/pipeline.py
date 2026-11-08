# GenIO v3 — manual de identidade sem IA: logo (foto/arquivo) → vetor por camadas → versões → cores por material → aplicações → manual HTML
# uso: python3 pipeline.py <logo> <cliente.json> <pasta_saida>
import sys,os,json,math,subprocess,base64,time
import numpy as np,cv2
from skimage.metrics import structural_similarity as ssim
T0=time.time()
LOGO,CLI,OUT=sys.argv[1],sys.argv[2],sys.argv[3]; os.makedirs(OUT,exist_ok=True)
C=json.load(open(CLI)); L=C.get("lacunas",{}); NOME=C.get("nome","Cliente")
KAP=json.load(open(os.path.join(os.path.dirname(__file__),'..','manual_kapazi.json')))
lum=lambda rgb:0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]
hx=lambda rgb:'#%02x%02x%02x'%tuple(int(v) for v in rgb)
def lab(rgb):return cv2.cvtColor(np.uint8([[rgb]]),cv2.COLOR_RGB2LAB)[0,0].astype(float)
def hsv_(rgb):return cv2.cvtColor(np.uint8([[rgb]]),cv2.COLOR_RGB2HSV)[0,0].astype(float)
def hdiff(a,b):d=abs(hsv_(a)[0]-hsv_(b)[0]);return min(d,180-d)*2
def dist(a,b):return float(np.linalg.norm(lab(a)-lab(b)))
def kapazi(rgb):
    if lum(rgb)<115 and max(rgb)-min(rgb)<45:return next(k for k in KAP if k['id']=='preto03')
    if lum(rgb)>205 and max(rgb)-min(rgb)<40:return next(k for k in KAP if k['id']=='branco')
    h,s,v=cv2.cvtColor(np.uint8([[rgb]]),cv2.COLOR_RGB2HSV)[0,0].astype(float)
    best=None
    for k in KAP:
        r=tuple(int(k["hex"][i:i+2],16) for i in (1,3,5));h2,s2,v2=cv2.cvtColor(np.uint8([[r]]),cv2.COLOR_RGB2HSV)[0,0].astype(float)
        if s<40 or s2<40: d=dist(rgb,r)*(0.6 if s<40 and s2<40 else 1.6)   # cinzas: distância; cromático×cinza: penaliza
        else: dh=min(abs(h-h2),180-abs(h-h2)); d=dh*1.2+abs(v-v2)*0.35+abs(s-s2)*0.15
        if best is None or d<best[0]:best=(d,k)
    return best[1]
def cmyk(rgb):
    r,g,b=[v/255 for v in rgb];k=1-max(r,g,b)
    if k>=1:return "C0 M0 Y0 K100"
    c,m,y=[(1-v-k)/(1-k) for v in (r,g,b)];return "C%d M%d Y%d K%d"%tuple(round(v*100) for v in (c,m,y,k))

# 1. ler e limpar ---------------------------------------------------------
im=cv2.imread(LOGO,cv2.IMREAD_UNCHANGED)
if im.shape[2]==4: alpha=im[:,:,3];rgb=cv2.cvtColor(im[:,:,:3],cv2.COLOR_BGR2RGB)
else: alpha=None;rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)
H0,W0=rgb.shape[:2];S=max(1,int(round(1200/max(H0,W0))))        # ampliar para ~1200 px
rgb=cv2.resize(rgb,(W0*S,H0*S),interpolation=cv2.INTER_CUBIC);rgb=cv2.bilateralFilter(rgb,9,40,9)
H,W=rgb.shape[:2]
if alpha is not None: fg=cv2.resize(alpha,(W,H))>128; bgcol=None
else:
    # fundo = cor dominante da borda (bins de 24)
    b=np.concatenate([rgb[:8].reshape(-1,3),rgb[-8:].reshape(-1,3),rgb[:,:8].reshape(-1,3),rgb[:,-8:].reshape(-1,3)])
    q=(b//24*24+12);vals,cnt=np.unique(q,axis=0,return_counts=True);bgcol=vals[cnt.argmax()]
    D=np.linalg.norm(cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).astype(float)-lab(bgcol),axis=2)
    Dn=np.clip(D/D.max()*255,0,255).astype(np.uint8);t,_=cv2.threshold(Dn,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU);tol=max(14,min(60,t/255*D.max()*0.9));fg=D>tol
    fg=cv2.morphologyEx(fg.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8)).astype(bool)
    # fundo preso dentro do logo (ex.: disco) fica; só o fundo conectado à borda sai
    n,lab_,st,_=cv2.connectedComponentsWithStats((~fg).astype(np.uint8),8)
    border=set(np.unique(np.concatenate([lab_[0],lab_[-1],lab_[:,0],lab_[:,-1]])))-{0}
    keep=np.isin(lab_,list(border));fg=~keep
# lascas: componentes do logo encostados na borda e pequenos (<10% do logo) saem
n,lab_,st,_=cv2.connectedComponentsWithStats(fg.astype(np.uint8),8)
tot=fg.sum()
for i in range(1,n):
    x,y,w,h,a=st[i]
    if a<0.10*tot and (x==0 or y==0 or x+w>=W or y+h>=H):fg[lab_==i]=False
# recorte com respiro
ys,xs=np.where(fg);y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max();p=int(0.04*max(y1-y0,x1-x0))
y0,x0=max(0,y0-p),max(0,x0-p);y1,x1=min(H,y1+p),min(W,x1+p);rgb=rgb[y0:y1,x0:x1];fg=fg[y0:y1,x0:x1];H,W=fg.shape

# 2. quantizar (k-means em Lab, só no logo) ------------------------------
px=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).reshape(-1,3).astype(np.float32)[fg.reshape(-1)]
K=10;_,lbl,cen=cv2.kmeans(px,K,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,30,0.5),4,cv2.KMEANS_PP_CENTERS)
cen_rgb=[tuple(int(v) for v in cv2.cvtColor(np.uint8([[c]]),cv2.COLOR_LAB2RGB)[0,0]) for c in cen]
# juntar parecidas (<22 Lab) e descartar <1.5% da área
cnt=np.bincount(lbl.ravel(),minlength=K);area=cnt.sum();order=np.argsort(-cnt);merge={}
for i in order:
    for j in merge.values():
        if j!=i and (dist(cen_rgb[i],cen_rgb[j])<32 or (hsv_(cen_rgb[i])[1]>60 and hsv_(cen_rgb[j])[1]>60 and hdiff(cen_rgb[i],cen_rgb[j])<10 and dist(cen_rgb[i],cen_rgb[j])<55)):merge[i]=j;break
    else:merge[i]=i
lbl2=np.array([merge[i] for i in lbl.ravel()]);cnt2=np.bincount(lbl2,minlength=K)
cand=[i for i in range(K) if merge[i]==i and cnt2[i]/area>=0.006];cand.sort(key=lambda i:-cnt2[i])
# mistura de borda (antisserrilhado): cor que está quase no segmento entre duas outras maiores → sai
mix=set()
for c in cand:
    for a in cand:
        for b in cand:
            if len({a,b,c})<3 or cnt2[a]<cnt2[c] or cnt2[b]<cnt2[c]:continue
            if dist(cen_rgb[a],cen_rgb[c])+dist(cen_rgb[c],cen_rgb[b])<dist(cen_rgb[a],cen_rgb[b])*1.12:mix.add(c)
cand=[c for c in cand if c not in mix];cores=[]
for i in cand:
    big=cnt2[i]/area>=0.015;distinto=all(hdiff(cen_rgb[i],cen_rgb[j])>25 for j in cores) and hsv_(cen_rgb[i])[1]>60
    if big or distinto:cores.append(i)
full=np.full(H*W,-1);full[fg.reshape(-1)]=lbl2;full=full.reshape(H,W)
# pixels de clusters raros vão para a cor mais próxima
for i in range(K):
    if i not in cores and (full==i).any():
        j=min(cores,key=lambda c:dist(cen_rgb[i],cen_rgb[c]));full[full==i]=j
# média real por cluster (não o centro)
cores.sort(key=lambda i:-cnt2[i])
pass #print('DBG bg',bgcol,'fg',round(float(fg.mean()),3),'cen',cen_rgb,'cnt2',cnt2.tolist(),'cores',cores,file=sys.stderr)
cor_rgb={i:tuple(int(v) for v in rgb[full==i].reshape(-1,3).mean(0)) for i in cores}

# 2b. retoque (arquivo pequeno escrito por pessoa ou IA; o programa aplica)
RET=json.load(open(sys.argv[4])) if len(sys.argv)>4 and os.path.exists(sys.argv[4]) else {}
for c_id,hexo in RET.get("cores",{}).items():   # força a cor de uma camada pelo índice (0 = maior)
    i=cores[int(c_id)];cor_rgb[i]=tuple(int(hexo[k:k+2],16) for k in (1,3,5))
if RET.get("fechar_tracos"):   # engrossa levemente a camada clara (traços finos perdidos na foto)
    for idx in RET["fechar_tracos"]:
        i=cores[idx];m=(full==i).astype(np.uint8);m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8));full[(m==1)&(full!=i)&fg]=i
# 3. vetorizar por camada (contornos com furos, suavizados) --------------
def layer_paths(mask,eps):
    mask=cv2.morphologyEx(mask.astype(np.uint8)*255,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    mask=cv2.medianBlur(mask,5)
    cs,hier=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
    d=[]
    for c in cs:
        if cv2.contourArea(c)<0.0004*H*W:continue
        c=cv2.approxPolyDP(c,eps,True)
        if len(c)<3:continue
        pts=c.reshape(-1,2)
        # curvas suaves: quadráticas pelo ponto médio
        s="M%.1f %.1f"%tuple(pts[0])
        for k in range(1,len(pts)+1):
            a=pts[k%len(pts)];m=(pts[k-1]+a)/2;s+=" Q%.1f %.1f %.1f %.1f"%(pts[k-1][0],pts[k-1][1],m[0],m[1])
        d.append(s+"Z")
    return " ".join(d)
EPS=max(1.0,0.0025*max(H,W))
camadas=[]   # da maior para a menor área (a maior fica embaixo)
for n_,i in enumerate(cores):
    pth=layer_paths(full==i,EPS)
    if n_==0 and RET.get("circulo"):   # fundo = círculo perfeito ajustado à camada maior
        ys_,xs_=np.where(fg);cx,cy=float(xs_.mean()),float(ys_.mean());r=math.sqrt(fg.sum()/math.pi)*(RET["circulo"] if isinstance(RET["circulo"],(int,float)) else 1)
        pth="M%.1f %.1f A%.1f %.1f 0 1 0 %.1f %.1f A%.1f %.1f 0 1 0 %.1f %.1fZ"%(cx-r,cy,r,r,cx+r,cy,r,r,cx-r,cy)
    if pth:camadas.append(dict(id=i,hex=hx(cor_rgb[i]),rgb=cor_rgb[i],area=float((full==i).mean()),d=pth))
TEXTOS=RET.get("textos",[])   # [{texto,x,y,tam,cor,fonte,peso,italico}] em % da largura/altura
def svg_marca(fills=None,stroke=None,bg=None,vb=True):
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"%s>'%(W,H,' width="%d" height="%d"'%(W,H) if vb else '')]
    if bg:out.append('<rect width="%d" height="%d" fill="%s"/>'%(W,H,bg))
    if stroke:
        for c in camadas:out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round" paint-order="stroke" fill-rule="evenodd"/>'%(c["d"],(fills or {}).get(c["id"],c["hex"]),stroke[0],stroke[1]))
    for c in camadas:out.append('<path d="%s" fill="%s" fill-rule="evenodd"/>'%(c["d"],(fills or {}).get(c["id"],c["hex"])))
    for t in TEXTOS:
        col=(fills or {}).get("texto",t.get("cor","#ffffff")) if fills else t.get("cor","#ffffff")
        out.append('<text x="%.1f" y="%.1f" font-size="%.1f" font-family="%s" font-weight="%s" font-style="%s" fill="%s" text-anchor="%s">%s</text>'%(t["x"]/100*W,t["y"]/100*H,t["tam"]/100*H,t.get("fonte","serif"),t.get("peso","700"),"italic" if t.get("italico") else "normal",col,t.get("anchor","middle"),t["texto"]))
    out.append('</svg>');return "".join(out)
open(f"{OUT}/marca-cor.svg","w").write(svg_marca())

# 4. checagem de fidelidade (render do SVG × raster limpo) ----------------
subprocess.run(["rsvg-convert","-w",str(W),"-h",str(H),f"{OUT}/marca-cor.svg","-o",f"{OUT}/_render.png"],check=True)
ren=cv2.imread(f"{OUT}/_render.png",cv2.IMREAD_UNCHANGED)
ren_rgb=cv2.cvtColor(ren[:,:,:3],cv2.COLOR_BGR2RGB);ren_a=ren[:,:,3]>0 if ren.shape[2]==4 else np.ones((H,W),bool)
ref=rgb.copy();ref[~fg]=255;comp=ren_rgb.copy();comp[~ren_a]=255
g1=cv2.cvtColor(ref,cv2.COLOR_RGB2GRAY);g2=cv2.cvtColor(comp,cv2.COLOR_RGB2GRAY)
fid=float(ssim(g1,g2,data_range=255));iou=float((fg&ren_a).sum()/max(1,(fg|ren_a).sum()))
# teste do espelho: se o espelhado "bate melhor", algo está invertido (não deveria)
fid_m=float(ssim(g1,cv2.flip(g2,1),data_range=255))
# 5. OCR (o que está escrito) --------------------------------------------
try:
    import pytesseract
    ocr=pytesseract.image_to_string(cv2.cvtColor(ref,cv2.COLOR_RGB2GRAY),lang="por",config="--psm 6").strip()
except Exception as e: ocr=""
palavras=[w for w in ocr.replace("\n"," ").split() if len(w)>1]

# 6. versões ---------------------------------------------------------------
principal=camadas[0];crom=[c for c in camadas if cv2.cvtColor(np.uint8([[c["rgb"]]]),cv2.COLOR_RGB2HSV)[0,0][1]>=40]
cor_marca=(crom[0] if crom else principal)["rgb"]
lum=lambda rgb:0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]
# fundo do logo = a maior camada se ela for "fundo" (cobre >35%)
fundo=camadas[0] if camadas[0]["area"]>0.35 else None
ids=[c["id"] for c in camadas]
def mono(cor):
    # mantém o contraste: camadas claras viram contra-forma (branco/fundo), escuras viram a cor
    f={}
    ref_l=lum(fundo["rgb"]) if fundo else 255
    for c in camadas:f[c["id"]]=cor if abs(lum(c["rgb"])-ref_l)>60 or c is fundo and False else ("#ffffff" if cor!="#ffffff" else "#1c1c1c")
    if fundo:f[fundo["id"]]=cor if lum(fundo["rgb"])<128 else "#ffffff"
    f["texto"]="#ffffff" if (fundo and f[fundo["id"]]==cor) else cor
    return f
V={"cor":svg_marca(),
   "preta":svg_marca(mono("#1c1c1c")),
   "branca":svg_marca(mono("#ffffff")),
   "negativo":svg_marca({**{c["id"]:(hx(cor_marca) if (c is fundo or lum(c["rgb"])<128) else "#ffffff") for c in camadas},"texto":"#ffffff"},bg=hx(cor_marca)),
   "borda":svg_marca(stroke=("#ffffff",max(4,0.03*H)))}
for k,v in V.items():open(f"{OUT}/marca-{k}.svg","w").write(v)
# 6b. logo recortado (forma fechada numa foto): a marca é o recorte inteiro; versões de uma cor exigem o arquivo original
RASTER=sys.argv[5] if len(sys.argv)>5 and os.path.exists(sys.argv[5]) else None
if RASTER:
    rb=base64.b64encode(open(RASTER,'rb').read()).decode();rw,rh=cv2.imread(RASTER,cv2.IMREAD_UNCHANGED).shape[1::-1]
    RSVG=lambda extra="":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {rw} {rh}">{extra}<image href="data:image/png;base64,{rb}" width="{rw}" height="{rh}"/></svg>'
    V={"cor":RSVG(),"borda":RSVG(f'<circle cx="{rw/2}" cy="{rh/2}" r="{rw/2*0.985}" fill="#fff" stroke="#fff" stroke-width="{rw*0.05}"/>')}
    for k in ("marca-preta.svg","marca-branca.svg","marca-negativo.svg"):
        try:os.remove(f"{OUT}/{k}")
        except:pass
    for k,v in V.items():open(f"{OUT}/marca-{k}.svg","w").write(v)
# 7. cores por material -----------------------------------------------------
tab=[]
for c in camadas:
    k=kapazi(c["rgb"]);tab.append(dict(hex=c["hex"],area=round(c["area"]*100),bobina=k["nome"],bobina_hex=k["hex"],cmyk=cmyk(c["rgb"]),papel="papel branco" if lum(c["rgb"])>235 else "vinil "+k["nome"].lower()))
# 8. medidas: traço mais fino (distância de transformada) → tamanho mínimo
dt=cv2.distanceTransform(fg.astype(np.uint8),cv2.DIST_L2,3);thin=float(np.percentile(dt[fg],15))*2  # px no vetor
minw={"impresso (1 mm)":round(W/thin*1/10,1),"vinil (2 mm)":round(W/thin*2/10,1),"capacho (8 mm)":round(W/thin*8/10,1)}  # largura mínima em cm
tel=L.get("tel",{}).get("valor","");end=L.get("endereco",{}).get("valor","");serv=L.get("servicos",{}).get("valor","");slogan=L.get("slogan",{}).get("valor","");reg=L.get("registro",{}).get("valor","")
# 9. aplicações (SVG com a marca embutida) ----------------------------------
def emb(svg):return "data:image/svg+xml;base64,"+base64.b64encode(svg.encode()).decode()
MC=emb(V["cor"]);MB=emb(V.get("branca",V["cor"]));MN=emb(V.get("negativo",V["cor"]));MP=emb(V.get("preta",V["cor"]))
cm=hx(cor_marca);esc=lum(cor_marca)<140;txtc="#f4f4f1" if esc else "#1c1c1c"
bob=kapazi(cor_marca)
def img(h,x,y,w,hh):return '<image href="%s" x="%d" y="%d" width="%d" height="%d" preserveAspectRatio="xMidYMid meet"/>'%(h,x,y,w,hh)
F='font-family="Rubik,system-ui,sans-serif"'
AP={
 "Capacho 90 × 60 · fundo na cor da marca":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 300"><rect width="450" height="300" fill="{bob["hex"]}"/><rect x="12" y="12" width="426" height="276" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="14"/>{img(MB if esc else MP,75,60,300,160)}<text x="225" y="262" text-anchor="middle" {F} font-weight="600" font-size="16" fill="{txtc}" letter-spacing="3">BEM-VINDO</text></svg>',
 "Capacho 90 × 60 · fundo Preto 03":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 300"><rect width="450" height="300" fill="#2b2b2d"/><rect x="12" y="12" width="426" height="276" fill="none" stroke="#111" stroke-width="14"/>{img(MC,75,50,300,200)}</svg>',
 "Placa de recepção 40 × 30":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 300"><rect width="450" height="300" fill="#e9e9e4"/><rect x="60" y="40" width="330" height="220" rx="6" fill="#fffefa" stroke="#c9c9c3"/>{img(MC,100,60,250,120)}<line x1="105" y1="200" x2="345" y2="200" stroke="{cm}" stroke-width="3"/><text x="225" y="236" text-anchor="middle" {F} font-size="13" fill="#6b6578">{serv or "atendimento"}</text></svg>',
 "Cartão de visita 9 × 5 · frente":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 300"><rect width="450" height="300" fill="#e9e9e4"/><rect x="45" y="60" width="360" height="200" rx="8" fill="#fffefa" stroke="#c9c9c3"/>{img(MC,65,80,150,90)}<text x="240" y="110" {F} font-weight="700" font-size="15" fill="#1c1c1c">{NOME}</text><text x="240" y="132" {F} font-size="11" fill="#6b6578">{slogan}</text><text x="240" y="170" {F} font-weight="600" font-size="13" fill="#1c1c1c">{tel or "telefone"}</text><text x="240" y="190" {F} font-size="11" fill="#6b6578">{end or "endereço"}</text><text x="240" y="210" {F} font-size="11" fill="{cm}">{reg}</text></svg>',
 "Cartão de visita · verso":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 300"><rect width="450" height="300" fill="#e9e9e4"/><rect x="45" y="60" width="360" height="200" rx="8" fill="{cm}"/>{img(MB if esc else MP,120,95,210,130)}</svg>',
 "Panfleto A5":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 424"><rect width="300" height="424" fill="#fffefa"/><rect width="300" height="150" fill="{cm}"/>{img(MB if esc else MP,50,25,200,100)}<text x="150" y="200" text-anchor="middle" {F} font-weight="700" font-size="22" fill="#1c1c1c">{serv.split("·")[0].strip() if serv else NOME}</text><text x="150" y="228" text-anchor="middle" {F} font-size="12" fill="#6b6578">{slogan}</text><rect x="90" y="260" width="120" height="4" fill="{cm}"/><text x="150" y="310" text-anchor="middle" {F} font-weight="700" font-size="20" fill="#1c1c1c">{tel or "telefone"}</text><text x="150" y="336" text-anchor="middle" {F} font-size="12" fill="#6b6578">{end or "endereço"}</text></svg>',
 "Adesivo de vitrine":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 424"><defs><linearGradient id="v" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a3340"/><stop offset="1" stop-color="#5b6b7c"/></linearGradient></defs><rect width="300" height="424" fill="url(#v)"/>{img(MB,40,90,220,180)}<text x="150" y="330" text-anchor="middle" {F} font-size="13" fill="#f4f4f1">{tel or "telefone"}</text></svg>',
 "Camiseta":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 424"><rect width="300" height="424" fill="#ebe3f5"/><g transform="translate(10 60) scale(.62)"><path d="M75 70 L115 50 Q150 75 185 50 L225 70 L260 125 L220 145 L220 330 L80 330 L80 145 L40 125 Z" fill="#1c1c1c"/>{img(MB,150,120,60,40)}</g><g transform="translate(150 60) scale(.62)"><path d="M75 70 L115 50 Q150 60 185 50 L225 70 L260 125 L220 145 L220 330 L80 330 L80 145 L40 125 Z" fill="#1c1c1c"/>{img(MB,85,150,130,90)}</g><text x="68" y="300" text-anchor="middle" {F} font-size="11" fill="#6b6578">frente · peito 8 cm</text><text x="232" y="300" text-anchor="middle" {F} font-size="11" fill="#6b6578">costas · 18 cm</text></svg>',
 "Banner 100 × 70":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 315"><rect width="450" height="315" fill="#fffefa" stroke="#c9c9c3"/>{img(MC,100,30,250,150)}<rect x="0" y="240" width="450" height="75" fill="{cm}"/><text x="225" y="285" text-anchor="middle" {F} font-weight="700" font-size="24" fill="{txtc}">{tel or "telefone"}</text></svg>',
}
# 10. manual HTML -----------------------------------------------------------
_o=cv2.imread(LOGO);_sc=min(1,700/max(_o.shape[:2]));_o=cv2.resize(_o,None,fx=_sc,fy=_sc) if _sc<1 else _o;orig=base64.b64encode(cv2.imencode(".jpg",_o,[cv2.IMWRITE_JPEG_QUALITY,80])[1]).decode();ext="jpeg"
st=lambda e:{"encontrado":"enc","porta":"conf","derivado":"der","confirmado":"conf","nao":"der"}.get(e,"pen")
rows="".join(f'<tr><td>{k}</td><td><span class="st {st(v.get("estado"))}">{v.get("estado","pendente")}</span></td><td>{(v.get("nome") or v.get("valor") or "")[:90] if not str(v.get("valor","")).startswith(("data:","clientes/")) else "arquivo"}</td></tr>' for k,v in L.items())
quadro=lambda svg,leg,bg="#fff":f'<div class="q" style="background:{bg}"><img src="{emb(svg)}" alt=""><small>{leg}</small></div>'
html=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Manual {NOME}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;600;700;800&display=swap">
<style>body{{margin:0;background:#fffefa;color:#1c1635;font:15px/1.5 Rubik,system-ui,sans-serif;padding:24px 16px 60px}}.w{{max-width:1040px;margin:0 auto;display:grid;gap:28px}}h1{{font-size:clamp(26px,5vw,36px);margin:0}}h1 i{{font-style:normal;color:#6933c5}}h2{{font-size:20px;margin:0 0 6px}}.sub{{color:#6b6578;margin:4px 0 0}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}}.q{{border:1px solid #d8ccea;border-radius:14px;padding:14px;display:grid;place-items:center;min-height:150px;position:relative}}.q img{{max-width:100%;max-height:170px}}.q small{{position:absolute;left:10px;bottom:6px;font-size:11px;color:#6b6578;font-weight:600}}
.cores{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}.c{{border:1px solid #d8ccea;border-radius:14px;overflow:hidden}}.c .sw{{height:56px}}.c .t{{padding:8px 12px;font-size:13px}}.c b{{display:block}}.c span{{color:#6b6578}}
.apl{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;align-items:start}}.ap{{background:#ebe3f5;border-radius:16px;overflow:hidden}}.ap img{{width:100%;display:block}}.ap b{{display:block;padding:8px 12px 10px;font-size:14px}}
table{{border-collapse:collapse;width:100%}}td{{padding:6px 8px;border-bottom:1px solid #d8ccea;font-size:13px;vertical-align:top}}.st{{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600;color:#fff}}.st.enc{{background:#1f5fa8}}.st.conf{{background:#1e8e5a}}.st.der{{background:#6933c5}}.st.pen{{background:#c8552b}}
.kpi{{display:flex;gap:10px;flex-wrap:wrap}}.kpi div{{background:#ebe3f5;border-radius:12px;padding:8px 12px;font-size:13px}}.kpi b{{display:block;font-size:18px}}ul{{margin:0;padding-left:20px}}li{{margin:3px 0}}</style></head><body><div class="w">
<header><div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#6b6578;font-weight:600">GenIO · manual de identidade inicial · gerado por programa, sem IA</div><h1>{NOME} · <i>manual de identidade</i></h1>
<p class="sub">{"A marca é o disco inteiro: recortado da foto do cadastro, com tudo que está dentro; nada foi redesenhado." if RASTER else "Marca reconstruída em vetor por camadas de cor a partir do arquivo do cadastro; nada foi redesenhado."} Dados públicos entram como encontrados; o que falta fica pendente.</p></header>
<section><div class="kpi">{"" if RASTER else f'<div><b>{fid:.2f}</b>fidelidade (SSIM)</div><div><b>{iou:.2f}</b>cobertura (IoU)</div><div><b>{"ok" if fid>=fid_m else "VERIFICAR"}</b>orientação</div>'}<div><b>{len(camadas)}</b>cores</div><div><b>{round(time.time()-T0,1)} s</b>tempo</div><div><b>{" ".join(palavras) or "—"}</b>texto lido (OCR)</div></div></section>
<section><h2>A marca: original e tratada</h2><div class="g" style="grid-template-columns:1fr 1fr">{quadro(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W0} {H0}"><image href="data:image/{ext};base64,{orig}" width="{W0}" height="{H0}"/></svg>',"original (cadastro)")}{quadro(V["cor"],"recorte do disco, fundo transparente" if RASTER else "vetor por camadas")}</div></section>
<section><h2>Versões</h2><div class="g">{quadro(V["cor"],"cor")}{quadro(V["preta"],"uma cor · preta") if "preta" in V else ""}{quadro(V["branca"],"uma cor · branca","#1c1c1c") if "branca" in V else ""}{quadro(V["negativo"],"negativo sobre a cor da marca") if "negativo" in V else ""}{quadro(V["borda"],"com borda branca (fundo de foto)","#777")}</div>{"<p class=sub><b>Versões de uma cor (preta, branca, negativo):</b> pendentes — a marca veio de foto; saem do arquivo original do cliente (pedir na porta).</p>" if RASTER else ""}
<ul><li><b>Tamanho mínimo</b> (pelo traço mais fino, {thin:.0f} px no vetor): impresso {minw["impresso (1 mm)"]} cm · vinil {minw["vinil (2 mm)"]} cm · capacho {minw["capacho (8 mm)"]} cm de largura.</li><li><b>Respiro:</b> 10% da largura da marca em volta.</li><li><b>Não fazer:</b> esticar, girar, mudar as cores das camadas, aplicar degradê, recortar o fundo da marca quando ele faz parte dela.</li></ul></section>
<section><h2>Cores por material</h2><div class="cores">{"".join(f'<div class="c"><div class="sw" style="background:{t["hex"]}"></div><div class="t"><b>{t["hex"]} · {t["area"]}% da marca</b><span>capacho: <b style="display:inline">{t["bobina"]}</b> · impressão: {t["cmyk"]} · {t["papel"]}</span></div></div>' for t in tab)}</div></section>
<section><h2>Aplicações</h2><div class="apl">{"".join(f'<div class="ap"><img src="{emb(s)}" alt=""><b>{k}</b></div>' for k,s in AP.items())}</div></section>
<section><h2>Lacunas do cadastro</h2><table>{rows}</table></section>
</div></body></html>'''
open(f"{OUT}/manual.html","w").write(html)
json.dump(dict(fidelidade=fid,iou=iou,espelho=fid_m,cores=tab,camadas=len(camadas),ocr=palavras,minimo_cm=minw,tempo_s=round(time.time()-T0,1)),open(f"{OUT}/relatorio.json","w"),ensure_ascii=False,indent=1)
print(json.dumps(dict(fid=round(fid,3),iou=round(iou,3),espelho=round(fid_m,3),cores=[(t["hex"],t["bobina"],t["area"]) for t in tab],ocr=palavras,min=minw,s=round(time.time()-T0,1)),ensure_ascii=False))
