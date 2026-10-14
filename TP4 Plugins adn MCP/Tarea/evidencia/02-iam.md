# Evidencia 02 — IAM del bucket de prueba

Capturado el 2026-10-14T01:45:27Z con la cuenta humana (dueña del proyecto), no con la SA.

## `gcloud storage buckets get-iam-policy gs://spec-driven-511601-gcsgrep-tp4`

```
bindings:
- members:
  - projectEditor:spec-driven-511601
  - projectOwner:spec-driven-511601
  role: roles/storage.legacyBucketOwner
- members:
  - projectViewer:spec-driven-511601
  role: roles/storage.legacyBucketReader
- members:
  - projectEditor:spec-driven-511601
  - projectOwner:spec-driven-511601
  role: roles/storage.legacyObjectOwner
- members:
  - projectViewer:spec-driven-511601
  role: roles/storage.legacyObjectReader
- members:
  - serviceAccount:gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
  role: roles/storage.objectViewer
etag: CAI=
```

## La SA no tiene roles a nivel proyecto

`gcloud projects get-iam-policy spec-driven-511601` filtrado por la SA:

```
(vacío = ningún rol de proyecto)
```

## El segundo bucket no le da nada a la SA

```
bindings:
- members:
  - projectEditor:spec-driven-511601
  - projectOwner:spec-driven-511601
  role: roles/storage.legacyBucketOwner
- members:
  - projectViewer:spec-driven-511601
  role: roles/storage.legacyBucketReader
- members:
  - projectEditor:spec-driven-511601
  - projectOwner:spec-driven-511601
  role: roles/storage.legacyObjectOwner
- members:
  - projectViewer:spec-driven-511601
  role: roles/storage.legacyObjectReader
etag: CAE=
```

## Objetos del bucket (`gcloud storage ls -l --recursive`)

```
gs://spec-driven-511601-gcsgrep-tp4/:

gs://spec-driven-511601-gcsgrep-tp4/archive/:
        81  2026-10-14T01:44:58Z  gs://spec-driven-511601-gcsgrep-tp4/archive/old.log.gz#1791942298185401  metageneration=1

gs://spec-driven-511601-gcsgrep-tp4/bin/:
        36  2026-10-14T01:44:58Z  gs://spec-driven-511601-gcsgrep-tp4/bin/blob.bin#1791942298573668  metageneration=1

gs://spec-driven-511601-gcsgrep-tp4/edge/:
         0  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/edge/empty.log#1791942299306598  metageneration=1
        11  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/edge/nonl.log#1791942299249823  metageneration=1

gs://spec-driven-511601-gcsgrep-tp4/fixtures/:

gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/:
       265  2026-10-14T01:44:58Z  gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/notas.log#1791942298536863  metageneration=1

gs://spec-driven-511601-gcsgrep-tp4/logs/:

gs://spec-driven-511601-gcsgrep-tp4/logs/2026/:

gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/:

gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/13/:

gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/13/deep/:
       171  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/13/deep/worker.log#1791942299385263  metageneration=1

gs://spec-driven-511601-gcsgrep-tp4/logs/app/:
        97  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log#1791942299674455  metageneration=1
        82  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log#1791942299285470  metageneration=1
       314  2026-10-14T01:44:59Z  gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log#1791942299203604  metageneration=1
TOTAL: 9 objects, 1057 bytes (1.03kiB)
```
