#!/bin/sh
# Deploy automatico do La Bodega no cPanel.
# Chamado por um Cron Job. Se nao houver commit novo, sai sem fazer nada.
#
# Cron sugerido (a cada 10 min):
#   */10 * * * * /bin/sh /home/labodegapetropol/repositories/labodega/deploy.sh >> /home/labodegapetropol/deploy.log 2>&1

set -e

CASA=/home/labodegapetropol
REPO=$CASA/repositories/labodega
PAINEL=$CASA/painel
SITE=$CASA/public_html
VENV=$CASA/virtualenv/painel/3.12/bin/activate

cd "$REPO"

ANTES=$(git rev-parse HEAD)
git pull -q origin main || exit 0
DEPOIS=$(git rev-parse HEAD)

# nada novo: encerra em silencio para nao poluir o log
[ "$ANTES" = "$DEPOIS" ] && exit 0

echo "[$(date '+%Y-%m-%d %H:%M')] deploy $ANTES -> $DEPOIS"

# 1. codigo do painel
cp -f painel/passenger_wsgi.py painel/app.py "$PAINEL/"
cp -f painel/painel.html painel/login.html painel/registro.html "$PAINEL/"
cp -f painel/site_template.html painel/requirements.txt "$PAINEL/"

# 2. arquivos do site (index.html NAO: e gerado pelo painel)
mkdir -p "$SITE/img" "$SITE/video"
cp -f public/img/* "$SITE/img/" 2>/dev/null || true
cp -f public/video/* "$SITE/video/" 2>/dev/null || true

# 3. reinicia o app (Passenger recarrega ao ver o arquivo mudar)
mkdir -p "$PAINEL/tmp"
touch "$PAINEL/tmp/restart.txt"

# 4. regera o site com o codigo novo
# shellcheck disable=SC1090
. "$VENV"
cd "$PAINEL"
python -c "import app; ok, msg = app.publish_site(app.load_cfg()); print('publish:', ok, msg)"

echo "deploy concluido"
