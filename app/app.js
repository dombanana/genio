// GênIO · app do representante (versão limpa) — núcleo: sessão, dados da zona, ficha do cliente, navegação.
const App=(()=>{
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
  // casca (shell.html): barra fixa + REC que continua gravando enquanto as telas trocam dentro do quadro
  const NA_CASCA=(()=>{try{return window.top!==window;}catch(e){return true;}})();
  if(!NA_CASCA&&!/shell\.html$/.test(location.pathname)&&!/[?&]solto=1/.test(location.search)){const alvo=location.pathname.split("/").pop()+location.search;location.replace("shell.html#"+alvo);}
  if(NA_CASCA){document.documentElement.classList.add("na-casca");try{window.top.postMessage({genio:"tela",href:location.pathname.split("/").pop()+location.search},location.origin);}catch(e){}}
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
  // plano de zonas (ordem da agenda a partir de 16/11): decisão do dono em 09/11 — Ipiranga e Cambuci primeiro, Cerealista depois. Guardado em /api/estado/plano.
  const PLANO_PADRAO=["ipiranga","cambuci-aclimacao","zona-cerealista"];let PLANO=PLANO_PADRAO;
  async function dados(){if(D)return D;
    PLANO=(await lerChave("plano"))||PLANO_PADRAO;if(!PLANO.includes(ZONA))PLANO=PLANO.concat([ZONA]);
    D={zonas:{},lojas:[],gerado:null};
    for(const z of PLANO){try{const r=await fetch(`/dados/captacao/${z}/lojas.json?t=${Date.now()}`,{cache:"no-store"});if(!r.ok)continue;const j=await r.json();
        D.zonas[z]={slug:z,nome:(j.zona.nome||z).split(" (")[0],base:j.zona.base,cidade:j.zona.cidade||"São Paulo",gerado:j.gerado};
        let m={};try{const c=await fetch(`/dados/captacao/${z}/clientes/index.json?t=${Date.now()}`,{cache:"no-store"});if(c.ok)(await c.json()).forEach(x=>m[x.slug]=x);}catch(e){}
        j.lojas.forEach(l=>{l.zona=z;l.cad=m[l.slug]||null;D.lojas.push(l);});}catch(e){}}
    if(!Object.keys(D.zonas).length)throw new Error("zona sem dados");
    D.zona=D.zonas[ZONA]||D.zonas[PLANO.find(z=>D.zonas[z])];localStorage.setItem("app-zona",D.zona.slug);
    D.lojas.forEach(l=>{l.estrelas=estrelas(l);});
    await migrarAparelho();            // o que algum aparelho ainda tiver guardado localmente sobe para o servidor (uma vez) e é apagado
    await carregarEstado();            // dia da rota, pedidos, avulsos, ocorrências — do servidor
    await carregarFichas(D.lojas.map(l=>l.slug).concat(AVU.map(a=>a.slug)));
    // clientes avulsos (pedido novo fora da rota): entram como lojas, sem dia/estrelas de rota
    AVU.forEach(a=>{if(!D.lojas.some(l=>l.slug===a.slug))D.lojas.push({...a,estrelas:0,avulso:true,dia:99,ordem:0});});
    return D;}
  // ---- estado compartilhado no servidor (/api/estado/<chave>): lido uma vez por página, gravado a cada mudança
  const API=async(metodo,url,corpo)=>{const r=await fetch(url,{method:metodo,credentials:"same-origin",cache:"no-store",headers:corpo!==undefined?{"Content-Type":"application/json"}:{},body:corpo!==undefined?JSON.stringify(corpo):undefined});if(r.status===401){location.href="/?entrar=1&volta="+encodeURIComponent("app/"+location.pathname.split("/").pop()+location.search);throw new Error("sem sessão");}return r;};
  const lerChave=async k=>{try{const r=await API("GET",`/api/estado/${k}`);if(!r.ok)return null;return (await r.json()).valor;}catch(e){return null;}};
  const _fila={};async function gravarChave(k,v){_fila[k]=v;if(_fila["_"+k])return;_fila["_"+k]=true;try{while(_fila[k]!==undefined){const val=_fila[k];delete _fila[k];const r=await API("PUT",`/api/estado/${k}`,{valor:val});if(!r.ok){console.warn("não gravou",k,r.status);avisarFalha("Não consegui gravar no servidor ("+r.status+"). Confira a conexão.");}}}catch(e){avisarFalha("Sem conexão com o servidor. A última alteração não foi gravada.");}finally{delete _fila["_"+k];}}
  let _aviso=0;function avisarFalha(t){if(Date.now()-_aviso<8000)return;_aviso=Date.now();try{const d=document.createElement("div");d.className="aviso-rede";d.textContent=t;document.body.appendChild(d);setTimeout(()=>d.remove(),6000);}catch(e){}}
  let EST={},AVU=[],OCO=[];
  async function carregarEstado(){let [e,a,o]=await Promise.all([lerChave("dia"),lerChave("avulsos"),lerChave("ocorrencias")]);if(!e||!Object.keys(e).length){const ant=await lerChave("dia-zona-cerealista");if(ant&&Object.keys(ant).length){e={feitas:ant.feitas||[],pedidos:ant.pedidos||{}};gravarChave("dia",e);}}EST=e||{};AVU=Array.isArray(a)?a:[];OCO=Array.isArray(o)?o:[];}
  const avulsos=()=>AVU;
  function novoAvulso(dadosA){const a={slug:"avulso-"+Date.now().toString(36),nome:(dadosA&&dadosA.nome)||("Pedido avulso "+new Date().toLocaleDateString("pt-BR")),tel:(dadosA&&dadosA.tel)||"",endereco:(dadosA&&dadosA.endereco)||"",setor:(dadosA&&dadosA.setor)||"comércio",criado:new Date().toISOString()};
    AVU.unshift(a);gravarChave("avulsos",AVU);if(D)D.lojas.push({...a,estrelas:0,avulso:true,dia:99,ordem:0});return a;}
  function atualizarAvulso(slug,campos){AVU=AVU.map(a=>a.slug===slug?{...a,...campos}:a);gravarChave("avulsos",AVU);if(D){const l=D.lojas.find(x=>x.slug===slug);if(l)Object.assign(l,campos);}}
  const zonaDe=slug=>{const l=D&&D.lojas.find(x=>x.slug===slug);return (l&&l.zona)||ZONA;};
  async function ficha(slug){try{const r=await fetch(`/dados/captacao/${zonaDe(slug)}/clientes/${slug}.json?t=${Date.now()}`,{cache:"no-store"});return r.ok?await r.json():null;}catch(e){return null;}}
  // ---- estrelas (1–5): proposta de 08/11, a validar com o Yoshio. Cada sinal soma 1; nunca menos de 1.
  function estrelas(l){let n=1;const L=(l.cad&&l.cad.lacunas)||{};
    if((l.nota||0)>=4.3&&(l.aval||0)>=20)n++;
    if(l.site||(L.site&&L.site.estado==="encontrado")||(L.redes&&L.redes.estado==="encontrado"))n++;
    if(["padaria","restaurante","bar","cafeteria","cereais/empório","clínica/consultório","salão/barbearia","academia/estúdio","ótica","pet","escola/curso","escritório/imobiliária"].includes(l.setor))n++;
    if((l.aval||0)>=80)n++;
    return Math.min(5,n);}
  const estrelasHTML=n=>`<span class="estrelas" title="${n} de 5">${"★".repeat(n)}<span class="off">${"★".repeat(5-n)}</span></span>`;
  // ---- estado do dia (feitas, seleções, pedidos): no servidor, compartilhado por todos os aparelhos da conta
  const estado=()=>EST;const salvar=e=>{EST=e;gravarChave("dia",e);};
  // ---- fichas dos clientes (logotipo, manual, artes): no servidor (/api/clientes/<slug>); aqui só um espelho em memória da página
  const FICHAS={};
  async function carregarFichas(slugs){try{const r=await API("GET",`/api/clientes?slugs=${encodeURIComponent(slugs.join(","))}`);if(!r.ok)return;(await r.json()).clientes.forEach(f=>{FICHAS[f.slug]=f;});}catch(e){}}
  const slugDeNome=nome=>{const n=chave(nome);const l=D&&D.lojas.find(x=>chave(nomeLoja(x.nome))===n);return l?l.slug:null;};
  async function lerCliente(nome){const slug=slugDeNome(nome);return slug?(await cliente({slug,nome})):null;}
  async function gravarCliente(o){if(!o.slug)throw new Error("ficha sem slug");try{const r=await API("PUT",`/api/clientes/${o.slug}`,o);if(!r.ok){const d=await r.json().catch(()=>({}));avisarFalha("Não gravou no servidor: "+(d.erro||r.status));return false;}
      const f=await r.json();for(const k of Object.keys(o))delete o[k];Object.assign(o,f);FICHAS[o.slug]=o;return true;}catch(e){avisarFalha("Sem conexão: a ficha não foi gravada.");return false;}}
  async function cliente(l){if(FICHAS[l.slug])return FICHAS[l.slug];const nome=nomeLoja(l.nome||"");
    try{const r=await API("GET",`/api/clientes/${l.slug}`);if(r.ok){const f=await r.json();FICHAS[l.slug]=f;return f;}}catch(e){}
    return FICHAS[l.slug]={k:chave(nome),nome,slug:l.slug,logos:[],arquivo:[],criado:new Date().toISOString()};}
  // ---- migração única: fichas/notas/estado que ficaram no aparelho (versão anterior) sobem para o servidor e o local é apagado
  // aviso de progresso na tela enquanto o aparelho esvazia para o servidor (pode levar minutos no 4G/5G)
  function progresso(t){let d=document.getElementById("migrando");if(!t){if(d)d.remove();return;}if(!d){d=document.createElement("div");d.id="migrando";d.style.cssText="position:fixed;inset:0;z-index:9998;display:grid;place-items:center;background:#EFEAFB;padding:24px;text-align:center;font:600 17px/1.5 Rubik,system-ui,sans-serif;color:#1C1635";document.body.appendChild(d);}d.innerHTML=`<div><div style="font-size:40px;margin-bottom:10px">☁️</div>${t}<div style="font-weight:400;font-size:14px;color:#5B5675;margin-top:10px">Mantenha o app aberto. Isso acontece uma vez só.</div></div>`;}
  async function migrarAparelho(){if(localStorage.getItem("app-migrado")==="2")return;let ok=true;
    try{const db=await Promise.race([abrirVendas(),new Promise(r=>setTimeout(()=>r(null),8000))]);if(db){const tudo=st=>new Promise(res=>{try{const t=db.transaction(st).objectStore(st).getAll();t.onsuccess=()=>res(t.result||[]);t.onerror=()=>res([]);}catch(e){res([]);}});
        const cl=await tudo("clientes");let i=0;const nCl=cl.length;for(const c of cl){i++;const slug=c.slug||slugDeNome(c.nome||"");if(!slug)continue;const temAlgo=(c.logos&&c.logos.length)||(c.manual&&c.manual.editado)||(c.artes&&Object.keys(c.artes).length)||c.fachada||(c.arquivo&&c.arquivo.length);if(!temAlgo)continue;
          progresso(`Enviando suas fichas para o servidor…<br>${i} de ${nCl} · ${esc(c.nome||slug)}`);
          const tam=JSON.stringify(c).length;if(tam>55*1024*1024){console.warn("ficha grande demais para subir inteira",slug,tam);const {artes,...semArtes}=c;c.artes={};c.artesPendentes=Object.keys(artes||{});}
          const peso=f=>Object.keys((f&&f.artes)||{}).length*10+((f&&f.manual&&f.manual.editado)?5:0)+(((f&&f.logos)||[]).length);
          const r0=await API("GET",`/api/clientes/${slug}`);if(r0.ok){const f=await r0.json();if(peso(f)>=peso(c))continue;}  // servidor já tem igual ou mais: não sobrescreve
          c.slug=slug;const r=await API("PUT",`/api/clientes/${slug}`,c);if(!r.ok)ok=false;}
        const ns=await tudo("notas");let j=0;for(const n of ns){j++;progresso(`Enviando suas notas…<br>${j} de ${ns.length}`);for(const k of ["audio","video","foto"]){if(n[k]&&typeof n[k]!=="string")n[k]=await blobParaDataURL(n[k]);}const r=await API("PUT",`/api/notas/${n.id}`,n);if(!r.ok)ok=false;}
        db.close();}
      for(const [lk,sk] of [["app-dia-"+ZONA,"dia-"+ZONA],["app-avulsos","avulsos"],["app-ocorrencias","ocorrencias"],["app-fornecedores","fornecedores"]]){const v=localStorage.getItem(lk);if(!v)continue;let val;try{val=JSON.parse(v);}catch(e){continue;}const atual=await lerChave(sk);if(atual&&(Array.isArray(atual)?atual.length:Object.keys(atual).length))continue;const r=await API("PUT",`/api/estado/${sk}`,{valor:val});if(!r.ok)ok=false;}
    }catch(e){ok=false;console.warn("migração",e);}
    progresso(null);
    if(ok){localStorage.setItem("app-migrado","2");["app-dia-"+ZONA,"app-avulsos","app-ocorrencias","app-fornecedores"].forEach(k=>localStorage.removeItem(k));try{indexedDB.deleteDatabase("genio-vendas");}catch(e){}}}
  const blobParaDataURL=b=>new Promise(res=>{const fr=new FileReader();fr.onload=()=>res(fr.result);fr.onerror=()=>res(null);fr.readAsDataURL(b);});
  // ---- (legado) banco local só é aberto pela migração acima; nada mais grava nele
  function abrirVendas(){return new Promise(res=>{try{const cria=d=>{["orcamentos","sessao"].forEach(n=>{if(!d.objectStoreNames.contains(n))d.createObjectStore(n,{keyPath:"id"});});if(!d.objectStoreNames.contains("clientes"))d.createObjectStore("clientes",{keyPath:"k"});if(!d.objectStoreNames.contains("notas"))d.createObjectStore("notas",{keyPath:"id"});};
    const r=indexedDB.open("genio-vendas");r.onupgradeneeded=()=>cria(r.result);r.onerror=()=>res(null);
    r.onsuccess=()=>{const d=r.result;if(d.objectStoreNames.contains("clientes")&&d.objectStoreNames.contains("notas"))return res(d);const v=Math.max(5,d.version+1);d.close();const r2=indexedDB.open("genio-vendas",v);r2.onupgradeneeded=()=>cria(r2.result);r2.onsuccess=()=>res(r2.result);r2.onerror=()=>res(null);r2.onblocked=()=>res(null);};}catch(e){res(null);}});}
  const chave=nome=>nome.toLowerCase();
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
  const luz=h=>{if(!h)return 255;const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);return 0.299*r+0.587*g+0.114*b;};
  function desenharLista(g,e){g.save();g.fillStyle=e.cor||"#1C1635";g.textBaseline="top";const tam=e.tam;const lh=tam*1.55;let y=e.y;
    for(const [n,p] of (e.itens||[])){if(y+lh>e.y+e.h+1)break;g.font=`500 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;g.textAlign="left";g.fillText(n,e.x,y);g.font=`700 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;g.textAlign="right";const pw=g.measureText(p).width;g.fillText(p,e.x+e.w,y);
      const nw=g.measureText(n).width;if(p){g.save();g.globalAlpha=0.35;g.setLineDash([2,tam*0.35]);g.lineWidth=Math.max(1,tam/14);g.strokeStyle=e.cor||"#1C1635";g.beginPath();g.moveTo(e.x+Math.min(nw*1.02+tam*0.5,e.w-pw-tam*0.5),y+tam*0.8);g.lineTo(e.x+e.w-pw-tam*0.4,y+tam*0.8);g.stroke();g.restore();}y+=lh;}
    g.restore();}
  // seta de sinalização com texto dentro (adesivo de parede)
  function desenharSeta(g,e){const dir=e.dir||"direita";const vert=dir==="cima"||dir==="baixo";const {x,y}=e;const w=vert?e.h:e.w,h=vert?e.w:e.h;  // desenha sempre "para a direita" e gira
    g.save();g.translate(x+e.w/2,y+e.h/2);g.rotate({direita:0,baixo:Math.PI/2,esquerda:Math.PI,cima:-Math.PI/2}[dir]||0);g.translate(-w/2,-h/2);
    const p=Math.min(h*0.5,w*0.28);g.fillStyle=e.cor||"#1C1635";g.beginPath();g.moveTo(0,h*0.18);g.lineTo(w-p,h*0.18);g.lineTo(w-p,0);g.lineTo(w,h/2);g.lineTo(w-p,h);g.lineTo(w-p,h*0.82);g.lineTo(0,h*0.82);g.closePath();g.fill();
    // texto sempre legível: desfaz a rotação para o texto nas setas verticais/esquerda
    const t=String(e.texto||"");let tam=e.tam||h*0.36;g.fillStyle=e.corTexto||"#FFFFFF";g.textBaseline="middle";g.textAlign="center";
    if(dir==="direita"||dir==="esquerda"){if(dir==="esquerda"){g.translate(w/2,h/2);g.rotate(Math.PI);g.translate(-w/2,-h/2);}const cxm=dir==="direita"?(w-p)/2:(w+p)/2;g.font=`800 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;while(g.measureText(t).width>(w-p)*0.9&&tam>6){tam*=0.94;g.font=`800 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;}g.fillText(t,cxm,h/2);}
    else{g.translate((w-p)/2,h/2);g.rotate(dir==="baixo"?-Math.PI/2:Math.PI/2);g.font=`800 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;while(g.measureText(t).width>h*0.6*0.9&&tam>6){tam*=0.94;g.font=`800 ${tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;}g.fillText(t,0,0);}
    g.restore();}
  function desenharElementos(g,el,imgs,doc){for(const e of el){g.save();if(e.rot){const cxm=e.x+e.w/2,cym=e.y+e.h/2;g.translate(cxm,cym);g.rotate(e.rot*Math.PI/180);g.translate(-cxm,-cym);}
    if(e.tipo==="camada"&&imgs[e.src]&&!e.oculta){const r=e.recorte;if(r)g.drawImage(imgs[e.src],r.sx,r.sy,r.sw,r.sh,e.x,e.y,e.w,e.h);else g.drawImage(imgs[e.src],e.x,e.y,e.w,e.h);}
    else if(e.tipo==="forma"){g.fillStyle=e.cor;g.beginPath();if(e.forma==="cir")g.ellipse(e.x+e.w/2,e.y+e.h/2,e.w/2,e.h/2,0,0,Math.PI*2);else if(e.forma==="tri"){g.moveTo(e.x+e.w/2,e.y);g.lineTo(e.x+e.w,e.y+e.h);g.lineTo(e.x,e.y+e.h);g.closePath();}else if(e.raio>0&&g.roundRect)g.roundRect(e.x,e.y,e.w,e.h,e.raio);else g.rect(e.x,e.y,e.w,e.h);
      if(e.cor!=="transparent")g.fill();if(e.borda>0){g.strokeStyle=e.bordaCor;g.lineWidth=e.borda;g.stroke();}}
    else if(e.tipo==="texto")desenharTexto(g,e);
    else if(e.tipo==="lista")desenharLista(g,e);
    else if(e.tipo==="seta")desenharSeta(g,e);
    else if(e.tipo==="carimbo")desenharCarimbo(g,e,(doc&&doc.campos)||{});
    else if(e.tipo==="qr")desenharQR(g,e);g.restore();}}
  // texto: alinhamento (left/center/right), espaçamento entre letras (esp) e entrelinha (alt)
  function desenharTexto(g,e){g.fillStyle=e.cor;g.font=`${e.peso||700} ${e.tam}px ${e.fonte||"Rubik, system-ui, sans-serif"}`;g.textBaseline="top";const al=e.alinh||"left";g.textAlign=al;try{g.letterSpacing=(e.esp||0)+"px";}catch(err){}
    const x=al==="center"?e.x+e.w/2:al==="right"?e.x+e.w:e.x;String(e.texto||"").split("\n").forEach((t,i)=>g.fillText(t,x,e.y+i*e.tam*(e.alt||1.2)));}
  // QR: real quando há endereço verificado (e.texto) e o codificador está carregado; senão um marcador genérico
  function desenharQR(g,e){const s=Math.min(e.w,e.h||e.w);g.fillStyle="#FFFFFF";g.fillRect(e.x-s*0.06,e.y-s*0.06,s*1.12,s*1.12);
    if(e.texto&&window.QR){try{window.QR.desenhar(g,e.texto,e.x,e.y,s,e.cor||"#000",null);return;}catch(err){}}
    const n=21,m=s/n;g.fillStyle=e.cor||"#000";let seed=7;const rnd=()=>{seed=(seed*9301+49297)%233280;return seed/233280;};
    const olho=(ox,oy)=>{g.fillRect(e.x+ox*m,e.y+oy*m,7*m,7*m);g.fillStyle="#fff";g.fillRect(e.x+(ox+1)*m,e.y+(oy+1)*m,5*m,5*m);g.fillStyle=e.cor||"#000";g.fillRect(e.x+(ox+2)*m,e.y+(oy+2)*m,3*m,3*m);};olho(0,0);olho(14,0);olho(0,14);
    for(let r=0;r<n;r++)for(let c=0;c<n;c++){const emOlho=(r<8&&c<8)||(r<8&&c>12)||(r>12&&c<8);if(!emOlho&&rnd()<0.45)g.fillRect(e.x+c*m,e.y+r*m,m,m);}}
  function aparar(im){try{const W=im.naturalWidth,H=im.naturalHeight;const k=Math.min(1,256/Math.max(W,H));const cv=document.createElement("canvas");cv.width=Math.max(1,Math.round(W*k));cv.height=Math.max(1,Math.round(H*k));const g=cv.getContext("2d");g.drawImage(im,0,0,cv.width,cv.height);const d=g.getImageData(0,0,cv.width,cv.height).data;
      let x0=cv.width,y0=cv.height,x1=-1,y1=-1;for(let y=0;y<cv.height;y++)for(let x=0;x<cv.width;x++){if(d[(y*cv.width+x)*4+3]>12){if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}}
      if(x1<0)return null;const m=Math.max(2,Math.round(Math.max(x1-x0,y1-y0)*0.03));x0=Math.max(0,x0-m);y0=Math.max(0,y0-m);x1=Math.min(cv.width-1,x1+m);y1=Math.min(cv.height-1,y1+m);
      const r={sx:Math.round(x0/k),sy:Math.round(y0/k),sw:Math.round((x1-x0+1)/k),sh:Math.round((y1-y0+1)/k)};if(r.sw>=W*0.92&&r.sh>=H*0.92)return null;return r;}catch(e){return null;}}
  // o editor trabalha com a imagem inteira: converte camadas com recorte em imagens já aparadas
  async function assarRecortes(doc){for(const e of (doc&&doc.el)||[]){if(e.tipo!=="camada"||!e.recorte)continue;const im=await carregarImg(e.src);if(!im){delete e.recorte;continue;}const r=e.recorte;const cv=document.createElement("canvas");cv.width=r.sw;cv.height=r.sh;cv.getContext("2d").drawImage(im,r.sx,r.sy,r.sw,r.sh,0,0,r.sw,r.sh);e.src=cv.toDataURL("image/png");delete e.recorte;}return doc;}
  const carregarScript=src=>new Promise((res,rej)=>{if(document.querySelector(`script[data-src="${src}"]`))return res();const s=document.createElement("script");s.dataset.src=src;s.src=src;s.onload=res;s.onerror=()=>rej(new Error("não carregou "+src));document.head.appendChild(s);});
  // flyer: cardápio fictício por kit (hoje só padaria; outros setores entram com os próximos kits)
  const CARDAPIOS={padaria:{titulo:"Nossos produtos",itens:[["Pão francês (kg)","R$ 18,90"],["Pão de queijo (un.)","R$ 4,50"],["Croissant de manteiga","R$ 9,00"],["Bolo de cenoura (fatia)","R$ 8,50"],["Sonho de creme","R$ 7,00"],["Café coado (copo)","R$ 4,00"],["Pão na chapa + café","R$ 9,90"],["Baguete artesanal","R$ 12,00"]],promo:["PROMOÇÃO DA SEMANA","Café + pão na chapa","por R$ 8,90","seg. a sex., das 6h às 10h","apresente este flyer"]}};
  const cardapioDe=()=>CARDAPIOS.padaria;
  // ---- recorte em lote: para cada loja com logotipo escolhido e ainda não tratado, o servidor tira o fundo (rembg) e separa as cores
  async function recortarLogo(l){const c=await cliente(l);const p=(c.logos||[])[0];if(!p||!p.src)return {ok:false,motivo:"sem logotipo"};if(c.manual&&c.manual.editado)return {ok:true,ja:true};
    let png=p.src;if(!png.startsWith("data:")){const im=await carregarImg(png.startsWith("/")||png.startsWith(location.origin)?png:`/api/img?u=${encodeURIComponent(png)}`);if(!im)return {ok:false,motivo:"imagem não abriu"};const cv=document.createElement("canvas");const k=Math.min(1,1400/Math.max(im.naturalWidth,im.naturalHeight));cv.width=Math.round(im.naturalWidth*k);cv.height=Math.round(im.naturalHeight*k);cv.getContext("2d").drawImage(im,0,0,cv.width,cv.height);png=cv.toDataURL("image/png");}
    const r=await fetch("/api/marca/preparar",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({png})});const d=await r.json().catch(()=>({}));
    if(!r.ok||!d.sem_fundo)return {ok:false,motivo:d.mensagem||d.erro||("servidor "+r.status)};
    const camadas=(d.camadas||[]).map((x,i)=>({nome:i===0?"Cor principal":(x.nome||"Cor")+" "+(x.hex||""),cor:x.hex||null,png:x.png,area:x.area}));
    c.manual={editado:true,tratado:d.sem_fundo,largura:d.largura,altura:d.altura,cores:(d.cores||[]).map(x=>({nome:x.nome||"Cor",hex:x.hex,area:x.area})),camadas:camadas.length>1?camadas:[{nome:"Logotipo",png:d.sem_fundo}],separado:true,auto:true,por:d.fundo_removido_por||"servidor",em:new Date().toISOString()};
    p.tratado=true;p.src=d.sem_fundo;await gravarCliente(c);return {ok:true,por:d.fundo_removido_por};}
  // ---- arte automática: logotipo tratado centralizado preenchendo a área segura do gabarito, cor padrão do material
  const COR_PADRAO={capacho:"#2B2B2D",rigido:"#F4F1EA",vinil:null,tecido:"#F4F1EA",papel:"#FFFFFF",lona:"#FFFFFF",carimbo:null};
  const PRODUTOS_IDS=["capacho","placas","adesivos","uniformes","impressos","panfleto","banners","parede","brindes","carimbo"];
  let _G=null;const gabaritos=async()=>_G||(_G=await (await fetch("gabaritos.json?v=9d8731c0e4")).json());
  const carregarImg=src=>new Promise(res=>{const i=new Image();i.crossOrigin="anonymous";i.onload=()=>res(i);i.onerror=()=>res(null);i.src=src;});
  // ---- carimbo: só texto — nome, razão social, CNPJ (negrito), endereço, telefone; nunca logotipo
  async function dadosCarimbo(l){const cad=await ficha(l.slug).catch(()=>null);const L=(cad&&cad.lacunas)||{};const leit=(L.leitura||{}).valor||"";const razao=((leit.match(/Razão social: ([^·]+)/)||[])[1]||"").trim();const cnpj=((leit.match(/CNPJ:? ?([\d./-]{14,18})/)||[])[1]||"");
    return {nome:nomeLoja(l.nome),razao,cnpj,endereco:((L.endereco||{}).valor||l.endereco||"").split(" · ")[0],tel:l.tel?telFmt(l.tel):""};}
  // cena do carimbo: uma folha com várias marcas de exemplo (sempre com o nome da empresa) e, por último, o carimbo completo
  function cenaCarimbo(cp){const W=1536,H=1024;const cv=document.createElement("canvas");cv.width=W;cv.height=H;const g=cv.getContext("2d");
    g.fillStyle="#D9D3C7";g.fillRect(0,0,W,H);g.fillStyle="#FBF8F1";g.shadowColor="rgba(0,0,0,.25)";g.shadowBlur=30;g.shadowOffsetY=12;g.fillRect(96,56,W-192,H-112);g.shadowColor="transparent";
    g.strokeStyle="#E6E1D6";g.lineWidth=1;for(let y=140;y<H-90;y+=46){g.beginPath();g.moveTo(130,y);g.lineTo(W-130,y);g.stroke();}
    const nome=(cp.nome||"NOME DA EMPRESA").toUpperCase();
    function marca(x,y,ang,cor,linhas,larg,alturaBase,grosso){const h=linhas.reduce((a,l)=>a+l[1]*1.35,0)+34;const oc=document.createElement("canvas");oc.width=Math.ceil(larg+40);oc.height=Math.ceil(h+40);const o=oc.getContext("2d");o.translate(oc.width/2,oc.height/2);
      o.strokeStyle=cor;o.fillStyle=cor;o.lineWidth=grosso||6;o.strokeRect(-larg/2,-h/2,larg,h);o.textAlign="center";o.textBaseline="top";let yy=-h/2+17;
      for(const [t,tam,peso] of linhas){let f=tam;o.font=`${peso||700} ${f}px Arial, Helvetica, sans-serif`;while(o.measureText(t).width>larg-30&&f>8){f*=0.94;o.font=`${peso||700} ${f}px Arial, Helvetica, sans-serif`;}o.fillText(t,0,yy);yy+=tam*1.35;}
      // falhas de tinta: pequenos furos só na própria marca
      o.globalCompositeOperation="destination-out";let sd=7;const rnd=()=>{sd=(sd*9301+49297)%233280;return sd/233280;};for(let i=0;i<260;i++){o.globalAlpha=0.5+rnd()*0.5;o.beginPath();o.arc((rnd()-0.5)*larg,(rnd()-0.5)*h,rnd()*2.2+0.6,0,7);o.fill();}
      g.save();g.translate(x,y);g.rotate(ang*Math.PI/180);g.globalAlpha=0.9;g.drawImage(oc,-oc.width/2,-oc.height/2);g.restore();}
    const AZ="#1F3A8A",VM="#B42318",VD="#1B6B3A",RX="#4C2A85";
    marca(380,230,-7,VM,[["ENTREGUE",52],[nome,18,500]],330,0);
    marca(800,215,5,AZ,[["EM PREPARAÇÃO",40],[nome,18,500]],360,0);
    marca(1180,250,-4,VD,[["RECEBIDO EM ___/___/______",26],[nome,18,500]],360,0);
    marca(420,470,6,RX,[["PAGO",56],[nome,18,500]],280,0);
    marca(850,480,-6,VM,[["CONFERIDO",44],[nome,18,500]],330,0);
    marca(1210,470,3,AZ,[["URGENTE",48],[nome,18,500]],300,0);
    // carimbo completo, reto e maior
    marca(W/2,790,0,"#141C3A",[[nome,44,800],[cp.razao||"Razão social: a preencher",26,400],["CNPJ "+(cp.cnpj||"00.000.000/0000-00"),32,800],[cp.endereco||"Endereço: a preencher",24,400],[cp.tel||"Telefone: a preencher",26,500]],760,0,7);
    return cv.toDataURL("image/jpeg",0.9);}
  // desenha o bloco do carimbo (usado na arte automática e no editor); x,y,w em px do gabarito; retorna a altura usada
  function desenharCarimbo(g,e,cp){const linhas=[[cp.nome||"NOME DA EMPRESA",1.15,800],[cp.razao||"Razão social: a preencher",0.78,400],[("CNPJ "+(cp.cnpj||"00.000.000/0000-00")),0.9,800],[cp.endereco||"Endereço: a preencher",0.72,400],[cp.tel||"Telefone: a preencher",0.78,500]];
    g.save();g.fillStyle=e.cor||"#1C1635";g.textBaseline="top";g.textAlign="center";let y=e.y;const cxm=e.x+e.w/2;
    for(const [t,f,p] of linhas){let tam=e.tam*f;g.font=`${p} ${Math.round(tam)}px ${e.fonte||"Arial, Helvetica, sans-serif"}`;while(g.measureText(t).width>e.w&&tam>6){tam*=0.95;g.font=`${p} ${Math.round(tam)}px ${e.fonte||"Arial, Helvetica, sans-serif"}`;}g.fillText(t,cxm,y);y+=tam*1.3;}
    g.restore();e.h=Math.max(y-e.y,10);return e.h;}
  async function artePadrao(pid,c,l){const G=await gabaritos();const P=G.produtos[pid];if(!P)return null;
    if(pid==="carimbo"){const sang=0,seg=P.seguranca_mm!=null?P.seguranca_mm:G.seguranca_mm;const PX=Math.min(100,Math.floor(3000/Math.max(P.w_cm,P.h_cm)));const W=Math.round(P.w_cm*PX),H=Math.round(P.h_cm*PX),S=Math.round(seg/10*PX);
      const cp=l?await dadosCarimbo(l):{nome:""};const e={tipo:"carimbo",id:"carimbo",nome:"Dados do carimbo",x:S,y:S,w:W-2*S,h:H-2*S,cor:"#1C1635",tam:Math.round(H/8.5),fonte:"Arial, Helvetica, sans-serif"};
      const cv=document.createElement("canvas");cv.width=W;cv.height=H;const g=cv.getContext("2d");g.strokeStyle="#1C1635";g.lineWidth=Math.max(2,W/120);g.strokeRect(g.lineWidth,g.lineWidth,W-2*g.lineWidth,H-2*g.lineWidth);
      desenharCarimbo(g,e,cp);const pngArte=cv.toDataURL("image/png");const doc={fundo:null,fundoImg:null,el:[{tipo:"forma",forma:"ret",id:"moldura",nome:"Moldura",x:0,y:0,w:W,h:H,cor:"transparent",borda:Math.max(2,W/120),bordaCor:"#1C1635"},e],campos:cp,carimbo:true,auto:true};
      return {doc,png:pngArte,pngArte,material:null,w_cm:P.w_cm,h_cm:P.h_cm,sangria_mm:0,em:new Date().toISOString(),contexto:null,soTexto:true};}
    if(!(c.manual&&c.manual.tratado))return null;const im=await carregarImg(c.manual.tratado);if(!im)return null;const rec=aparar(im);const LW=rec?rec.sw:im.naturalWidth,LH=rec?rec.sh:im.naturalHeight;
    const sang=P.sangria_mm!=null?P.sangria_mm:G.sangria_mm,seg=P.seguranca_mm!=null?P.seguranca_mm:G.seguranca_mm;
    const PX=Math.min(100,Math.floor(3000/Math.max(P.w_cm+sang/5,P.h_cm+sang/5)));const W=Math.round((P.w_cm+2*sang/10)*PX),H=Math.round((P.h_cm+2*sang/10)*PX),B=Math.round(sang/10*PX),S=Math.round(seg/10*PX);
    const aw=W-2*(B+S),ah=H-2*(B+S);const f=Math.min(aw/LW,(P.ancora==="topo"?ah*0.45:ah)/LH);const w=LW*f,h=LH*f;const x=(W-w)/2,y=P.ancora==="topo"?B+S+ah*0.05:(H-h)/2;
    const fundo=P.sem_fundo?null:(COR_PADRAO[P.superficie]===undefined?"#FFFFFF":COR_PADRAO[P.superficie]);
    if(pid==="impressos"||pid==="panfleto"){await carregarScript("qr.js?v=9d8731c0e4");await carregarScript("impressos.js?v=9d8731c0e4");return window.Impressos.arteImpressa(App,pid,c,l,{P,G,W,H,B,S,PX,im,sang,rec});}
    if(pid==="panfleto"){const M=cardapioDe();const f1=B+S,ah3=(H-2*(B+S))/3;const lf=Math.min(aw/im.naturalWidth,(ah3*0.8)/im.naturalHeight);const lw=im.naturalWidth*lf,lh=im.naturalHeight*lf;
      const cor=(c.manual.cores&&c.manual.cores[0]&&c.manual.cores[0].hex)||"#6933C5";const esc_=luz(cor)<140?"#FFFFFF":"#1C1635";
      const el=[{tipo:"camada",id:"logo",nome:"Logotipo",src:c.manual.tratado,cor:null,usarCor:false,x:(W-lw)/2,y:f1+(ah3-lh)/2,w:lw,h:lh,borda:0,bordaCor:"#FFFFFF",grupo:"logo"},
        {tipo:"texto",id:"tit",nome:"Título da lista",texto:M.titulo,x:f1+W*0.06,y:f1+ah3+ah3*0.04,w:W*0.8,h:ah3*0.12,cor:"#1C1635",tam:Math.round(ah3*0.11),fonte:"Rubik, system-ui, sans-serif",peso:800},
        {tipo:"lista",id:"lista",nome:"Lista de produtos (exemplo)",itens:M.itens,x:f1+W*0.06,y:f1+ah3+ah3*0.2,w:W-2*f1-W*0.12,h:ah3*0.78,cor:"#1C1635",tam:Math.round(ah3*0.065),fonte:"Rubik, system-ui, sans-serif"},
        {tipo:"forma",forma:"ret",id:"faixa",nome:"Faixa da promoção",x:0,y:f1+2*ah3+ah3*0.04,w:W,h:H-(f1+2*ah3+ah3*0.04),cor,borda:0,bordaCor:"#1C1635"},
        {tipo:"texto",id:"promo",nome:"Promoção",texto:M.promo.join("\n"),x:f1+W*0.06,y:f1+2*ah3+ah3*0.14,w:W*0.8,h:ah3*0.7,cor:esc_,tam:Math.round(ah3*0.085),fonte:"Rubik, system-ui, sans-serif",peso:800}];
      const doc={fundo:"#FFFFFF",fundoImg:null,el,campos:null,auto:true};const k=Math.min(1,1400/Math.max(W,H));const cv=document.createElement("canvas");cv.width=Math.round(W*k);cv.height=Math.round(H*k);const g=cv.getContext("2d");g.scale(k,k);
      desenharElementos(g,el,{[c.manual.tratado]:im});const pngArte=cv.toDataURL("image/png");g.globalCompositeOperation="destination-over";g.fillStyle="#FFFFFF";g.fillRect(0,0,W,H);const png=cv.toDataURL("image/jpeg",0.88);
      return {doc,png,pngArte,material:"#FFFFFF",w_cm:P.w_cm,h_cm:P.h_cm,sangria_mm:sang,em:new Date().toISOString(),contexto:null};}
    if(pid==="parede"){const cor=(c.manual.cores&&c.manual.cores[0]&&c.manual.cores[0].hex)||"#1C1635";const ct=luz(cor)<140?"#FFFFFF":"#1C1635";
      const colL=aw*0.46,colR=aw*0.48,x0=B+S,y0=B+S;const lf=Math.min(colL/LW,(ah*0.6)/LH);const lw=LW*lf,lh=LH*lf;
      const sh=ah*0.14,gap=ah*0.05,yS=(H-(3*sh+2*gap))/2,xS=x0+colL+aw*0.06;
      const el=[{tipo:"camada",id:"logo",nome:"Logotipo",src:c.manual.tratado,recorte:rec||undefined,cor:null,usarCor:false,x:x0+(colL-lw)/2,y:(H-lh)/2,w:lw,h:lh,borda:0,bordaCor:"#FFFFFF",grupo:"logo"}];
      ["Balcão","Caixa","Banheiros"].forEach((t,i)=>el.push({tipo:"seta",id:"seta"+(i+1),nome:"Seta · "+t,texto:t,x:xS,y:yS+i*(sh+gap),w:colR,h:sh,cor,corTexto:ct,tam:Math.round(sh*0.38),fonte:"Rubik, system-ui, sans-serif"}));
      const doc={fundo:null,fundoImg:null,el,campos:null,auto:true};const k=Math.min(1,1400/Math.max(W,H));const cv=document.createElement("canvas");cv.width=Math.round(W*k);cv.height=Math.round(H*k);const g=cv.getContext("2d");g.scale(k,k);
      desenharElementos(g,el,{[c.manual.tratado]:im});const pngArte=cv.toDataURL("image/png");
      return {doc,png:pngArte,pngArte,material:null,w_cm:P.w_cm,h_cm:P.h_cm,sangria_mm:sang,em:new Date().toISOString(),contexto:null};}
    const cams=(c.manual.camadas||[]).filter(q=>q.png);const el=cams.length>1?cams.map((q,i)=>({tipo:"camada",id:"c"+i,nome:q.nome||("Cor "+(i+1)),src:q.png,recorte:rec||undefined,cor:q.cor||null,usarCor:false,x,y,w,h,borda:0,bordaCor:"#FFFFFF",grupo:"logo"})):[{tipo:"camada",id:"logo",nome:"Logotipo",src:c.manual.tratado,recorte:rec||undefined,cor:null,usarCor:false,x,y,w,h,borda:0,bordaCor:"#FFFFFF",grupo:"logo"}];
    const doc={fundo,fundoImg:null,el,campos:null,auto:true};
    const k=Math.min(1,1400/Math.max(W,H));const cv=document.createElement("canvas");cv.width=Math.round(W*k);cv.height=Math.round(H*k);const g=cv.getContext("2d");
    if(rec)g.drawImage(im,rec.sx,rec.sy,rec.sw,rec.sh,x*k,y*k,w*k,h*k);else g.drawImage(im,x*k,y*k,w*k,h*k);const pngArte=cv.toDataURL("image/png");
    g.globalCompositeOperation="destination-over";if(fundo){g.fillStyle=fundo;g.fillRect(0,0,cv.width,cv.height);}const png=cv.toDataURL(fundo?"image/jpeg":"image/png",0.88);
    return {doc,png,pngArte,material:fundo,w_cm:P.w_cm,h_cm:P.h_cm,sangria_mm:sang,em:new Date().toISOString(),contexto:null};}
  // gera (e contextualiza) todos os produtos de uma loja; pula os que já têm arte feita à mão
  async function gerarProdutos(l,aoPasso){let c=await garantirCamadas(l);if(!(c.manual&&c.manual.editado))return {ok:0,falhas:["sem logotipo tratado"]};c.artes=c.artes||{};let ok=0;const falhas=[];
    for(const pid of PRODUTOS_IDS){const ant=c.artes[pid];if(pid==="carimbo"&&ant&&!ant.soTexto){/* carimbo antigo com logotipo: refaz só texto */}else if(ant&&ant.contexto&&!(ant.doc&&ant.doc.auto))continue;if(aoPasso)aoPasso(pid);
      try{const logoAnt=ant&&ant.doc&&ant.doc.auto&&(ant.doc.el||[]).find(e=>e.grupo==="logo");const mesmoKit=!ant||!["impressos","panfleto"].includes(pid)||ant.kitBase==="genio-ra-1.1";
        const a=ant&&ant.contexto&&logoAnt&&logoAnt.src===c.manual.tratado&&mesmoKit&&pid!=="carimbo"?ant:await artePadrao(pid,c,l);if(!a){falhas.push(pid+": sem gabarito");continue;}
        if(pid==="carimbo"&&!a.contexto){a.contexto=cenaCarimbo((a.doc&&a.doc.campos)||{});a.kit="carimbo-folha";}
        if(!a.contexto){const r=await fetch("/api/kit/aplicar",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({setor:l.setor,produto:pid,png:a.pngArte,material:a.material})});const d=await r.json();if(r.ok&&d.jpg){a.contexto=d.jpg;a.kit=d.kit;}else falhas.push(pid+": "+(d.mensagem||d.erro||r.status));}
        c.artes[pid]=a;ok++;}catch(e){falhas.push(pid+": "+e.message);}}
    await gravarCliente(c);return {ok,falhas};}
  // ---- notas (gravador): áudio + texto, ligadas à última loja aberta
  async function listarNotas(){try{const r=await API("GET","/api/notas");if(!r.ok)return [];return (await r.json()).notas;}catch(e){return [];}}
  async function gravarNota(n){const o={...n};for(const k of ["audio","video","foto"]){if(o[k]&&typeof o[k]!=="string")o[k]=await blobParaDataURL(o[k]);}try{const r=await API("PUT",`/api/notas/${o.id}`,o);if(!r.ok){avisarFalha("A nota não foi gravada no servidor ("+r.status+").");return false;}return true;}catch(e){avisarFalha("Sem conexão: a nota não foi gravada.");return false;}}
  async function apagarNota(id){try{const r=await API("DELETE",`/api/notas/${id}`);return r.ok;}catch(e){return false;}}
  // ---- agenda de rotas: lojas 3–5★ em dias de 50; dia 1 = data do início (primeira abertura); seg–sex; sábado = recuperação das pendentes
  const META=50;
  function diasDeRota(D){const dias=[];/* 1–2 estrelas ficam fora da rota; zonas na ordem do plano, cada uma em dias de 50 */
    for(const z of PLANO){const lista=D.lojas.filter(l=>l.zona===z&&l.estrelas>=3).sort((a,b)=>b.estrelas-a.estrelas||a.dia-b.dia||a.ordem-b.ordem);for(let i=0;i<lista.length;i+=META){const g=lista.slice(i,i+META);g.zona=z;dias.push(g);}}
    // primeira saída de vendas: segunda 16/11/2026 (decisão do dono); datas anteriores guardadas no aparelho são corrigidas
    const INICIO="2026-11-16";const e=estado();if(!e.inicio||e.inicio<INICIO){e.inicio=INICIO;delete e.datas;salvar(e);}const datas=[];let d=new Date(e.inicio+"T12:00:00");for(let k=0;k<dias.length;k++){while(d.getDay()===0||d.getDay()===6)d.setDate(d.getDate()+1);/* rotas só de segunda a sexta */datas.push(d.toISOString().slice(0,10));d.setDate(d.getDate()+1);}
    const mov=e.datas||{};const out=dias.map((lojas,i)=>({n:i+1,data:mov[i+1]||datas[i],dataOriginal:datas[i],lojas,zona:lojas.zona}));
    // janela da agenda: hoje, 15 dias úteis para trás e 15 para a frente (31 datas); dias sem lojas ficam "a captar"
    const hoje=hojeISO();const vistos=new Set(out.map(x=>x.data));const util=d=>d.getDay()!==0&&d.getDay()!==6;const iso=d=>d.toISOString().slice(0,10);
    const add=d=>{const k=iso(d);if(!vistos.has(k)){out.push({n:0,data:k,dataOriginal:k,lojas:[],vazio:true});vistos.add(k);}};
    let dj=new Date(hoje+"T12:00:00");if(util(dj))add(dj);let k=0;while(k<15){dj.setDate(dj.getDate()+1);if(util(dj)){add(dj);k++;}}
    dj=new Date(hoje+"T12:00:00");k=0;while(k<15){dj.setDate(dj.getDate()-1);if(util(dj)){add(dj);k++;}}
    const lim0=(()=>{const x=new Date(hoje+"T12:00:00");let c=0;while(c<15){x.setDate(x.getDate()-1);if(util(x))c++;}return iso(x);})();const lim1=(()=>{const x=new Date(hoje+"T12:00:00");let c=0;while(c<15){x.setDate(x.getDate()+1);if(util(x))c++;}return iso(x);})();
    // rotas com lojas fora da janela continuam existindo (ex.: início em 16/11 fora dos 15 dias), mas a faixa mostra só a janela + rotas com lojas
    for(let i=out.length-1;i>=0;i--){const o=out[i];if(o.vazio&&(o.data<lim0||o.data>lim1))out.splice(i,1);}
    out.filter(o=>o.vazio).forEach(o=>{o.n=0;});let nn=Math.max(0,...out.map(o=>o.n))+1;out.sort((a,b)=>a.data.localeCompare(b.data));out.forEach(o=>{if(!o.n)o.n=nn++;});
    out.sort((a,b)=>a.data.localeCompare(b.data));return out;}
  // rota não feita continua presa à sua data; reagendar move só aquela rota
  function reagendar(n,iso){const e=estado();e.datas=e.datas||{};if(iso)e.datas[n]=iso;else delete e.datas[n];salvar(e);}
  const hojeISO=()=>{const d=new Date();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,10);};
  const dataCurta=iso=>{const d=new Date(iso+"T12:00:00");return {dia:d.getDate(),sem:["dom","seg","ter","qua","qui","sex","sáb"][d.getDay()],mes:["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][d.getMonth()]};};
  // ---- separação de cores do logotipo (no aparelho): k-means em RGB, junta cores parecidas, descarta <3% → uma camada por cor
  async function separarCores(png,maxK){const im=await carregarImg(png);if(!im)return null;const k0=Math.min(1,900/Math.max(im.naturalWidth,im.naturalHeight));
    const W=Math.max(1,Math.round(im.naturalWidth*k0)),H=Math.max(1,Math.round(im.naturalHeight*k0));const cv=document.createElement("canvas");cv.width=W;cv.height=H;const g=cv.getContext("2d",{willReadFrequently:true});g.drawImage(im,0,0,W,H);const d=g.getImageData(0,0,W,H).data;
    const pts=[];for(let i=0;i<W*H;i++)if(d[i*4+3]>60)pts.push(i);if(pts.length<50)return null;
    const amostra=[];for(let j=0;j<pts.length;j+=Math.max(1,Math.floor(pts.length/6000)))amostra.push(pts[j]);
    let K=Math.min(maxK||5,6);let cent=[];for(let k=0;k<K;k++){const i=amostra[Math.floor(amostra.length*(k+0.5)/K)];cent.push([d[i*4],d[i*4+1],d[i*4+2]]);}
    const perto=i=>{let b=0,bd=1e9;for(let k=0;k<cent.length;k++){const dr=d[i*4]-cent[k][0],dg=d[i*4+1]-cent[k][1],db=d[i*4+2]-cent[k][2];const dd=dr*dr+dg*dg+db*db;if(dd<bd){bd=dd;b=k;}}return b;};
    for(let it=0;it<10;it++){const soma=cent.map(()=>[0,0,0,0]);for(const i of amostra){const k=perto(i);soma[k][0]+=d[i*4];soma[k][1]+=d[i*4+1];soma[k][2]+=d[i*4+2];soma[k][3]++;}cent=soma.filter(x=>x[3]).map(x=>[x[0]/x[3],x[1]/x[3],x[2]/x[3]]);}
    let m=true;while(m&&cent.length>1){m=false;for(let a=0;a<cent.length&&!m;a++)for(let b=a+1;b<cent.length&&!m;b++){if(Math.hypot(cent[a][0]-cent[b][0],cent[a][1]-cent[b][1],cent[a][2]-cent[b][2])<40){cent[a]=cent[a].map((v,i)=>(v+cent[b][i])/2);cent.splice(b,1);m=true;}}}
    const rot=new Uint8Array(W*H);const cont=cent.map(()=>0);for(const i of pts){const k=perto(i);rot[i]=k+1;cont[k]++;}
    const ordem=cent.map((c,k)=>k).filter(k=>cont[k]/pts.length>=0.03).sort((a,b)=>cont[b]-cont[a]);if(ordem.length<2)return null;
    const hex=c=>"#"+c.map(v=>Math.round(v).toString(16).padStart(2,"0")).join("");
    const nomes=ordem.map((k,i)=>{const c=cent[k];const l=(0.299*c[0]+0.587*c[1]+0.114*c[2]);return i===0?"Cor principal":l<70?"Escuro":l>200?"Claro":"Cor "+(i+1);});
    const camadas=ordem.map((k,i)=>{const o=document.createElement("canvas");o.width=W;o.height=H;const og=o.getContext("2d");const id=og.createImageData(W,H);const e=id.data;
      for(const p of pts){let r=rot[p]-1;if(!ordem.includes(r)){let b=ordem[0],bd=1e9;for(const q of ordem){const dd=Math.hypot(d[p*4]-cent[q][0],d[p*4+1]-cent[q][1],d[p*4+2]-cent[q][2]);if(dd<bd){bd=dd;b=q;}}r=b;}
        if(r===k){e[p*4]=d[p*4];e[p*4+1]=d[p*4+1];e[p*4+2]=d[p*4+2];e[p*4+3]=d[p*4+3];}}
      og.putImageData(id,0,0);return {nome:nomes[i],cor:hex(cent[k]),png:o.toDataURL("image/png"),area:Math.round(cont[k]*100/pts.length)};});
    return {camadas,cores:camadas.map(c=>({nome:c.nome,hex:c.cor,area:c.area})),largura:W,altura:H};}
  // garante que o manual da loja tem camadas por cor (separa uma vez e guarda)
  async function garantirCamadas(l){const c=await cliente(l);const m=c.manual;if(!m||!m.editado||!m.tratado)return c;if((m.camadas||[]).length>1&&m.separado)return c;
    const r=await separarCores(m.tratado,5);if(r){m.camadas=r.camadas;m.cores=r.cores;m.separado=true;}else{m.camadas=[{nome:"Logotipo",png:m.tratado}];m.separado=true;}await gravarCliente(c);return c;}
  // ---- ícones da barra: ilustrações 3D (Fluent Emoji 3D, MIT) + rosto do vendedor; o servidor baixa para vendor/icones, senão vem do CDN
  const ICO_CDN={entrada:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Inbox%20tray/3D/inbox_tray_3d.png",processamento:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Hammer%20and%20wrench/3D/hammer_and_wrench_3d.png",saida:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Delivery%20truck/3D/delivery_truck_3d.png",ocorrencias:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Warning/3D/warning_3d.png",financeiro:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Money%20bag/3D/money_bag_3d.png","rec-audio":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Studio%20microphone/3D/studio_microphone_3d.png","rec-transcrever":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Memo/3D/memo_3d.png","rec-video":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Video%20camera/3D/video_camera_3d.png","rec-selfie":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Selfie/3D/selfie_3d_default.png","rec-foto":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Camera%20with%20flash/3D/camera_with_flash_3d.png","rec-tela":"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Mobile%20phone/3D/mobile_phone_3d.png",config:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Gear/3D/gear_3d.png",notas:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Spiral%20notepad/3D/spiral_notepad_3d.png",mapa:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/World%20map/3D/world_map_3d.png",pedidos:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Clipboard/3D/clipboard_3d.png",rec:"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Red%20circle/3D/red_circle_3d.png"};
  const ico=(n,alt)=>`<img src="vendor/icones/${n}.png" alt="${alt||""}" onerror="this.onerror=null;this.src='${ICO_CDN[n]||""}'">`;
  const ICONES={rota:`<span class="ic-mapa">${ico("mapa","")}<svg viewBox="0 0 48 48"><path d="M8 36 C14 30, 16 22, 22 20 S30 26, 34 18 S40 12, 42 10" fill="none" stroke="#6933C5" stroke-width="4.5" stroke-linecap="round" stroke-dasharray="7 4"/><circle cx="8" cy="36" r="4.5" fill="#14B8B0" stroke="#fff" stroke-width="2"/><path d="M42 3c-3.3 0-6 2.6-6 5.9C36 13 42 19 42 19s6-6 6-10.1C48 5.6 45.3 3 42 3z" fill="#C62828" stroke="#fff" stroke-width="1.5"/><circle cx="42" cy="8.8" r="2.2" fill="#fff"/></svg></span>`,
    pedidos:ico("pedidos"),perfil:`<img src="vendor/icones/vendedor.png" alt="">`,notas:ico("rec"),notasLista:ico("notas"),config:ico("config"),financeiro:ico("financeiro"),ocorrencias:ico("ocorrencias"),entrada:ico("entrada"),processamento:ico("processamento"),saida:ico("saida"),recModo:t=>ico({audio:"rec-audio",transcrever:"rec-transcrever","video-tras":"rec-video","video-frente":"rec-selfie",foto:"rec-foto",selfie:"rec-selfie",tela:"rec-tela"}[t]||"rec-audio")};
  // ---- etapas do pedido: entrada (selecionando/orçando) → processamento (produção) → saída (entrega/instalação) → entregue
  const ETAPAS=["entrada","processamento","saida","entregue"];
  const etapaDe=slug=>{const e=estado();return ((e.pedidos||{})[slug]||{}).etapa||"entrada";};
  function moverEtapa(slug,etapa,dados){const e=estado();e.pedidos=e.pedidos||{};const p=e.pedidos[slug]||{};p.etapa=etapa;p.hist=(p.hist||[]).concat([{etapa,em:new Date().toISOString()}]);Object.assign(p,dados||{});e.pedidos[slug]=p;salvar(e);return p;}
  // ---- ocorrências: o que está atravancando algum processo (automáticas) + as que o vendedor registra
  const ocorrenciasManuais=()=>OCO;
  const gravarOcorrencias=l=>{OCO=l;gravarChave("ocorrencias",l);};
  async function ocorrenciasAuto(D){const out=[];const e=estado();const sel=e.sel||{};const hoje=hojeISO();
    for(const l of D.lojas){const c=await cliente(l);const S=sel[l.slug]||{};const pedidos=Object.entries(S).filter(([k,v])=>v&&v.q>0&&!v.servico).map(([k])=>k);
      if(pedidos.length&&!(c.manual&&c.manual.editado))out.push({nivel:"urgente",loja:l,texto:"Pedido com itens, mas o logotipo não está tratado",acao:`visita.html?l=${encodeURIComponent(l.slug)}`});
      for(const pid of pedidos){const A=(c.artes||{})[pid];if(!A)out.push({nivel:"urgente",loja:l,texto:`Item "${(S[pid].nome||pid)}" no orçamento sem arte`,acao:pid==="capacho"?`capacho.html?l=${encodeURIComponent(l.slug)}`:`editor.html?l=${encodeURIComponent(l.slug)}&p=${pid}`});}
      if(l.avulso&&(!l.tel||/^Pedido avulso/.test(l.nome)))out.push({nivel:"atencao",loja:l,texto:"Cliente avulso sem nome ou telefone",acao:`visita.html?l=${encodeURIComponent(l.slug)}`});
      if((c.logos||[]).length&&!(c.manual&&c.manual.editado)&&e.feitas&&e.feitas.includes(l.slug))out.push({nivel:"atencao",loja:l,texto:"Visitada, logotipo escolhido e ainda sem recorte",acao:`visita.html?l=${encodeURIComponent(l.slug)}`});}
    try{const notas=await listarNotas();const velhas=notas.filter(n=>!n.loja&&n.em.slice(0,10)<hoje);if(velhas.length)out.push({nivel:"atencao",texto:`${velhas.length} nota(s) de dias anteriores sem cliente`,acao:"notas.html"});}catch(e){}
    try{const dias=diasDeRota(D);const pend=dias.filter(d=>!d.vazio&&d.data<hoje&&d.lojas.some(l=>!(e.feitas||[]).includes(l.slug)));if(pend.length)out.push({nivel:"atencao",texto:`${pend.length} rota(s) passada(s) com lojas não visitadas`,acao:"index.html"});}catch(e){}
    return out;}
  const nav=on=>NA_CASCA?"":`<nav class="nav"><a href="index.html" class="${on==="rota"?"on":""}"><span class="ic">${ICONES.rota}</span>Rota</a><a href="pedidos.html" class="${on==="pedidos"?"on":""}"><span class="ic">${ICONES.pedidos}</span>Pedidos</a><a href="perfil.html" class="${on==="perfil"?"on":""}"><span class="ic">${ICONES.perfil}</span>Perfil</a><a href="notas.html" class="${on==="notas"?"on":""}"><span class="ic">${ICONES.notasLista}</span>Notas</a></nav>`;
  // avatar (canto superior direito) abre o menu da conta: Perfil · Configuração · Sair
  const topo=()=>`<header class="topo"><div class="logo">Gên<i>IO</i></div><div class="papel">Representante</div><div class="fill"></div><button type="button" class="avatar" id="avatarBtn" title="${esc(eu().nome)}" aria-label="Conta">${esc(ini(eu().nome))}</button></header>`;
  document.addEventListener("click",ev=>{const b=ev.target.closest("#avatarBtn");const aberto=document.querySelector(".menu-conta");if(!b){if(aberto&&!ev.target.closest(".menu-conta"))aberto.remove();return;}if(aberto){aberto.remove();return;}
    const m=document.createElement("div");m.className="menu-conta";m.innerHTML=`<div class="quem"><b>${esc(eu().nome)}</b><small>${esc(eu().email||"")}</small></div><a href="perfil.html">${ICONES.perfil}<span>Perfil</span></a><a href="financeiro.html">${ICONES.financeiro}<span>Financeiro</span></a><a href="config.html">${ICONES.config}<span>Configuração</span></a><a href="/api/sair" class="sair"><span>Sair</span></a>`;document.body.appendChild(m);});
  const voltar=(href,txt)=>`<div class="faixa"><a href="${href}">${esc(txt)}</a></div>`;
  const acoes=(voltaHref,voltaTxt,avancaId,avancaTxt)=>`<div class="acoes"><div class="w">${voltaHref?`<a class="btn sec" href="${voltaHref}">← ${esc(voltaTxt)}</a>`:""}<button class="btn" id="${avancaId}" type="button">${esc(avancaTxt)}</button></div></div>`;
  // menu lateral de toque longo: devolve o item escolhido (ou null)
  function menuLongo(titulo,itens){return new Promise(res=>{const f=document.createElement("div");f.className="fundo";const m=document.createElement("div");m.className="menu-lado";m.innerHTML=`<b>${esc(titulo)}</b>${itens.map(i=>`<button type="button" data-k="${i.k}">${i.ic?`<span>${i.ic}</span>`:""}${esc(i.t)}</button>`).join("")}<button type="button" class="cancela" data-k="">Cancelar</button>`;
    const fim=k=>{f.remove();m.remove();res(k||null);};f.onclick=()=>fim(null);m.onclick=ev=>{const b=ev.target.closest("button");if(b)fim(b.dataset.k);};document.body.append(f,m);});}
  // toque longo em elementos [data-longo]: chama fn(el) após 450 ms sem mover
  function ligarLongo(root,fn){$$("[data-longo]",root).forEach(el=>{let t=null,p=null;el.addEventListener("pointerdown",ev=>{p={x:ev.clientX,y:ev.clientY};t=setTimeout(()=>{t=null;if(navigator.vibrate)navigator.vibrate(12);fn(el);},450);});
    const c=ev=>{if(t&&p&&ev.type==="pointermove"&&Math.hypot(ev.clientX-p.x,ev.clientY-p.y)<8)return;clearTimeout(t);t=null;};el.addEventListener("pointermove",c);el.addEventListener("pointerup",c);el.addEventListener("pointercancel",c);el.addEventListener("contextmenu",ev=>ev.preventDefault());});}
  return {$,$$,esc,qs,ZONA,zonaDe,get PLANO(){return PLANO;},setorNome,nomeLoja,telFmt,ini,sessao,eu,dados,ficha,estrelas,estrelasHTML,estado,salvar,abrirVendas,lerCliente,gravarCliente,cliente,lerChave,gravarChave,API,definirCliente,classificar,logoPrincipal,removerLogo,escolherImagem,abrirLogotipo,entradas,ligarEntradas,artePadrao,gerarProdutos,aparar,assarRecortes,desenharElementos,desenharTexto,desenharQR,carregarScript,recortarLogo,PRODUTOS_IDS,separarCores,garantirCamadas,dadosCarimbo,desenharCarimbo,cenaCarimbo,desenharLista,desenharSeta,listarNotas,gravarNota,apagarNota,diasDeRota,reagendar,hojeISO,dataCurta,META,ICONES,NA_CASCA,avulsos,novoAvulso,atualizarAvulso,ocorrenciasManuais,gravarOcorrencias,ocorrenciasAuto,ETAPAS,etapaDe,moverEtapa,nav,topo,voltar,acoes,menuLongo,ligarLongo};
})();
