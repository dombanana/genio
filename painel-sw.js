/* GênIO · avisos do painel do lojista. A campainha chega sem conteúdo; o celular pergunta ao painel o que há de novo e mostra. */
self.addEventListener("install",()=>self.skipWaiting());
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("push",e=>{e.waitUntil((async()=>{
  let n={mensagens:0,horarios:0,loja:""};
  try{const r=await fetch("/api/painel/novidades",{credentials:"same-origin",cache:"no-store"});if(r.ok)n=await r.json();}catch(err){}
  const p=[];if(n.horarios)p.push(n.horarios===1?"1 horário novo para confirmar":n.horarios+" horários novos para confirmar");
  if(n.mensagens)p.push(n.mensagens===1?"1 mensagem de cliente":n.mensagens+" mensagens de clientes");
  await self.registration.showNotification(n.loja||"Painel da loja",{body:p.join(" · ")||"Há novidade no seu painel.",tag:"genio-painel",renotify:true,icon:"/genio-512.png",badge:"/genio-favicon.png",data:{url:"/painel.html"}});
})());});
self.addEventListener("notificationclick",e=>{e.notification.close();e.waitUntil((async()=>{
  const cs=await self.clients.matchAll({type:"window",includeUncontrolled:true});
  for(const c of cs){if(new URL(c.url).pathname==="/painel.html"){await c.focus();return;}}
  await self.clients.openWindow("/painel.html");})());});
