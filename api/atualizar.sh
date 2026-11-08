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
if [ ! -f /var/lib/genio/pacotes2.ok ]; then
  # pacotes do manual de identidade: um a um (nome ausente numa distro não derruba os outros); pip como reserva
  DEBIAN_FRONTEND=noninteractive apt-get update -q >>/var/lib/genio/apt.log 2>&1
  for pk in python3-opencv python3-skimage librsvg2-bin tesseract-ocr tesseract-ocr-por python3-pytesseract python3-pip; do
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$pk" >>/var/lib/genio/apt.log 2>&1 || echo "apt: falhou $pk" >>/var/lib/genio/apt.log
  done
  python3 -c "import cv2, skimage" >/dev/null 2>&1 || pip3 install -q --break-system-packages opencv-python-headless scikit-image pytesseract >>/var/lib/genio/apt.log 2>&1 || true
  if python3 -c "import cv2, skimage" >/dev/null 2>&1 && command -v rsvg-convert >/dev/null; then touch /var/lib/genio/pacotes2.ok; echo "pacotes do manual ok $(date -Is)" >> /var/lib/genio/esteira.log; else echo "pacotes do manual incompletos $(date -Is)" >> /var/lib/genio/esteira.log; fi
fi
if [ ! -f /var/lib/genio/pacotes3.ok ] && [ ! -f /var/lib/genio/pacotes3.rodando ]; then
  # ferramentas da versão limpa (passada 1 e exportação): em segundo plano, para não travar a esteira
  touch /var/lib/genio/pacotes3.rodando
  nohup bash -c '
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q inkscape ghostscript >>/var/lib/genio/apt.log 2>&1 || echo "apt: falhou inkscape/ghostscript" >>/var/lib/genio/apt.log
    pip3 install -q --break-system-packages vtracer "rembg[cpu]" >>/var/lib/genio/apt.log 2>&1 || pip3 install -q --break-system-packages vtracer rembg onnxruntime >>/var/lib/genio/apt.log 2>&1 || echo "pip: falhou vtracer/rembg" >>/var/lib/genio/apt.log
    pip3 install -q --break-system-packages --index-url https://download.pytorch.org/whl/cpu torch torchvision >>/var/lib/genio/apt.log 2>&1 && pip3 install -q --break-system-packages realesrgan >>/var/lib/genio/apt.log 2>&1 || echo "pip: falhou realesrgan" >>/var/lib/genio/apt.log
    python3 -c "import vtracer, rembg" >/dev/null 2>&1 && command -v inkscape >/dev/null && command -v gs >/dev/null && touch /var/lib/genio/pacotes3.ok
    python3 -c "import realesrgan" >/dev/null 2>&1 && touch /var/lib/genio/realesrgan.ok
    echo "pacotes da versão limpa: $( [ -f /var/lib/genio/pacotes3.ok ] && echo ok || echo incompletos ) · realesrgan $( [ -f /var/lib/genio/realesrgan.ok ] && echo ok || echo nao ) $(date -Is)" >> /var/lib/genio/esteira.log
    rm -f /var/lib/genio/pacotes3.rodando
  ' >/dev/null 2>&1 &
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
# (d) backup diário dos dados do servidor (estado, chaves, captação, kits): /var/backups/genio, guarda 14 dias
hoje=$(date +%F)
if [ ! -f /var/backups/genio/genio-$hoje.tar.gz ]; then
  mkdir -p /var/backups/genio
  tar -czf /var/backups/genio/genio-$hoje.tar.gz.tmp -C / var/lib/genio opt/genio/dados 2>/dev/null && mv /var/backups/genio/genio-$hoje.tar.gz.tmp /var/backups/genio/genio-$hoje.tar.gz
  find /var/backups/genio -name 'genio-*.tar.gz' -mtime +14 -delete
  echo "backup $hoje ok $(date -Is)" >> /var/lib/genio/esteira.log
fi
