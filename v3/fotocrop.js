// ================= câmera + ajuste da foto (recorte e endireitar) =================
// FotoCrop.abrir({titulo, varias, onFim(files)}): abre a câmera na hora, deixa tirar uma ou várias fotos,
// e cada foto passa pelo ajuste (recortar, endireitar, girar) antes de entrar no aplicativo. Usado pela Arte, pelo Local e pela Identidade visual.
const FotoCrop=(()=>{
  const CSS=`.fc{position:fixed;inset:0;z-index:10000;background:#121018;color:#fff;display:flex;flex-direction:column;font-family:Rubik,system-ui,sans-serif;touch-action:none}
.fc[hidden]{display:none}
.fc .fc-top{display:flex;align-items:center;justify-content:space-between;padding:calc(10px + env(safe-area-inset-top,0px)) 14px 10px;font-weight:600;font-size:16px}
.fc .fc-x{appearance:none;border:0;background:rgba(255,255,255,.12);color:#fff;width:40px;height:40px;border-radius:50%;font-size:22px;cursor:pointer}
.fc .fc-mid{flex:1;position:relative;overflow:hidden;display:grid;place-items:center;min-height:0}
.fc video{width:100%;height:100%;object-fit:cover;background:#000}
.fc .fc-shots{position:absolute;left:12px;bottom:12px;display:flex;gap:6px}
.fc .fc-shots img{width:46px;height:46px;object-fit:cover;border-radius:8px;border:2px solid #fff}
.fc .fc-bot{display:flex;align-items:center;justify-content:center;gap:18px;padding:14px 16px calc(16px + env(safe-area-inset-bottom,0px));flex-wrap:wrap}
.fc .fc-shutter{width:72px;height:72px;border-radius:50%;border:5px solid #fff;background:#6933C5;cursor:pointer}
.fc .fc-btn{appearance:none;border:0;border-radius:12px;padding:12px 18px;font:600 15px Rubik,system-ui,sans-serif;cursor:pointer;background:rgba(255,255,255,.14);color:#fff}
.fc .fc-btn.p{background:#04C6C0;color:#0b3a38}
.fc .fc-btn[disabled]{opacity:.4;cursor:default}
.fc .fc-n{font-size:14px;opacity:.8;min-width:60px;text-align:center}
.fc .fc-stage{position:relative;max-width:100%;max-height:100%;touch-action:none;user-select:none}
.fc .fc-stage canvas{display:block;max-width:100%;max-height:100%}
.fc .fc-hint{font-size:13px;opacity:.7;text-align:center;padding:4px 16px 0}
.fc .fc-dim{position:absolute;inset:0;pointer-events:none;box-shadow:0 0 0 9999px rgba(0,0,0,.55);border:1.5px solid #fff}
.fc .fc-dim:before,.fc .fc-dim:after{content:"";position:absolute;background:rgba(255,255,255,.35)}
.fc .fc-dim:before{left:33.33%;right:33.33%;top:0;bottom:0;border-left:1px solid rgba(255,255,255,.35);border-right:1px solid rgba(255,255,255,.35);background:none}
.fc .fc-dim:after{top:33.33%;bottom:33.33%;left:0;right:0;border-top:1px solid rgba(255,255,255,.35);border-bottom:1px solid rgba(255,255,255,.35);background:none}
.fc .fc-h{position:absolute;width:34px;height:34px;margin:-17px 0 0 -17px;cursor:pointer;touch-action:none}
.fc .fc-h:after{content:"";position:absolute;inset:7px;border-radius:50%;background:#fff;box-shadow:0 0 0 2px #6933C5}
.fc .fc-ctl{display:flex;align-items:center;gap:12px;padding:8px 16px 0;flex-wrap:wrap;justify-content:center}
.fc .fc-ctl label{display:flex;align-items:center;gap:8px;font-size:14px;opacity:.9}
.fc input[type=range]{width:min(260px,55vw);accent-color:#04C6C0}
.fc .fc-msg{font-size:14px;opacity:.85;text-align:center;padding:0 16px}`;
  let el=null,stream=null,st={};
  const $=(s,r=el)=>r.querySelector(s);
  function montar(){if(el)return;const s=document.createElement("style");s.textContent=CSS;document.head.appendChild(s);
    el=document.createElement("div");el.className="fc";el.hidden=true;el.innerHTML=`
<div class="fc-top"><span class="fc-t"></span><button type="button" class="fc-x" aria-label="Fechar">×</button></div>
<div class="fc-mid"></div>
<div class="fc-ctl" hidden></div>
<div class="fc-bot"></div>
<input type="file" accept="image/*" capture="environment" multiple hidden class="fc-file">`;
    document.body.appendChild(el);$(".fc-x").onclick=fechar;
    $(".fc-file").addEventListener("change",e=>{const fs=[...e.target.files||[]];e.target.value="";if(!fs.length){if(!st.shots.length)fechar();return;}fs.forEach(f=>st.shots.push(f));iniciarAjuste();});}
  function fechar(){pararCam();el.hidden=true;document.body.style.overflow="";const fim=st.onFim;st={};if(fim)fim([]);}
  function pararCam(){if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}}
  async function abrir(o){montar();st={titulo:o.titulo||"Foto",varias:!!o.varias,onFim:o.onFim||(()=>{}),shots:[],prontas:[],i:0};
    el.hidden=false;document.body.style.overflow="hidden";$(".fc-t").textContent=st.titulo;await camera();}
  // 1) câmera ao vivo: botão grande tira a foto; "Concluir" leva para o ajuste
  async function camera(){const mid=$(".fc-mid"),bot=$(".fc-bot"),ctl=$(".fc-ctl");ctl.hidden=true;ctl.innerHTML="";mid.innerHTML="";bot.innerHTML="";
    let ok=false;try{if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia){stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"},width:{ideal:2560},height:{ideal:1920}},audio:false});ok=true;}}catch(e){ok=false;}
    if(!ok){$(".fc-file").multiple=st.varias;$(".fc-file").click();mid.innerHTML=`<p class="fc-msg">Abrindo a câmera do aparelho…</p>`;bot.innerHTML=`<button type="button" class="fc-btn fc-again">Tentar de novo</button>`;$(".fc-again").onclick=()=>$(".fc-file").click();return;}
    const v=document.createElement("video");v.setAttribute("playsinline","");v.muted=true;v.srcObject=stream;mid.appendChild(v);await v.play().catch(()=>{});
    const shots=document.createElement("div");shots.className="fc-shots";mid.appendChild(shots);
    bot.innerHTML=`<span class="fc-n"></span><button type="button" class="fc-shutter" aria-label="Tirar foto"></button><button type="button" class="fc-btn p fc-ok" disabled>Concluir</button>`;
    const n=$(".fc-n"),ok2=$(".fc-ok");const conta=()=>{n.textContent=st.shots.length?`${st.shots.length} foto${st.shots.length>1?"s":""}`:"";ok2.disabled=!st.shots.length;};
    $(".fc-shutter").onclick=()=>{const c=document.createElement("canvas");const k=Math.min(1,2400/Math.max(v.videoWidth,v.videoHeight));c.width=Math.round(v.videoWidth*k);c.height=Math.round(v.videoHeight*k);c.getContext("2d").drawImage(v,0,0,c.width,c.height);
      c.toBlob(b=>{if(!b)return;st.shots.push(new File([b],`foto-${Date.now()}.jpg`,{type:"image/jpeg"}));const im=document.createElement("img");im.src=URL.createObjectURL(b);shots.appendChild(im);conta();
        mid.style.outline="4px solid #fff";setTimeout(()=>mid.style.outline="",120);if(!st.varias){pararCam();iniciarAjuste();}},"image/jpeg",.92);};
    ok2.onclick=()=>{pararCam();iniciarAjuste();};conta();}
  // 2) ajuste: recorte com cantos, endireitar e girar; "Usar" fecha a foto tratada
  function iniciarAjuste(){st.i=0;st.prontas=[];ajustar();}
  async function ajustar(){const f=st.shots[st.i];if(!f){terminar();return;}
    const mid=$(".fc-mid"),bot=$(".fc-bot"),ctl=$(".fc-ctl");mid.innerHTML="";$(".fc-t").textContent=`${st.titulo} · ${st.shots.length>1?`${st.i+1} de ${st.shots.length} · `:""}ajustar`;
    const img=await carregar(f);let ang=0,rot=0,crop=null;
    const stage=document.createElement("div");stage.className="fc-stage";const cv=document.createElement("canvas");stage.appendChild(cv);const dim=document.createElement("div");dim.className="fc-dim";stage.appendChild(dim);
    const hs=[0,1,2,3].map(i=>{const h=document.createElement("div");h.className="fc-h";h.dataset.i=i;stage.appendChild(h);return h;});mid.appendChild(stage);
    ctl.hidden=false;ctl.innerHTML=`<label>Endireitar <input type="range" class="fc-ang" min="-45" max="45" step="0.5" value="0"><output class="fc-ango">0°</output></label><button type="button" class="fc-btn fc-rot">Girar 90°</button><p class="fc-hint" style="width:100%;margin:0">Dois dedos: pinça abre ou fecha o recorte; girar os dedos endireita a foto.</p>`;
    bot.innerHTML=`<button type="button" class="fc-btn fc-redo">Refazer</button><button type="button" class="fc-btn p fc-use">Usar foto</button>`;
    // desenho: imagem girada (90° + fino) num canvas do tamanho da caixa girada; mostrada no tamanho que couber
    const full=document.createElement("canvas");
    const render=()=>{const a=(rot*90+ang)*Math.PI/180,w=img.width,h=img.height,cw=Math.abs(w*Math.cos(a))+Math.abs(h*Math.sin(a)),ch=Math.abs(w*Math.sin(a))+Math.abs(h*Math.cos(a));
      full.width=Math.round(cw);full.height=Math.round(ch);const x=full.getContext("2d");x.translate(cw/2,ch/2);x.rotate(a);x.drawImage(img,-w/2,-h/2);
      const box=mid.getBoundingClientRect(),k=Math.min((box.width-8)/cw,(box.height-8)/ch,1);cv.width=Math.round(cw*k);cv.height=Math.round(ch*k);cv.style.width=cv.width+"px";cv.style.height=cv.height+"px";cv.getContext("2d").drawImage(full,0,0,cv.width,cv.height);
      if(!crop)crop={x:cv.width*0.04,y:cv.height*0.04,w:cv.width*0.92,h:cv.height*0.92};else{crop.x=Math.min(crop.x,cv.width-40);crop.y=Math.min(crop.y,cv.height-40);crop.w=Math.min(crop.w,cv.width-crop.x);crop.h=Math.min(crop.h,cv.height-crop.y);}
      desenharCrop();};
    const desenharCrop=()=>{dim.style.left=crop.x+"px";dim.style.top=crop.y+"px";dim.style.width=crop.w+"px";dim.style.height=crop.h+"px";
      const P=[[crop.x,crop.y],[crop.x+crop.w,crop.y],[crop.x+crop.w,crop.y+crop.h],[crop.x,crop.y+crop.h]];hs.forEach((h,i)=>{h.style.left=P[i][0]+"px";h.style.top=P[i][1]+"px";});};
    const pos=e=>{const r=cv.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];};
    hs.forEach(h=>{h.addEventListener("pointerdown",e=>{e.stopPropagation();try{h.setPointerCapture(e.pointerId);}catch(_){}h._on=true;});
      h.addEventListener("pointermove",e=>{if(!h._on)return;const [px,py]=pos(e),i=+h.dataset.i,c=crop,x=Math.max(0,Math.min(cv.width,px)),y=Math.max(0,Math.min(cv.height,py)),r=c.x+c.w,b=c.y+c.h;
        if(i===0){c.w=Math.max(40,r-x);c.x=r-c.w;c.h=Math.max(40,b-y);c.y=b-c.h;}else if(i===1){c.w=Math.max(40,x-c.x);c.h=Math.max(40,b-y);c.y=b-c.h;}else if(i===2){c.w=Math.max(40,x-c.x);c.h=Math.max(40,y-c.y);}else{c.w=Math.max(40,r-x);c.x=r-c.w;c.h=Math.max(40,y-c.y);}desenharCrop();});
      const up=()=>{h._on=false;};h.addEventListener("pointerup",up);h.addEventListener("pointercancel",up);});
    // um dedo: move o recorte. Dois dedos: pinça abre/fecha o recorte, girar os dedos endireita a foto
    const pts=new Map();let drag=null,two=null;
    const setAng=v=>{ang=Math.max(-45,Math.min(45,v));$(".fc-ang").value=ang;$(".fc-ango").textContent=(ang>0?"+":"")+(Math.round(ang*2)/2).toString().replace(".",",")+"°";};
    stage.addEventListener("pointerdown",e=>{if(e.target.classList.contains("fc-h"))return;const [px,py]=pos(e);try{stage.setPointerCapture(e.pointerId);}catch(_){}pts.set(e.pointerId,[px,py]);
      if(pts.size===2){const P=[...pts.values()];two={d:Math.hypot(P[1][0]-P[0][0],P[1][1]-P[0][1]),a:Math.atan2(P[1][1]-P[0][1],P[1][0]-P[0][0]),ang,crop:Object.assign({},crop)};drag=null;return;}
      if(px<crop.x||px>crop.x+crop.w||py<crop.y||py>crop.y+crop.h)return;drag={px,py,x:crop.x,y:crop.y};});
    stage.addEventListener("pointermove",e=>{if(!pts.has(e.pointerId))return;pts.set(e.pointerId,pos(e));
      if(two&&pts.size===2){const P=[...pts.values()],d=Math.hypot(P[1][0]-P[0][0],P[1][1]-P[0][1]),a=Math.atan2(P[1][1]-P[0][1],P[1][0]-P[0][0]);
        setAng(two.ang-(a-two.a)*180/Math.PI);const k=Math.max(0.2,d/two.d),c=two.crop,cx=c.x+c.w/2,cy=c.y+c.h/2;
        let w=Math.max(40,Math.min(cv.width,c.w*k)),h=Math.max(40,Math.min(cv.height,c.h*k));crop.w=w;crop.h=h;crop.x=Math.max(0,Math.min(cv.width-w,cx-w/2));crop.y=Math.max(0,Math.min(cv.height-h,cy-h/2));render();return;}
      if(!drag)return;const [px,py]=pos(e);crop.x=Math.max(0,Math.min(cv.width-crop.w,drag.x+px-drag.px));crop.y=Math.max(0,Math.min(cv.height-crop.h,drag.y+py-drag.py));desenharCrop();});
    const fimDrag=e=>{pts.delete(e.pointerId);drag=null;if(pts.size<2)two=null;};stage.addEventListener("pointerup",fimDrag);stage.addEventListener("pointercancel",fimDrag);
    $(".fc-ang").oninput=e=>{setAng(+e.target.value);render();};
    $(".fc-rot").onclick=()=>{rot=(rot+1)%4;crop=null;render();};
    $(".fc-redo").onclick=async()=>{st.shots.splice(st.i,1);if(!st.shots.length&&!st.prontas.length){await camera();return;}ajustar();};
    $(".fc-use").onclick=()=>{const k=full.width/cv.width,o=document.createElement("canvas");o.width=Math.round(crop.w*k);o.height=Math.round(crop.h*k);o.getContext("2d").drawImage(full,crop.x*k,crop.y*k,crop.w*k,crop.h*k,0,0,o.width,o.height);
      o.toBlob(b=>{st.prontas.push(new File([b],f.name.replace(/\.\w+$/,"")+"-ajustada.jpg",{type:"image/jpeg"}));st.i++;ajustar();},"image/jpeg",.92);};
    render();window.addEventListener("resize",render,{once:true});}
  function terminar(){const fim=st.onFim,fs=st.prontas;el.hidden=true;document.body.style.overflow="";st={};fim(fs);}
  const carregar=f=>new Promise((res,rej)=>{const u=URL.createObjectURL(f),im=new Image();im.onload=()=>{URL.revokeObjectURL(u);res(im);};im.onerror=rej;im.src=u;});
  return {abrir};
})();
