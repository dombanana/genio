#!/bin/bash
# Instala o Gênio na VPS sem mexer no que já existe (banco da hotelaria, outros sites).
# Pode rodar de novo sem problema: cada passo confere se já foi feito.
set -euo pipefail
echo "== 1. pacotes"
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-pymysql git >/dev/null
echo "== 2. usuário do sistema"
id genio >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin genio
echo "== 3. banco separado e usuário que só enxerga ele"
mkdir -p /etc/genio && chmod 700 /etc/genio
if [ ! -f /etc/genio/env ]; then
  P=$(openssl rand -hex 24); K=$(openssl rand -hex 16)
  printf 'GENIO_DB_HOST=localhost\nGENIO_DB_USER=genio\nGENIO_DB_PASS=%s\nGENIO_DB_NAME=genio\nGENIO_CHAVE=%s\nGENIO_PORT=8110\n' "$P" "$K" > /etc/genio/env
  chmod 600 /etc/genio/env
fi
set -a; . /etc/genio/env; set +a
mariadb -e "CREATE DATABASE IF NOT EXISTS genio CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'genio'@'localhost' IDENTIFIED BY '${GENIO_DB_PASS}';
ALTER USER 'genio'@'localhost' IDENTIFIED BY '${GENIO_DB_PASS}';
GRANT ALL PRIVILEGES ON genio.* TO 'genio'@'localhost';
FLUSH PRIVILEGES;"
echo "== 4. código"
[ -d /opt/genio/.git ] || git clone -q https://github.com/dombanana/genio.git /opt/genio
chmod 755 /opt/genio
echo "== 5. serviço da API"
cp /opt/genio/api/genio-api.service /etc/systemd/system/
cp /opt/genio/api/genio-atualizar.service /opt/genio/api/genio-atualizar.timer /etc/systemd/system/
chgrp genio /etc/genio/env && chmod 640 /etc/genio/env && chgrp genio /etc/genio && chmod 750 /etc/genio
systemctl daemon-reload
systemctl enable -q --now genio-api genio-atualizar.timer
sleep 2
curl -fsS http://127.0.0.1:8110/api/saude && echo
echo "== 6. site no nginx (http; o https entra com o certbot depois do DNS)"
if [ ! -f /etc/nginx/sites-available/genio.dombanana.tech.conf ]; then
  cp /opt/genio/api/nginx-genio.conf /etc/nginx/sites-available/genio.dombanana.tech.conf
  ln -sf /etc/nginx/sites-available/genio.dombanana.tech.conf /etc/nginx/sites-enabled/genio.dombanana.tech.conf
fi
nginx -t 2>&1 | tail -1
systemctl reload nginx
echo "== pronto"
