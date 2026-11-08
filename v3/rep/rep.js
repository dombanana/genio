// GênIO · app do representante (v3) — dados da captação da zona + estado do dia no aparelho.
const Rep=(()=>{
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ini=n=>n.split(/\s+/).filter((p,i,a)=>i===0||i===a.length-1).map(p=>p[0]||"").join("").toUpperCase();
  const qs=new URLSearchParams(location.search);
  const ZONA=qs.get("zona")||localStorage.getItem("rep-zona")||"zona-cerealista";
  const KEY="rep-dia-"+ZONA;
  const estado=()=>{try{return JSON.parse(localStorage.getItem(KEY)||"{}");}catch(e){return {};}};
  const salvar=e=>localStorage.setItem(KEY,JSON.stringify(e));
  const vendedor=()=>{let v=null;try{v=JSON.parse(localStorage.getItem("genio-vendedor")||"null");}catch(e){}return v||{nome:"Yoshio Tanaka"};};
  const PROD={"padaria":["Capacho","Adesivo de vitrine","Cardápio de parede"],"restaurante":["Capacho","Cardápio de parede","Mostra Aí"],"bar":["Capacho","Cardápio","Banner"],"cafeteria":["Capacho","Cardápio de parede","Mostra Aí"],"salão/barbearia":["Capacho","Adesivo de vitrine","Cartões"],"pet":["Capacho","Placa","Adesivo de vitrine"],"clínica/consultório":["Placa","Cartões","Capacho"],"academia/estúdio":["Placa","Adesivo de parede","Uniformes"],"ótica":["Adesivo de vitrine","Placa","Cartões"],"loja de roupas/calçados":["Adesivo de vitrine","Banner","Capacho"],"floricultura/presentes":["Adesivo de vitrine","Cartões","Capacho"],"cereais/empório":["Capacho","Placa de preços","Adesivo de vitrine"],"mercado/hortifruti":["Banner","Placa","Capacho"],"embalagens/utilidades":["Capacho","Banner","Placa"],"celular/assistência":["Adesivo de vitrine","Placa","Cartões"],"escritório/imobiliária":["Placa","Cartões","Capacho"],"escola/curso":["Placa","Adesivo de parede","Uniformes"],"comércio":["Capacho","Placa","Cartões"]};
  const SETOR_NOME={"cereais/empório":"Empório","salão/barbearia":"Barbearia","clínica/consultório":"Clínica","academia/estúdio":"Academia","loja de roupas/calçados":"Moda","floricultura/presentes":"Presentes","mercado/hortifruti":"Mercado","embalagens/utilidades":"Embalagens","celular/assistência":"Assistência","escritório/imobiliária":"Escritório","escola/curso":"Escola"};
  const nomeLoja=n=>/^[^a-z]*$/.test(n)&&n.length>4?n.toLowerCase().replace(/(^|[\s\-·(])(\S)/g,(m,a,b)=>a+b.toUpperCase()).replace(/\b(Da|De|Do|Das|Dos|E|Em)\b/g,m=>m.toLowerCase()):n;
  const setorNome=s=>SETOR_NOME[s]||(s||"comércio").replace(/^./,c=>c.toUpperCase());
  const telFmt=t=>{const d=(t||"").replace(/\D/g,"").replace(/^55(?=\d{10,11}$)/,"");return d.length>=10?`(${d.slice(0,2)}) ${d.slice(2,-4)}-${d.slice(-4)}`:(t||"");};
  const dist=(a,b)=>{const R=6371e3,toR=x=>x*Math.PI/180,dl=toR(b.lat-a.lat),dg=toR(b.lng-a.lng),s=Math.sin(dl/2)**2+Math.cos(toR(a.lat))*Math.cos(toR(b.lat))*Math.sin(dg/2)**2;return Math.round(2*R*Math.asin(Math.sqrt(s)));};
  let D=null;
  async function dados(){if(D)return D;
    // lojas reais da captação do servidor; se ainda não houver, a lista local da zona
    try{const r=await fetch(`/dados/captacao/${ZONA}/lojas.json`,{cache:"no-cache"});if(r.ok){const j=await r.json();D={zona:{slug:ZONA,nome:j.zona.nome.split(" (")[0],base:j.zona.base},gerado:j.gerado,lojas:j.lojas};}}catch(e){}
    if(!D){const r=await fetch(`dados/${ZONA}.json`);D=await r.json();}
    localStorage.setItem("rep-zona",ZONA);
    // cadastro da captação (quando existir): estado do logo por loja
    try{const c=await fetch(`/dados/captacao/${ZONA}/clientes/index.json`);if(c.ok){const idx=await c.json();const m={};idx.forEach(x=>m[x.slug]=x.logo);D.lojas.forEach(l=>l.logo=m[l.slug]||null);}}catch(e){}
    return D;}
  const hojeDia=D=>{const e=estado();return e.dia||1;};
  const lojasDoDia=(D,dia)=>D.lojas.filter(l=>l.dia===dia).sort((a,b)=>a.ordem-b.ordem);
  const vizinhos=(D,l,r=200)=>D.lojas.filter(x=>x!==l&&dist(l,x)<=r);
  const abertaAgora=h=>{if(!h)return null;const dias=["dom","seg","ter","qua","qui","sex","sáb"];const d=dias[new Date().getDay()];const m=h.split(" · ").find(p=>p.startsWith(d));if(!m)return null;if(/fechad/i.test(m))return false;const hs=[...m.matchAll(/(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?/gi)].map(x=>{let hh=+x[1];const mm=+(x[2]||0);if(x[3]){if(/pm/i.test(x[3])&&hh<12)hh+=12;if(/am/i.test(x[3])&&hh===12)hh=0;}return hh*60+mm;});if(hs.length<2)return null;const agora=new Date().getHours()*60+new Date().getMinutes();return agora>=hs[0]&&agora<=hs[1];};
  const stLogo=l=>l.logo==="encontrado"?{t:"Marca pronta",c:"ok"}:(l.logo==="pendente"?{t:"Decidir marca",c:"dec"}:{t:"Marca na porta",c:""});
  const nav=on=>`<nav class="nav"><a href="index.html" class="${on==="rota"?"on":""}"><span class="ic">📍</span>Rota</a><a href="pedidos.html" class="${on==="pedidos"?"on":""}"><span class="ic">📄</span>Pedidos</a><a href="vendas.html" class="${on==="vendas"?"on":""}"><span class="ic">📊</span>Vendas</a><a href="perfil.html" class="${on==="perfil"?"on":""}"><span class="ic">👤</span>Perfil</a></nav>`;
  const topo=()=>`<header class="topo"><div class="logo">Gên<i>IO</i></div><div class="papel">Representante</div><div class="fill"></div><div class="avatar" title="${esc(vendedor().nome)}">${esc(ini(vendedor().nome))}</div></header>`;
  // microfone: só o botão; arrasta para qualquer lugar (posição guardada), toque liga/desliga a gravação
  const voz=()=>`<div class="voz" id="voz"><button type="button" aria-label="Nota de voz">🎙</button><span class="dica" hidden></span></div>`;
  function ligarVoz(slug){const v=$("#voz");if(!v)return;const b=$("button",v),s=$(".dica",v);const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec=null;
    try{const p=JSON.parse(localStorage.getItem("rep-mic")||"null");if(p){v.style.left=p.x+"px";v.style.top=p.y+"px";v.style.right="auto";v.style.bottom="auto";}}catch(e){}
    const dica=t=>{s.textContent=t;s.hidden=!t;if(t)setTimeout(()=>{s.hidden=true;},1800);};
    let d=null;
    b.onpointerdown=ev=>{d={x:ev.clientX,y:ev.clientY,moved:false,r:v.getBoundingClientRect()};b.setPointerCapture(ev.pointerId);};
    b.onpointermove=ev=>{if(!d)return;const dx=ev.clientX-d.x,dy=ev.clientY-d.y;if(!d.moved&&Math.hypot(dx,dy)<8)return;d.moved=true;const x=Math.max(4,Math.min(innerWidth-d.r.width-4,d.r.left+dx)),y=Math.max(4,Math.min(innerHeight-d.r.height-4,d.r.top+dy));v.style.left=x+"px";v.style.top=y+"px";v.style.right="auto";v.style.bottom="auto";};
    b.onpointerup=ev=>{if(!d)return;const foi=d.moved;if(foi){const r=v.getBoundingClientRect();localStorage.setItem("rep-mic",JSON.stringify({x:r.left,y:r.top}));}d=null;if(!foi)gravar();};
    b.onpointercancel=()=>{d=null;};
    function gravar(){if(!SR){dica("Sem voz neste aparelho");return;}if(rec){rec.stop();return;}rec=new SR();rec.lang="pt-BR";rec.interimResults=false;v.classList.add("gravando");let txt="";
      rec.onresult=e=>{txt=[...e.results].map(r=>r[0].transcript).join(" ");};
      rec.onend=()=>{v.classList.remove("gravando");rec=null;if(txt.trim()){const e=estado();(e.notas=e.notas||[]).push({loja:slug||null,em:new Date().toISOString(),texto:txt.trim()});salvar(e);dica("Nota guardada");}};
      rec.start();}}
  function ouvir(txt,btn){if(!window.speechSynthesis){btn.textContent="Sem voz";return;}speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(txt);u.lang="pt-BR";u.rate=1;speechSynthesis.speak(u);}
  function roteiro(l){const p=(PROD[l.setor]||PROD["comércio"]);const abre=l.logo==="encontrado"?`A marca da ${nomeLoja(l.nome)} já está pronta: mostre o capacho com ela na entrada.`:`Apresente o capacho e pergunte pela marca — a foto da placa resolve na hora.`;return `${abre} ${p[0]} primeiro; ${p[1].toLowerCase()} e ${p[2].toLowerCase()} se houver interesse.`;}
  const CHECK=[["chuva","Chuva bate"],["degrau","Tem degrau"],["vidro","Porta de vidro"],["piso","Piso irregular"],["fluxo","Fluxo alto"],["sombra","Entrada coberta"]];
  // preço de referência (até o catálogo de fornecedores): custo R$ 250/m² × margem 2,2; borda rebaixada +R$ 25
  const precoCapacho=(wcm,hcm,borda)=>Math.round(((wcm/100)*(hcm/100)*250*2.2+(borda?25:0))/1)*1;
  const money=v=>"R$ "+v.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
  // orçamentos reais do módulo de capacho (IndexedDB genio-vendas · orcamentos) + etapa operacional guardada à parte
  function orcamentos(){return new Promise(res=>{try{const rq=indexedDB.open("genio-vendas");rq.onsuccess=()=>{const db=rq.result;if(!db.objectStoreNames.contains("orcamentos")){db.close();return res([]);}const t=db.transaction("orcamentos").objectStore("orcamentos").getAll();t.onsuccess=()=>{db.close();res(t.result||[]);};t.onerror=()=>res([]);};rq.onerror=()=>res([]);rq.onupgradeneeded=()=>{};}catch(e){res([]);}});}
  const etapaDe=q=>{const e=estado();const op=(e.oper||{})[q.id];if(op&&op.etapa)return op.etapa;return q.status==="aprovado"?"pagamento":q.status==="enviado"?"arte":"orcamento";};
  const setEtapa=(id,et)=>{const e=estado();e.oper=e.oper||{};e.oper[id]={...(e.oper[id]||{}),etapa:et,em:new Date().toISOString()};salvar(e);};
  return {$,$$,esc,qs,ZONA,nomeLoja,orcamentos,etapaDe,setEtapa,estado,salvar,vendedor,dados,hojeDia,lojasDoDia,vizinhos,abertaAgora,stLogo,nav,topo,voz,ligarVoz,ouvir,roteiro,CHECK,PROD,setorNome,telFmt,dist,precoCapacho,money};
})();
