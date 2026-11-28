/* GênIO · PDF de impressão feito no próprio aparelho (sem servidor e sem biblioteca de fora).
   Medidas em milímetros, a partir do canto de cima à esquerda. Fontes padrão do PDF (Helvetica), com acentos.
   Uso: const d=PDFMini.novo(216,303); d.ret(0,0,216,303,"#FFFFFF"); d.txt("Cardápio",12,24,28,{negrito:true}); d.baixar("cardapio.pdf");
   Peças prontas: PDFMini.cardapio({...}) e PDFMini.plaquinha({...}) — as duas já saem com 3 mm de sangria. */
(function(){
  const MM=72/25.4;
  const W=[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584];
  const WB=[278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584];
  const ESP={"•":0x95,"·":0xB7,"–":0x96,"—":0x97,"“":0x93,"”":0x94,"‘":0x91,"’":0x92,"…":0x85,"€":0x80,"×":0xD7,"º":0xBA,"ª":0xAA,"°":0xB0};
  const semAcento=c=>c.normalize("NFD").replace(/[̀-ͯ]/g,"");
  function largura(s,tam,negrito){const T=negrito?WB:W;let w=0;for(const ch of String(s)){const b=semAcento(ch).charCodeAt(0);w+=(b>=32&&b<=126)?T[b-32]:(ESP[ch]?350:556);}return w*tam/1000/MM;}   // em mm; tam em pontos
  function bytes(s){const o=[];for(const ch of String(s)){let c=ch.charCodeAt(0);if(ESP[ch])c=ESP[ch];else if(c>255)c=63;if(c===40||c===41||c===92)o.push(92);o.push(c);}return o;}
  const rgb=h=>{h=String(h||"#000").replace("#","");if(h.length===3)h=h.split("").map(x=>x+x).join("");return [0,2,4].map(i=>(parseInt(h.slice(i,i+2),16)/255).toFixed(3)).join(" ");};
  const n=v=>(Math.round(v*100)/100).toString();
  function novo(wmm,hmm){
    const pags=[];const imgs=[];let cur=null;
    const pagina=()=>{cur=[];pags.push(cur);};pagina();
    const Y=y=>(hmm-y)*MM;
    const put=s=>{for(let i=0;i<s.length;i++)cur.push(s.charCodeAt(i)&255);};
    const d={w:wmm,h:hmm,largura,
      pagina,
      ret(x,y,w,h,cor){put(`${rgb(cor)} rg ${n(x*MM)} ${n(Y(y+h))} ${n(w*MM)} ${n(h*MM)} re f\n`);return d;},
      retArr(x,y,w,h,r,cor){const k=.5523*r*MM,X=x*MM,T=Y(y),B=Y(y+h),R=(x+w)*MM,rr=r*MM;put(`${rgb(cor)} rg ${n(X+rr)} ${n(T)} m ${n(R-rr)} ${n(T)} l ${n(R-rr+k)} ${n(T)} ${n(R)} ${n(T-rr+k)} ${n(R)} ${n(T-rr)} c ${n(R)} ${n(B+rr)} l ${n(R)} ${n(B+rr-k)} ${n(R-rr+k)} ${n(B)} ${n(R-rr)} ${n(B)} c ${n(X+rr)} ${n(B)} l ${n(X+rr-k)} ${n(B)} ${n(X)} ${n(B+rr-k)} ${n(X)} ${n(B+rr)} c ${n(X)} ${n(T-rr)} l ${n(X)} ${n(T-rr+k)} ${n(X+rr-k)} ${n(T)} ${n(X+rr)} ${n(T)} c f\n`);return d;},
      linha(x1,y1,x2,y2,esp,cor,traco){put(`${rgb(cor)} RG ${n(esp*MM)} w ${traco?`[${n(traco*MM)} ${n(traco*MM)}] 0 d`:"[] 0 d"} ${n(x1*MM)} ${n(Y(y1))} m ${n(x2*MM)} ${n(Y(y2))} l S\n`);return d;},
      /* y = linha de base do texto; o.alinha: "e" (padrão), "c" ou "d" */
      txt(s,x,y,tam,o){o=o||{};s=String(s);const lw=largura(s,tam,o.negrito);const X=o.alinha==="c"?x-lw/2:o.alinha==="d"?x-lw:x;
        put(`BT /${o.negrito?"F2":"F1"} ${n(tam)} Tf ${rgb(o.cor||"#000")} rg ${n(X*MM)} ${n(Y(y))} Td (`);for(const b of bytes(s))cur.push(b);put(`) Tj ET\n`);return lw;},
      /* quebra em linhas para caber em larg (mm); devolve as linhas */
      quebrar(s,tam,larg,negrito){const out=[];let l="";for(const p of String(s).split(/\s+/)){const t=l?l+" "+p:p;if(largura(t,tam,negrito)<=larg||!l)l=t;else{out.push(l);l=p;}}if(l)out.push(l);return out;},
      /* imagem JPEG (dataURL) */
      img(dataURL,x,y,w,h,pxW,pxH){const b=atob(String(dataURL).split(",")[1]);const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);imgs.push({u,pxW,pxH});
        put(`q ${n(w*MM)} 0 0 ${n(h*MM)} ${n(x*MM)} ${n(Y(y+h))} cm /Im${imgs.length} Do Q\n`);return d;},
      bytes(){const partes=[];let pos=0;const off=[];const S=s=>{const u=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i)&255;partes.push(u);pos+=u.length;};const U=u=>{partes.push(u);pos+=u.length;};
        const obj=(i,corpo)=>{off[i]=pos;S(`${i} 0 obj\n`);corpo();S(`\nendobj\n`);};
        S("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
        const nP=pags.length,nI=imgs.length;const idPag=i=>5+i*2,idCont=i=>6+i*2,idImg=i=>5+nP*2+i;
        obj(1,()=>S(`<< /Type /Catalog /Pages 2 0 R >>`));
        obj(2,()=>S(`<< /Type /Pages /Count ${nP} /Kids [${pags.map((_,i)=>idPag(i)+" 0 R").join(" ")}] >>`));
        obj(3,()=>S(`<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>`));
        obj(4,()=>S(`<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>`));
        const xo=nI?`/XObject << ${imgs.map((_,i)=>`/Im${i+1} ${idImg(i)} 0 R`).join(" ")} >>`:"";
        pags.forEach((c,i)=>{obj(idPag(i),()=>S(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${n(wmm*MM)} ${n(hmm*MM)}] /TrimBox [${n(3*MM)} ${n(3*MM)} ${n((wmm-3)*MM)} ${n((hmm-3)*MM)}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> ${xo} >> /Contents ${idCont(i)} 0 R >>`));
          obj(idCont(i),()=>{S(`<< /Length ${c.length} >>\nstream\n`);U(new Uint8Array(c));S(`\nendstream`);});});
        imgs.forEach((im,i)=>obj(idImg(i),()=>{S(`<< /Type /XObject /Subtype /Image /Width ${im.pxW} /Height ${im.pxH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${im.u.length} >>\nstream\n`);U(im.u);S(`\nendstream`);}));
        const total=4+nP*2+nI;const xr=pos;S(`xref\n0 ${total+1}\n0000000000 65535 f \n`);for(let i=1;i<=total;i++)S(String(off[i]).padStart(10,"0")+" 00000 n \n");
        S(`trailer\n<< /Size ${total+1} /Root 1 0 R >>\nstartxref\n${xr}\n%%EOF\n`);
        const out=new Uint8Array(pos);let p=0;for(const u of partes){out.set(u,p);p+=u.length;}return out;},
      baixar(nome){const b=new Blob([d.bytes()],{type:"application/pdf"});const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=nome;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},2000);}};
    return d;}
  /* logotipo (qualquer formato que o navegador abra) → JPEG com fundo, para entrar no PDF */
  function logoJPEG(src,fundo){return new Promise(res=>{if(!src)return res(null);const im=new Image();im.crossOrigin="anonymous";im.onload=()=>{try{const m=Math.min(1,900/Math.max(im.naturalWidth,im.naturalHeight));const c=document.createElement("canvas");c.width=Math.max(1,Math.round(im.naturalWidth*m));c.height=Math.max(1,Math.round(im.naturalHeight*m));const g=c.getContext("2d");g.fillStyle=fundo||"#FFFFFF";g.fillRect(0,0,c.width,c.height);g.drawImage(im,0,0,c.width,c.height);res({url:c.toDataURL("image/jpeg",.92),w:c.width,h:c.height});}catch(e){res(null);}};im.onerror=()=>res(null);im.src=src;});}
  const SANGRIA=3;
  /* Cardápio A4 em pé (210×297 mm + 3 mm de sangria). secoes: [{titulo, itens:[{nome, preco, desc, apartir}]}]. Devolve o documento. */
  async function cardapio(o){const LW=210+2*SANGRIA,LH=297+2*SANGRIA,M=SANGRIA+12;const cor=o.cor||"#1C1635",claro="#6B6580";
    const secs=(o.secoes||[]).map(s=>({titulo:s.titulo||"",itens:(s.itens||[]).filter(i=>i&&i.nome)})).filter(s=>s.itens.length);
    const lg=await logoJPEG(o.logo,"#FFFFFF");const d=novo(LW,LH);
    const nIt=secs.reduce((a,s)=>a+s.itens.length,0);const col=nIt>18?2:1;const larg=(LW-2*M-(col-1)*10)/col;
    // tamanho da letra pelo volume: poucos itens, letra grande; muitos, menor (nunca abaixo de 9 pt)
    const tam=nIt<=8?19:nIt<=12?17:nIt<=18?14.5:nIt<=36?11.5:nIt<=56?10:9;const alt=tam*.62,entre=tam*.30,tit=tam*1.35;
    const cab=()=>{d.ret(0,0,LW,LH,"#FFFFFF");let y=M+4;
      if(lg){const h=22,w=Math.min(60,h*lg.w/lg.h);d.img(lg.url,M,M-2,w,h,lg.w,lg.h);d.txt(o.nome||"",M+w+6,M+8,20,{negrito:true,cor});d.txt("Cardápio",M+w+6,M+16,12,{cor:claro});y=M+26;}
      else{d.txt(o.nome||"Cardápio",M,M+8,24,{negrito:true,cor});d.txt("Cardápio",M,M+16,12,{cor:claro});y=M+22;}
      d.ret(M,y,LW-2*M,.9,cor);return y+9;};
    let y0=cab(),c=0,y=y0;const fim=LH-M-6;
    const prox=()=>{c++;if(c>=col){d.pagina();y0=cab();c=0;}y=y0;};
    for(const s of secs){
      const altSec=(s.titulo?tit*.62+3:0)+alt+entre;if(y+altSec>fim)prox();
      const x=M+c*(larg+10);
      if(s.titulo){d.txt(s.titulo,x,y+tit*.3,tit,{negrito:true,cor});y+=tit*.62+3;}
      for(const it of s.itens){const preco=it.preco?(it.apartir?"a partir de ":"")+"R$ "+it.preco:"";const pw=preco?d.largura(preco,tam,true)+3:0;
        const linhas=d.quebrar(it.nome,tam,larg-pw-4);const hItem=linhas.length*alt+(it.desc?tam*.5:0)+entre;
        if(y+hItem>fim){prox();}const xx=M+c*(larg+10);
        linhas.forEach((l,i)=>{const lw=d.txt(l,xx,y+alt*.72+i*alt,tam,{cor:"#141024"});
          if(i===linhas.length-1&&preco){d.txt(preco,xx+larg,y+alt*.72+i*alt,tam,{negrito:true,alinha:"d",cor:"#141024"});const a=xx+lw+1.5,b=xx+larg-pw+1;if(b-a>3)d.linha(a,y+alt*.72+i*alt-.4,b,y+alt*.72+i*alt-.4,.15,"#B9B2CC",.6);}});
        y+=linhas.length*alt;if(it.desc){d.txt(String(it.desc).slice(0,70),xx,y+tam*.36,tam*.78,{cor:claro});y+=tam*.5;}y+=entre;}
      y+=3;}
    return d;}
  /* Plaquinha de balcão A6 em pé (105×155 mm + 3 mm de sangria) com o QR da loja. o.qr = QR.matriz(url). */
  function plaquinha(o){const LW=105+2*SANGRIA,LH=155+2*SANGRIA;const d=novo(LW,LH);const cor=o.cor||"#49258B";const cx=LW/2;
    d.ret(0,0,LW,LH,"#FFFFFF");
    const t1=o.agenda?"Agende o seu horário":"Fale com o gerente";const t2=o.agenda?"ou fale com o gerente":"Elogio, sugestão, reclamação ou dúvida";
    d.txt(t1,cx,SANGRIA+24,o.agenda?21:23,{negrito:true,alinha:"c",cor});d.txt(t2,cx,SANGRIA+33,11.5,{alinha:"c",cor:"#5B5670"});
    const q=o.qr,lado=66,zona=2,mod=lado/(q.n+2*zona),x0=cx-lado/2,y0=SANGRIA+42;
    for(let r=0;r<q.n;r++){let ini=-1;for(let c=0;c<=q.n;c++){const on=c<q.n&&q.m[r][c];if(on&&ini<0)ini=c;if(!on&&ini>=0){d.ret(x0+(ini+zona)*mod,y0+(r+zona)*mod,(c-ini)*mod+.02,mod+.02,"#000000");ini=-1;}}}
    d.txt("Aponte a câmera do celular",cx,y0+lado+9,13,{negrito:true,alinha:"c",cor:"#141024"});
    const nome=d.quebrar(o.nome||"",12,LW-2*SANGRIA-16,true).slice(0,2);nome.forEach((l,i)=>d.txt(l,cx,y0+lado+19+i*5.4,12,{negrito:true,alinha:"c",cor}));
    d.txt(o.codigo||"",cx,LH-SANGRIA-7,8,{alinha:"c",cor:"#8A84A0"});
    return d;}
  window.PDFMini={novo,largura,logoJPEG,cardapio,plaquinha};
})();
