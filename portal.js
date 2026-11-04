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
  // módulos do GenIO: o Capacho funciona; os outros entram aos poucos com a mesma base (fotos, prévia, orçamento, Pix)
  const MODULOS=[
    {id:"capacho",nome:"Capachos personalizados",desc:"Prévia no chão do cliente.",url:"capacho.html",on:true,img:"img/mod-capacho.jpg"},
    {id:"placas",nome:"Placas e sinalização",desc:"Fachada, porta e sinalização.",img:"img/mod-placas.jpg"},
    {id:"adesivos",nome:"Adesivos e vitrines",desc:"Vitrine, frota e recorte.",img:"img/mod-adesivos.jpg"},
    {id:"uniformes",nome:"Uniformes e camisetas",desc:"Camisetas e polos com a marca.",img:"img/mod-uniformes.jpg"},
    {id:"impressos",nome:"Cartões e impressos",desc:"Cartões, panfletos e cardápios.",img:"img/mod-cartoes.jpg"},
    {id:"banners",nome:"Banners e faixas",desc:"Lonas, faixas e wind banners.",img:"img/mod-banners.jpg"},
    {id:"brindes",nome:"Brindes e carimbos",desc:"Canecas, chaveiros e carimbos.",img:"img/mod-brindes.jpg"},
    {id:"parede",nome:"Adesivos de parede",desc:"Sob medida, com instalação.",img:"img/mod-parede.jpg"}];
  // fotos de capa: banco de imagens livre (Pexels, uso comercial livre), provisórias até ter fotos reais dos produtos
  // aplicativo instalado: guarda o pedido de instalação do navegador
  let inst=null;window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();inst=e;document.dispatchEvent(new Event("genio-instalavel"));});
  const instalar=async()=>{if(!inst)return false;inst.prompt();const r=await inst.userChoice.catch(()=>null);inst=null;return r&&r.outcome==="accepted";};
  const podeInstalar=()=>!!inst;
  if("serviceWorker" in navigator&&(location.protocol==="https:"||location.hostname==="localhost"||location.hostname==="127.0.0.1"))navigator.serviceWorker.register("sw.js").catch(()=>{});
  return {api,aparelho,nomeAparelho,eu,sair,guardada,$,$$,msg,olho,esc,data,MODULOS,instalar,podeInstalar,ls};
})();
