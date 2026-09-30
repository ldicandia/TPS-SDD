# Context capsule — `ssh-pane` en `tmux`

> Descubrimiento destilado de [`notas-exploracion.md`](./notas-exploracion.md) y
> [`spec-brownfield.md`](./spec-brownfield.md) para la próxima tarea sobre `tmux`.
> Commit base `5e4b8cc39e635f8e2c4d9c95c205e987a618d50b`. Referencias revisadas el
> 2026-09-30 en una copia sin modificaciones. **Sin compilación ni pruebas de ejecución**.

## Qué se especificó

Comando `ssh-pane`: un pane con sesión SSH hablada por `libssh`, sin `exec` de `ssh`. Solo
Linux, opt-in (`--enable-ssh`). Clave sin frase con `-i`; sin agent. **No se implementó.**

## El mapa

`cmd.c` (tabla) → `cmd_*_exec` arma `struct spawn_context` (`tmux.h:2500`) → **`spawn_pane`**
(`spawn.c:243`) → `fdforkpty` (`spawn.c:478`) → `window_pane_set_event` (`spawn.c:590` →
`window.c:1673`) → `bufferevent` sobre `wp->fd`.

**La interfaz de I/O es un fd + un `bufferevent`.** El `socketpair` propuesto puede reutilizar
el parser, pero resize, utempter y ciclo de vida conservan suposiciones de PTY/proceso.
Teclado: `window_pane_key` (`window.c:2071`) → `input_key_pane` (`input-keys.c:398`);
el pegado es otro camino (`window_pane_paste`, `window.c:2052`).

## Las trampas

1. **`window_pane_send_resize`** (`window.c:597`) usa `ioctl(TIOCSWINSZ)`: sobre un socket
   si falla, llama `fatal` (`window.c:622`, `log.c:140-152`) y termina el server.
2. **`PANE_STATUSREADY`**: sin él, `server_destroy_pane` retorna en `server-fn.c:382`. Un pane
   sin proceso hijo necesita un estado codificado como `waitpid` (`format.c:2293-2294`).
3. **`PLATFORM` se calcula tarde** (`configure.ac:1008-1118`), después de las
   opciones `--enable-*`. La guarda de Linux tiene que mirar `$host_os`, como
   `--enable-static` (`configure.ac:84-97`).
4. **utempter** recibe el fd en `spawn.c:581`, `window.c:1581` y `server-fn.c:367`.
   **`remain-on-exit`** conserva el pane (`server-fn.c:420`): liberar el bridge solo en
   `window_pane_destroy` no cubre el fin de sesión: `server-fn.c` entra en el alcance,
   con liberación idempotente y exclusión SSH de las tres llamadas utempter. La identidad
   SSH se conserva en el pane muerto para rechazar respawn antes de `spawn.c:312-349`.

## La guarda "solo Linux"

Dos capas: `--enable-ssh` opt-in que aborta en no-Linux (patrón `--enable-systemd` /
`--enable-cgroups`, `configure.ac:503-542`) **y** `#ifdef ENABLE_SSH_PANE` en todo el código
compartido. El precedente systemd no trae rechazo por SO: SSH agrega su propia guarda.
El código nuevo **propuesto** va en la raíz (`cmd-ssh-pane.c`, `ssh-pane.c`), como sixel
(`Makefile.am:253-254`), **no** en `compat/`.

## Invariantes

La spec exige preservar los comandos existentes y el modelo de PTY/panes, excluir SSH
de builds no-Linux y mantener `tmux-protocol.h` sin cambios. **Son obligaciones propuestas,
no resultados medidos**; sus comprobaciones se revisarán al cerrar invariantes.
La matriz macOS está en `.github/workflows/regress.yml:34-37`; su ejecución no se verificó.
La base macOS ya exige opciones explícitas de utf8proc y jemalloc (`configure.ac:1033-1055`).

## Descartado

| Se descartó | Por qué |
|---|---|
| Usar un flag de `split-window` para SSH | Cambia un comando existente; `-S` ya tiene otro uso |
| Crear `compat/ssh-pane.c` (alternativa; no existe) | `compat/` tapa agujeros de SO; esto es una feature |
| Auth por contraseña | Se mantiene el alcance sin prompts |
| Aceptar hosts desconocidos | MITM; `known_hosts` es solo lectura |
| OpenBSD | `pledge` del server (`server.c:207`) sin `inet`/`dns` |

## Sin medir

La línea de base (`make`, `regress/*.sh`, 172 scripts contados) **no se corrió**.
API y LGPL-2.1-or-later verificadas por lectura de libssh 0.9.0; enlace dinámico propuesto.
El agent de esa versión puede bloquear: se eligió `-i`. DNS y lectura de archivos
siguen síncronos. Se desactiva `SSH_OPTIONS_PROCESS_CONFIG` para evitar configuración
SSH automática y se obtiene exit status por callback. Fuentes externas en las notas.
Se usa `event_set`, como tmux, porque el build admite libevent antiguo
(`configure.ac:281-300`, `compat.h:30-40`). No se probó el bridge ni su rendimiento.

## Sin explorar

No se auditó el parser completo, las reglas de layout, todo control mode ni toda la
traducción de teclas. Sí se leyeron `input_init` (`input.c:875`), `input_parse_pane`
(`input.c:1028`), los puntos de entrada de teclado/pegado y la llamada a
`control_write_output` (`window.c:1653`, definición en `control.c:619`).
