// GênIO · app do representante (versão limpa) — núcleo: sessão, dados da zona, ficha do cliente, navegação.
const App=(()=>{
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const qs=new URLSearchParams(location.search);
  const ZONA=qs.get("zona")||localStorage.getItem("app-zona")||"zona-cerealista";
  const SETOR_NOME={"cereais/empório":"Empório","salão/barbearia":"Barbearia","clínica/consultório":"Clínica","academia/estúdio":"Academia","loja de roupas/calçados":"Moda","floricultura/presentes":"Presentes","mercado/hortifruti":"Mercado","embalagens/utilidades":"Embalagens","celular/assistência":"Assistência","escritório/imobiliária":"Escritório","escola/curso":"Escola"};
  const setorNome=s=>SETOR_NOME[s]||(s||"comércio").replace(/^./,c=>c.toUpperCase());
  const nomeLoja=n=>/^[^a-z]*$/.test(n||"")&&(n||"").length>4?n.toLowerCase().replace(/(^|[\s\-·(])(\S)/g,(m,a,b)=>a+b.toUpperCase()).replace(/\b(Da|De|Do|Das|Dos|E|Em)\b/g,m=>m.toLowerCase()):(n||"");
  const telFmt=t=>{const d=(t||"").replace(/\D/g,"").replace(/^55(?=\d{10,11}$)/,"");return d.length>=10?`(${d.slice(0,2)}) ${d.slice(2,-4)}-${d.slice(-4)}`:(t||"");};
  const ini=n=>(n||"").split(/\s+/).filter((p,i,a)=>i===0||i===a.length-1).map(p=>p[0]||"").join("").toUpperCase();
  // ---- sessão: login uma vez (cookie da API); sem sessão → tela de entrada do site e volta para cá
  let EU=null;
  async function sessao(obrigatoria=true){
    if(EU)return EU;
    try{const r=await fetch("/api/eu",{credentials:"same-origin",cache:"no-store"});if(r.ok){EU=await r.json();if(EU&&EU.nome)localStorage.setItem("app-eu",JSON.stringify({nome:EU.nome,email:EU.email}));return EU;}}catch(e){}
    try{EU=JSON.parse(localStorage.getItem("app-eu")||"null");}catch(e){}
    if(!EU&&obrigatoria&&!navigator.onLine===false){location.href="/?entrar=1&volta="+encodeURIComponent("app/"+location.pathname.split("/").pop()+location.search);return null;}
    return EU;}
  const eu=()=>EU||{nome:"Representante"};
  // ---- dados da zona (captação do servidor)
  let D=null;
  async function dados(){if(D)return D;
    const r=await fetch(`/dados/captacao/${ZONA}/lojas.json?t=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw new Error("zona sem dados");
    const j=await r.json();D={zona:{slug:ZONA,nome:(j.zona.nome||ZONA).split(" (")[0],base:j.zona.base,cidade:j.zona.cidade||"São Paulo"},gerado:j.gerado,lojas:j.lojas};
    localStorage.setItem("app-zona",ZONA);
    try{const c=await fetch(`/dados/captacao/${ZONA}/clientes/index.json?t=${Date.now()}`,{cache:"no-store"});if(c.ok){const m={};(await c.json()).forEach(x=>m[x.slug]=x);D.lojas.forEach(l=>{l.cad=m[l.slug]||null;});}}catch(e){}
    D.lojas.forEach(l=>{l.estrelas=estrelas(l);});
    return D;}
  async function ficha(slug){try{const r=await fetch(`/dados/captacao/${ZONA}/clientes/${slug}.json?t=${Date.now()}`,{cache:"no-store"});return r.ok?await r.json():null;}catch(e){return null;}}
  // ---- estrelas (1–5): proposta de 08/11, a validar com o Yoshio. Cada sinal soma 1; nunca menos de 1.
  function estrelas(l){let n=1;const L=(l.cad&&l.cad.lacunas)||{};
    if((l.nota||0)>=4.3&&(l.aval||0)>=20)n++;
    if(l.site||(L.site&&L.site.estado==="encontrado")||(L.redes&&L.redes.estado==="encontrado"))n++;
    if(["padaria","restaurante","bar","cafeteria","cereais/empório","clínica/consultório","salão/barbearia","academia/estúdio","ótica","pet","escola/curso","escritório/imobiliária"].includes(l.setor))n++;
    if((l.aval||0)>=80)n++;
    return Math.min(5,n);}
  const estrelasHTML=n=>`<span class="estrelas" title="${n} de 5">${"★".repeat(n)}<span class="off">${"★".repeat(5-n)}</span></span>`;
  // ---- estado do dia no aparelho (feitas, seleções)
  const KEY="app-dia-"+ZONA;const estado=()=>{try{return JSON.parse(localStorage.getItem(KEY)||"{}");}catch(e){return {};}};const salvar=e=>localStorage.setItem(KEY,JSON.stringify(e));
  // ---- ficha local do cliente (IndexedDB genio-vendas › clientes): fonte única de logotipo, manual e artes
  function abrirVendas(){return new Promise(res=>{try{const cria=d=>{["orcamentos","sessao"].forEach(n=>{if(!d.objectStoreNames.contains(n))d.createObjectStore(n,{keyPath:"id"});});if(!d.objectStoreNames.contains("clientes"))d.createObjectStore("clientes",{keyPath:"k"});if(!d.objectStoreNames.contains("notas"))d.createObjectStore("notas",{keyPath:"id"});};
    const r=indexedDB.open("genio-vendas");r.onupgradeneeded=()=>cria(r.result);r.onerror=()=>res(null);
    r.onsuccess=()=>{const d=r.result;if(d.objectStoreNames.contains("clientes")&&d.objectStoreNames.contains("notas"))return res(d);const v=Math.max(5,d.version+1);d.close();const r2=indexedDB.open("genio-vendas",v);r2.onupgradeneeded=()=>cria(r2.result);r2.onsuccess=()=>res(r2.result);r2.onerror=()=>res(null);r2.onblocked=()=>res(null);};}catch(e){res(null);}});}
  const chave=nome=>nome.toLowerCase();
  async function lerCliente(nome){const db=await abrirVendas();if(!db)return null;return new Promise(res=>{const t=db.transaction("clientes").objectStore("clientes").get(chave(nome));t.onsuccess=()=>{res(t.result||null);db.close();};t.onerror=()=>{res(null);db.close();};});}
  async function gravarCliente(o){const db=await abrirVendas();if(!db)return false;return new Promise(res=>{const t=db.transaction("clientes","readwrite");o.atualizado=new Date().toISOString();t.objectStore("clientes").put(o);t.oncomplete=()=>{db.close();res(true);};t.onerror=()=>{db.close();res(false);};});}
  async function cliente(l){const nome=nomeLoja(l.nome);return (await lerCliente(nome))||{k:chave(nome),nome,slug:l.slug,logos:[],arquivo:[],criado:new Date().toISOString()};}
  function definirCliente(l){try{localStorage.setItem("genio-cliente",nomeLoja(l.nome));localStorage.setItem("genio-cliente-dados",JSON.stringify({slug:l.slug,tel:telFmt(l.tel),endereco:l.endereco,setor:l.setor}));}catch(e){}}
  // imagem classificada pelo dedo (menu da galeria): logotipo · fachada · arquivo · produto
  async function classificar(l,src,papel,fonte){const c=await cliente(l);const item={src,fonte:fonte||"",em:new Date().toISOString()};
    if(papel==="logotipo"){c.logos=[{id:"cap"+Date.now().toString(36),src,nome:"Logotipo"+(fonte?" · "+fonte:""),origem:"escolha",...item},...(c.logos||[]).filter(x=>x.src!==src)].slice(0,12);if(c.manual&&!c.manual.editado)delete c.manual;}
    else if(papel==="fachada"){c.fachada=item;}
    else if(papel==="produto"){c.produtos=[...(c.produtos||[]),item];}
    else if(papel==="arquivo"){c.arquivo=[...(c.arquivo||[]),item];}
    else if(papel==="descartar"){c.descartadas=[...(c.descartadas||[]),src];}
    return gravarCliente(c);}
  // logotipo principal = logos[0]; o tratado vale como "pronto" para o catálogo
  async function logoPrincipal(l,id){const c=await cliente(l);const i=(c.logos||[]).findIndex(x=>x.id===id);if(i>0){const [x]=c.logos.splice(i,1);c.logos.unshift(x);}
    const p=c.logos[0];if(p&&p.tratado&&p.src)c.manual={editado:true,tratado:p.src,largura:p.largura,altura:p.altura,camadas:[{nome:"Logotipo",png:p.src}],em:new Date().toISOString()};else if(c.manual&&p&&c.manual.tratado!==p.src)delete c.manual;
    return gravarCliente(c);}
  async function removerLogo(l,id){const c=await cliente(l);c.logos=(c.logos||[]).filter(x=>x.id!==id);const p=c.logos[0];if(!p)delete c.manual;else if(c.manual&&c.manual.tratado!==p.src){if(p.tratado)c.manual={editado:true,tratado:p.src,largura:p.largura,altura:p.altura,camadas:[{nome:"Logotipo",png:p.src}],em:new Date().toISOString()};else delete c.manual;}
    return gravarCliente(c);}
  // ---- entradas de imagem: Fotografar (câmera) · Enviar arquivo → dataURL reduzido (lado maior 1600 px)
  function escolherImagem(camera){return new Promise(res=>{const i=document.createElement("input");i.type="file";i.accept="image/*";if(camera)i.capture="environment";i.style.display="none";document.body.appendChild(i);let feito=false;
    const fim=v=>{if(feito)return;feito=true;i.remove();res(v);};
    i.onchange=()=>{const f=i.files&&i.files[0];if(!f)return fim(null);const u=URL.createObjectURL(f);const im=new Image();im.onload=()=>{const s=Math.min(1,1600/Math.max(im.width,im.height));const cv=document.createElement("canvas");cv.width=Math.round(im.width*s);cv.height=Math.round(im.height*s);cv.getContext("2d").drawImage(im,0,0,cv.width,cv.height);URL.revokeObjectURL(u);fim(cv.toDataURL(/png$/i.test(f.type)?"image/png":"image/jpeg",0.92));};im.onerror=()=>fim(null);im.src=u;};
    i.addEventListener("cancel",()=>fim(null));window.addEventListener("focus",()=>setTimeout(()=>{if(!i.files||!i.files.length)fim(null);},1200),{once:true});i.click();});}
  // abre a tela do logotipo com uma imagem (URL ou dataURL grande vai pela sessão)
  function abrirLogotipo(slug,src,fonte,de,extra){let u=src;if(src.length>1500){const k="sess:"+Date.now().toString(36);sessionStorage.setItem(k,src);u=k;}
    location.href=`logotipo.html?l=${encodeURIComponent(slug)}&u=${encodeURIComponent(u)}&fonte=${encodeURIComponent(fonte||"")}&de=${de||"visita"}${extra||""}`;}
  // os três botões de entrada (Pesquisa · Fotografar · Enviar arquivo) para uma área de imagem
  const entradas=(slug,id)=>`<div class="entradas" id="${id}"><a class="btn sec" href="fontes.html?l=${encodeURIComponent(slug)}&tipo=busca">🔍 Pesquisa</a><button type="button" class="btn sec" data-e="camera">📷 Fotografar</button><button type="button" class="btn sec" data-e="arquivo">📁 Enviar arquivo</button></div>`;
  // liga os botões: ao receber a imagem, pergunta o que ela é (ou usa `papel` fixo) e segue
  function ligarEntradas(root,l,papel,aoFim){$$("[data-e]",root).forEach(b=>b.onclick=async()=>{const src=await escolherImagem(b.dataset.e==="camera");if(!src)return;
    const k=papel||await menuLongo("Esta imagem é…",[{k:"logotipo",ic:"✦",t:"Logotipo"},{k:"fachada",ic:"🏬",t:"Fachada"},{k:"arquivo",ic:"🗂",t:"Imagem de arquivo"},{k:"produto",ic:"🛍",t:"Foto de produto"}]);if(!k)return;
    const fonte=b.dataset.e==="camera"?"foto":"arquivo";if(k==="logotipo"){abrirLogotipo(l.slug,src,fonte,"visita");return;}await classificar(l,src,k,fonte);if(aoFim)aoFim(k);});}
  // ---- arte automática: logotipo tratado centralizado preenchendo a área segura do gabarito, cor padrão do material
  const COR_PADRAO={capacho:"#2B2B2D",rigido:"#F4F1EA",vinil:null,tecido:"#F4F1EA",papel:"#FFFFFF",lona:"#FFFFFF",carimbo:null};
  const PRODUTOS_IDS=["capacho","placas","adesivos","uniformes","impressos","panfleto","banners","parede","brindes","carimbo"];
  let _G=null;const gabaritos=async()=>_G||(_G=await (await fetch("gabaritos.json?v=0e64fe8284")).json());
  const carregarImg=src=>new Promise(res=>{const i=new Image();i.crossOrigin="anonymous";i.onload=()=>res(i);i.onerror=()=>res(null);i.src=src;});
  async function artePadrao(pid,c){const G=await gabaritos();const P=G.produtos[pid];if(!P||!(c.manual&&c.manual.tratado))return null;const im=await carregarImg(c.manual.tratado);if(!im)return null;
    const sang=P.sangria_mm!=null?P.sangria_mm:G.sangria_mm,seg=P.seguranca_mm!=null?P.seguranca_mm:G.seguranca_mm;
    const PX=Math.min(100,Math.floor(3000/Math.max(P.w_cm+sang/5,P.h_cm+sang/5)));const W=Math.round((P.w_cm+2*sang/10)*PX),H=Math.round((P.h_cm+2*sang/10)*PX),B=Math.round(sang/10*PX),S=Math.round(seg/10*PX);
    const aw=W-2*(B+S),ah=H-2*(B+S);const f=Math.min(aw/im.naturalWidth,(P.ancora==="topo"?ah*0.45:ah)/im.naturalHeight);const w=im.naturalWidth*f,h=im.naturalHeight*f;const x=(W-w)/2,y=P.ancora==="topo"?B+S+ah*0.05:(H-h)/2;
    const fundo=P.sem_fundo?null:(COR_PADRAO[P.superficie]===undefined?"#FFFFFF":COR_PADRAO[P.superficie]);
    const doc={fundo,fundoImg:null,el:[{tipo:"camada",id:"logo",nome:"Logotipo",src:c.manual.tratado,cor:null,usarCor:false,x,y,w,h,borda:0,bordaCor:"#FFFFFF",grupo:"logo"}],campos:null,auto:true};
    const k=Math.min(1,1400/Math.max(W,H));const cv=document.createElement("canvas");cv.width=Math.round(W*k);cv.height=Math.round(H*k);const g=cv.getContext("2d");
    g.drawImage(im,x*k,y*k,w*k,h*k);const pngArte=cv.toDataURL("image/png");
    g.globalCompositeOperation="destination-over";if(fundo){g.fillStyle=fundo;g.fillRect(0,0,cv.width,cv.height);}const png=cv.toDataURL(fundo?"image/jpeg":"image/png",0.88);
    return {doc,png,pngArte,material:fundo,w_cm:P.w_cm,h_cm:P.h_cm,sangria_mm:sang,em:new Date().toISOString(),contexto:null};}
  // gera (e contextualiza) todos os produtos de uma loja; pula os que já têm arte feita à mão
  async function gerarProdutos(l,aoPasso){let c=await cliente(l);if(!(c.manual&&c.manual.editado))return {ok:0,falhas:["sem logotipo tratado"]};c.artes=c.artes||{};let ok=0;const falhas=[];
    for(const pid of PRODUTOS_IDS){const ant=c.artes[pid];if(ant&&ant.contexto&&!(ant.doc&&ant.doc.auto))continue;if(aoPasso)aoPasso(pid);
      try{const a=ant&&ant.contexto&&ant.doc&&ant.doc.auto&&ant.doc.el[0]&&ant.doc.el[0].src===c.manual.tratado?ant:await artePadrao(pid,c);if(!a){falhas.push(pid+": sem gabarito");continue;}
        if(!a.contexto){const r=await fetch("/api/kit/aplicar",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({setor:l.setor,produto:pid,png:a.pngArte,material:a.material})});const d=await r.json();if(r.ok&&d.jpg){a.contexto=d.jpg;a.kit=d.kit;}else falhas.push(pid+": "+(d.mensagem||d.erro||r.status));}
        c.artes[pid]=a;ok++;}catch(e){falhas.push(pid+": "+e.message);}}
    await gravarCliente(c);return {ok,falhas};}
  // ---- notas (gravador): áudio + texto, ligadas à última loja aberta
  async function listarNotas(){const db=await abrirVendas();if(!db)return [];return new Promise(res=>{const t=db.transaction("notas").objectStore("notas").getAll();t.onsuccess=()=>{res((t.result||[]).sort((a,b)=>b.em.localeCompare(a.em)));db.close();};t.onerror=()=>{res([]);db.close();};});}
  async function gravarNota(n){const db=await abrirVendas();if(!db)return false;return new Promise(res=>{const t=db.transaction("notas","readwrite");t.objectStore("notas").put(n);t.oncomplete=()=>{res(true);db.close();};t.onerror=()=>{res(false);db.close();};});}
  async function apagarNota(id){const db=await abrirVendas();if(!db)return false;return new Promise(res=>{const t=db.transaction("notas","readwrite");t.objectStore("notas").delete(id);t.oncomplete=()=>{res(true);db.close();};t.onerror=()=>{res(false);db.close();};});}
  // ---- agenda de rotas: todas as lojas da zona por estrelas, em dias de 50; dia 1 = data do início (hoje, na primeira abertura); pula domingo
  const META=50;
  function diasDeRota(D){const lista=D.lojas.slice().sort((a,b)=>b.estrelas-a.estrelas||a.dia-b.dia||a.ordem-b.ordem);const dias=[];for(let i=0;i<lista.length;i+=META)dias.push(lista.slice(i,i+META));
    const e=estado();if(!e.inicio){e.inicio=hojeISO();salvar(e);}const datas=[];let d=new Date(e.inicio+"T12:00:00");for(let k=0;k<dias.length;k++){while(d.getDay()===0)d.setDate(d.getDate()+1);datas.push(d.toISOString().slice(0,10));d.setDate(d.getDate()+1);}
    return dias.map((lojas,i)=>({n:i+1,data:datas[i],lojas}));}
  const hojeISO=()=>{const d=new Date();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,10);};
  const dataCurta=iso=>{const d=new Date(iso+"T12:00:00");return {dia:d.getDate(),sem:["dom","seg","ter","qua","qui","sex","sáb"][d.getDay()],mes:["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][d.getMonth()]};};
  // ---- ícones da barra (SVG)
  const ICONES={rota:`<svg viewBox="0 0 48 48"><defs><linearGradient id="gpin" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F0786B"/><stop offset="1" stop-color="#C62828"/></linearGradient></defs><ellipse cx="24" cy="43" rx="9" ry="2.5" fill="rgba(0,0,0,.18)"/><path d="M24 4c-8.3 0-15 6.6-15 14.8C9 30 24 42 24 42s15-12 15-23.2C39 10.6 32.3 4 24 4z" fill="url(#gpin)"/><circle cx="24" cy="18.5" r="6" fill="#fff"/><circle cx="24" cy="18.5" r="3" fill="#F8D7D3"/><path d="M15 12c2-4 5.5-6 9-6" stroke="rgba(255,255,255,.55)" stroke-width="2" stroke-linecap="round" fill="none"/></svg>`,
    pedidos:`<svg viewBox="0 0 48 48"><defs><linearGradient id="gclip" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8F6BE0"/><stop offset="1" stop-color="#5A2EB5"/></linearGradient></defs><rect x="9" y="7" width="30" height="37" rx="4" fill="url(#gclip)"/><rect x="12.5" y="12" width="23" height="29" rx="2" fill="#FFFDF7"/><rect x="17" y="4" width="14" height="7" rx="2.5" fill="#2B2B2D"/><rect x="21" y="6" width="6" height="3" rx="1.5" fill="#9A9B9D"/><path d="M16 20h16M16 25h16M16 30h10" stroke="#B9B1CC" stroke-width="2" stroke-linecap="round"/><path d="M15.5 35.5l3 3 6-6" stroke="#14B8B0" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
    perfil:`<svg viewBox="0 0 48 48"><defs><linearGradient id="gface" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD9B8"/><stop offset="1" stop-color="#E8A878"/></linearGradient><linearGradient id="gshirt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2B6CB0"/><stop offset="1" stop-color="#1F3A5F"/></linearGradient></defs><circle cx="24" cy="24" r="21" fill="#EEE9F7"/><path d="M8 40c2-8 8-11 16-11s14 3 16 11a21 21 0 0 1-32 0z" fill="url(#gshirt)"/><path d="M19 29l5 8 5-8" fill="#fff"/><circle cx="24" cy="18" r="8" fill="url(#gface)"/><path d="M16 17c0-6 4-9 8-9s8 3 8 9c-2-3-5-4-8-4s-6 1-8 4z" fill="#3B2A1E"/></svg>`,
    notas:`<svg viewBox="0 0 48 48"><defs><linearGradient id="gmic" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C9CCD6"/><stop offset="1" stop-color="#6E7383"/></linearGradient></defs><rect x="17" y="5" width="14" height="24" rx="7" fill="url(#gmic)"/><path d="M19 10h10M19 14h10M19 18h10M19 22h10" stroke="rgba(0,0,0,.25)" stroke-width="1.4"/><path d="M12 22a12 12 0 0 0 24 0" stroke="#2B2B2D" stroke-width="3" fill="none" stroke-linecap="round"/><rect x="22.5" y="33" width="3" height="7" fill="#2B2B2D"/><rect x="15" y="40" width="18" height="3.5" rx="1.75" fill="#2B2B2D"/><circle cx="36" cy="10" r="5" fill="#C62828"/><circle cx="36" cy="10" r="2" fill="#fff"/></svg>`};
  const nav=on=>`<nav class="nav"><a href="index.html" class="${on==="rota"?"on":""}"><span class="ic">${ICONES.rota}</span>Rota</a><a href="pedidos.html" class="${on==="pedidos"?"on":""}"><span class="ic">${ICONES.pedidos}</span>Pedidos</a><a href="perfil.html" class="${on==="perfil"?"on":""}"><span class="ic">${ICONES.perfil}</span>Perfil</a><span class="sep"></span><a href="notas.html" class="${on==="notas"?"on":""}"><span class="ic">${ICONES.notas}</span>Notas</a></nav>`;
  const topo=()=>`<header class="topo"><div class="logo">Gên<i>IO</i></div><div class="papel">Representante</div><div class="fill"></div><a class="avatar" href="perfil.html" title="${esc(eu().nome)}">${esc(ini(eu().nome))}</a></header>`;
  const voltar=(href,txt)=>`<div class="faixa"><a href="${href}">${esc(txt)}</a></div>`;
  const acoes=(voltaHref,voltaTxt,avancaId,avancaTxt)=>`<div class="acoes"><div class="w">${voltaHref?`<a class="btn sec" href="${voltaHref}">← ${esc(voltaTxt)}</a>`:""}<button class="btn" id="${avancaId}" type="button">${esc(avancaTxt)}</button></div></div>`;
  // menu lateral de toque longo: devolve o item escolhido (ou null)
  function menuLongo(titulo,itens){return new Promise(res=>{const f=document.createElement("div");f.className="fundo";const m=document.createElement("div");m.className="menu-lado";m.innerHTML=`<b>${esc(titulo)}</b>${itens.map(i=>`<button type="button" data-k="${i.k}">${i.ic?`<span>${i.ic}</span>`:""}${esc(i.t)}</button>`).join("")}<button type="button" class="cancela" data-k="">Cancelar</button>`;
    const fim=k=>{f.remove();m.remove();res(k||null);};f.onclick=()=>fim(null);m.onclick=ev=>{const b=ev.target.closest("button");if(b)fim(b.dataset.k);};document.body.append(f,m);});}
  // toque longo em elementos [data-longo]: chama fn(el) após 450 ms sem mover
  function ligarLongo(root,fn){$$("[data-longo]",root).forEach(el=>{let t=null,p=null;el.addEventListener("pointerdown",ev=>{p={x:ev.clientX,y:ev.clientY};t=setTimeout(()=>{t=null;if(navigator.vibrate)navigator.vibrate(12);fn(el);},450);});
    const c=ev=>{if(t&&p&&ev.type==="pointermove"&&Math.hypot(ev.clientX-p.x,ev.clientY-p.y)<8)return;clearTimeout(t);t=null;};el.addEventListener("pointermove",c);el.addEventListener("pointerup",c);el.addEventListener("pointercancel",c);el.addEventListener("contextmenu",ev=>ev.preventDefault());});}
  return {$,$$,esc,qs,ZONA,setorNome,nomeLoja,telFmt,ini,sessao,eu,dados,ficha,estrelas,estrelasHTML,estado,salvar,abrirVendas,lerCliente,gravarCliente,cliente,definirCliente,classificar,logoPrincipal,removerLogo,escolherImagem,abrirLogotipo,entradas,ligarEntradas,artePadrao,gerarProdutos,PRODUTOS_IDS,listarNotas,gravarNota,apagarNota,diasDeRota,hojeISO,dataCurta,META,nav,topo,voltar,acoes,menuLongo,ligarLongo};
})();
