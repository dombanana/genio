// GenIO v3 — campanha "Vizinhos juntos": arte do raio (200 m) com as lojas aptas, progresso e contador regressivo real.
// Campanha.arte(el,{eu:{nome}, vizinhos:[{nome,m,dx,dy,logo?,fechou?,eu?}], meta:3, desconto:15, prazo:ISO, agora:ISO(servidor)})
const Campanha=(()=>{
  const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ini=n=>n.split(/\s+/).filter((p,i,a)=>i===0||i===a.length-1).map(p=>p[0]||"").join("").toUpperCase();
  function restante(prazo,agora){const ms=new Date(prazo)-new Date(agora);if(ms<=0)return null;const d=Math.floor(ms/864e5),h=Math.floor(ms%864e5/36e5),m=Math.floor(ms%36e5/6e4),s=Math.floor(ms%6e4/1e3);return {d,h,m,s,txt:(d?d+" d ":"")+String(h).padStart(2,"0")+" h "+String(m).padStart(2,"0")+" min"+(d?"":" "+String(s).padStart(2,"0")+" s")};}
  function arte(el,o){
    const R=o.raio_m||200,S=150,C=170;  // raio em px, centro
    const viz=o.vizinhos.slice(0,24);const fech=viz.filter(v=>v.fechou).length+(o.euFechei?1:0);
    const pts=viz.map(v=>{const k=Math.min(1,v.m/R);const ang=Math.atan2(v.dy,v.dx);const r=20+k*(S-28);return {...v,x:C+Math.cos(ang)*r,y:C-Math.sin(ang)*r};});
    const dot=p=>`<g class="vz ${p.fechou?"fechou":"apta"}" transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})"><circle r="${p.fechou?15:12}"/>${p.logo?`<clipPath id="c${p.slug}"><circle r="11"/></clipPath><image href="${p.logo}" x="-11" y="-11" width="22" height="22" clip-path="url(#c${p.slug})" preserveAspectRatio="xMidYMid slice"/>`:`<text y="4" text-anchor="middle">${esc(ini(p.nome))}</text>`}${p.fechou?'<text class="ok" x="11" y="-9">✓</text>':''}<title>${esc(p.nome)} · ${p.m} m</title></g>`;
    const prazoFmt=new Date(o.prazo).toLocaleString("pt-BR",{weekday:"short",hour:"2-digit",minute:"2-digit"}).replace(".","");
    el.innerHTML=`<div class="camp">
      <div class="camp-top"><b>Vizinhos juntos</b><span class="camp-prog">${fech} de ${o.meta}</span></div>
      <svg viewBox="0 0 340 340" class="camp-arte" role="img" aria-label="Lojas vizinhas num raio de ${R} m">
        <circle cx="${C}" cy="${C}" r="${S}" class="raio"/><circle cx="${C}" cy="${C}" r="${S/2}" class="raio fina"/>
        <text x="${C}" y="${C-S-6}" text-anchor="middle" class="leg">${R} m</text>
        ${pts.map(dot).join("")}
        <g class="eu ${o.euFechei?"fechou":""}" transform="translate(${C} ${C})"><circle r="22"/><text y="5" text-anchor="middle">${esc(ini(o.eu.nome))}</text>${o.euFechei?'<text class="ok" x="16" y="-14">✓</text>':''}<title>${esc(o.eu.nome)} (você)</title></g>
      </svg>
      <div class="camp-txt">${fech>=o.meta?`<b>Fechou!</b> ${o.desconto}% para todas — a diferença de quem já pagou vira crédito.`:`Quando <b>${o.meta} lojas</b> neste raio fecharem até <b>${prazoFmt}</b>, todas ganham <b>${o.desconto}%</b>. Faltam <b>${o.meta-fech}</b>.`}</div>
      <div class="camp-rel" data-prazo="${o.prazo}" data-agora="${o.agora}"><span class="camp-ct"></span></div>
      <div class="camp-lista">${viz.map(v=>`<span class="${v.fechou?"fechou":""}">${esc(v.nome)} <i>${v.m} m</i></span>`).join("")}</div>
      <div class="camp-acts"><button type="button" class="btn btn-p" data-chamar>Chamar vizinho</button></div>
    </div>`;
    // contador regressivo com hora do servidor (deriva local só o avanço)
    const rel=el.querySelector(".camp-rel"),ct=el.querySelector(".camp-ct");const t0=Date.now(),a0=new Date(o.agora).getTime();
    const tick=()=>{const agora=new Date(a0+(Date.now()-t0)).toISOString();const r=restante(o.prazo,agora);ct.textContent=r?"termina em "+r.txt+" · "+prazoFmt:"oferta encerrada em "+prazoFmt;if(!r)rel.classList.add("fim");};tick();el._camp=setInterval(tick,1000);
    el.querySelector("[data-chamar]").onclick=()=>{const txt=`Oi! Estou fechando a ${o.eu.nome} com a GenIO (capacho, placas, adesivos com a nossa marca). Se 3 lojas aqui da rua fecharem até ${prazoFmt}, todas ganham ${o.desconto}%. Dá uma olhada: ${o.link||location.href}`;if(navigator.share)navigator.share({text:txt}).catch(()=>{});else location.href="https://wa.me/?text="+encodeURIComponent(txt);};
  }
  return {arte,restante};
})();
