#!/bin/bash
# Verificación posterior al corte. VERIFICAR_URLS: lista "url=codigo" separada por espacios.
# En la VM: "https://communitylab.nodnexa.com/healthz=200 http://communitylab.nodnexa.com/=301".
# Sin VERIFICAR_URLS solo comprueba la API desde su contenedor.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
dc exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)" \
  || fallar "la API no responde"
for par in ${VERIFICAR_URLS:-}; do
  url=${par%=*}; esperado=${par##*=}
  real=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || true)
  [ "$real" = "$esperado" ] || fallar "$url devolvió $real (esperado $esperado)"
  log "verificado $url -> $real"
done
