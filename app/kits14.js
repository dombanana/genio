/* GênIO · kit de 14 setores (10/11/2026) — artes frontais e fotos dos 16 produtos.
   Fonte: brand/kits14 (GenIO_14_Setores_Kit_Completo). Regras: PASSO_A_PASSO_PARA_A_INTELIGENCIA.md + REGRAS_MONTAGEM.json.
   A maquete frontal do setor (SVG) vira um documento do editor: "GIO" → logotipo tratado da loja; cores → identidade
   da loja (precedência: identidade aprovada > escolha do cliente > paleta do setor); dados fictícios → dados reais da
   ficha ou saem; preços ilustrativos saem; QR → endereço real verificado (sem endereço, sem QR). */
(function(){
  const BASE="/brand/kits14/";
  // ---- setor do app → pasta do kit (o ramo mais próximo entre os 14)
  const SETOR_KIT={"cafeteria":"01_Cafeteria","restaurante":"02_Restaurante","bar":"02_Restaurante","padaria":"03_Padaria",
    "clínica/consultório":"04_Clinica","estética":"05_Estetica","salão/barbearia":"06_Salao","escritório/imobiliária":"07_Imobiliaria",
    "loja de roupas/calçados":"08_Loja_Roupas","floricultura/presentes":"08_Loja_Roupas","pet":"09_Pet_Shop","farmácia":"10_Farmacia","ótica":"10_Farmacia",
    "academia/estúdio":"11_Academia","autopeças/oficina":"12_Autopecas","celular/assistência":"13_Escritorio","escola/curso":"13_Escritorio",
    "cereais/empório":"14_Mercado","mercado/hortifruti":"14_Mercado","embalagens/utilidades":"14_Mercado","comércio":"14_Mercado"};
  const kitDe=setor=>SETOR_KIT[setor]||SETOR_KIT[(setor||"").split("/")[0]]||"14_Mercado";
  // ---- produto do app → arquivo do kit (IDs estáveis 01–16)
  const ARQ={capacho:"01_capacho",placas:"02_placa",adesivos:"03_adesivo_vitrine",uniformes:"04_uniforme_polo",impressos:"05_cartao",panfleto:"06_flyer_cardapio",
    banners:"07_banner_retratil",parede:"08_adesivo_parede_rotas",brindes:"09_ecobag",carimbo:"10_carimbos_papeis",windbanner:"11_wind_banner",faixa:"12_faixa_horizontal",
    folheto:"13_folheto_promocional",camiseta:"14_camiseta",bone:"15_bone",avental:"16_avental"};
  const SEM_SUPERFICIE=new Set(["03","04","08","09","10","14","15","16"]);   // vinil e tecido: só a arte (sem fundo)
  const cache={};const txt=async u=>cache[u]||(cache[u]=await (await fetch(u,{cache:"force-cache"})).text());
  const json=async u=>JSON.parse(await txt(u));
  // ---- fontes do kit (DejaVu) carregadas na página: o canvas desenha e mede com elas
  let fontes=null;function carregarFontes(){if(fontes)return fontes;const v="vendor/fontes/";const F=[["DejaVu Sans","DejaVuSans.woff","400"],["DejaVu Sans","DejaVuSans-Bold.woff","700"],["DejaVu Serif","DejaVuSerif.woff","400"],["DejaVu Serif","DejaVuSerif-Bold.woff","700"]];
    fontes=Promise.all(F.map(([f,a,w])=>{const ff=new FontFace(f,`url(${v}${a})`,{weight:w});document.fonts.add(ff);return ff.load().catch(()=>null);}));return fontes;}
  // ---- cor
  const hex2=h=>{h=String(h||"#000").replace("#","");if(h.length===3)h=h.split("").map(c=>c+c).join("");const n=parseInt(h,16);return [(n>>16)&255,(n>>8)&255,n&255];};
  const rgb2=a=>"#"+a.map(v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,"0")).join("");
  const norm=c=>{if(!c||c==="none")return null;c=c.trim().toLowerCase();if(c==="white")return "#ffffff";if(c==="black")return "#000000";if(/^#[0-9a-f]{3}$/.test(c))c="#"+c.slice(1).split("").map(x=>x+x).join("");return /^#[0-9a-f]{6}$/.test(c)?c:null;};
  const lum=h=>{const [r,g,b]=hex2(h);return 0.2126*r+0.7152*g+0.0722*b;};
  const sat=h=>{const [r,g,b]=hex2(h).map(v=>v/255);const mx=Math.max(r,g,b),mn=Math.min(r,g,b);return mx?(mx-mn)/mx:0;};
  const mix=(a,b,t)=>{const A=hex2(a),B=hex2(b);return rgb2(A.map((v,i)=>v+(B[i]-v)*t));};
  const relL=h=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};const [r,g,b]=hex2(h);return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);};
  const contraste=(a,b)=>{const x=relL(a),y=relL(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);};
  const escurecerAte=(c,fundo,min)=>{let k=0,x=c;while(contraste(x,fundo)<min&&k<12){x=mix(x,"#000000",0.12);k++;}return x;};
  const neutra=h=>lum(h)>200&&sat(h)<0.16;
  // papéis da identidade da loja: P (principal, painéis), T (texto escuro), A (destaque), sobreP (texto sobre P)
  function papeis(cores,setorPal){const cs=(cores||[]).filter(x=>x&&x.hex).slice().sort((a,b)=>(b.area||0)-(a.area||0)).map(x=>norm(x.hex)).filter(Boolean);
    const usaSetor=!cs.length;const fonte=usaSetor?"paleta do setor":"identidade da loja";
    if(usaSetor)return {P:setorPal.principal,T:setorPal.texto,A:setorPal.destaque,sobreP:setorPal.texto_sobre_principal||"#ffffff",fonte};
    const coloridas=cs.filter(h=>sat(h)>0.22&&lum(h)>25&&lum(h)<225);const escuras=cs.filter(h=>lum(h)<80);
    let T=escuras[0]||(coloridas[0]?mix(coloridas[0],"#0b1020",0.65):"#1c1635");if(lum(T)>90)T=mix(T,"#000000",0.5);
    let P=coloridas[0]||T;let A=coloridas.find(h=>Math.hypot(...hex2(h).map((v,i)=>v-hex2(P)[i]))>70)||(coloridas[0]&&P!==coloridas[0]?coloridas[0]:mix(P,"#ffffff",0.35));
    if(neutra(A)||contraste(A,"#fffdf7")<2.2)A=escurecerAte(A,"#fffdf7",3);
    let sobreP="#ffffff";if(contraste("#ffffff",P)<4.5){if(contraste(T,P)>=4.5)sobreP=T;else P=escurecerAte(P,"#ffffff",4.5);}
    return {P,T,A,sobreP,fonte};}
  // ---- SVG → elementos achatados com a matriz de cada um (medidos pelo próprio navegador)
  function montarSVG(src){const doc=new DOMParser().parseFromString(src,"image/svg+xml");const svg=doc.documentElement;
    const host=document.createElement("div");host.style.cssText="position:fixed;left:-99999px;top:0;visibility:hidden;pointer-events:none";
    const vb=svg.getAttribute("viewBox").split(/\s+/).map(Number);svg.setAttribute("width",vb[2]);svg.setAttribute("height",vb[3]);
    host.appendChild(document.importNode(svg,true));document.body.appendChild(host);return {host,svg:host.firstChild,W:vb[2],H:vb[3]};}
  const ctmDe=(svg,el)=>svg.getScreenCTM().inverse().multiply(el.getScreenCTM());
  function caixaGlobal(svg,el){const b=el.getBBox(),m=ctmDe(svg,el);const P=[[b.x,b.y],[b.x+b.width,b.y],[b.x+b.width,b.y+b.height],[b.x,b.y+b.height]].map(([x,y])=>[m.a*x+m.c*y+m.e,m.b*x+m.d*y+m.f]);
    const xs=P.map(p=>p[0]),ys=P.map(p=>p[1]);return {x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)};}
  const assinatura=el=>el.tagName+"|"+[...el.attributes].map(a=>a.name+"="+a.value).sort().join("|")+"|"+(el.tagName==="text"?el.textContent:"");
  const folhas=svg=>[...svg.querySelectorAll("rect,line,circle,path,text")];
  const ehQR=el=>el.tagName==="path"&&((el.getAttribute("d")||"").match(/h5\.0+v5\.0+/g)||[]).length>40;
  // ---- textos fictícios → dados reais (ou saem)
  function trocarDados(t,ct){const s=t.trim();
    if(/ilustrativ|fict[ií]ci|amostra/i.test(s))return null;
    if(/^R\$\s*\d/.test(s))return null;                                       // preço ilustrativo: não vai sem o cliente informar
    if(/@gio\.example|contato@/i.test(s))return ct.email||null;
    if(/^CNPJ/i.test(s))return ct.carimbo&&ct.carimbo.cnpj?"CNPJ: "+ct.carimbo.cnpj:null;
    if(/^CEP\s*0/i.test(s))return ct.tel?"Tel. "+ct.tel:null;
    if(/Rua Exemplo/i.test(s))return ct.endereco||null;
    if(/^S[ãa]o Paulo\s*·\s*SP$/i.test(s))return ct.endereco?null:null;  // a cidade já vem no endereço real
    if(/\(11\)\s*0000/.test(s))return ct.tel||null;
    if(/^SEG A S[ÁA]B|^Atendimento:/i.test(s))return ct.horario?ct.horario.split(" · ").slice(0,2).join(" · "):null;
    if(/^\d{2} [A-Z]{3} \d{4}$/.test(s)){const d=new Date();return `${String(d.getDate()).padStart(2,"0")} ${["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"][d.getMonth()]} ${d.getFullYear()}`;}
    if(/^GIO .* LTDA\.?$/i.test(s))return ct.carimbo&&ct.carimbo.razao?ct.carimbo.razao.toUpperCase():null;
    if(/\bGIO\b/.test(s)){const nm=ct.curto||ct.nome;return s.replace(/\bGIO(\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+)?\b/,(m0,setorPal)=>(s===s.toUpperCase()?nm.toUpperCase():nm));}
    return s;}
  // ---- monta o documento do editor a partir da arte frontal do setor
  async function montar(App,pid,c,l,geo){const arq=ARQ[pid];if(!arq)return null;const nId=arq.slice(0,2);const setor=kitDe(l&&l.setor);
    await carregarFontes();await document.fonts.ready;
    const [com,sem,regras]=await Promise.all([txt(`${BASE}${setor}/Artes_Frontais/COM_ARTE/${arq}.svg`),txt(`${BASE}${setor}/Artes_Frontais/SEM_ARTE/${arq}.svg`),json(`${BASE}REGRAS_MONTAGEM.json`)]);
    const pal=papeis((c.manual&&c.manual.cores)||[],regras.paletas_setor[setor]||regras.paletas_setor["14_Mercado"]);
    const ct=await window.Impressos.contato(App,l||{nome:"",slug:""});ct.curto=App.nomeLoja(ct.nome||"").split(/\s+[-–|·]\s+/)[0].slice(0,28);
    const S0=montarSVG(sem);const semSig=new Set(folhas(S0.svg).map(assinatura));S0.host.remove();
    const K=montarSVG(com);const svg=K.svg;const VW=K.W,VH=K.H;
    try{
      const todos=folhas(svg);const bg=todos.find(e=>e.tagName==="rect"&&+e.getAttribute("width")>=VW&&+e.getAttribute("height")>=VH);
      // 1. bloco do logotipo: "GIO" + nome do ramo logo abaixo + filete → caixa do logotipo da loja
      const logos=[];
      for(const g of todos.filter(e=>e.tagName==="text"&&e.textContent.trim()==="GIO")){const fs=+g.getAttribute("font-size");const x0=+g.getAttribute("x"),y0=+g.getAttribute("y");
        const sub=todos.find(e=>e!==g&&e.tagName==="text"&&Math.abs(+e.getAttribute("x")-x0)<3&&+e.getAttribute("y")>y0&&+e.getAttribute("y")<y0+fs*0.75&&+e.getAttribute("font-size")<fs*0.5);
        const fil=todos.find(e=>e.tagName==="line"&&Math.abs((+e.getAttribute("x1")+ +e.getAttribute("x2"))/2-x0)<4&&+e.getAttribute("y1")>y0&&+e.getAttribute("y1")<y0+fs*1.1&&e.getAttribute("y1")===e.getAttribute("y2"));
        const partes=[g,sub,fil].filter(Boolean);const bx=partes.map(p=>caixaGlobal(svg,p));
        const caixa={x:Math.min(...bx.map(b=>b.x)),y:Math.min(...bx.map(b=>b.y)),w:0,h:0};caixa.w=Math.max(...bx.map(b=>b.x+b.w))-caixa.x;caixa.h=Math.max(...bx.map(b=>b.y+b.h))-caixa.y;
        const ang=Math.round(Math.atan2(ctmDe(svg,g).b,ctmDe(svg,g).a)*180/Math.PI);
        logos.push({caixa,ang,arte:!semSig.has(assinatura(g))});partes.forEach(p=>p.remove());}
      // 2. textos: dados fictícios → reais; GIO → nome da loja; refaz a medida se cresceu
      const rects=todos.filter(e=>e.tagName==="rect"&&e!==bg).map(e=>caixaGlobal(svg,e));
      const painel=(b)=>{const cx=b.x+b.w/2,cy=b.y+b.h/2;if(nId==="13"){const c=Math.floor(cx/(VW/3));return {x:c*VW/3,y:0,w:VW/3,h:VH};}
        const dentro=rects.filter(r=>cx>=r.x&&cx<=r.x+r.w&&cy>=r.y&&cy<=r.y+r.h).sort((a,b)=>a.w*a.h-b.w*b.h);return dentro[0]||{x:0,y:0,w:VW,h:VH};};
      for(const t of folhas(svg).filter(e=>e.tagName==="text")){const antes=caixaGlobal(svg,t);const novo=trocarDados(t.textContent,ct);
        if(novo===null){t.remove();continue;}if(novo!==t.textContent.trim()){t.textContent=novo;const dep=caixaGlobal(svg,t);const r=painel(antes);const anc=t.getAttribute("text-anchor")||"start";
          const rot=Math.abs(ctmDe(svg,t).b)>0.5;const larg=rot?dep.h:dep.w,ant=rot?antes.h:antes.w;   // texto girado (wind banner): mede no comprimento
          const cx=antes.x+antes.w/2;let lim=anc==="middle"?2*Math.min(cx-r.x,r.x+r.w-cx)*0.9:anc==="end"?(antes.x+antes.w-r.x)*0.9:(r.x+r.w-antes.x)*0.92;
          if(rot)lim=Math.max(ant*1.15,(r.h||VH)*0.8);if(larg>lim){t.setAttribute("font-size",(+t.getAttribute("font-size")*lim/larg).toFixed(1));}}}
      // 3. QR do kit (exemplo) → QR real; sem endereço verificado, sai junto com o fundo branco
      const qrs=[];let semPainelQR=false;for(const q of folhas(svg).filter(ehQR)){const b=caixaGlobal(svg,q);const fundo=folhas(svg).find(e=>e.tagName==="rect"&&e!==bg&&(norm(e.getAttribute("fill"))==="#ffffff")&&(()=>{const r=caixaGlobal(svg,e);return r.x<=b.x+1&&r.y<=b.y+1&&r.x+r.w>=b.x+b.w-1&&r.y+r.h>=b.y+b.h-1&&r.w<b.w*1.6;})());
        const cx=fundo?caixaGlobal(svg,fundo):b;if(ct.url)qrs.push(cx);if(fundo)fundo.remove();q.remove();
        if(!ct.url){const dentro=(r)=>folhas(svg).filter(e=>e!==bg&&e.tagName!=="rect").some(e=>{const c=caixaGlobal(svg,e);const mx=c.x+c.w/2,my=c.y+c.h/2;return mx>=r.x&&mx<=r.x+r.w&&my>=r.y&&my<=r.y+r.h;});
          for(const pn of folhas(svg).filter(e=>e.tagName==="rect"&&e!==bg)){const r=caixaGlobal(svg,pn);if(r.x<=cx.x&&r.y<=cx.y&&r.x+r.w>=cx.x+cx.w&&r.y+r.h>=cx.y+cx.h&&r.w*r.h<VW*VH*0.6&&!dentro(r)){pn.remove();semPainelQR=true;}}}}
      // 4. cores: papel de cada cor pelo uso (painel grande, texto escuro, destaque) → identidade da loja
      const areaV=VW*VH;const papelDe={};
      for(const e of folhas(svg)){if(e===bg)continue;const art=!semSig.has(assinatura(e));if(!art)continue;
        for(const at of ["fill","stroke"]){const c0=norm(e.getAttribute(at));if(!c0)continue;
          const b=caixaGlobal(svg,e);const grande=at==="fill"&&e.tagName!=="text"&&b.w*b.h>areaV*0.03;
          let p;if(e.tagName==="text"){p=neutra(c0)||lum(c0)>220?"sobreP":(lum(c0)<110?"T":"A");}else if(neutra(c0)||c0==="#ffffff")p=null;else if(grande)p="P";else p=lum(c0)<70?"T":"A";
          if(p){const k=at+":"+c0;papelDe[k]=papelDe[k]||p;e.setAttribute(at,pal[p]);}}}
      // 5. elementos do documento (coordenadas do kit)
      const el=[];let n=0;const id=()=>"k"+(n++);
      const surf=[];const arteCx=[];
      for(const e of folhas(svg)){if(e===bg)continue;const art=!semSig.has(assinatura(e));const b=caixaGlobal(svg,e);
        if(!art){const sup=!SEM_SUPERFICIE.has(nId)&&(e.tagName==="rect"||e.tagName==="path")&&norm(e.getAttribute("fill"))&&b.w*b.h>=areaV*0.2;if(!sup)continue;surf.push(b);}
        else arteCx.push(b);
        const m=ctmDe(svg,e);const fill=norm(e.getAttribute("fill"))||(e.getAttribute("fill")==="none"?"transparent":e.tagName==="line"?null:"#000000");const stroke=norm(e.getAttribute("stroke"));const sw=+(e.getAttribute("stroke-width")||0);
        if(e.tagName==="text"){const fs=+e.getAttribute("font-size");const anc=e.getAttribute("text-anchor")||"start";const lb=e.getBBox();const ang=Math.atan2(m.b,m.a);
          const cxl=lb.x+lb.width/2,cyl=lb.y+lb.height/2;const gx=m.a*cxl+m.c*cyl+m.e,gy=m.b*cxl+m.d*cyl+m.f;
          el.push({tipo:"texto",id:id(),nome:e.textContent.slice(0,24),texto:e.textContent,x:gx-lb.width/2,y:gy-lb.height/2,w:lb.width,h:lb.height,cor:fill||"#000",tam:fs,fonte:`'${e.getAttribute("font-family")||"DejaVu Sans"}', sans-serif`,peso:+(e.getAttribute("font-weight")||400)>=600?700:400,alinh:anc==="middle"?"center":anc==="end"?"right":"left",alt:1.17,rot:Math.round(ang*180/Math.PI)||0,kit:true});}
        else if(e.tagName==="rect"&&Math.abs(m.b)<1e-6){el.push({tipo:"forma",forma:"ret",id:id(),nome:art?"Bloco":"Superfície",x:b.x,y:b.y,w:b.w,h:b.h,cor:fill||"transparent",borda:stroke?sw:0,bordaCor:stroke||"#000",raio:+(e.getAttribute("rx")||0),kit:true,superficie:!art||undefined,sem:!art||undefined});}
        else if(e.tagName==="circle"){el.push({tipo:"forma",forma:"cir",id:id(),nome:"Círculo",x:b.x,y:b.y,w:b.w,h:b.h,cor:fill||"transparent",borda:stroke?sw:0,bordaCor:stroke||"#000",kit:true});}
        else{let d;if(e.tagName==="line")d=`M${e.getAttribute("x1")} ${e.getAttribute("y1")} L${e.getAttribute("x2")} ${e.getAttribute("y2")}`;else if(e.tagName==="rect"){const x=+e.getAttribute("x"),y=+e.getAttribute("y"),w=+e.getAttribute("width"),h=+e.getAttribute("height");d=`M${x} ${y} h${w} v${h} h${-w} Z`;}else d=e.getAttribute("d");
          el.push({tipo:"vetor",id:id(),nome:e.tagName==="line"?"Linha":"Forma",d,m:[m.a,m.b,m.c,m.d,m.e,m.f],fill:e.tagName==="line"?null:fill,stroke:stroke||(e.tagName==="line"?"#000":null),sw,dash:e.getAttribute("stroke-dasharray")||null,ox:b.x,oy:b.y,ow:Math.max(b.w,1),oh:Math.max(b.h,1),x:b.x,y:b.y,w:Math.max(b.w,1),h:Math.max(b.h,1),kit:true,superficie:!art||undefined,sem:!art||undefined});}}
      for(const q of qrs)el.push({tipo:"qr",id:id(),nome:"QR · "+ct.urlTipo,texto:ct.url,x:q.x,y:q.y,w:Math.min(q.w,q.h),h:Math.min(q.w,q.h),cor:"#101820",kit:true});
      // 6. cor base (decisão do dono, 10/11): a cor do fundo da arte antes do recorte vira a cor do produto;
      //    sem essa cor e com logotipo claro, a base é a cor escura da marca (arte branca nunca vai em fundo branco)
      const im=geo.im,rec=geo.rec;const LW=rec?rec.sw:im.naturalWidth,LH=rec?rec.sh:im.naturalHeight;const luz=luzLogo(im,rec);
      const fm=norm(c.manual&&c.manual.fundoMarca);let base=fm||(luz>170?pal.T:null);
      if(base&&nId==="01")base=maisProxima(base,CORES_CAPACHO);   // capacho: a cor de vinil disponível mais próxima
      const TEXTEIS=new Set(["04","09","14","15","16"]);
      for(const L of logos){const b=L.caixa;const f=Math.min(b.w*1.12/LW,b.h/LH);const w=LW*f,h=LH*f;const x=b.x+(b.w-w)/2,y=b.y+(b.h-h)/2;
        el.push({tipo:"camada",id:id(),nome:"Logotipo",src:c.manual.tratado,recorte:rec||undefined,cor:null,usarCor:false,x,y,w,h,borda:0,bordaCor:"#FFFFFF",grupo:"logo",rot:L.ang||0});arteCx.push({x,y,w,h});}
      // 7. enquadramento no gabarito: superfície estica até a sangria; o resto entra proporcional (contain) na área útil
      const uni=bs=>bs.length?{x:Math.min(...bs.map(b=>b.x)),y:Math.min(...bs.map(b=>b.y)),w:Math.max(...bs.map(b=>b.x+b.w))-Math.min(...bs.map(b=>b.x)),h:Math.max(...bs.map(b=>b.y+b.h))-Math.min(...bs.map(b=>b.y))}:{x:0,y:0,w:VW,h:VH};
      const sup=surf.length?surf.sort((a,b)=>b.w*b.h-a.w*a.h)[0]:null;const corte=sup||uni(arteCx);const ref=uni(arteCx);  // ref = região que a foto do kit recebe
      // superfície (placa, capacho, cartão, faixa…): retângulo do tamanho do corte estica até a sangria do gabarito
      const quase=(e)=>e.tipo==="forma"&&e.forma==="ret"&&Math.abs(e.x-corte.x)<=corte.w*0.03&&Math.abs(e.y-corte.y)<=corte.h*0.03&&Math.abs(e.w-corte.w)<=corte.w*0.04&&Math.abs(e.h-corte.h)<=corte.h*0.04;
      el.forEach(e=>{if(quase(e))e.estica=true;});
      const {W,H,B}=geo;const tw=W-2*B,th=H-2*B;const k=Math.min(tw/corte.w,th/corte.h);const ox=B+(tw-corte.w*k)/2-corte.x*k,oy=B+(th-corte.h*k)/2-corte.y*k;
      for(const e of el){if(e.estica){e.x=0;e.y=0;e.w=W;e.h=H;e.raio=0;e.borda=0;delete e.estica;e.superficie=true;continue;}
        e.x=ox+e.x*k;e.y=oy+e.y*k;e.w*=k;e.h*=k;if(e.tam)e.tam=Math.round(e.tam*k*10)/10;if(e.borda)e.borda*=k;if(e.raio)e.raio*=k;}
      // cartão sem o painel do QR: a arte que sobrou volta para o centro da face
      if(semPainelQR&&nId==="05"){const arte=el.filter(e=>!e.superficie);if(arte.length){const x0=Math.min(...arte.map(e=>e.x)),x1=Math.max(...arte.map(e=>e.x+e.w));const dx=W/2-(x0+x1)/2;arte.forEach(e=>{e.x+=dx;});}}
      // 8. cor base na superfície (a esticada até a sangria, as do kit e o painel principal da peça)
      if(base&&!SEM_SUPERFICIE.has(nId)){for(const e of el){const grande=(e.tipo==="forma"||e.tipo==="vetor")&&e.w*e.h>=W*H*0.5&&e.grupo!=="logo";if(!(e.superficie||grande))continue;
          if(e.tipo==="forma"&&e.cor&&e.cor!=="transparent"){e.cor=base;delete e.sem;}else if(e.tipo==="vetor"&&e.fill&&e.fill!=="transparent"){e.fill=base;delete e.sem;}}
        // contraste: textos, traços e QR do kit que ficaram sobre a base continuam legíveis
        const melhor=bg=>["#ffffff",pal.T,"#1c1635",pal.A].sort((a,b)=>contraste(b,bg)-contraste(a,bg))[0];
        for(const e of el){if(e.superficie||e.grupo==="logo")continue;const at=corAtras(el.slice(0,el.indexOf(e)),e.x+e.w/2,e.y+e.h/2);if(!at)continue;
          if(e.tipo==="texto"&&contraste(e.cor,at)<3)e.cor=melhor(at);
          else if(e.tipo==="vetor"){if(e.stroke&&contraste(e.stroke,at)<1.6)e.stroke=melhor(at);if(e.fill&&e.fill!=="transparent"&&e.w*e.h<W*H*0.5&&contraste(e.fill,at)<1.4)e.fill=melhor(at);}
          else if(e.tipo==="forma"&&e.cor&&e.cor!=="transparent"&&e.w*e.h<W*H*0.5&&contraste(e.cor,at)<1.3)e.cor=mix(e.cor,lum(at)<128?"#ffffff":"#000000",0.35);
          else if(e.tipo==="qr")e.cor="#101820";}}   // o QR sempre sai escuro na sua própria caixa branca
      const COR_PECA={"09":"#ece4d4","03":"#30343a"};   // ecobag crua (não muda de cor) e vidro da vitrine
      const fundoPeca=COR_PECA[nId]||(TEXTEIS.has(nId)?base:null);
      if(fundoPeca){const melhor=bg=>["#ffffff",pal.T,"#1c1635"].sort((a,b)=>contraste(b,bg)-contraste(a,bg))[0];
        for(const e of el){if(e.grupo==="logo")continue;if(e.tipo==="texto"&&contraste(e.cor,fundoPeca)<3)e.cor=melhor(fundoPeca);else if(e.tipo==="vetor"&&e.stroke&&contraste(e.stroke,fundoPeca)<1.6)e.stroke=melhor(fundoPeca);}}
      // 9. logotipo sem contraste com o que está atrás → apoio claro/escuro (também no adesivo de parede quando a arte é clara)
      for(const L of el.filter(e=>e.grupo==="logo")){const at=corAtras(el.slice(0,el.indexOf(L)),L.x+L.w/2,L.y+L.h/2)||COR_PECA[nId]||(SEM_SUPERFICIE.has(nId)?(nId==="08"?"#f2efe8":null):"#fffdf7");if(!at)continue;
        const cinza=rgb2([luz,luz,luz]);
        // painel atrás da marca sem contraste: primeiro tenta pintar o painel com a cor base; não dando, entra o apoio
        if(base&&contraste(cinza,at)<3&&contraste(cinza,base)>=3){const atrasEl=[...el.slice(0,el.indexOf(L))].reverse().find(e=>((e.tipo==="forma"&&e.cor&&e.cor!=="transparent")||(e.tipo==="vetor"&&e.fill&&e.fill!=="transparent"))&&L.x+L.w/2>=e.x&&L.x+L.w/2<=e.x+e.w&&L.y+L.h/2>=e.y&&L.y+L.h/2<=e.y+e.h);
          if(atrasEl&&!atrasEl.superficie){if(atrasEl.tipo==="forma")atrasEl.cor=base;else atrasEl.fill=base;continue;}}
        if((!SEM_SUPERFICIE.has(nId)||(nId==="08"&&luz>170)||nId==="09"||nId==="03")&&(Math.abs(lum(at)-luz)<70||contraste(cinza,at)<2.5)){const p=Math.min(L.w,L.h)*0.14;
          el.splice(el.indexOf(L),0,{tipo:"forma",forma:"ret",id:id(),nome:"Apoio da marca",x:L.x-p,y:L.y-p,w:L.w+2*p,h:L.h+2*p,cor:lum(at)<128?"#ffffff":(base&&contraste(base,"#ffffff")>2?base:pal.T),borda:0,bordaCor:"#fff",raio:p,kit:true});}}
      const fundoEl=el.find(e=>e.superficie&&e.tipo==="forma"&&e.w===W&&e.h===H);
      const fundo=SEM_SUPERFICIE.has(nId)?null:(fundoEl?fundoEl.cor:"#fffdf7");
      // região que a foto do kit recebe: a superfície inteira quando há superfície (placa, cartão, faixa…); senão a caixa da arte
      const esticou=el.some(e=>e.superficie&&e.w===W&&e.h===H);
      const kitRef=sup?(esticou?{x:B,y:B,w:tw,h:th}:{x:ox+corte.x*k,y:oy+corte.y*k,w:corte.w*k,h:corte.h*k}):{x:ox+ref.x*k,y:oy+ref.y*k,w:ref.w*k,h:ref.h*k};
      // tecidos: a cor base tinge a peça na foto (camiseta, polo, boné, avental, ecobag)
      const material=TEXTEIS.has(nId)?(base||null):(fundo||null);
      return {el,fundo,material,base,fundoMarca:fm,kitRef,paleta:pal,setorKit:setor,arquivo:arq};
    }finally{K.host.remove();}}
  // cores de vinil do capacho (as mesmas do editor)
  const CORES_CAPACHO=["#2B2B2D","#9A9B9D","#1F3A5F","#7A1E1E","#2E5E3A","#EE6A1D","#C8A95B","#5B3A29"];
  const lab=h=>{const [r,g,b]=hex2(h).map(v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4);});const X=(r*0.4124+g*0.3576+b*0.1805)/0.95047,Y=r*0.2126+g*0.7152+b*0.0722,Z=(r*0.0193+g*0.1192+b*0.9505)/1.08883;const f=t=>t>0.008856?Math.cbrt(t):7.787*t+16/116;return [116*f(Y)-16,500*(f(X)-f(Y)),200*(f(Y)-f(Z))];};
  const maisProxima=(h,lista)=>{const a=lab(h);return lista.slice().sort((x,y)=>{const p=lab(x),q=lab(y);return Math.hypot(p[0]-a[0],p[1]-a[1],p[2]-a[2])-Math.hypot(q[0]-a[0],q[1]-a[1],q[2]-a[2]);})[0];};
  // cor do fundo da arte original (moldura de 3%): a mesma regra do servidor; transparente ou sem cor dominante → null
  function fundoDaImagem(im){try{const s=Math.min(1,400/Math.max(im.naturalWidth||im.width,im.naturalHeight||im.height));const W=Math.max(8,Math.round((im.naturalWidth||im.width)*s)),H=Math.max(8,Math.round((im.naturalHeight||im.height)*s));
    const cv=document.createElement("canvas");cv.width=W;cv.height=H;const g=cv.getContext("2d");g.drawImage(im,0,0,W,H);const d=g.getImageData(0,0,W,H).data;const b=Math.max(2,Math.round(Math.min(W,H)*0.03));
    const cont={},soma={};let tot=0,op=0;for(let y=0;y<H;y++)for(let x=0;x<W;x++){if(!(x<b||y<b||x>=W-b||y>=H-b))continue;tot++;const i=(y*W+x)*4;if(d[i+3]<=200)continue;op++;const k=(d[i]>>4)*256+(d[i+1]>>4)*16+(d[i+2]>>4);cont[k]=(cont[k]||0)+1;(soma[k]=soma[k]||[0,0,0]);soma[k][0]+=d[i];soma[k][1]+=d[i+1];soma[k][2]+=d[i+2];}
    if(op<0.6*tot)return null;let top=null;for(const k in cont)if(top===null||cont[k]>cont[top])top=k;if(!top||cont[top]<0.45*tot)return null;return rgb2(soma[top].map(v=>v/cont[top]));}catch(e){return null;}}
  function corAtras(el,x,y){for(let i=el.length-1;i>=0;i--){const e=el[i];if((e.tipo==="forma"&&e.forma==="ret"&&e.cor&&e.cor!=="transparent")||(e.tipo==="vetor"&&e.fill&&e.fill!=="transparent")){if(x>=e.x&&x<=e.x+e.w&&y>=e.y&&y<=e.y+e.h)return e.cor||e.fill;}}return null;}
  function luzLogo(im,rec){try{const cv=document.createElement("canvas");cv.width=48;cv.height=48;const g=cv.getContext("2d");if(rec)g.drawImage(im,rec.sx,rec.sy,rec.sw,rec.sh,0,0,48,48);else g.drawImage(im,0,0,48,48);const d=g.getImageData(0,0,48,48).data;let s=0,n=0;for(let i=0;i<d.length;i+=4){if(d[i+3]>100){s+=0.2126*d[i]+0.7152*d[i+1]+0.0722*d[i+2];n++;}}return n?s/n:128;}catch(e){return 128;}}
  // ---- foto do produto no ramo da loja (para a vitrine de produtos)
  async function foto(setor,pid,comArte){const s=kitDe(setor),arq=ARQ[pid];if(!arq)return null;try{const cal=await json(`${BASE}${s}/calibracao.json`);const p=cal.produtos[arq.slice(0,2)];if(!p)return null;return `${BASE}${s}/${comArte?p.demo:p.arquivo}`.replace(/\/[^/]+\/\.\.\//,"/");}catch(e){return null;}}
  window.Kits14={montar,kitDe,ARQ,foto,papeis,carregarFontes,fundoDaImagem,maisProxima,CORES_CAPACHO};
})();
