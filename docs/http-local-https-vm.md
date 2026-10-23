# HTTP local y HTTPS en la VM

Docker Compose 2.24.4 o posterior: compose.https.yml usa !override para reemplazar puertos, sin conservar el puerto local.

## Computadora local

Copiar .env.example a .env y definir POSTGRES_PASSWORD. En Intel/AMD, usar DOCKER_PLATFORM=linux/amd64; en ARM usar linux/arm64. Mantener WORKER_MODE=simulado para probar sin IA externa.

```sh
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml up -d --build
```

Abrir http://127.0.0.1:8080. HTTP_BIND_ADDRESS y HTTP_PORT permiten cambiar la dirección y el puerto. No se requieren dominio ni certificados. El proxy sirve /healthz y conserva /api/ al reenviar al backend.

## VM HTTPS

Usar el mismo .env con la plataforma de la VM y credenciales privadas. El dominio de esta configuración es communitylab.nodnexa.com y debe apuntar a la VM. Deben existir certificados válidos en /etc/letsencrypt/live/communitylab.nodnexa.com/; emisión y renovación siguen a cargo del mecanismo de Let's Encrypt de la VM.

```sh
docker compose -f docker-compose.yml -f compose.https.yml config --quiet
docker compose -f docker-compose.yml -f compose.https.yml up -d --build
docker compose -f docker-compose.yml -f compose.https.yml exec proxy nginx -t
```

Es obligatorio incluir ambos archivos en los comandos de despliegue de la VM; ejecutar solo el base activa el modo local. HTTPS_BIND_ADDRESS (por defecto 0.0.0.0), HTTPS_HTTP_PORT (80), HTTPS_PORT (443) y LETSENCRYPT_DIR (/etc/letsencrypt) son configurables. Se monta el directorio completo para conservar los enlaces a archive/. No se crea automáticamente un directorio de certificados inexistente.

Nginx mantiene la redirección HTTP al dominio HTTPS y las cabeceras de seguridad del PR22. Tras renovar certificados, comprobar nginx -t y recargar el proxy con los mismos archivos Compose. Este cambio no configura ni verifica la renovación automática.

## Prueba aislada reproducible

Requisitos: Docker activo, Python 3 y OpenSSL. La prueba no necesita dependencias Python adicionales ni claves de IA. Usa nginx:stable-alpine (descargar antes si no está disponible).

```sh
python tools/probar_proxy.py --report resultado-proxy.json
```

Windows con Git for Windows:

```powershell
python tools/probar_proxy.py --openssl 'C:\Program Files\Git\usr\bin\openssl.exe' --report resultado-proxy.json
```

Comprueba la combinación Compose, puertos y montajes, rechazo de certificados ausentes, nginx -t, healthchecks HTTP, rutas web/API, preservación de query y X-Forwarded-Proto, redirección HTTPS y cabeceras TLS. El cliente valida un certificado temporal con nombre localhost y CA explícita, sin omitir la validación SSL. Los upstreams web/API son ficticios y sirven para verificar el proxy, no para validar la lógica de negocio. Contenedores, red y claves temporales se limpian al terminar.

Antes de aprobar la puesta en producción: verificar el despliegue con certificados reales en la VM y que sus comandos de operación incluyan compose.https.yml. La prueba aislada no acredita el estado actual de la VM, DNS, firewall o renovación.
