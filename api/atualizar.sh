#!/bin/bash
# Puxa a versão nova do GitHub; se a API mudou, reinicia o serviço.
# Também: (a) junta chaves novas de api/env.seed em /etc/genio/env e as apaga do disco;
#         (b) instala unidades systemd novas de api/*.service|*.timer;
#         (c) roda a captação quando api/captacao.run mudar (gatilho pela esteira).
set -e
cd /opt/genio
antes=$(git rev-parse HEAD)
git fetch -q origin main
git reset -q --hard origin/main
depois=$(git rev-parse HEAD)
mkdir -p /var/lib/genio /opt/genio/dados
id genio >/dev/null 2>&1 && chown -R genio:genio /var/lib/genio /opt/genio/dados

# (a) chaves pela esteira: cada KEY=VAL do seed entra (ou substitui) no env, uma vez
if [ -f api/env.seed ]; then
  while IFS= read -r linha; do
    [[ "$linha" =~ ^[A-Z_]+= ]] || continue
    k="${linha%%=*}"
    if grep -q "^${k}=" /etc/genio/env; then sed -i "s|^${k}=.*|${linha}|" /etc/genio/env; else echo "$linha" >> /etc/genio/env; fi
  done < api/env.seed
  rm -f api/env.seed
  echo "seed aplicado $(date -Is)" >> /var/lib/genio/esteira.log
  systemctl restart genio-api || true
fi

# (b) pacotes e unidades
if [ ! -f /var/lib/genio/pacotes.ok ]; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-pil python3-numpy >/dev/null 2>&1 && touch /var/lib/genio/pacotes.ok || true
fi
for u in api/*.service api/*.timer; do
  [ -f "$u" ] || continue
  if ! cmp -s "$u" "/etc/systemd/system/$(basename "$u")"; then
    cp "$u" /etc/systemd/system/ && systemctl daemon-reload
    case "$u" in *.timer) systemctl enable -q --now "$(basename "$u")";; esac
  fi
done

if [ "$antes" != "$depois" ] && ! git diff --quiet "$antes" "$depois" -- api/genio_api.py api/genio-api.service; then
  systemctl restart genio-api
fi

# (c2) pedido do admin (API grava /var/lib/genio/captacao/pedido.json) → roda agora
if [ -f /var/lib/genio/captacao/pedido.json ]; then
  hp=$(sha256sum /var/lib/genio/captacao/pedido.json | cut -c1-16)
  if [ "$(cat /var/lib/genio/captacao.pedido.sha 2>/dev/null)" != "$hp" ]; then
    echo "$hp" > /var/lib/genio/captacao.pedido.sha
    systemctl start --no-block genio-captacao.service
  fi
fi
# (c) gatilho: conteúdo de api/captacao.run mudou → roda agora (em segundo plano)
if [ -f api/captacao.run ]; then
  h=$(sha256sum api/captacao.run | cut -c1-16)
  if [ "$(cat /var/lib/genio/captacao.run.sha 2>/dev/null)" != "$h" ]; then
    echo "$h" > /var/lib/genio/captacao.run.sha
    systemctl start --no-block genio-captacao.service
  fi
fi
