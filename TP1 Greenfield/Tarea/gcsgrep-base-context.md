# gcsgrep — base context

> Este documento es la salida de la fase previa al pipeline SDD. Toma el borrador
> del profesor (`gcsgrep-requirements.md`), resuelve sus preguntas abiertas y
> registra las decisiones que alimentan la spec. No es la spec ni reemplaza los
> VCs: la spec define el contrato verificable.

## 1. Problema e idea

Se necesita buscar texto dentro del contenido de objetos remotos de Google Cloud
Storage sin descargar los objetos previamente a disco.

La experiencia buscada es similar a `grep`:

```bash
gcsgrep -i -n "timeout" gs://logs/app/
```

La herramienta debe indicar en qué objeto y línea apareció cada coincidencia,
reducir el uso innecesario de disco y mantener un comportamiento apto para scripts.

## 2. Usuarios y actores

### Usuario principal

Una persona de desarrollo u operaciones que ya utiliza la terminal y tiene acceso
a Google Cloud Storage mediante credenciales configuradas en su entorno.

### Actores del sistema

| Actor | Responsabilidad |
|---|---|
| Persona usuaria | Proporciona el patrón, la ubicación y los flags. |
| Script | Ejecuta el CLI y toma decisiones mediante el exit code. |
| Google Cloud Storage | Lista y entrega objetos; controla permisos y generaciones. |
| Application Default Credentials | Proveen la identidad autorizada para leer GCS. |

## 3. Alcance decidido

### En la primera entrega

- Solo Google Cloud Storage.
- Solo CLI, sin API web ni interfaz gráfica.
- Solo operaciones de listado y lectura.
- Búsqueda literal sobre objetos UTF-8.
- Soporte de `gs://bucket` y `gs://bucket/prefijo`.
- Flags `-i` y `-n`.
- Lectura secuencial por streaming.
- Salida estilo grep.
- Exit codes aptos para scripting.
- Límites predeterminados para evitar costos accidentales.

### Fuera de la primera entrega

- S3, Azure Blob y otros proveedores.
- Regex.
- Escritura, copia, movimiento, borrado o cambios de permisos.
- `.gz` y otros formatos comprimidos.
- Concurrencia configurable.
- JSON, colores, conteos y filtros avanzados.
- Snapshot global y consistencia transaccional del bucket.

## 4. Decisiones sobre las preguntas abiertas

### 4.1 Sabor de expresiones regulares

**Decisión:** la primera entrega hace búsqueda literal; no interpreta regex.

**Motivo:** es el camino más pequeño para obtener una herramienta útil y evita
ambigüedades de escape entre la shell y el lenguaje de implementación. La búsqueda
regex se reserva para una iteración posterior con un flag explícito como `-E`.

**Ejemplo:**

```bash
gcsgrep "timeout.*error" gs://logs/
```

busca literalmente `timeout.*error` en la primera entrega.

### 4.2 Autenticación

**Decisión:** usar Application Default Credentials (ADC), mediante el cliente
oficial de Google Cloud Storage.

El usuario puede configurar ADC, por ejemplo, con:

```bash
gcloud auth application-default login
```

No se acepta un archivo de service account por flag ni se almacenan credenciales.

**Motivo:** respeta la identidad y los permisos ya configurados, reduce el riesgo
de subir secretos al repositorio y mantiene el uso compatible con entornos locales
y de CI.

**Trade-off aceptado:** sin un flag para pasar un archivo de clave, quien necesite
usar una service account tiene que exponerla por `GOOGLE_APPLICATION_CREDENTIALS`,
que ADC ya lee. Se pierde la comodidad de elegir la identidad por invocación, a
cambio de que la herramienta nunca reciba un secreto por la línea de comandos,
donde queda en el historial de la shell y en la lista de procesos.

Si no hay credenciales válidas, el comando termina con código `2` y un mensaje por
`stderr`.

### 4.3 Direccionamiento de GCS

**Decisión:** aceptar solamente ubicaciones con esquema `gs://`:

```text
gs://bucket
gs://bucket/
gs://bucket/prefijo/
```

La parte posterior al bucket es un prefijo exacto de nombres de objeto. No se
agrega automáticamente `/` al final:

- `gs://logs/app/` busca nombres que comienzan con `app/`.
- `gs://logs/app` busca nombres que comienzan con `app`.

**Motivo:** hace explícita la semántica real de prefijos de GCS y evita asumir que
los nombres contienen directorios.

### 4.4 Flags de grep

**Decisión para la primera entrega:**

| Flag | Comportamiento |
|---|---|
| `-i` | Ignora mayúsculas y minúsculas. |
| `-n` | Muestra el número de línea. |

El prefijo de GCS ya define el alcance recursivo, por lo que `-r` no es necesario.

Quedan para después `-E`, `-l`, `-c`, `--include` y `--json`. `-v` no entra en
la v1.

Además, los límites de costo de 4.6 se ajustan con `--max-objects N` y
`--max-bytes N`, que no son flags de `grep`.

**Motivo:** `-i` y `-n` son los dos flags que usa la experiencia buscada
(`gcsgrep -i -n "timeout" gs://logs/app/`, §1). Cubren los pedidos del borrador de
buscar sin distinguir mayúsculas (FR-d) y de mostrar la línea (FR-c). Los demás
flags no hacen falta para responder "en qué objeto y en qué línea". Se difieren
para que la v1 sea el camino más chico hacia una herramienta útil.

### 4.5 Binarios y `.gz`

**Decisión:** saltear `.gz` y objetos cuyos primeros 8.192 bytes contienen un byte
NUL.
Procesar como texto los objetos UTF-8 restantes. Un UTF-8 inválido se informa como
error de lectura.

No se descomprime `.gz` en la primera entrega.

**Motivo:** evita imprimir basura binaria y mantiene el uso de memoria y el alcance
de la implementación controlables. `Content-Type` se considera una pista, no una
prueba suficiente, porque sus metadatos pueden ser incorrectos.

**Por qué 8.192 bytes:** sigue la heurística de GNU `grep` y de `git`, que
buscan un NUL al principio del contenido (`git` mira los primeros 8.000 bytes;
se redondea a 8 KiB). Una muestra de 8 KiB alcanza para
reconocer los formatos binarios comunes, que suelen tener NUL en la cabecera, y
se lee en el primer tramo del stream sin sumar lecturas.

**Trade-off aceptado:** la heurística del byte NUL saltea como binario un texto
codificado en UTF-16. Como la v1 solo soporta UTF-8, se acepta.

### 4.6 Guardrails de costo

**Decisión:** aplicar por defecto ambos límites:

```text
Máximo de objetos: 1.000
Máximo de bytes declarados: 1 GiB
```

El límite que se alcance primero detiene la ejecución, informa el motivo por
`stderr` y devuelve código `2`. Los valores se ajustan con `--max-objects N` y
`--max-bytes N`, que aceptan enteros positivos, con `N` en bytes para el segundo.

El límite de bytes se evalúa sobre el tamaño declarado en el listado, antes de
leer cada objeto, y no sobre los bytes efectivamente leídos. Así se evita empezar
a leer un objeto que ya se sabe que excede el tope.

**Motivo:** las lecturas de GCS pueden generar costos y un prefijo amplio puede
ser accidental. No se agrega todavía un modo ilimitado.

**Por qué esos valores:** 1.000 objetos es el tamaño de una página del listado de
GCS, así que el límite por defecto se alcanza sin pedir una segunda página. 1 GiB
alcanza para un día de logs de una aplicación chica, que es el caso de uso típico,
y leerlo completo cuesta unos USD 0,12 de egreso a internet (y nada dentro de la
misma región), así que un error con los valores por defecto sale barato.

**Trade-off aceptado:** un tope bajo protege contra un costo accidental, pero
obliga a pasar `--max-objects`/`--max-bytes` en búsquedas legítimas grandes. Se
prefiere que la ejecución falle ruidosamente (exit `2` y el motivo por `stderr`)
antes que escanear de más sin avisar. Un límite alcanzado siempre devuelve `2`,
aunque no haya habido matches, porque el prefijo no se revisó completo.

### 4.7 Formato de salida

**Decisión:** una línea por match, con formato estilo grep y `:` como separador:

```text
gs://bucket/objeto:contenido de la línea        (sin -n)
gs://bucket/objeto:42:contenido de la línea     (con -n)
```

Los matches van a `stdout`; errores y progreso van a `stderr` con el prefijo
`gcsgrep: `. No se usan colores ni JSON en la primera entrega.

**Motivo:** es el mismo formato que `grep -H` y `grep -Hn` usan con varios
archivos, así que los hábitos y scripts existentes (`cut -d:`, editores que
abren `archivo:línea`) siguen sirviendo. Se imprime el URI completo para poder
pasarlo tal cual a otros comandos que aceptan `gs://`.

### 4.8 Exit codes

**Decisión:** copiar la convención de `grep`:

| Código | Significado |
|---:|---|
| `0` | Se encontró al menos una coincidencia. |
| `1` | La búsqueda terminó sin coincidencias. |
| `2` | Error operativo, entrada inválida, credenciales o límite alcanzado. |

Si hubo matches pero falló la lectura de al menos un objeto, se devuelve `2` para
dejar claro que el resultado es parcial. De un objeto fallido se imprimen los
matches de las líneas anteriores a la línea donde se detectó la falla, y ninguno
de ahí en adelante. Por eso el contenido se decodifica línea por línea y no por
bloque: así la salida parcial no depende de dónde caen los bordes de lectura.

**Motivo:** el usuario objetivo ya usa `grep`, y los scripts existentes ya
distinguen "encontró" (`0`), "no encontró" (`1`) y "falló" (`2`)
(`if gcsgrep ...; then`, `set -e`, `|| true`). Con otra convención, esos scripts
tratarían un error como "sin matches" o al revés. Un resultado parcial devuelve
`2` y no `0`, porque un script que ve `0` supone que se revisó todo el prefijo.

### 4.9 Concurrencia

**Decisión:** procesar un objeto a la vez en la primera entrega.

**Motivo:** mantiene el orden determinista, reduce el consumo de memoria y hace
más fácil respetar los límites de costo y verificar la salida. Una iteración futura
puede agregar `--jobs`, manteniendo límites globales.

### 4.10 Cambios durante la lectura

**Decisión:** leer la generación que GCS devuelve al enumerar cada objeto cuando
esa información esté disponible. No prometer una snapshot global del bucket.

Objetos creados después del listado pueden no ser incluidos. Si la generación
enumerada ya no está disponible, se informa el error y se continúa con los objetos
restantes.

**Motivo:** GCS permite identificar versiones individuales, pero congelar todo el
bucket excede el alcance de la primera entrega.

### 4.11 Reintentos de red

**Decisión:** reintentar hasta 3 veces los errores transitorios de lectura
(timeout, conexión cortada, HTTP 429 o 5xx), con esperas fijas de 1 s, 2 s y 4 s
(backoff exponencial sin aleatoriedad). El reintento vuelve a pedir el tramo en
curso desde el mismo offset. Al agotar los reintentos, el objeto se informa como
fallido, se continúa con el resto y la ejecución termina con código `2`.

**Motivo:** los errores transitorios de GCS suelen resolverse en segundos. Con
3 reintentos, la espera extra por objeto queda acotada a 7 s, así que la corrida
no parece colgada y una falla persistente no bloquea a los demás objetos. Qué
errores son reintentables se toma de la clasificación de la librería oficial,
para no reimplementarla. La cantidad de intentos y las esperas los fija
`gcsgrep`, porque la política por defecto de la librería reintenta por tiempo
(hasta un plazo total) y con esperas aleatorias, y así no se podría verificar
NFR-2.

**Trade-off aceptado:** la aleatoriedad (jitter) sirve para que muchos clientes
no reintenten a la vez. `gcsgrep` hace una sola lectura secuencial por
ejecución, así que ese riesgo es bajo y se prefiere un comportamiento
determinista y verificable.

## 5. Notas de diseño y arquitectura

La implementación se separa en tres responsabilidades:

```text
cli → gcs → matcher
```

- `cli`: parsea argumentos, formatea salida y traduce errores a exit codes.
- `gcs`: valida URIs, enumera objetos y lee streams desde GCS.
- `matcher`: aplica la búsqueda literal línea por línea.

El flujo principal es:

```text
argv
  ↓
cli: parseo y validación
  ↓
gcs: listado y streaming de objetos
  ↓
matcher: comparación línea por línea
  ↓
cli: stdout/stderr y exit code
```

La dependencia de GCS se inyecta en los tests para verificar la lógica sin
credenciales reales. Además, la entrega requiere una verificación de integración
contra un bucket de prueba. Para que esa verificación sea reproducible y sin
costo se usa el emulador de GCS de [Floci](https://floci.io/gcp/): el cliente
oficial lo detecta mediante `STORAGE_EMULATOR_HOST`, por lo que `gcsgrep` no
necesita código específico de emulador y la misma suite sirve contra GCP real.

## 6. Riesgos y decisiones aceptadas

- Leer un bucket muy grande puede ser costoso; los límites son obligatorios.
- No existe una snapshot global del bucket.
- La primera entrega no garantiza orden útil para futuras lecturas concurrentes,
  porque todavía es secuencial.
- Los objetos pueden cambiar o borrarse mientras se ejecuta el listado.
- Un error de un objeto produce resultado parcial y exit code `2`.
- Los tests unitarios no sustituyen la corrida real contra GCS.

## 7. Qué alimenta este documento

Este base context alimenta:

1. [`gcsgrep-spec.md`](./gcsgrep-spec.md), que convierte estas decisiones en
   requerimientos y VCs.
2. [`gcsgrep-plan.md`](./gcsgrep-plan.md), que separa la Iteración 1 del alcance
   diferido.
3. [`gcsgrep-cobertura-vc.md`](./gcsgrep-cobertura-vc.md), que registra la
   evidencia de verificación.

Las decisiones implementadas y el alcance diferido no deben inferirse del código:
la fuente de verdad es la spec y este documento de contexto.
