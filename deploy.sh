#!/bin/sh
# Deploy automatico do La Bodega no cPanel.
# Cron a cada 2 minutos:
#   */2 * * * * /bin/sh /home/labodegapetropol/repositories/labodega/deploy.sh >> /home/labodegapetropol/deploy.log 2>&1
#
# Duas etapas INDEPENDENTES, de proposito:
#   1. copiar codigo novo do repositorio (so quando ha diferenca) e reiniciar o app
#   2. regerar o site a partir da config salva (sempre - barato e idempotente)
# O site pode estar velho mesmo com os arquivos ja no lugar, quando o painel nao
# publicou depois da atualizacao. Por isso a etapa 2 nao depende da 1.

set -e

CASA=/home/labodegapetropol
REPO=$CASA/repositories/labodega
PAINEL=$CASA/painel
SITE=$CASA/public_html
VENV=$CASA/virtualenv/painel/3.12/bin/activate

cd "$REPO"

ANTES=$(git rev-parse --short HEAD 2>/dev/null || echo "?")
git pull -q origin main 2>&1 || echo "aviso: git pull falhou; seguindo com o local"
DEPOIS=$(git rev-parse --short HEAD 2>/dev/null || echo "?")

COPIAR=0
[ "$ANTES" != "$DEPOIS" ] && COPIAR=1
cmp -s painel/app.py "$PAINEL/app.py" || COPIAR=1
cmp -s painel/site_template.html "$PAINEL/site_template.html" || COPIAR=1
cmp -s painel/painel.html "$PAINEL/painel.html" || COPIAR=1

if [ "$COPIAR" = "1" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M')] atualizando $ANTES -> $DEPOIS"
  cp -f painel/passenger_wsgi.py painel/app.py "$PAINEL/"
  cp -f painel/painel.html painel/login.html painel/registro.html "$PAINEL/"
  cp -f painel/site_template.html painel/requirements.txt "$PAINEL/"
  mkdir -p "$SITE/img" "$SITE/video"
  cp -f public/img/* "$SITE/img/" 2>/dev/null || true
  cp -f public/video/* "$SITE/video/" 2>/dev/null || true
  mkdir -p "$PAINEL/tmp"
  touch "$PAINEL/tmp/restart.txt"
  echo "  arquivos copiados, app reiniciado"
fi

# regera o site sempre
# shellcheck disable=SC1090
. "$VENV"
cd "$PAINEL"
SAIDA=$(python -c "import app; ok, msg = app.publish_site(app.load_cfg()); print(ok, msg)")

if [ "$COPIAR" = "1" ]; then
  echo "  publish: $SAIDA"
  echo "  concluido"
fi
