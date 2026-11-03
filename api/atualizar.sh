#!/bin/bash
# Puxa a versão nova do GitHub; se a API mudou, reinicia o serviço.
set -e
cd /opt/genio
antes=$(git rev-parse HEAD)
git fetch -q origin main
git reset -q --hard origin/main
depois=$(git rev-parse HEAD)
if [ "$antes" != "$depois" ] && ! git diff --quiet "$antes" "$depois" -- api/; then
  cp /opt/genio/api/genio-api.service /etc/systemd/system/genio-api.service
  systemctl daemon-reload
  systemctl restart genio-api
fi
