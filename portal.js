// GenIO — funções comuns das páginas de entrada, módulos, convite e administração.
const G=(()=>{
  const ls={get:k=>{try{return localStorage.getItem(k);}catch(e){return null;}},set:(k,v)=>{try{localStorage.setItem(k,v);}catch(e){}},del:k=>{try{localStorage.removeItem(k);}catch(e){}}};
  async function api(path,body){
    let r;
    try{r=await fetch("/api/"+path,body===undefined?{credentials:"same-origin",cache:"no-store"}:{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});}
    catch(e){const x=new Error("Sem internet agora. Confira a conexão e tente de novo.");x.status=0;throw x;}
    let d={};try{d=await r.json();}catch(e){}
    if(!r.ok){const x=new Error(cap(d.erro||"Não consegui falar com o servidor."));x.status=r.status;throw x;}
    return d;}
  const cap=s=>s?s.charAt(0).toUpperCase()+s.slice(1)+(/[.!?]$/.test(s)?"":"."):s;
  // cada aparelho tem uma chave guardada nele: o plano conta aparelhos
  function aparelho(){let k=ls.get("genio-aparelho");if(!k||!/^[A-Za-z0-9_-]{8,64}$/.test(k)){const a=new Uint8Array(18);crypto.getRandomValues(a);k=btoa(String.fromCharCode(...a)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");ls.set("genio-aparelho",k);}return k;}
  function nomeAparelho(){const u=navigator.userAgent;const so=/iPhone/.test(u)?"iPhone":/iPad/.test(u)?"iPad":/Android/.test(u)?"Android":/Windows/.test(u)?"Windows":/Mac OS X/.test(u)?"Mac":/Linux/.test(u)?"Linux":"Aparelho";
    const nav=/Edg\//.test(u)?"Edge":/SamsungBrowser/.test(u)?"Samsung Internet":/Chrome\//.test(u)?"Chrome":/Firefox\//.test(u)?"Firefox":/Safari\//.test(u)?"Safari":"navegador";
    const app=(matchMedia("(display-mode: standalone)").matches||navigator.standalone)?"aplicativo":nav;return `${so} · ${app}`;}
  const guardar=c=>ls.set("genio-conta",JSON.stringify({id:c.id,nome:c.nome,email:c.email,papel:c.papel,plano:c.plano,plano_nome:c.plano_nome,em:Date.now()}));
  const guardada=()=>{try{return JSON.parse(ls.get("genio-conta")||"null");}catch(e){return null;}};
  // quem está entrando: pela internet; sem internet, a última conta que entrou neste aparelho
  async function eu(){try{const c=await api("eu");guardar(c);return c;}catch(e){if(e.status===401||e.status===403){ls.del("genio-conta");return null;}const c=guardada();if(c){c.offline=true;return c;}throw e;}}
  async function sair(){try{await api("sair",{});}catch(e){}ls.del("genio-conta");location.href="/";}
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
  function msg(el,t,tipo){el.hidden=!t;el.className="msg "+(tipo||"erro");el.textContent=t||"";}
  function olho(){$$(".senha").forEach(w=>{const i=$("input",w),b=$("button",w);if(!b)return;b.onclick=()=>{const v=i.type==="password";i.type=v?"text":"password";b.textContent=v?"Esconder":"Mostrar";b.setAttribute("aria-pressed",v);i.focus();};});}
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const data=s=>{if(!s)return"—";const d=new Date(s+"Z");return d.toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit",year:"2-digit"})+" "+d.toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"});};
  const I=p=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
  // módulos do GenIO: o Capacho funciona; os outros entram aos poucos com a mesma base (fotos, prévia, orçamento, Pix)
  const MODULOS=[
    {id:"capacho",nome:"Capachos personalizados",desc:"Tapetes e capachos personalizados, com a prévia no chão do cliente.",url:"capacho.html",on:true,img:"img/mod-capacho.jpg",ic:I('<rect x="3" y="7" width="18" height="10" rx="2"/><rect x="6" y="10" width="12" height="4" rx="1"/>')},
    {id:"placas",nome:"Placas e sinalização",desc:"Placas de porta, fachada, PVC, acrílico e sinalização.",img:"img/mod-placas.jpg",ic:I('<rect x="4" y="5" width="16" height="10" rx="1.5"/><path d="M12 15v5M9 20h6"/>')},
    {id:"adesivos",nome:"Adesivos e vitrines",desc:"Adesivos de vitrine, parede, frota e recorte.",img:"img/mod-adesivos.jpg",ic:I('<path d="M5 4h10l4 4v12H5z"/><path d="M15 4v4h4"/><path d="M8 13h8M8 16h5"/>')},
    {id:"uniformes",nome:"Uniformes e camisetas",desc:"Camisetas, polos, aventais e jalecos com a marca.",img:"img/mod-uniformes.jpg",ic:I('<path d="M8 4l-5 3 2 4 3-1v10h8V10l3 1 2-4-5-3c-.5 1.5-2 2.5-4 2.5S8.5 5.5 8 4z"/>')},
    {id:"impressos",nome:"Cartões e impressos",desc:"Cartões de visita, panfletos, cardápios e blocos.",img:"img/mod-cartoes.jpg",ic:I('<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h6M7 13h10"/>')},
    {id:"banners",nome:"Banners e faixas",desc:"Banners, faixas, wind banners e lonas.",img:"img/mod-banners.jpg",ic:I('<path d="M6 3v18"/><path d="M6 4h12l-3 4 3 4H6"/>')},
    {id:"brindes",nome:"Brindes e carimbos",desc:"Canecas, chaveiros, sacolas, carimbos e brindes com a marca.",img:"img/mod-brindes.jpg",ic:I('<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M3 9h18M12 9v11M12 9c-2-3-6-3-6-1s3 1 6 1c3 0 6 1 6-1s-4-2-6 1"/>')},
    {id:"parede",nome:"Adesivos de parede",desc:"Adesivos decorativos de parede, sob medida, com instalação.",img:"img/mod-parede.jpg",ic:I('<path d="M5 4h14v16H5z"/><path d="M9 4c2 4 2 8 0 16M15 4c-2 4-2 8 0 16"/>')}];
  // fotos de capa: banco de imagens livre (Pexels, uso comercial livre), provisórias até ter fotos reais dos produtos
  // aplicativo instalado: guarda o pedido de instalação do navegador
  let inst=null;window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();inst=e;document.dispatchEvent(new Event("genio-instalavel"));});
  const instalar=async()=>{if(!inst)return false;inst.prompt();const r=await inst.userChoice.catch(()=>null);inst=null;return r&&r.outcome==="accepted";};
  const podeInstalar=()=>!!inst;
  if("serviceWorker" in navigator&&(location.protocol==="https:"||location.hostname==="localhost"||location.hostname==="127.0.0.1"))navigator.serviceWorker.register("sw.js").catch(()=>{});
  return {api,aparelho,nomeAparelho,eu,sair,guardada,$,$$,msg,olho,esc,data,MODULOS,instalar,podeInstalar,ls};
})();
