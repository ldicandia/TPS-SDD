# Spec — acción `clear-history` en `fzf`

> Spec **brownfield**, construida sobre
> [`notas-exploracion.md`](./notas-exploracion.md).
>
> Lo que la distingue de una spec greenfield son tres secciones: **fuera de alcance** con
> paths concretos, **invariantes** que dicen qué no puede cambiar, y una **línea de base
> de regresión** establecida antes de tocar nada.

**Repo:** [`junegunn/fzf`](https://github.com/junegunn/fzf) · commit base `b1be3a8`

## Propósito

Permitir borrar el historial de búsquedas de `fzf` desde adentro de la sesión, con una
acción bindeable, sin salir ni borrar el archivo a mano.

## Alcance

### Dentro

| Archivo | Cambio |
|---|---|
| `src/history.go` | Un método `clear()` que trunca el archivo y resetea el estado en memoria |
| `src/terminal.go` | Una constante `actClearHistory` y su `case` en el switch de ejecución |
| `src/options.go` | Un `case "clear-history"` en el parseo de acciones |
| `src/actiontype_string.go` | **Regenerado**, nunca editado a mano |
| `man/man1/fzf.1` | Una entrada en `AVAILABLE ACTIONS` |
| `src/history_test.go` | Cobertura del método nuevo |

### Fuera de alcance

Explícito, por path:

- **`src/algo/`** — el motor de matching no se toca.
- **`src/tui/`** — sin cambios de interfaz ni de render.
- **`src/server.go`** — la acción no se expone por el server HTTP en esta iteración.
- **`src/proxy_*.go`, `src/terminal_unix.go`, `src/terminal_windows.go`,
  `src/winpty_windows.go`** — la capa de portabilidad no se modifica.
- **Los bindings por default** (`src/options.go:3794-3800`) — `clear-history` no toma
  ninguna tecla por default. Es destructiva: se activa solo si el usuario la bindea.
- **Confirmación interactiva** — fuera de alcance. Si se quisiera, es una iteración
  aparte con su propio diseño de UI.

## Invariantes

Cosas que tienen que seguir siendo verdad **después** del cambio:

| # | Invariante | Cómo se comprueba |
|---|---|---|
| **INV-1** | `fzf` sin `--history` sigue funcionando y la acción nueva no rompe nada | `fzf --bind 'ctrl-d:clear-history'` sin `--history` no panica |
| **INV-2** | El archivo de historial conserva permisos `0600` | `stat` sobre el archivo después de `clear` |
| **INV-3** | `prev-history` / `next-history` siguen comportándose igual | `ruby test/test_core.rb -n test_history` sigue en verde |
| **INV-4** | El enum de acciones queda consistente | `make generate` no deja diff pendiente (`git diff --exit-code src/actiontype_string.go`) |
| **INV-5** | El cambio no agrega dependencia de plataforma | `src/history.go` sigue sin ser un archivo `_unix` / `_windows` |

## Línea de base de regresión

Medida **antes** de tocar una línea:

```bash
make test     # tests de Go: src, src/algo, src/tui, src/util  → todo en verde
make lint     # gofmt -s sin diff, rubocop y scripts de shell (necesita bundle install)
ruby test/test_core.rb -n test_history   # integración del historial (necesita tmux)
```

Al cerrar la iteración, las tres tienen que dar lo mismo. Cualquier diferencia es una
regresión, no un efecto colateral aceptable.

## Requerimientos

### FR-1 · La acción se parsea

**Dado** un binding `--bind 'ctrl-alt-d:clear-history'`,
**cuando** `fzf` arranca,
**entonces** no hay error de parseo y la tecla queda asociada a la acción.

**VC-1:** `fzf --history=/tmp/h --bind 'ctrl-alt-d:clear-history' --version` sale con
código 0.

### FR-2 · La acción vacía el archivo

**Dado** una sesión con `--history=ARCHIVO` y entradas previas,
**cuando** se dispara `clear-history`,
**entonces** `ARCHIVO` queda vacío.

**VC-2:** el archivo existe y tiene tamaño 0 después de disparar la acción y salir con
`ESC`. Salir aceptando con una query no sirve para medirlo: `fzf` escribe la query en el
historial al terminar (ver hallazgo 5 de las notas).

### FR-3 · El estado en memoria se resetea

**Dado** que se disparó `clear-history`,
**cuando** el usuario presiona la tecla de `prev-history`,
**entonces** la query no cambia: no hay entradas para recorrer.

**VC-3:** tras `clear-history`, `previous()` devuelve cadena vacía.

### FR-4 · Sin historial, no pasa nada

**Dado** una sesión **sin** `--history`,
**cuando** se dispara `clear-history`,
**entonces** `fzf` sigue corriendo normalmente.

**VC-4:** el proceso no termina ni escribe a stderr. Cubre INV-1.

### BR-1 · Los permisos no se aflojan

El truncado usa los mismos permisos que `append`: `0600`.

**VC-5:** `stat -c %a ARCHIVO` (en macOS, `stat -f %Lp ARCHIVO`) devuelve `600` después de
`clear`. Cubre INV-2.

### BR-2 · La acción no se ejecuta sin que el usuario la pida

No se agrega ningún binding por default.

**VC-6:** `grep -c 'actClearHistory' src/options.go` devuelve 1: la única aparición es el
`case` del parseo. Si apareciera también en el bloque de defaults de teclas, serían 2.
(No se chequea por número de línea: agregar el `case` corre todas las líneas de abajo.)

### NFR-1 · Documentación

La acción figura en `man/man1/fzf.1`, sección `AVAILABLE ACTIONS`, con los guiones
escapados en roff (`clear\-history`).

**VC-7:** `grep -c 'clear\\-history' man/man1/fzf.1` devuelve al menos 1.

## Plan de iteraciones

| Iteración | Alcance | Cierra |
|---|---|---|
| **1** | `clear()` en `src/history.go` + test unitario | VC-3, VC-5 |
| **2** | Constante, regeneración del enum, dispatch y parseo | VC-1, VC-2, VC-4, VC-6 |
| **3** | Documentación en el man page | VC-7 |

La Iteración 1 es el camino más angosto que se puede ejercitar solo: el método del módulo,
con su test, sin tocar el enum ni el parseo.

## Preguntas abiertas — resueltas

| Pregunta | Decisión | Por qué |
|---|---|---|
| ¿Borra el archivo o lo trunca? | **Trunca** | Borrarlo perdería los permisos y el dueño que tenía; el próximo `append` lo recrearía con los del proceso |
| ¿Pide confirmación? | **No**, en esta iteración | La UI de confirmación es un diseño aparte. Se mitiga no dándole tecla por default |
| ¿Tecla por default? | **No** | Operación destructiva e irreversible |
| ¿Se expone por el server HTTP? | **No** | Ampliaría la superficie de ataque de `--listen` sin pedido concreto |
