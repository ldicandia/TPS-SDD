# Context capsule — acción `clear-history` en `fzf`

> Salida de `freeze-spec`, producida cuando
> [`spec-brownfield.md`](./spec-brownfield.md) se entregó y verificó.
>
> **Para qué sirve:** la próxima spec sobre `fzf` lee esto, no toda la historia. Es
> descubrimiento destilado y preservado, para no volver a pagarlo.
>
> Fijate el tamaño. La spec tiene ~150 líneas y las notas de exploración ~190: juntas,
> más de 300. La capsule tiene ~70. Si fuera tan larga como la spec no serviría de nada: el
> punto es que entre en la ventana de contexto de la próxima tarea junto con todo lo demás.

## Qué se construyó

Una acción `clear-history` para `fzf`, bindeable, que vacía el archivo de historial desde
adentro de la sesión.

## El mapa que costó descubrir

El camino de una acción, de la línea de comandos a su ejecución:

| Paso | Dónde |
|---|---|
| Parseo del nombre | `src/options.go` — switch de acciones (~1909) |
| Declaración de la constante | `src/terminal.go` — `type actionType` (~557) |
| Ejecución | `src/terminal.go` — switch de dispatch (~7850) |
| Trabajo real | el módulo correspondiente (acá, `src/history.go`) |

**Agregar una acción toca esos cuatro lugares. Siempre.**

## La trampa

`src/actiontype_string.go` es **generado** (`//go:generate stringer -type=actionType`, en
`src/terminal.go:556`) y contiene índices posicionales. Agregar una constante en el medio
del bloque desplaza todo lo que sigue.

**Se regenera con `make generate` (necesita `stringer`). Nunca se edita a mano.** Ignorarlo rompe el
build con errores que no señalan la causa.

## Invariantes que quedaron establecidos

- `fzf` sin `--history` tiene `t.history == nil`. **Toda acción de historial necesita el
  guard.**
- El archivo de historial vive con permisos `0600`, fijados en `NewHistory` y `append`.
- `append` corre **al salir** con código 0 o 1 (`src/terminal.go:6572`): la query final
  siempre se escribe en el historial.
- `src/history.go` es multiplataforma: usa `os.ReadFile` / `os.WriteFile`. La capa
  específica de plataforma son otros cinco archivos (`*_unix.go`, `*_windows.go`).

## Línea de base de regresión

```bash
make test     # Go: src, src/algo, src/tui, src/util
make lint     # gofmt -s, rubocop y scripts de shell
```

Integración en Ruby bajo `test/` (`make itest`, necesita `tmux`); `test/test_core.rb:525`
(`test_history`) cubre el historial de punta a punta.

## Decisiones tomadas, y lo que se descartó

| Decisión | Se descartó |
|---|---|
| Truncar el archivo | Borrarlo — perdería permisos y dueño |
| Sin tecla por default | Bindear `CTRL-ALT-D` — borrado accidental irreversible |
| Sin confirmación interactiva | Un diálogo — es diseño de UI, va en su propia spec |
| No exponerla por `--listen` | Ampliaría la superficie de ataque sin pedido concreto |

## Lo que sigue sin explorarse

`src/algo/`, `src/tui/`, el preview, y `src/server.go`. Si la próxima tarea los toca, ese
descubrimiento está por hacerse.
