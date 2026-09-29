# Notas de exploración — pane con SSH nativo en `tmux`

> Salida del paso **Descubrir**. Exploración de **solo lectura** sobre una copia de
> [`tmux/tmux`](https://github.com/tmux/tmux); no se editó ni se compiló nada.
>
> Explorado sobre el commit **`5e4b8cc`** (rama `master`, clonada con `--depth 1` el
> 2026-09-29; `configure.ac` declara `AC_INIT([tmux], next-3.9)`). Son ~101.000 líneas de
> C en los `*.c` de la raíz. Los números de línea se corren entre versiones; los nombres de
> archivo y de función son lo estable.
>
> **Qué se verificó y qué no.** Todo `archivo:línea` de abajo se leyó en el clone. **No se
> pudo compilar `tmux` ni correr `make test`/`regress/`**: el entorno de exploración (WSL)
> no tiene `libevent`, `autoconf` ni `libssh`. La línea de base de regresión de la spec
> está definida, pero **no se midió**; eso está marcado donde corresponde.

## Qué se quiere lograr

Un comando nuevo que abre un pane cuyo contenido es una sesión SSH remota, hablada por una
biblioteca enlazada dentro del proceso `tmux` (`libssh`), **sin `fork`/`exec` del binario
`ssh`**. Solo Linux.

```bash
tmux ssh-pane -i ~/.ssh/id_ed25519 usuario@host     # split del pane actual, sesión remota adentro
```

## El terreno: cómo nace hoy un pane

Varios comandos crean o recrean un pane, y **todos terminan en la misma función**:

```
tabla de comandos (cmd.c)
   │  new-window / split-window / new-pane / respawn-pane / new-session
   ▼
cmd_*_exec()                      arma un `struct spawn_context`
   │
   ▼
spawn_window() ──► spawn_pane()   spawn.c
                        │
                        ├─ arma el entorno del hijo             (spawn.c:407-445)
                        ├─ bloquea señales                      (spawn.c:454-456)
                        ├─ fdforkpty(ptm_fd, &wp->fd, …)        (spawn.c:478)   ◄── el único fork
                        ├─ [hijo] tcsetattr, closefrom, exec*   (spawn.c:504-575)
                        └─ [padre] complete: window_pane_set_event(wp)   (spawn.c:577-590)
                                            │
                                            ▼
                             bufferevent_new(wp->fd, read_cb, NULL, error_cb)  (window.c:1677)
```

### 1 · La tabla de comandos

**`cmd.c`** declara cada comando con `extern const struct cmd_entry cmd_X_entry;` y lo
lista en el arreglo `cmd_table`. Para los que nos importan:

| Comando | `extern` | Entrada en la tabla | Definición |
|---|---|---|---|
| `new-pane` | `cmd.c:74` | `cmd.c:168` | `cmd-split-window.c:39` |
| `new-window` | `cmd.c:76` | `cmd.c:170` | `cmd-new-window.c:37` |
| `respawn-pane` | `cmd.c:88` | `cmd.c:182` | `cmd-respawn-pane.c:33` |
| `split-window` | (idem) | (idem) | `cmd-split-window.c:58` |

Un `struct cmd_entry` tiene `.name`, `.alias`, `.args` (cadena estilo `getopt`, p. ej.
`"abc:de:EF:kn:PSt:"` en `cmd-new-window.c:40`), `.usage`, `.target` y `.exec`. **Agregar un
comando es: un `.c` nuevo con su `cmd_entry`, un `extern` y una fila en `cmd_table`.** El
resto de los archivos de comando no se toca.

### 2 · El contrato entre comando y spawn

**`tmux.h:2500`** define `struct spawn_context`: `item`, `s`, `wl`, `tc`, `wp0`, `lc`,
`name`, `argv/argc`, `environ`, `idx`, `cwd` y `flags`. Los flags son `SPAWN_KILL 0x1` …
`SPAWN_FLOATOVERZOOM 0x1000` (`tmux.h:2519-2531`); **el próximo bit libre es `0x2000`**.

`cmd_split_window_exec` (`cmd-split-window.c:76`) es el modelo a imitar: resuelve el target,
calcula el hueco de layout (`layout_get_tiled_cell` o `layout_get_floating_cell`), llena
`sc` (`cmd-split-window.c:~190-206`) y llama `spawn_pane(&sc, &cause)` en la línea **208**.
Si devuelve `NULL` reporta `"create pane failed: %s"`.

### 3 · `spawn_pane`: dónde engancha

**`spawn.c:243`**. El cuerpo, en orden:

1. Crea el `window_pane` y el hueco de layout, o reutiliza `sc->wp0` si es `SPAWN_RESPAWN`.
2. Arma el entorno del hijo (`spawn.c:407-445`: `TMUX_PANE`, `PATH`, `SHELL`).
3. Calcula `struct winsize` desde `screen_size_x/y` (`spawn.c:447-452`).
4. **Bloquea todas las señales** (`spawn.c:454-456`) hasta que termine el fork.
5. Si `sc->flags & SPAWN_EMPTY` (`spawn.c:459`) **no forkea**: marca `PANE_EMPTY` y salta a
   `complete`. **Es el precedente de un pane sin proceso hijo**, y el punto más limpio para
   ramificar.
6. **`new_wp->pid = fdforkpty(ptm_fd, &new_wp->fd, new_wp->tty, NULL, &ws);`**
   (`spawn.c:478`). Es el único lugar del camino donde se crea un PTY y un proceso. Si falla,
   `spawn_pane` deshace el pane (`spawn.c:479-490`) y devuelve `NULL`.
7. En el hijo (`pid == 0`): `tcsetattr`, `proc_clear_signals`, `closefrom(STDERR_FILENO + 1)`
   (`spawn.c:541`) y `execvp` / `execl "$SHELL -c"` / login shell (`spawn.c:552-574`).
8. En el padre, `complete:` (`spawn.c:577`): registra en utmp si `HAVE_UTEMPTER`
   (`spawn.c:578`) y llama **`window_pane_set_event(new_wp)`** (`spawn.c:590`).

También hay **otro llamador interno de `spawn_pane` en `spawn.c:772`**, y
`spawn_window` (`spawn.c:114`) la llama en `spawn.c:209`. Cualquier cambio en el contrato de
`spawn_pane` los afecta a todos.

### 4 · Cómo se conecta un pane a un fd: `window.c`

Esto es lo más importante para el diseño: **el modelo de pane de `tmux` es "un fd
pollable + un `bufferevent`"**, no "un PTY".

| Función | Línea | Qué hace | ¿Asume PTY? |
|---|---|---|---|
| `window_pane_set_event` | `window.c:1673` | `setblocking(fd,0)` + `bufferevent_new(wp->fd, read_cb, NULL, error_cb, wp)` + `input_init` | **No** |
| `window_pane_read_callback` | `window.c:1632` | Alimenta `input_parse_pane(wp)` | **No** |
| `window_pane_error_callback` | `window.c:1660` | Pone `PANE_EXITED` y destruye el pane si está listo | **No** |
| escritura de teclas | `window.c:2064` | `bufferevent_write(wp->event, buf, len)` | **No** |
| `window_pane_destroy_ready` | `window.c:495` | `ioctl(wp->fd, FIONREAD, …)`; si falla, sigue | No (tolera error) |
| **`window_pane_send_resize`** | **`window.c:597`** | **`ioctl(wp->fd, TIOCSWINSZ, &ws)`** (`window.c:612`) | **Sí** |
| `window_pane_destroy` | `window.c:1567` | `bufferevent_free` + `close(wp->fd)` | No |

**Hallazgo:** casi todo el camino de I/O funciona con cualquier fd que soporte
`read`/`write`, incluido un `socketpair`. **La excepción es `window_pane_send_resize`**: sobre un
socket, `TIOCSWINSZ` falla con `ENOTTY` y el tamaño remoto nunca se entera. Es un punto donde
hay que ramificar sí o sí.

### 5 · Cómo muere un pane

- **Proceso hijo:** `server_child_exited` (`server.c:491`) recibe el `pid` de `waitpid`
  (`server.c:474`), busca el pane con `wp->pid == pid` (`server.c:498`), guarda `wp->status`,
  levanta `PANE_STATUSREADY` y `PANE_EXITED`.
- **`server_destroy_pane`** (`server-fn.c:354`) cierra `wp->fd` y **retorna sin hacer nada si
  `PANE_STATUSREADY` no está** (`server-fn.c:382`); recién después aplica `remain-on-exit`
  leyendo `WIFEXITED(wp->status)`.
- **EOF del fd:** `window_pane_error_callback` (`window.c:1660`) marca `PANE_EXITED` sin tocar
  `PANE_STATUSREADY`.

**Hallazgo:** un pane sin proceso hijo **nunca recibe `PANE_STATUSREADY`** salvo que alguien
lo levante a mano. Un pane SSH que muere por EOF quedaría colgado en `server_destroy_pane`
si no se le fija `status` y `PANE_STATUSREADY`. `wp->pid = -1` nunca coincide con un `pid`
real de `waitpid`, así que el pane SSH no es reclamado por error por `server_child_exited`.

### 6 · Formatos que asumen proceso y TTY

- `format_cb_pane_pid` (`format.c:2580`) imprime `wp->pid` si `wp->fd != -1`.
- `format_cb_pane_tty` (`format.c:2697`) devuelve `wp->tty`.
- `format_cb_pane_dead_status` (`format.c:2288`) usa `WIFEXITED(wp->status)`.
- `cmd-find.c:89` compara `wp->tty` con `c->ttyname` para resolver "el pane de este cliente".

Un pane SSH tendría `pid == -1` y `tty` vacío. **`#{pane_pid}` mostraría `-1`** y
`#{pane_tty}` cadena vacía. Es una limitación conocida, no un bug a arreglar en la v1.

## La capa de portabilidad: cómo `tmux` aísla lo específico de plataforma

Hay **cuatro mecanismos**, de menor a mayor intrusión. Entenderlos es lo que define dónde
puede vivir la guarda "solo Linux".

### A · `configure.ac` decide la plataforma

`configure.ac:1011-1118` es un `case "$host_os"` que fija `PLATFORM` (`aix`, `darwin`,
`linux` en la **línea 1064**, `freebsd`, `netbsd`, `openbsd`, `sunos`, `hpux`, `cygwin`,
`haiku`, `unknown`) y lo exporta con `AC_SUBST(PLATFORM)`. De ahí salen los
`AM_CONDITIONAL(IS_LINUX, …)` (`configure.ac:1122`) y el archivo `osdep-@PLATFORM@.c` de
`Makefile.am`. Existe **`osdep-linux.c`** y once más para los otros SO (`aix`, `cygwin`, `darwin`,
`dragonfly`, `freebsd`, `haiku`, `hpux`, `netbsd`, `openbsd`, `sunos`, `unknown`).

> ⚠ **Orden.** `PLATFORM` se calcula **al final** de `configure.ac` (línea ~1011+), y las
> opciones `--enable-*` se declaran mucho antes (líneas ~84-540). Una guarda que quiera
> rechazar `--enable-ssh` en no-Linux **no puede leer `$PLATFORM`** donde declara la opción.
> El precedente que sí funciona es `--enable-static` (`configure.ac:84-97`), que mira
> `$host_os` directamente: `case "$host_os" in *darwin*) AC_MSG_ERROR(…)`.

### B · Dependencias opcionales: `--enable-X` + `AC_DEFINE` + `AM_CONDITIONAL`

Tres precedentes, todos con la misma forma:

| Feature | `configure.ac` | `Makefile.am` | Código |
|---|---|---|---|
| **systemd** | `501-527` (`PKG_CHECK_MODULES(SYSTEMD, libsystemd, …)`, `AC_DEFINE(HAVE_SYSTEMD)`) | `242-244`: `if HAVE_SYSTEMD` → `nodist_tmux_SOURCES += compat/systemd.c` | `compat.h:444-448`, uso en `spawn.c:504`, `server.c:223` |
| **utempter** | `417-439` | (solo `LIBS`) | `tmux.h:31-32`, `spawn.c:578`, `window.c:1581`, `server-fn.c:367` |
| **sixel** | `544-551` (`ENABLE_SIXEL`) | `Makefile.am:252`, `if ENABLE_SIXEL` → `dist_tmux_SOURCES += image.c image-sixel.c` | archivos de raíz con `#ifdef ENABLE_SIXEL` |

**systemd es el mejor precedente**: Linux-only en la práctica, opt-in (`--enable-systemd`),
dependencia externa vía `pkg-config`, se engancha en `spawn_pane` con `#if defined(...)`, y
`--enable-cgroups` sin systemd **aborta el configure** (`configure.ac:528-541`). Por default,
nada de esto entra en el build.

### C · `compat/`: reemplazos, no features

`compat/` (~45 archivos) implementa **funciones que faltan en algún SO** (`strlcpy.c`,
`closefrom.c`, `imsg.c`, `getpeereid.c`…) y se agregan con `AC_REPLACE_FUNCS`
(`configure.ac:183-...`) / `AC_LIBOBJ`. Sus prototipos viven en **`compat.h`**. Para el
camino que nos importa:

- `compat/fdforkpty.c` — envuelve `forkpty` (`getptmfd()` devuelve `INT_MAX`) y
  `compat/forkpty-{aix,haiku,hpux,sunos}.c`. Se elige con `AC_SEARCH_LIBS` en
  `configure.ac:828-839` y `AM_CONDITIONAL(NEED_FORKPTY, …)`.
- `ptm_fd` es un global de `tmux.c:43`, inicializado en `tmux.c:538` con `getptmfd()`.

**Conclusión de la capa `compat/`:** existe para *tapar agujeros de portabilidad*, no para
alojar features de un solo SO. `compat/systemd.c` es la excepción y es un helper chico
que incluye `tmux.h`.

### D · Guardas de preprocesador en el código común

`#ifdef HAVE_UTEMPTER`, `#if defined(HAVE_SYSTEMD) && defined(ENABLE_CGROUPS)`,
`#ifdef ENABLE_SIXEL`, `#ifdef __sun` (`window.c:613`). **Es la forma habitual de meter algo
opcional en un archivo compartido**, y la que hay que usar en `spawn.c`, `window.c` y `cmd.c`.

### E · Historia de compat/build que importa

- **`SYNCING.md`**: el repo portable se mantiene junto con un repo cutover de **OpenBSD**
  (`usr.bin/tmux/`), y los cambios de OpenBSD se **mergean** al portable. `spawn.c`, `window.c`
  y `cmd.c` son código *compartido*. **Todo cambio en ellos es un futuro conflicto de merge**;
  por eso el diff en archivos compartidos tiene que ser mínimo y quedar entero dentro de
  `#ifdef`.
- **`server.c:207`** hace `pledge("stdio rpath wpath cpath fattr unix getpw recvfd proc exec
  tty ps")` en OpenBSD. **No incluye `inet` ni `dns`**: un cliente SSH dentro del server
  *no puede* conectarse en OpenBSD sin ampliar el pledge. Es una razón técnica (no solo de
  alcance) para excluir OpenBSD.
- **CI:** `.github/workflows/regress.yml` (líneas ~25-34) corre `ubuntu-24.04` x64 y arm64 y
  **`macos-26` arm64**, todos con `--enable-utf8proc --enable-asan`. **macOS es un build
  gateado por CI**: si el feature no se compila afuera, ese job se rompe.

## Decisiones de diseño (y por qué)

| Decisión | Elegido | Descartado | Fundamento (con evidencia) |
|---|---|---|---|
| ¿Comando nuevo o flag de uno existente? | **Comando nuevo `ssh-pane`** | Flag `-S` en `split-window` / `new-window` | Agregar un flag cambiaría `.args` y `.usage` de un comando existente (`cmd-split-window.c:61`) y viola el invariante "los comandos existentes no cambian" |
| ¿Dónde engancha en spawn? | Ramificar en **`spawn_pane`** con un flag nuevo `SPAWN_SSH` (`0x2000`), junto a la rama de `SPAWN_EMPTY` (`spawn.c:459`) | Función paralela que duplique la creación de pane | `spawn_pane` ya arma layout, entorno, `window_pane_set_event` y los hooks `pane-created`; duplicarlo diverge del upstream |
| ¿`libssh` u OpenSSH? | **`libssh`** (≥ 0.9, vía `pkg-config`) | Invocar `ssh` | La consigna prohíbe invocar el binario. OpenSSH no expone una biblioteca cliente estable. `libssh` es LGPL-2.1, se enlaza dinámico y es opt-in: no toca la licencia ISC del binario por default |
| ¿Cómo entra al event loop? | **`socketpair(AF_UNIX)`**: un extremo es `wp->fd`, el otro lo maneja el *bridge* con `libssh` en modo no bloqueante y `event_new` sobre `ssh_get_fd()` | `wp->fd` = socket TCP crudo; hilo aparte | Deja `window_pane_set_event`, `input_parse_pane` y las escrituras (**§4**) **sin cambios**; el pane sigue siendo "un fd + un `bufferevent`" |
| ¿Auth? | **Agent** (`SSH_AUTH_SOCK`), luego **clave** con `-i` | Contraseña / interactivo por teclado | Un prompt de contraseña necesita I/O de terminal antes de que el pane exista y filtra secretos por el `input_parse_pane` |
| ¿Qué guarda deja afuera a no-Linux? | **Dos capas**: (1) `configure` con `--enable-ssh` opt-in que aborta en no-Linux; (2) `#ifdef ENABLE_SSH_PANE` en todo el código | Solo `#ifdef __linux__` | Es el patrón de `--enable-systemd`/`--enable-cgroups`; y como es opt-in, un build sin flag no puede fallar |
| ¿Dónde vive el código nuevo? | **Raíz**: `cmd-ssh-pane.c` y `ssh-pane.c` (patrón sixel) | `compat/ssh-pane.c` | `compat/` es para tapar agujeros de SO; esto es una *feature* con un comando y usa `struct window_pane` |

## Riesgos

| Riesgo | Por qué |
|---|---|
| **Pane que nunca se destruye** | Sin `PANE_STATUSREADY`, `server_destroy_pane` retorna en `server-fn.c:382`. Hay que fijar `wp->status` y el flag al cerrarse el canal |
| **Resize inaudible** | `TIOCSWINSZ` sobre un socket falla en silencio (`window.c:612`); el `vim` remoto quedaría en 80×24 |
| **Bloqueo del event loop** | `getaddrinfo` dentro de `ssh_connect` **es bloqueante** aun con `ssh_set_blocking(s, 0)`. Un DNS lento congela *todos* los panes del server |
| **Fuga de fds/sesiones** | `window_pane_destroy` (`window.c:1567`) cierra `wp->fd` pero no sabe nada de una `ssh_session`; hay que liberar el bridge ahí |
| **`respawn-pane` sobre un pane SSH** | `spawn_pane` con `SPAWN_RESPAWN` reutiliza `wp0`; forkearía una shell local encima del bridge vivo |
| **Confianza en el host** | Aceptar claves desconocidas sin preguntar es un agujero MITM; no hay TTY para preguntar antes de que exista el pane |
| **Conflictos de merge con OpenBSD** | `spawn.c`, `window.c`, `cmd.c` se sincronizan desde OpenBSD (`SYNCING.md`) |
| **Romper macOS/BSD** | Es un build gateado por CI (`regress.yml`); un `#include <libssh/libssh.h>` fuera de `#ifdef` lo rompe |
| **`pane_pid`/`pane_tty` engañosos** | Ver §6 |

## Lo que NO hace falta entender

El parser de comandos (`cmd-parse.y`), el render (`tty*.c`, `screen*.c`, `grid*.c`), el
layout más allá de `layout_get_tiled_cell`, el modo copia (`window-copy.c`), el protocolo
cliente/servidor (`tmux-protocol.h`), y el 95% de `window.c`. Se lee `input.c` solo para
confirmar que consume un `bufferevent` cualquiera.

## Afirmaciones para verificar a mano

Elegí dos. Si alguna falla, las notas no sirven:

```bash
git clone --depth 1 https://github.com/tmux/tmux && cd tmux
grep -n "fdforkpty(ptm_fd" spawn.c                     # ¿línea 478?
grep -n "TIOCSWINSZ" window.c                          # ¿línea 612, dentro de window_pane_send_resize?
grep -n "PANE_STATUSREADY" server-fn.c                 # ¿el return temprano de server_destroy_pane?
grep -n "pledge" server.c                              # ¿sin "inet" ni "dns"?
grep -n "enable-static" -A8 configure.ac               # ¿usa $host_os y no $PLATFORM?
```
