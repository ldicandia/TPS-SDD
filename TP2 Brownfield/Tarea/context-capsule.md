# Context capsule — `ssh-pane` en `tmux`

> Descubrimiento destilado de [`notas-exploracion.md`](./notas-exploracion.md) y
> [`spec-brownfield.md`](./spec-brownfield.md) para la próxima tarea sobre `tmux`.
> Commit base `5e4b8cc`. **Nada de esto se compiló ni se corrió**: ver "Sin medir".

## Qué se especificó

Comando `ssh-pane`: un pane con sesión SSH hablada por `libssh`, sin `exec` de `ssh`. Solo
Linux, opt-in (`--enable-ssh`). **No se implementó.**

## El mapa

`cmd.c` (tabla) → `cmd_*_exec` arma `struct spawn_context` (`tmux.h:2500`) → **`spawn_pane`**
(`spawn.c:243`) → `fdforkpty` (`spawn.c:478`) → `window_pane_set_event` (`spawn.c:590` →
`window.c:1673`) → `bufferevent` sobre `wp->fd`.

**Un pane es un fd + un `bufferevent`, no un PTY.** Por eso un `socketpair` alcanza para
todo el I/O.

## Las tres trampas

1. **`window_pane_send_resize`** (`window.c:597`) usa `ioctl(TIOCSWINSZ)`: sobre un socket
   falla sin ruido. Es el único punto del I/O que asume PTY.
2. **`PANE_STATUSREADY`**: sin él, `server_destroy_pane` retorna en `server-fn.c:382`. Un pane
   sin proceso hijo tiene que recibir `wp->status` a mano.
3. **`PLATFORM` se calcula al final de `configure.ac`** (~1011-1118), después de las
   opciones `--enable-*`. La guarda de Linux tiene que mirar `$host_os`, como
   `--enable-static` (`configure.ac:84-97`).

## La guarda "solo Linux"

Dos capas: `--enable-ssh` opt-in que aborta en no-Linux (patrón `--enable-systemd` /
`--enable-cgroups`, `configure.ac:501-541`) **y** `#ifdef ENABLE_SSH_PANE` en todo el código
compartido. El código nuevo va en la raíz (`cmd-ssh-pane.c`, `ssh-pane.c`), como sixel
(`Makefile.am:252`), **no** en `compat/`.

## Invariantes

Sin el flag, `spawn.c`/`window.c`/`cmd.c` preprocesados son idénticos a la base; los comandos
existentes no cambian (`list-commands` idéntico); `tmux-protocol.h` sin diff; el build de
macOS (`regress.yml`, `macos-26`) no cambia.

## Descartado

| Se descartó | Por qué |
|---|---|
| Flag `-S` en `split-window` | Cambia un comando existente |
| `compat/ssh-pane.c` | `compat/` tapa agujeros de SO; esto es una feature |
| Auth por contraseña | No hay TTY antes de que exista el pane |
| Aceptar hosts desconocidos | MITM; `known_hosts` es solo lectura |
| OpenBSD | `pledge` del server (`server.c:207`) sin `inet`/`dns` |

## Sin medir

La línea de base (`make`, `regress/*.sh`, 172 scripts) **no se corrió**: el entorno no tenía
`libevent`, `autoconf` ni `libssh`. `getaddrinfo` bloqueante dentro de `ssh_connect` es
conocimiento de la API de `libssh`, **no verificado en el código de `libssh`**.

## Sin explorar

`input.c` (solo se asumió que consume un `bufferevent` genérico), el layout flotante
(`layout_get_floating_cell`), control mode (`control_write_output` en
`window_pane_read_callback`) y `window_pane_key`.
