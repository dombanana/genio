// GênIO · toque longo em qualquer imagem do sistema → Trocar (câmera) · Ajustar · Apagar · Marcar como errada.
// Guarda a correção no aparelho (por loja e campo) e numa fila de correções que sobe para o servidor quando houver rede.
// Uso: <img data-img="logo" data-loja="slug" src="..."> ou um contêiner com data-img (ex.: .foto). Imagem.ligar(root).
const Imagem=(()=>{
  const CSS=`.im-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9000;background:#fff;border-radius:22px 22px 0 0;padding:14px 16px calc(18px + env(safe-area-inset-bottom,0));box-shadow:0 -8px 30px rgba(28,22,53,.18);font-family:Rubik,system-ui,sans-serif;transform:translateY(100%);transition:transform .2s}
.im-sheet.on{transform:none}
.im-fundo{position:fixed;inset:0;z-index:8999;background:rgba(28,22,53,.35)}
.im-sheet h3{margin:4px 0 12px;font-size:17px;color:#1C1635}
.im-sheet .im-prev{width:100%;height:120px;object-fit:contain;background:#F1EEF8;border-radius:12px;margin:0 0 12px}
.im-sheet button{display:flex;align-items:center;gap:12px;width:100%;border:0;background:#F1EEF8;color:#1C1635;font:600 17px Rubik,system-ui,sans-serif;padding:14px 16px;border-radius:14px;margin:0 0 8px;cursor:pointer;text-align:left}
.im-sheet button .ic{font-size:20px;width:26px;text-align:center}
.im-sheet button.perigo{color:#A33A2A}
.im-sheet button.fechar{background:transparent;justify-content:center;color:#6B6578;margin:4px 0 0}
[data-img]{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
[data-img].im-press{transform:scale(.98);filter:brightness(.95);transition:transform .15s}`;
  const KEY="genio-imagens", FILA="genio-correcoes";
  const ler=k=>{try{return JSON.parse(localStorage.getItem(k)||(k===FILA?"[]":"{}"));}catch(e){return k===FILA?[]:{};}};
  const gravar=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
  const id=el=>`${el.dataset.loja||"geral"}/${el.dataset.img}`;
  let css=false;
  function estilo(){if(css)return;css=true;const s=document.createElement("style");s.textContent=CSS;document.head.appendChild(s);}
  // aplica no carregamento o que já foi corrigido no aparelho (troca, ajuste ou apagar)
  function aplicar(root=document){const M=ler(KEY);root.querySelectorAll("[data-img]").forEach(el=>{const c=M[id(el)];if(!c)return;const img=el.tagName==="IMG"?el:el.querySelector("img");
    if(c.apagada){if(img)img.remove();el.classList.add("im-vazia");if(!el.querySelector(".im-aviso")){const a=document.createElement("div");a.className="im-aviso";a.textContent="Sem imagem — toque e segure para fotografar";a.style.cssText="display:grid;place-items:center;height:100%;color:#6B6578;font-size:14px;text-align:center;padding:12px";el.appendChild(a);}}
    else if(c.dados){if(img)img.src=c.dados;else{const i=document.createElement("img");i.src=c.dados;el.innerHTML="";el.appendChild(i);}el.classList.remove("im-vazia");const a=el.querySelector(".im-aviso");if(a)a.remove();}});}
  function fila(item){const f=ler(FILA);f.push({...item,em:new Date().toISOString()});gravar(FILA,f);enviar();}
  let enviando=false;
  async function enviar(){if(enviando||!navigator.onLine)return;const f=ler(FILA);if(!f.length)return;enviando=true;
    try{const r=await fetch("../api/correcoes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({correcoes:f.map(x=>({...x,dados:undefined}))})});if(r.ok)gravar(FILA,[]);}catch(e){}enviando=false;}
  function salvarImg(el,dados,acao,extra){const M=ler(KEY);M[id(el)]={dados,acao,em:new Date().toISOString(),...(extra||{})};gravar(KEY,M);aplicar(el.parentElement||document);fila({loja:el.dataset.loja||null,campo:el.dataset.img,fonte:el.dataset.fonte||null,acao,...(extra||{})});if(typeof el.onImagem==="function")el.onImagem(dados,acao);el.dispatchEvent(new CustomEvent("imagem",{bubbles:true,detail:{acao,dados}}));}
  function arquivoDe(src){return fetch(src).then(r=>r.blob()).then(b=>new File([b],"imagem.jpg",{type:b.type||"image/jpeg"}));}
  function comoDados(file,max=1400){return new Promise(res=>{const u=URL.createObjectURL(file),i=new Image();i.onload=()=>{const c=document.createElement("canvas"),k=Math.min(1,max/Math.max(i.width,i.height));c.width=i.width*k;c.height=i.height*k;c.getContext("2d").drawImage(i,0,0,c.width,c.height);URL.revokeObjectURL(u);res(c.toDataURL("image/jpeg",.85));};i.src=u;});}
  function menu(el){estilo();const img=el.tagName==="IMG"?el:el.querySelector("img");const src=img&&img.src;const nome=el.dataset.nome||({logo:"Logo",local:"Foto do local",entrada:"Foto da entrada",fachada:"Fachada"})[el.dataset.img]||"Imagem";
    const fundo=document.createElement("div");fundo.className="im-fundo";const sh=document.createElement("div");sh.className="im-sheet";
    sh.innerHTML=`<h3>${nome}${el.dataset.fonte?` <small style="font-weight:400;color:#6B6578">· ${el.dataset.fonte}</small>`:""}</h3>${src?`<img class="im-prev" src="${src}" alt="">`:""}
      <button data-a="trocar"><span class="ic">📷</span>Trocar por foto agora</button>
      ${src?`<button data-a="ajustar"><span class="ic">✂️</span>Ajustar (recortar, endireitar, girar)</button>`:""}
      ${src?`<button data-a="errada"><span class="ic">⚠️</span>Marcar como errada e apagar</button>`:""}
      ${src?`<button data-a="apagar" class="perigo"><span class="ic">🗑</span>Apagar</button>`:""}
      <button data-a="x" class="fechar">Cancelar</button>`;
    document.body.append(fundo,sh);requestAnimationFrame(()=>sh.classList.add("on"));
    const fechar=()=>{sh.classList.remove("on");setTimeout(()=>{sh.remove();fundo.remove();},200);};fundo.onclick=fechar;
    sh.onclick=async e=>{const b=e.target.closest("button");if(!b)return;const a=b.dataset.a;fechar();
      if(a==="trocar"){if(window.FotoCrop){FotoCrop.abrir({titulo:nome,varias:false,onFim:async fs=>{if(fs&&fs[0])salvarImg(el,await comoDados(fs[0]),"trocada");}});}else{const inp=document.createElement("input");inp.type="file";inp.accept="image/*";inp.capture="environment";inp.onchange=async()=>{if(inp.files[0])salvarImg(el,await comoDados(inp.files[0]),"trocada");};inp.click();}}
      if(a==="ajustar"&&src){const f=await arquivoDe(src).catch(()=>null);if(!f)return;if(window.FotoCrop&&FotoCrop.ajustarArquivo)FotoCrop.ajustarArquivo(f,{titulo:nome,onFim:async fs=>{if(fs&&fs[0])salvarImg(el,await comoDados(fs[0]),"ajustada");}});}
      if(a==="apagar")salvarImg(el,null,"apagada",{apagada:true});
      if(a==="errada")salvarImg(el,null,"errada",{apagada:true,errada:true});};}
  function ligar(root=document){estilo();aplicar(root);root.querySelectorAll("[data-img]").forEach(el=>{if(el._im)return;el._im=true;let t=null,moved=false;
    const down=e=>{moved=false;el.classList.add("im-press");t=setTimeout(()=>{el.classList.remove("im-press");if(!moved){if(navigator.vibrate)navigator.vibrate(12);menu(el);}},480);};
    const up=()=>{clearTimeout(t);el.classList.remove("im-press");};
    el.addEventListener("pointerdown",down);el.addEventListener("pointerup",up);el.addEventListener("pointercancel",up);el.addEventListener("pointerleave",up);el.addEventListener("pointermove",()=>{moved=true;});
    el.addEventListener("contextmenu",e=>{e.preventDefault();clearTimeout(t);menu(el);});});
    window.addEventListener("online",enviar);enviar();}
  return {ligar,aplicar,menu,ler:()=>ler(KEY),fila:()=>ler(FILA)};
})();
