# GenIO v3 — recorte do logo que é uma forma fechada (disco) numa foto: acha o círculo, corta, fundo transparente. Sem IA.
import sys,math,json,numpy as np,cv2
src,out=sys.argv[1],sys.argv[2]
im=cv2.imread(src);H,W=im.shape[:2]
lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB).astype(float)
# fundo = cor dominante da borda; logo = o que difere do fundo (Otsu)
b=np.concatenate([lab[:8].reshape(-1,3),lab[-8:].reshape(-1,3),lab[:,:8].reshape(-1,3),lab[:,-8:].reshape(-1,3)])
bg=np.median(b,axis=0);D=np.linalg.norm(lab-bg,axis=2);Dn=np.clip(D/D.max()*255,0,255).astype(np.uint8)
Db=np.linalg.norm(b-bg,axis=1);mad=float(np.median(np.abs(Db-np.median(Db))));tol=max(18.0,min(40.0,6*mad+8));fg=(D>tol).astype(np.uint8)
fg=cv2.morphologyEx(fg,cv2.MORPH_CLOSE,np.ones((15,15),np.uint8))
# maior componente = o logo; buracos internos preenchidos (o conteúdo escuro dentro do disco é logo)
n,lbl,st,_=cv2.connectedComponentsWithStats(fg,8);i=1+np.argmax(st[1:,cv2.CC_STAT_AREA]);m=(lbl==i).astype(np.uint8)
cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);c=max(cs,key=cv2.contourArea);cv2.drawContours(m,[c],-1,1,-1)
# círculo: ajuste por mínimos quadrados no contorno (robusto a lascas: usa só pontos perto da mediana do raio)
pts=c.reshape(-1,2).astype(float)
def fit(p):
    A=np.c_[2*p[:,0],2*p[:,1],np.ones(len(p))];bb=(p**2).sum(1);x=np.linalg.lstsq(A,bb,rcond=None)[0];cx,cy=x[0],x[1];return cx,cy,math.sqrt(x[2]+cx*cx+cy*cy)
cx,cy,r=fit(pts)
for _ in range(3):
    d=np.hypot(pts[:,0]-cx,pts[:,1]-cy);keep=np.abs(d-r)<0.06*r;cx,cy,r=fit(pts[keep])
circ=float(cv2.contourArea(c))/(math.pi*r*r)
# máscara circular com borda suave; recorte quadrado com 3% de respiro
mask=np.zeros((H,W),np.float32);cv2.circle(mask,(int(round(cx)),int(round(cy))),int(round(r)),1,-1);mask=cv2.GaussianBlur(mask,(0,0),1.2)
rgba=cv2.cvtColor(im,cv2.COLOR_BGR2BGRA);rgba[:,:,3]=(mask*255).astype(np.uint8)
p=int(r*1.03);x0,y0=int(round(cx))-p,int(round(cy))-p
canvas=np.zeros((2*p,2*p,4),np.uint8);sx0,sy0=max(0,x0),max(0,y0);sx1,sy1=min(W,x0+2*p),min(H,y0+2*p)
canvas[sy0-y0:sy1-y0,sx0-x0:sx1-x0]=rgba[sy0:sy1,sx0:sx1]
cv2.imwrite(out,canvas)
print(json.dumps(dict(centro=[round(cx),round(cy)],raio=round(r),circularidade=round(circ,3),tamanho=canvas.shape[:2])))
