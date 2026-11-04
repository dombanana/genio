// Gênio: funciona sem internet. Cada página abre do que está guardado no aparelho e se atualiza quando há rede.
const V="genio-10fe7b41e4",PAGS=["index.html","app.html","capacho.html","convite.html","admin.html"],
  CORE=PAGS.concat(["portal.css?v=10fe7b41e4","portal.js?v=10fe7b41e4","manifest.webmanifest","icon-192.png","icon-512.png","apple-touch-icon.png","favicon.png"]);
self.addEventListener("install",e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V&&k!=="genio-fontes").map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
// endereço → página guardada ("/" e "/?app=1" são a página de vendas e entrar)
const pag=u=>{const n=u.pathname.replace(/^\//,"");return n===""?"index.html":n;};
self.addEventListener("fetch",e=>{const r=e.request;if(r.method!=="GET")return;const u=new URL(r.url);
  if(u.origin===location.origin&&(u.pathname.startsWith("/api/")||u.pathname.startsWith("/t/")))return;   // dados do servidor: nunca do guardado
  // página: rede primeiro (sempre confere a versão nova), sem rede usa a guardada
  if(r.mode==="navigate"){const k=pag(u);e.respondWith(fetch(r,{cache:"no-cache"}).then(res=>{if(res.ok&&PAGS.includes(k)){const cp=res.clone();caches.open(V).then(c=>c.put(k,cp));}return res;})
      .catch(()=>caches.match(k).then(x=>x||caches.match("app.html"))));return;}
  // fontes do Google: guarda e usa a guardada, atualizando por trás
  if(/fonts\.(googleapis|gstatic)\.com$/.test(u.hostname)){e.respondWith(caches.open("genio-fontes").then(c=>c.match(r).then(hit=>{const net=fetch(r).then(res=>{c.put(r,res.clone());return res;}).catch(()=>hit);return hit||net;})));return;}
  if(u.origin===location.origin)e.respondWith(caches.match(r).then(hit=>hit||fetch(r).then(res=>{if(res.ok){const cp=res.clone();caches.open(V).then(c=>c.put(r,cp));}return res;})));});
