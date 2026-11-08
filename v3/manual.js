// GenIO — manual de identidade inicial: trata o logo (tira fundo, achata cores no catálogo, limpa detalhe que não sai no tapete),
// gera as versões (cor, mono escuro, mono claro, negativo, horizontal, vertical) e as aplicações nos formatos do app.
const Manual=(()=>{
  const CAT=[["cinza","Cinza","#9a9b9d"],["grafite","Grafite","#55575c"],["preto03","Preto 03","#2b2b2d"],["marrom","Marrom","#4a2f22"],["bege","Bege","#c4a979"],["ouro","Ouro Carajás","#c98d2b"],["branco","Branco","#eeede8"],["amarelo08","Amarelo 08","#f2c21b"],["laranja","Laranja","#ee6a1d"],["vermelho","Vermelho","#c8232c"],["vinho","Bordô","#6e1f27"],["marinho","Azul Marinho","#1f2a52"],["azul","Azul Royal","#1f4fae"],["verdemusgo","Verde Musgo","#5c6332"],["verde","Verde Bandeira","#1c7a3a"]];
  const hex2=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];
  const PAL=CAT.map(([id,nome,hex])=>({id,nome,hex,rgb:hex2(hex)}));
  const cdist=(a,b)=>{const dr=a[0]-b[0],dg=a[1]-b[1],db=a[2]-b[2];return Math.sqrt((2*dr*dr+4*dg*dg+3*db*db)/9);};
  const chroma=c=>Math.max(c[0],c[1],c[2])-Math.min(c[0],c[1],c[2]);
  const keyDist=(c,bg)=>cdist(c,bg)+0.8*Math.abs(chroma(c)-chroma(bg));
  function hsl(rgb){const r=rgb[0]/255,g=rgb[1]/255,b=rgb[2]/255,mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2,d=mx-mn;let h=0,s=0;if(d>0){s=d/(1-Math.abs(2*l-1));h=mx===r?((g-b)/d+(g<b?6:0)):mx===g?((b-r)/d+2):((r-g)/d+4);h*=60;}return {h,s,l,c:d*255};}
  // bobina mais parecida: tom primeiro, depois brilho e saturação; cinzas pela distância simples
  function rank(rgb){const a=hsl(rgb);if(a.c<9)return PAL.map(p=>({p,d:cdist(rgb,p.rgb)*0.6})).sort((x,y)=>x.d-y.d);
    return PAL.map(p=>{const b=hsl(p.rgb);let dh=Math.abs(a.h-b.h);dh=Math.min(dh,360-dh);if(b.c<9)dh=90;return {p,d:dh+50*Math.abs(a.l-b.l)+30*Math.abs(a.s-b.s)};}).sort((x,y)=>x.d-y.d);}
  const load=src=>new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=src;});
  function cv(w,h){const c=document.createElement("canvas");c.width=w;c.height=h;return c;}
  // ---------- 1. tratamento ----------
  async function tratar(src,opts){opts=opts||{};const img=await load(src);const k=Math.min(1,900/Math.max(img.width,img.height)),w=Math.round(img.width*k),h=Math.round(img.height*k);
    const c=cv(w,h),x=c.getContext("2d");x.drawImage(img,0,0,w,h);const im=x.getImageData(0,0,w,h),d=im.data,n=w*h;
    // transparência do arquivo vale como recorte; senão, fundo = cor mais comum da borda
    let A=new Float32Array(n),transp=false;{let tr=0;for(let i=3;i<d.length;i+=16)if(d[i]<128)tr++;transp=tr>n/4*0.02;}
    let bg=null;
    if(transp){for(let i=0;i<n;i++)A[i]=d[i*4+3]/255;}
    else{const b=Math.max(2,Math.round(Math.min(w,h)*0.03)),bins=new Map();
      for(let y=0;y<h;y+=2)for(let xx=0;xx<w;xx+=2){if(xx>=b&&xx<w-b&&y>=b&&y<h-b)continue;const i=(y*w+xx)*4,kk=((d[i]>>5)<<6)|((d[i+1]>>5)<<3)|(d[i+2]>>5);const e=bins.get(kk)||{n:0,r:0,g:0,b:0};e.n++;e.r+=d[i];e.g+=d[i+1];e.b+=d[i+2];bins.set(kk,e);}
      let best=null;bins.forEach(e=>{if(!best||e.n>best.n)best=e;});bg=[Math.round(best.r/best.n),Math.round(best.g/best.n),Math.round(best.b/best.n)];
      const H=new Float64Array(256);let tot=0;for(let i=0;i<n;i+=2){H[Math.min(255,Math.round(keyDist([d[i*4],d[i*4+1],d[i*4+2]],bg)))]++;tot++;}
      let sum=0;for(let i=0;i<256;i++)sum+=i*H[i];let sb=0,wb=0,bv=0,thr=60;for(let t=0;t<256;t++){wb+=H[t];if(!wb)continue;const wf=tot-wb;if(!wf)break;sb+=t*H[t];const mb=sb/wb,mf=(sum-sb)/wf,v=wb*wf*(mb-mf)**2;if(v>bv){bv=v;thr=t;}}
      const tol=opts.tol||Math.max(18,Math.min(55,Math.round(thr*0.7))),soft=Math.max(3,Math.round(tol*0.15));
      for(let i=0;i<n;i++){const dd=keyDist([d[i*4],d[i*4+1],d[i*4+2]],bg);A[i]=Math.max(0,Math.min(1,(dd-(tol-soft))/(2*soft)));}}
    // limpeza: tira pontinhos (componentes com menos de 0,15% da área) — detalhe que não sai no capacho
    const lab=new Int32Array(n).fill(-1);let nl=0;const sizes=[];const st=[];
    for(let i=0;i<n;i++){if(A[i]<0.5||lab[i]>=0)continue;let sz=0;st.push(i);lab[i]=nl;while(st.length){const p=st.pop();sz++;const px=p%w,py=(p/w)|0;for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const qx=px+dx,qy=py+dy;if(qx<0||qy<0||qx>=w||qy>=h)continue;const q=qy*w+qx;if(A[q]>=0.5&&lab[q]<0){lab[q]=nl;st.push(q);}}}sizes.push(sz);nl++;}
    const minSz=Math.max(12,n*0.0015);for(let i=0;i<n;i++)if(lab[i]>=0&&sizes[lab[i]]<minSz)A[i]=0;
    // cores: k-means (até 4) sobre pixels firmes + traços finos; junta parecidas; mapeia no catálogo (tom primeiro, cores distintas)
    const pts=[];for(let i=0;i<n;i++){if(A[i]<0.9)continue;const px=i%w,py=(i/w)|0;let core=true;for(const q of [i-1,i+1,i-w,i+w]){if(q<0||q>=n||A[q]<0.9){core=false;break;}}if(core||A[i]>=0.995)pts.push([d[i*4],d[i*4+1],d[i*4+2]]);}
    const S=[];const step=Math.max(1,Math.floor(pts.length/10000));for(let i=0;i<pts.length;i+=step)S.push(pts[i]);
    let C=S.length?[S[0]]:[[0,0,0]];const K=opts.maxCores||4;
    while(C.length<K){let far=null,fd=-1;for(let j=0;j<S.length;j+=5){const dd=Math.min(...C.map(c=>cdist(c,S[j])));if(dd>fd){fd=dd;far=S[j];}}if(fd<18)break;C.push(far.slice());}
    for(let it=0;it<10;it++){const acc=C.map(()=>[0,0,0,0]);S.forEach(p=>{let bi=0,bd=1e9;C.forEach((c,i)=>{const dd=cdist(c,p);if(dd<bd){bd=dd;bi=i;}});const a=acc[bi];a[0]+=p[0];a[1]+=p[1];a[2]+=p[2];a[3]++;});C=C.map((c,i)=>acc[i][3]?[acc[i][0]/acc[i][3],acc[i][1]/acc[i][3],acc[i][2]/acc[i][3]]:c);}
    let groups=C.map((c,i)=>({rgb:c,n:0}));S.forEach(p=>{let bi=0,bd=1e9;C.forEach((c,i)=>{const dd=cdist(c,p);if(dd<bd){bd=dd;bi=i;}});groups[bi].n++;});
    groups=groups.filter(g=>g.n>0).sort((a,b)=>b.n-a.n);
    let merged=true;while(merged){merged=false;outer:for(let i=0;i<groups.length;i++)for(let j=i+1;j<groups.length;j++)if(cdist(groups[i].rgb,groups[j].rgb)<48){const a=groups[i],b=groups[j],t=a.n+b.n;a.rgb=a.rgb.map((v,k2)=>(v*a.n+b.rgb[k2]*b.n)/t);a.n=t;groups.splice(j,1);merged=true;break outer;}}
    const tot2=groups.reduce((s,g)=>s+g.n,0);groups=groups.filter((g,i)=>i===0||g.n/tot2>=0.02).slice(0,K);
    const used=new Set();const cores=groups.map(g=>{const r=rank(g.rgb);const pick=r.find(x=>!used.has(x.p.id)&&x.d<r[0].d+30)||r.find(x=>!used.has(x.p.id))||r[0];used.add(pick.p.id);return {orig:g.rgb.map(Math.round),cat:pick.p,n:g.n};});
    // rótulo por pixel e logo achatado (transparente)
    const out=cv(w,h),od=out.getContext("2d").createImageData(w,h),o=od.data;const cc=groups.map(g=>g.rgb);
    for(let i=0;i<n;i++){if(A[i]<0.06)continue;const p=[d[i*4],d[i*4+1],d[i*4+2]];let bi=0,bd=1e9;cc.forEach((c,ii)=>{const dd=cdist(c,p);if(dd<bd){bd=dd;bi=ii;}});const col=cores[bi].cat.rgb;o[i*4]=col[0];o[i*4+1]=col[1];o[i*4+2]=col[2];o[i*4+3]=Math.round(A[i]*255);}
    out.getContext("2d").putImageData(od,0,0);
    // recorta nas bordas do conteúdo
    let x0=w,y0=h,x1=0,y1=0;for(let i=0;i<n;i++)if(A[i]>=0.5){const px=i%w,py=(i/w)|0;if(px<x0)x0=px;if(px>x1)x1=px;if(py<y0)y0=py;if(py>y1)y1=py;}
    const pad=Math.round(Math.max(x1-x0,y1-y0)*0.04);x0=Math.max(0,x0-pad);y0=Math.max(0,y0-pad);x1=Math.min(w-1,x1+pad);y1=Math.min(h-1,y1+pad);
    const crop=cv(x1-x0+1,y1-y0+1);crop.getContext("2d").drawImage(out,x0,y0,crop.width,crop.height,0,0,crop.width,crop.height);
    const fundo=bg&&!transp?rank(bg)[0].p:null;
    return {tratado:crop,cores,fundo,bg,transp};}
  // ---------- 2. versões ----------
  function recolor(c,hex){const o=cv(c.width,c.height),x=o.getContext("2d");x.drawImage(c,0,0);x.globalCompositeOperation="source-in";x.fillStyle=hex;x.fillRect(0,0,o.width,o.height);return o;}
  function negativo(c,hexBox,hexLogo){const pad=Math.round(Math.max(c.width,c.height)*0.12),o=cv(c.width+2*pad,c.height+2*pad),x=o.getContext("2d");x.fillStyle=hexBox;x.beginPath();x.roundRect(0,0,o.width,o.height,pad*0.5);x.fill();x.drawImage(recolor(c,hexLogo),pad,pad);return o;}
  function lockup(c,nome,vertical,hexText){const fs=vertical?Math.round(c.width*0.11):Math.round(c.height*0.42);const t=cv(10,10).getContext("2d");t.font=`800 ${fs}px Rubik, sans-serif`;const tw=Math.ceil(t.measureText(nome).width);
    const gap=Math.round(fs*0.6);const o=vertical?cv(Math.max(c.width,tw)+2,c.height+gap+fs*1.3):cv(c.width+gap+tw+2,Math.max(c.height,fs*1.3));const x=o.getContext("2d");x.font=`800 ${fs}px Rubik, sans-serif`;x.fillStyle=hexText;x.textBaseline="middle";
    if(vertical){x.drawImage(c,(o.width-c.width)/2,0);x.textAlign="center";x.fillText(nome,o.width/2,c.height+gap+fs*0.65);}else{x.drawImage(c,0,(o.height-c.height)/2);x.textAlign="left";x.fillText(nome,c.width+gap,o.height/2);}return o;}
  function versoes(t,nome){const esc="#1C1635",cla="#FFFEFA",dark=t.cores.length&&hsl(t.cores[0].cat.rgb).l<0.45;
    return {cor:t.tratado,monoEscuro:recolor(t.tratado,"#2b2b2d"),monoClaro:recolor(t.tratado,"#eeede8"),
      negativo:negativo(t.tratado,(t.cores[0]&&hsl(t.cores[0].cat.rgb).l<0.6?t.cores[0].cat.hex:(t.fundo&&hsl(t.fundo.rgb).l<0.6?t.fundo.hex:"#2b2b2d")),"#eeede8"),
      horizontal:lockup(t.tratado,nome,false,esc),vertical:lockup(t.tratado,nome,true,esc),horizontalClaro:lockup(recolor(t.tratado,"#eeede8"),nome,false,"#eeede8"),
      fundoClaro:cla,fundoEscuro:esc,logoEscuro:dark};}
  // ---------- 3. aplicações (mockups nos formatos do app) ----------
  function fit(x,c,bx,by,bw,bh){const k=Math.min(bw/c.width,bh/c.height),w=c.width*k,h=c.height*k;x.drawImage(c,bx+(bw-w)/2,by+(bh-h)/2,w,h);}
  function aplicacoes(t,V,nome,tel){const A={},fundoHex=(t.fundo||PAL[2]).hex,fundoEsc=hsl((t.fundo||PAL[2]).rgb).l<0.5;const logoNoFundo=fundoEsc&&V.logoEscuro?V.monoClaro:V.cor;
    // capacho 90×60 (paisagem) com borda
    {const o=cv(900,600),x=o.getContext("2d");x.fillStyle=fundoHex;x.fillRect(0,0,900,600);x.strokeStyle="rgba(0,0,0,.25)";x.lineWidth=28;x.strokeRect(14,14,872,572);fit(x,logoNoFundo,120,100,660,400);
      // textura de vinil (pontilhado leve)
      x.fillStyle="rgba(255,255,255,.06)";for(let i=0;i<900;i+=6)for(let j=0;j<600;j+=6)if((i+j)%12===0)x.fillRect(i,j,2,2);A.capacho=o;}
    // placa 40×30 (paisagem), fundo claro
    {const o=cv(800,600),x=o.getContext("2d");x.fillStyle="#FFFEFA";x.fillRect(0,0,800,600);x.strokeStyle="#D8CCEA";x.lineWidth=6;x.strokeRect(3,3,794,594);fit(x,V.cor,100,60,600,330);x.fillStyle="#1C1635";x.font="700 44px Rubik, sans-serif";x.textAlign="center";x.fillText(nome,400,470);x.font="500 26px Rubik, sans-serif";x.fillStyle="#6B6578";x.fillText("Recepção",400,520);A.placa=o;}
    // cartão de visita 9×5 (paisagem) frente e verso
    {const o=cv(900,500),x=o.getContext("2d");x.fillStyle="#FFFEFA";x.fillRect(0,0,900,500);fit(x,V.cor,60,60,330,380);x.fillStyle="#1C1635";x.font="800 40px Rubik, sans-serif";x.textAlign="left";x.fillText(nome,430,210);x.font="500 26px Rubik, sans-serif";x.fillStyle="#6B6578";x.fillText(tel||"(11) 00000-0000",430,262);x.fillStyle=fundoHex;x.fillRect(430,300,320,8);A.cartao=o;
      const v=cv(900,500),y=v.getContext("2d");y.fillStyle=fundoHex;y.fillRect(0,0,900,500);fit(y,fundoEsc?V.monoClaro:V.cor,250,100,400,300);A.cartaoVerso=v;}
    // panfleto A5 (retrato)
    {const o=cv(600,850),x=o.getContext("2d");x.fillStyle="#FFFEFA";x.fillRect(0,0,600,850);x.fillStyle=fundoHex;x.fillRect(0,0,600,300);fit(x,fundoEsc?V.monoClaro:V.cor,100,50,400,200);x.fillStyle="#1C1635";x.font="800 46px Rubik, sans-serif";x.textAlign="center";x.fillText(nome,300,390);x.font="500 24px Rubik, sans-serif";x.fillStyle="#6B6578";["Texto da oferta ou do serviço","em duas ou três linhas curtas."].forEach((s,i)=>x.fillText(s,300,450+i*34));x.fillStyle=fundoHex;x.fillRect(150,560,300,6);x.fillStyle="#1C1635";x.font="700 30px Rubik, sans-serif";x.fillText(tel||"(11) 00000-0000",300,640);x.font="500 20px Rubik, sans-serif";x.fillStyle="#6B6578";x.fillText("endereço · horário",300,690);A.panfleto=o;}
    // adesivo de vitrine (retrato): marca em branco sobre vidro
    {const o=cv(600,850),x=o.getContext("2d");const g=x.createLinearGradient(0,0,600,850);g.addColorStop(0,"#2a3340");g.addColorStop(1,"#5b6b7c");x.fillStyle=g;x.fillRect(0,0,600,850);x.fillStyle="rgba(255,255,255,.08)";x.fillRect(0,0,600,850);fit(x,V.monoClaro,80,230,440,300);x.fillStyle="#fff";x.font="700 26px Rubik, sans-serif";x.textAlign="center";x.fillText("horário · telefone",300,600);A.vitrine=o;}
    // camiseta (peito esquerdo) — retrato
    {const o=cv(600,700),x=o.getContext("2d");x.fillStyle="#EBE3F5";x.fillRect(0,0,600,700);x.fillStyle=fundoHex;x.beginPath();x.moveTo(150,120);x.lineTo(230,80);x.quadraticCurveTo(300,130,370,80);x.lineTo(450,120);x.lineTo(520,230);x.lineTo(440,270);x.lineTo(440,640);x.lineTo(160,640);x.lineTo(160,270);x.lineTo(80,230);x.closePath();x.fill();fit(x,fundoEsc?V.monoClaro:V.cor,330,200,90,70);A.camiseta=o;}
    // banner 100×70 (paisagem)
    {const o=cv(1000,700),x=o.getContext("2d");x.fillStyle=fundoHex;x.fillRect(0,0,1000,700);fit(x,fundoEsc?V.monoClaro:V.cor,120,80,760,330);x.fillStyle=fundoEsc?"#FFFEFA":"#1C1635";x.font="800 64px Rubik, sans-serif";x.textAlign="center";x.fillText(nome,500,520);x.font="500 32px Rubik, sans-serif";x.fillText(tel||"(11) 00000-0000",500,590);A.banner=o;}
    return A;}
  // ---------- 4. o manual inteiro ----------
  async function gerar(src,nome,tel,opts){try{await document.fonts.load("800 20px Rubik");}catch(_){}
    const t=await tratar(src,opts),V=versoes(t,nome),A=aplicacoes(t,V,nome,tel);
    const png=c=>c.toDataURL("image/png");
    return {cores:t.cores.map(c=>({id:c.cat.id,nome:c.cat.nome,hex:c.cat.hex,orig:c.orig})),fundo:t.fundo?{id:t.fundo.id,nome:t.fundo.nome,hex:t.fundo.hex}:null,
      versoes:{cor:png(V.cor),monoEscuro:png(V.monoEscuro),monoClaro:png(V.monoClaro),negativo:png(V.negativo),horizontal:png(V.horizontal),vertical:png(V.vertical),horizontalClaro:png(V.horizontalClaro)},
      aplicacoes:Object.fromEntries(Object.entries(A).map(([k,c])=>[k,c.toDataURL("image/jpeg",0.88)])),tratado:png(V.cor),geradoEm:new Date().toISOString()};}
  return {gerar,PAL,tratar};
})();
