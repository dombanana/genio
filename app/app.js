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
  function abrirVendas(){return new Promise(res=>{try{const cria=d=>{["orcamentos","sessao"].forEach(n=>{if(!d.objectStoreNames.contains(n))d.createObjectStore(n,{keyPath:"id"});});if(!d.objectStoreNames.contains("clientes"))d.createObjectStore("clientes",{keyPath:"k"});};
    const r=indexedDB.open("genio-vendas");r.onupgradeneeded=()=>cria(r.result);r.onerror=()=>res(null);
    r.onsuccess=()=>{const d=r.result;if(d.objectStoreNames.contains("clientes"))return res(d);const v=Math.max(4,d.version+1);d.close();const r2=indexedDB.open("genio-vendas",v);r2.onupgradeneeded=()=>cria(r2.result);r2.onsuccess=()=>res(r2.result);r2.onerror=()=>res(null);r2.onblocked=()=>res(null);};}catch(e){res(null);}});}
  const chave=nome=>nome.toLowerCase();
  async function lerCliente(nome){const db=await abrirVendas();if(!db)return null;return new Promise(res=>{const t=db.transaction("clientes").objectStore("clientes").get(chave(nome));t.onsuccess=()=>{res(t.result||null);db.close();};t.onerror=()=>{res(null);db.close();};});}
  async function gravarCliente(o){const db=await abrirVendas();if(!db)return false;return new Promise(res=>{const t=db.transaction("clientes","readwrite");o.atualizado=new Date().toISOString();t.objectStore("clientes").put(o);t.oncomplete=()=>{db.close();res(true);};t.onerror=()=>{db.close();res(false);};});}
  async function cliente(l){const nome=nomeLoja(l.nome);return (await lerCliente(nome))||{k:chave(nome),nome,slug:l.slug,logos:[],arquivo:[],criado:new Date().toISOString()};}
  function definirCliente(l){try{localStorage.setItem("genio-cliente",nomeLoja(l.nome));localStorage.setItem("genio-cliente-dados",JSON.stringify({slug:l.slug,tel:telFmt(l.tel),endereco:l.endereco,setor:l.setor}));}catch(e){}}
  // imagem classificada pelo dedo (menu da galeria): logotipo · fachada · arquivo · produto
  async function classificar(l,src,papel,fonte){const c=await cliente(l);const item={src,fonte:fonte||"",em:new Date().toISOString()};
    if(papel==="logotipo"){c.logos=[{id:"cap"+Date.now().toString(36),src,nome:"Logotipo"+(fonte?" · "+fonte:""),origem:"escolha",...item},...(c.logos||[]).filter(x=>x.origem!=="escolha"&&x.origem!=="captacao")];if(c.manual&&!c.manual.editado)delete c.manual;}
    else if(papel==="fachada"){c.fachada=item;}
    else if(papel==="produto"){c.produtos=[...(c.produtos||[]),item];}
    else if(papel==="arquivo"){c.arquivo=[...(c.arquivo||[]),item];}
    else if(papel==="descartar"){c.descartadas=[...(c.descartadas||[]),src];}
    return gravarCliente(c);}
  const nav=on=>`<nav class="nav"><a href="index.html" class="${on==="rota"?"on":""}"><span class="ic">📍</span>Rota</a><a href="pedidos.html" class="${on==="pedidos"?"on":""}"><span class="ic">📄</span>Pedidos</a><a href="perfil.html" class="${on==="perfil"?"on":""}"><span class="ic">👤</span>Perfil</a></nav>`;
  const topo=()=>`<header class="topo"><div class="logo">Gên<i>IO</i></div><div class="papel">Representante</div><div class="fill"></div><a class="avatar" href="perfil.html" title="${esc(eu().nome)}">${esc(ini(eu().nome))}</a></header>`;
  const voltar=(href,txt)=>`<div class="faixa"><a href="${href}">${esc(txt)}</a></div>`;
  const acoes=(voltaHref,voltaTxt,avancaId,avancaTxt)=>`<div class="acoes"><div class="w">${voltaHref?`<a class="btn sec" href="${voltaHref}">← ${esc(voltaTxt)}</a>`:""}<button class="btn" id="${avancaId}" type="button">${esc(avancaTxt)}</button></div></div>`;
  // menu lateral de toque longo: devolve o item escolhido (ou null)
  function menuLongo(titulo,itens){return new Promise(res=>{const f=document.createElement("div");f.className="fundo";const m=document.createElement("div");m.className="menu-lado";m.innerHTML=`<b>${esc(titulo)}</b>${itens.map(i=>`<button type="button" data-k="${i.k}">${i.ic?`<span>${i.ic}</span>`:""}${esc(i.t)}</button>`).join("")}<button type="button" class="cancela" data-k="">Cancelar</button>`;
    const fim=k=>{f.remove();m.remove();res(k||null);};f.onclick=()=>fim(null);m.onclick=ev=>{const b=ev.target.closest("button");if(b)fim(b.dataset.k);};document.body.append(f,m);});}
  // toque longo em elementos [data-longo]: chama fn(el) após 450 ms sem mover
  function ligarLongo(root,fn){$$("[data-longo]",root).forEach(el=>{let t=null,p=null;el.addEventListener("pointerdown",ev=>{p={x:ev.clientX,y:ev.clientY};t=setTimeout(()=>{t=null;if(navigator.vibrate)navigator.vibrate(12);fn(el);},450);});
    const c=ev=>{if(t&&p&&ev.type==="pointermove"&&Math.hypot(ev.clientX-p.x,ev.clientY-p.y)<8)return;clearTimeout(t);t=null;};el.addEventListener("pointermove",c);el.addEventListener("pointerup",c);el.addEventListener("pointercancel",c);el.addEventListener("contextmenu",ev=>ev.preventDefault());});}
  return {$,$$,esc,qs,ZONA,setorNome,nomeLoja,telFmt,ini,sessao,eu,dados,ficha,estrelas,estrelasHTML,estado,salvar,abrirVendas,lerCliente,gravarCliente,cliente,definirCliente,classificar,nav,topo,voltar,acoes,menuLongo,ligarLongo};
})();
