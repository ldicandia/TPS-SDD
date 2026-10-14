#!/usr/bin/env bash
# crear-bucket.sh — arma el bucket de prueba de gcsgrep y la cuenta de solo lectura.
#
# Lo corre UNA PERSONA, con su propia cuenta de gcloud (no la service account): es la
# única que puede crear y subir. El agente nunca corre esto.
#
#   cp .env.example .env    # y completá PROYECTO (y si querés CUENTA_HUMANA, BUCKET)
#   bash bucket/crear-bucket.sh            # desde `TP4 Plugins adn MCP/`
#
# Deja:
#   gs://$PROYECTO-gcsgrep-tp4            objetos sintéticos (bucket/objetos/ + .gz + binario)
#   gs://$PROYECTO-gcsgrep-tp4-sinacceso  un objeto que la SA no puede leer (VC de 403)
#   gcsgrep-mcp-lector@…                  SA con roles/storage.objectViewer SOLO sobre el primero
# y te da a vos roles/iam.serviceAccountTokenCreator sobre la SA, para impersonarla.
# Sin keys JSON: la credencial del server sale de ADC por impersonación.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
# Datos del equipo en ../.env (fuera de git; plantilla en ../.env.example).
# Lo que ya esté exportado en el entorno tiene prioridad.
if [ -f "$AQUI/../.env" ]; then
  while IFS='=' read -r k v; do
    case "$k" in PROYECTO|CUENTA_HUMANA|BUCKET|REGION) [ -n "${!k:-}" ] || export "$k=$v" ;; esac
  done < <(grep -E '^[A-Z_]+=' "$AQUI/../.env" | tr -d '\r')
fi
: "${PROYECTO:?definí PROYECTO (en .env o en el entorno) con el id del proyecto de prueba}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-$PROYECTO-gcsgrep-tp4}"
SIN_ACCESO="$BUCKET-sinacceso"
SA_NOMBRE=gcsgrep-mcp-lector
SA="$SA_NOMBRE@$PROYECTO.iam.gserviceaccount.com"
YO="${CUENTA_HUMANA:-$(gcloud config get-value account 2>/dev/null)}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

gcloud config set project "$PROYECTO" >/dev/null
gcloud services enable storage.googleapis.com iamcredentials.googleapis.com

for b in "$BUCKET" "$SIN_ACCESO"; do
  gcloud storage buckets describe "gs://$b" >/dev/null 2>&1 \
    || gcloud storage buckets create "gs://$b" --location="$REGION" \
         --uniform-bucket-level-access --public-access-prevention
done

# Objetos: los de texto vienen del repo; el .gz y el binario se generan acá.
cp -R "$AQUI/objetos/." "$TMP/"
rm -rf "$TMP/archive-src"; mkdir -p "$TMP/archive" "$TMP/bin"
gzip -9 -n -c "$AQUI/objetos/archive-src/old.log" > "$TMP/archive/old.log.gz"
printf 'GCSB\x00\x01\x02timeout\x00\xff\xfe binario sintetico\n' > "$TMP/bin/blob.bin"
gcloud storage cp --recursive "$TMP/"* "gs://$BUCKET/"
# El content-type explícito no es cosmético: en Windows gcloud sube los .log como
# application/octet-stream, y storage-mcp 0.6.0 se niega a leer ese tipo como texto
# (UnsupportedContentType). Cambiar el content-type toca solo la metadata: la
# generation de cada objeto no cambia.
gcloud storage objects update "gs://$BUCKET/**.log" --content-type=text/plain
gcloud storage objects update "gs://$BUCKET/archive/old.log.gz" --content-type=application/gzip
printf 'secreto sintetico: este objeto no lo puede leer la SA\n' \
  | gcloud storage cp - "gs://$SIN_ACCESO/privado/no-leer.log"

# La cuenta del agente: solo lectura, solo este bucket. Nada a nivel proyecto.
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NOMBRE" \
       --display-name="gcsgrep MCP (solo lectura del bucket de prueba)"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SA" --role=roles/storage.objectViewer >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="user:$YO" --role=roles/iam.serviceAccountTokenCreator >/dev/null

cat <<FIN

Listo. Bucket: gs://$BUCKET   SA: $SA

Siguiente, en la terminal desde donde abrís claude:
  gcloud auth application-default login --impersonate-service-account=$SA
  export GCSGREP_BUCKET=$BUCKET
FIN
