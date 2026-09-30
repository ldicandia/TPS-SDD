# Notas de exploración — pane con SSH nativo en `tmux`

> Salida del paso **Descubrir**. Exploración de **solo lectura** sobre una copia de
> [`tmux/tmux`](https://github.com/tmux/tmux); no se modificó su código ni se compiló.
>
> Commit base **`5e4b8cc39e635f8e2c4d9c95c205e987a618d50b`**, registrado en la entrega
> del 2026-09-29 y vuelto a verificar el 2026-09-30 en un checkout separado. No se usa el
> `master` actual como base. `configure.ac:3` declara `AC_INIT([tmux], next-3.9)`.
> Se contaron **101.303 líneas** en los 153 `*.c` de la raíz. Las referencias de abajo
> corresponden exclusivamente a ese commit; archivo y función identifican cada ancla.
>
> **Qué se verificó y qué no.** Se leyeron los archivos y funciones citados, sus llamadas,
> las reglas de build y el workflow; se comprobaron rutas, anclas y conteos. El checkout
> de tmux quedó sin cambios. **No se ejecutaron `autogen.sh`, `configure`, `make`,
> `regress/`, conexiones SSH ni pruebas de rendimiento.** La línea de base sigue **sin medir**.
> Las APIs y licencia externas se verificaron luego, por lectura de libssh 0.9.0
> (apartado «Validación externa»). Esa evidencia se distingue de los hallazgos de tmux;
> no se compiló ni se ejecutó la biblioteca.

## Qué se quiere lograr

Un comando nuevo que abre un pane cuyo contenido es una sesión SSH remota, hablada por una
biblioteca enlazada dentro del proceso `tmux` (`libssh`), **sin `fork`/`exec` del binario
`ssh`**. Solo Linux.

```bash
tmux ssh-pane -i ~/.ssh/id_ed25519 -u usuario host     # split del pane actual, sesión remota adentro
```

## El terreno: cómo nace hoy un pane

Los comandos enumerados abajo crean o recrean panes mediante `spawn_pane`:

```
tabla de comandos (cmd.c:123)
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
                        ├─ [hijo] tcsetattr, closefrom, exec*   (spawn.c:524-575)
                        └─ [padre] complete: window_pane_set_event(wp)   (spawn.c:577-590)
                                            │
                                            ▼
                             bufferevent sobre wp->fd  (window.c:1677)
```

### 1 · La tabla de comandos

**`cmd.c`** declara cada comando (por ejemplo, `extern const struct cmd_entry cmd_new_pane_entry;`) y lo
lista en el arreglo `cmd_table`. Para los que nos importan:

| Comando | `extern` | Entrada en la tabla | Definición |
|---|---|---|---|
| `new-pane` | `cmd.c:74` | `cmd.c:168` | `cmd-split-window.c:39` |
| `new-window` | `cmd.c:76` | `cmd.c:170` | `cmd-new-window.c:37` |
| `respawn-pane` | `cmd.c:88` | `cmd.c:182` | `cmd-respawn-pane.c:33` |
| `split-window` | `cmd.c:112` | `cmd.c:206` | `cmd-split-window.c:58` |

Un `struct cmd_entry` tiene `.name`, `.alias`, `.args` (cadena estilo `getopt`, p. ej.
`"abc:de:EF:kn:PSt:"` en `cmd-new-window.c:41`), `.usage`, `.target` y `.exec`. **Agregar un
comando es: un `.c` nuevo con su `cmd_entry`, un `extern` y una fila en `cmd_table`.** El
resto de los archivos de comando no se toca.

### 2 · El contrato entre comando y spawn

**`tmux.h:2500`** define `struct spawn_context`: `item`, `s`, `wl`, `tc`, `wp0`, `lc`,
`name`, `argv/argc`, `environ`, `idx`, `cwd` y `flags`. Los flags son `SPAWN_KILL 0x1` …
`SPAWN_FLOATOVERZOOM 0x1000` (`tmux.h:2519-2531`); **el próximo bit libre es `0x2000`**.

`cmd_split_window_exec` (`cmd-split-window.c:76`) es el modelo a imitar: resuelve el target,
calcula el hueco de layout (`layout_get_tiled_cell` o `layout_get_floating_cell`), llena
`sc` (`cmd-split-window.c:188-206`) y llama `spawn_pane(&sc, &cause)` en `cmd-split-window.c:208`.
Si devuelve `NULL` reporta `"create pane failed: %s"`.

Los otros caminos citados también se comprobaron: `cmd_new_window_exec`
(`cmd-new-window.c:53`) llama `spawn_window` en `cmd-new-window.c:161`;
`cmd_new_session_exec` (`cmd-new-session.c:68`) lo hace en `cmd-new-session.c:305`;
`cmd_respawn_pane_exec` (`cmd-respawn-pane.c:48`) llama directamente a `spawn_pane` en
`cmd-respawn-pane.c:83`. `new-pane` y `split-window` comparten `cmd_split_window_exec`.

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
7. En el hijo (`pid == 0`): `tcsetattr`, `proc_clear_signals` (definida en `proc.c:279`), `closefrom(STDERR_FILENO + 1)`
   (`spawn.c:541`) y `execvp` / `execl "$SHELL -c"` / login shell (`spawn.c:552-574`).
8. En el padre, `complete:` (`spawn.c:577`): si `HAVE_UTEMPTER` y no es `PANE_EMPTY`,
   llama `utempter_add_record` (`spawn.c:581`), restaura las señales (`spawn.c:589`), llama
   **`window_pane_set_event(new_wp)`** (`spawn.c:590`) y dispara el hook mediante
   `spawn_fire_pane_created` (`spawn.c:592`). Reutilizar `complete` no evita el registro
   utempter: un socket SSH necesita excluirse de esa operación de PTY.

También hay **otro llamador interno de `spawn_pane` en `spawn.c:772`**;
`spawn_window` (`spawn.c:114`) la llama en `spawn.c:209`, y `cmd_display_popup_exec`
(`cmd-display-menu.c:389`) lo hace en `cmd-display-menu.c:499`. Junto con split y respawn,
son todos los sitios de llamada encontrados al buscar `spawn_pane(` en los `.c` de la raíz.
Cualquier cambio en su contrato debe preservar esos caminos sin `SPAWN_SSH`.

### 4 · Cómo se conecta un pane a un fd: `window.c`

La interfaz de lectura y escritura del pane es **`wp->fd` + un `bufferevent`**.
Eso permite proponer un `socketpair` para el transporte, pero **no elimina las
suposiciones de PTY o de proceso hijo** del resto del ciclo de vida.

| Función | Línea | Qué hace | ¿Asume PTY? |
|---|---|---|---|
| `window_pane_set_event` | `window.c:1673` | Pone `wp->fd` no bloqueante, crea el `bufferevent` con los callbacks de lectura/error de abajo y llama `input_init` | **No** |
| `window_pane_read_callback` | `window.c:1632` | Alimenta `input_parse_pane(wp)` | **No** |
| `window_pane_error_callback` | `window.c:1660` | Pone `PANE_EXITED` y destruye el pane si está listo | **No** |
| `window_pane_key` → `input_key_pane` | `window.c:2071`, `input-keys.c:398` | Traduce teclas; `input_key_write` (`input-keys.c:414`) escribe con `bufferevent_write` en `input-keys.c:418` | **No** |
| `window_pane_paste` | `window.c:2052` | El pegado escribe con `bufferevent_write` en `window.c:2064`; es un camino distinto del teclado | **No** |
| `window_pane_destroy_ready` | `window.c:495` | `ioctl(wp->fd, FIONREAD, …)`; si falla, sigue | No (tolera error) |
| **`window_pane_send_resize`** | **`window.c:597`** | **`ioctl(wp->fd, TIOCSWINSZ, &ws)`** (`window.c:612`); si falla, llama `fatal` (`window.c:622`) | **Sí** |
| `window_pane_destroy` | `window.c:1567` | `bufferevent_free` + `close(wp->fd)`; además `utempter_remove_record` si `HAVE_UTEMPTER` (`window.c:1581`) | Sí, si hay utempter |

**Hallazgo:** sobre un socket en Linux, el resize no se puede dejar pasar al ioctl de PTY:
su error lleva a `fatal("ioctl failed")`, que termina el proceso con `exit(1)`
(`log.c:140-152`). La inferencia es estática; no se provocó ese fallo en ejecución.

También se leyó `input_init` (`input.c:875`), que guarda el `bufferevent`, e
`input_parse_pane` (`input.c:1028`), que consume datos mediante `window_pane_get_new_data`
(`window.c:2562`) y llama `input_parse_buffer` (`input.c:1042`). Ninguna de esas funciones
crea un PTY. Esto respalda reutilizar el parser, no demuestra por sí solo el funcionamiento
de un bridge SSH. Se ubicó además la llamada a `control_write_output` en `window.c:1653`
y su definición en `control.c:619`; no se auditó todo control mode.

### 5 · Cómo muere un pane

- **Proceso hijo:** `server_child_exited` (`server.c:491`) recibe el `pid` de `waitpid`
  (`server.c:474`), busca el pane con `wp->pid == pid` (`server.c:498`), guarda `wp->status`,
  levanta `PANE_STATUSREADY` y `PANE_EXITED`.
- **`server_destroy_pane`** (`server-fn.c:354`) libera el evento y cierra `wp->fd`
  (`server-fn.c:365-374`) y **retorna antes de eliminar el pane si `PANE_STATUSREADY` no está**
  (`server-fn.c:382`); recién después aplica `remain-on-exit`
  leyendo `WIFEXITED(wp->status)`.
- **EOF del fd:** `window_pane_error_callback` (`window.c:1660`) marca `PANE_EXITED` sin tocar
  `PANE_STATUSREADY`.

**Hallazgo:** un pane sin proceso hijo **nunca recibe `PANE_STATUSREADY`** salvo que alguien
lo levante explícitamente. Un pane SSH que muere por EOF quedaría sin eliminar si no se
le fija `status` y `PANE_STATUSREADY`. `wp->pid = -1` es un valor **propuesto**, no el default:
`window_pane_create` (`window.c:1435`) usa `xcalloc` en `window.c:1440`, así que inicialmente
`pid` vale 0. El valor propuesto no coincide con un PID positivo devuelto por `waitpid`.

Hay otra diferencia: con `remain-on-exit on`, `server_destroy_pane` retorna en
`server-fn.c:420` conservando el pane y sin llegar a `window_remove_pane`
(`server-fn.c:429`). Liberar el bridge solo en `window_pane_destroy` no cubre ese fin de
sesión. El cierre por `server_destroy_pane` también llama `utempter_remove_record`
(`server-fn.c:367`). Por esos dos hallazgos, la spec incorpora `server-fn.c` a la
superficie y excluye SSH de las tres operaciones utempter.

### 6 · Formatos que asumen proceso y TTY

- `format_cb_pane_pid` (`format.c:2580`) imprime `wp->pid` si `wp->fd != -1`.
- `format_cb_pane_tty` (`format.c:2697`) devuelve `wp->tty`.
- `format_cb_pane_dead` (`format.c:2257`) exige fd cerrado y `PANE_STATUSREADY`.
- `format_cb_pane_dead_status` (`format.c:2288`) usa `WIFEXITED` y `WEXITSTATUS`
  (`format.c:2293-2294`): espera un estado codificado como el de `waitpid`, no el código
  remoto crudo. La representación propuesta debe respetar ese contrato.
- `cmd-find.c:89` compara `wp->tty` con `c->ttyname` para resolver "el pane de este cliente".

Si el bridge asigna `pid == -1` y conserva `tty` vacío, **`#{pane_pid}` mostraría `-1`
mientras el fd esté abierto** y `#{pane_tty}` cadena vacía. Con el fd cerrado, `pane_pid`
no devuelve ese valor. Son consecuencias del diseño propuesto, no comportamiento SSH ya
existente en tmux.

## La capa de portabilidad: cómo `tmux` aísla lo específico de plataforma

Hay **cuatro mecanismos**, de menor a mayor intrusión. Entenderlos es lo que define dónde
puede vivir la guarda "solo Linux".

### A · `configure.ac` decide la plataforma

`configure.ac:1008-1118` es un `case "$host_os"` que fija `PLATFORM` (`aix`, `darwin`,
`linux` en `configure.ac:1064`, `freebsd`, `netbsd`, `openbsd`, `sunos`, `hpux`, `cygwin`,
`haiku`, `unknown`; también `dragonfly`) y lo exporta con `AC_SUBST(PLATFORM)`. De ahí salen los
`AM_CONDITIONAL(IS_LINUX, …)` (`configure.ac:1122`) y el archivo `osdep-@PLATFORM@.c` de
`Makefile.am`. Existe **`osdep-linux.c`** y once más para los otros SO (`aix`, `cygwin`, `darwin`,
`dragonfly`, `freebsd`, `haiku`, `hpux`, `netbsd`, `openbsd`, `sunos`, `unknown`).

> **Orden.** `PLATFORM` se calcula tarde (`configure.ac:1008`), y las opciones opcionales
> citadas se declaran antes. `$host_os` está disponible desde `AC_CANONICAL_HOST`
> (`configure.ac:10`). Una guarda que quiera
> rechazar `--enable-ssh` en no-Linux **no puede leer `$PLATFORM`** donde declara la opción.
> El precedente que sí funciona es `--enable-static` (`configure.ac:84-97`), que mira
> `$host_os` directamente: `case "$host_os" in *darwin*) AC_MSG_ERROR(…)`.

### B · Dependencias opcionales: `--enable-X` + `AC_DEFINE` + `AM_CONDITIONAL`

Tres precedentes de features opcionales; no usan exactamente el mismo mecanismo:

| Feature | `configure.ac` | `Makefile.am` | Código |
|---|---|---|---|
| **systemd** | `configure.ac:503-527`: opción, dependencia, `AC_DEFINE(HAVE_SYSTEMD)` y `AM_CONDITIONAL` | `Makefile.am:243-244`: `if HAVE_SYSTEMD` → `compat/systemd.c` | `compat.h:444-448`, uso en `spawn.c:504`, `server.c:223` |
| **utempter** | `configure.ac:419-439`: opción, `AC_SEARCH_LIBS` y `AC_DEFINE(HAVE_UTEMPTER)` | Sin lista condicional de fuentes propias; la búsqueda agrega la biblioteca | `tmux.h:31-32`, `spawn.c:578`, `window.c:1581`, `server-fn.c:367` |
| **sixel** | `configure.ac:545-552`: opción, `AC_DEFINE(ENABLE_SIXEL)` y `AM_CONDITIONAL` | `Makefile.am:253-254`: incluye `image.c` e `image-sixel.c` | Declaraciones comunes protegidas, por ejemplo `tmux.h:79`; las dos fuentes se excluyen mediante `Makefile.am` |

**systemd es un precedente de dependencia opcional**: opt-in (`--enable-systemd`),
dependencia externa vía `pkg-config`, se engancha en `spawn_pane` con `#if defined(...)`, y
`--enable-cgroups` sin systemd **aborta el configure** (`configure.ac:528-542`). Ese bloque
no comprueba `$host_os`: la exclusión Linux de SSH necesita su propia guarda. También
propaga CFLAGS de la dependencia a `AM_CPPFLAGS` y las bibliotecas a `LIBS`
(`configure.ac:512-514`); no alcanza con detectar el paquete. Sin activar systemd,
sus fuentes y su dependencia no se agregan.

**Compatibilidad del event loop.** El build admite la búsqueda de `event-1.4`
(`configure.ac:281-300`), y `compat.h:30-40` contempla headers `event2` o `event.h`.
El código observado usa `event_set` (`server.c:424`). La propuesta inicial `event_new`
requiere libevent 2; se reemplaza por `event_set`/`event_add`/`event_del` para preservar
la compatibilidad de esta base. La fuente externa de esa distinción se registra abajo.

### C · `compat/`: reemplazos, no features

`compat/` (46 archivos) implementa **funciones que faltan en algún SO** (`compat/strlcpy.c`,
`compat/closefrom.c`, `compat/imsg.c`, `compat/getpeereid.c`) y se agregan con
`AC_REPLACE_FUNCS` (`configure.ac:183-205`) o `AC_LIBOBJ` (`configure.ac:775-776` para imsg).
Sus prototipos viven en **`compat.h`**. Para el
camino que nos importa:

- `compat/fdforkpty.c` — `getptmfd` (`compat/fdforkpty.c:24`) devuelve `INT_MAX` y
  `fdforkpty` (`compat/fdforkpty.c:30`) delega en `forkpty`. Hay reemplazos
  `compat/forkpty-aix.c`, `compat/forkpty-haiku.c`, `compat/forkpty-hpux.c` y
  `compat/forkpty-sunos.c`. Se eligen con `AC_SEARCH_LIBS` en
  `configure.ac:828-839` y `AM_CONDITIONAL(NEED_FORKPTY, …)`.
- `ptm_fd` es un global de `tmux.c:43`, inicializado en `tmux.c:538` con `getptmfd()`.

**Conclusión de la capa `compat/`:** existe para *tapar agujeros de portabilidad*, no para
alojar features de un solo SO. `compat/systemd.c` es la excepción y es un helper chico
que incluye `tmux.h`; también existe `compat/utf8proc.c` como helper opcional
(`Makefile.am:248-249`). Esos precedentes no obligan a poner una feature nueva allí.

### D · Guardas de preprocesador en el código común

`#ifdef HAVE_UTEMPTER`, `#if defined(HAVE_SYSTEMD) && defined(ENABLE_CGROUPS)`,
`#ifdef ENABLE_SIXEL`, `#ifdef __sun` (`window.c:613`). **Es la forma habitual de meter algo
opcional en un archivo compartido**, y la que hay que usar en `spawn.c`, `window.c` y `cmd.c`.

### E · Historia de compat/build que importa

- **`SYNCING.md`**: el repo portable se mantiene junto con un repo cutover de **OpenBSD**
  y los cambios de OpenBSD se **mergean** al portable (`SYNCING.md:3-22` identifica
  `usr.bin/tmux/` como ruta en el repositorio externo de OpenBSD, no en este checkout).
  Cambiar código común como `spawn.c`, `window.c` y `cmd.c` **puede** generar conflictos en
  esos merges; las guardas y un diff mínimo reducen el riesgo, no lo eliminan.
- **`server.c:207`** hace `pledge("stdio rpath wpath cpath fattr unix getpw recvfd proc exec
  tty ps")` en OpenBSD. **No incluye `inet` ni `dns`**: un cliente SSH dentro del server
  *no puede* conectarse en OpenBSD sin ampliar el pledge. Es una razón técnica (no solo de
  alcance) para excluir OpenBSD.
- **CI:** `.github/workflows/regress.yml:25-37` define `ubuntu-24.04` x64 y arm64 y
  **`macos-26` arm64**, con `--enable-utf8proc --enable-asan`. El workflow se dispara
  manualmente o por cron (`.github/workflows/regress.yml:3-6`), no por cada PR; su existencia
  no prueba que los jobs hayan pasado. Conserva builds sin SSH y corre la suite desde
  `regress/` (`.github/workflows/regress.yml:79-82`).
- **macOS ya exige opciones explícitas en la base:** `configure.ac:1033-1041` comprueba
  `--enable-utf8proc`/`--disable-utf8proc`, y `configure.ac:1047-1055` hace lo mismo con
  jemalloc. Un `./configure` sin esas opciones no es una línea de base válida en macOS,
  aunque SSH esté apagado. Es lectura del build, no una compilación realizada.
- **Regresión:** se contaron 172 `regress/*.sh`. `regress/Makefile:1` descubre todos los
  `.sh` y los ejecuta con entorno limpio en `regress/Makefile:35-36`. En 155 scripts aparece
  `TEST_TMUX=$(readlink -f ../tmux)`; `regress/new-window-command.sh:8` es un ejemplo, no una
  regla universal. Los scripts SSH propuestos deberán contemplar builds sin la función.

## Decisiones de diseño (y por qué)

| Decisión | Elegido | Descartado | Fundamento (con evidencia) |
|---|---|---|---|
| ¿Comando nuevo o flag de uno existente? | **Comando nuevo `ssh-pane`** | Usar un flag de `split-window` / `new-window` para SSH | Cambiar `.args` y `.usage` de un comando existente (`cmd-split-window.c:62-67`) viola el invariante; `-S` ya existe en `split-window` para el estilo del borde, no para SSH |
| ¿Dónde engancha en spawn? | Ramificar en **`spawn_pane`** con un flag nuevo `SPAWN_SSH` (`0x2000`), junto a la rama de `SPAWN_EMPTY` (`spawn.c:459`) | Función paralela que duplique la creación de pane | `spawn_pane` ya arma layout, entorno, `window_pane_set_event` y los hooks `pane-created`; duplicarlo diverge del upstream |
| ¿`libssh` u OpenSSH? | **`libssh` ≥ 0.9**, vía `pkg-config`, enlace dinámico | Invocar `ssh` | La consigna prohíbe el binario. API mínima y LGPL-2.1-or-later verificadas en la fuente externa; dependencia opcional según `configure.ac:512-514` |
| ¿Cómo entra al event loop? | **`socketpair(AF_UNIX)`**: un extremo es `wp->fd`, el otro lo maneja el *bridge* con `libssh` en modo no bloqueante y `event_set` sobre `ssh_get_fd()` | `wp->fd` = socket TCP crudo; hilo aparte | Deja `window_pane_set_event`, `input_parse_pane` y las escrituras (**§4**) **sin cambios**; el pane sigue siendo "un fd + un `bufferevent`" |
| ¿Auth? | **Solo clave sin frase con `-i`** | Agent, contraseña y teclado interactivo | La consigna permite claves o agent. La fuente externa confirma esperas bloqueantes del agent de 0.9.0; decisión del usuario: claves, para mantener una v1 simple. No cambia la construcción del entorno en `spawn.c:408` |
| ¿Qué guarda deja afuera a no-Linux? | **Dos capas**: (1) `configure` con `--enable-ssh` opt-in que aborta en no-Linux; (2) `#ifdef ENABLE_SSH_PANE` en todo el código | Solo `#ifdef __linux__` | Reutiliza el patrón de dependencia opcional y agrega el rechazo por `host_os`. El objetivo es no introducir dependencias ni fallos por SSH en builds que no lo activan; aún debe verificarse al implementar |
| ¿Dónde vive el código nuevo? | **Raíz**: `cmd-ssh-pane.c` y `ssh-pane.c` (**propuestos, nuevos**, patrón sixel) | Crear `compat/ssh-pane.c` (**alternativa descartada; no existe**) | `compat/` es para tapar agujeros de SO; esto es una feature con un comando y usa `struct window_pane` |

## Riesgos

| Riesgo | Por qué |
|---|---|
| **Pane que nunca se destruye** | Sin `PANE_STATUSREADY`, `server_destroy_pane` retorna en `server-fn.c:382`. Hay que fijar `wp->status` y el flag al cerrarse el canal |
| **Resize que termina el server** | El error de `TIOCSWINSZ` (`window.c:612`) llama `fatal` (`window.c:622`, `log.c:140-152`); la rama SSH debe evitar el ioctl de PTY |
| **Bloqueo del event loop** | El loop del server atiende otros panes (`window.c:1632`, `server.c:424`). DNS y lectura de archivos siguen síncronos; se registran como limitaciones. Agent excluido y exit status por callback para evitar otras esperas verificadas en libssh |
| **Fuga de fds/sesiones** | `window_pane_destroy` (`window.c:1567`) no conoce el bridge propuesto; además `server_destroy_pane` conserva el pane con `remain-on-exit` (`server-fn.c:420`), sin llamar al destructor |
| **`respawn-pane` sobre un pane SSH** | `spawn.c:312-349` libera el evento/fd y reutiliza `wp0`; con `-k` continuaría al fork local. El rechazo SSH debe preceder esa mutación |
| **Registro utempter sobre un socket** | El alta (`spawn.c:581`) y las bajas (`window.c:1581`, `server-fn.c:367`) reciben el fd sin reconocer un transporte SSH; la spec excluye SSH del alta y ambas bajas |
| **Confianza en el host** | Riesgo de diseño SSH: aceptar hosts desconocidos permite suplantación. No es un mecanismo de SSH encontrado en tmux ni una prueba ejecutada |
| **Conflictos de merge con OpenBSD** | `spawn.c`, `window.c`, `cmd.c` se sincronizan desde OpenBSD (`SYNCING.md`) |
| **Romper builds sin SSH** | Las fuentes comunes se incluyen desde `Makefile.am`; CI tiene un build macOS sin SSH (`.github/workflows/regress.yml:34-37`). Un include de libssh no condicionado introduciría una dependencia nueva en ese build |
| **`pane_pid`/`pane_tty` engañosos** | Ver §6 |

## Lo que NO hace falta entender

El parser de comandos (`cmd-parse.y`), el render (`tty*.c`, `screen*.c`, `grid*.c`), el
layout más allá de sus puntos de llamada (las funciones `layout_get_tiled_cell` y
`layout_get_floating_cell` existen en `layout.c:1640` y `layout.c:1698`), el modo copia
(`window-copy.c`) ni el protocolo cliente/servidor completo (`tmux-protocol.h`). De
`input.c` se leyeron las funciones de inicialización y consumo nombradas en §4;
no se auditó el parser completo, control mode ni toda la implementación de teclas.

## Afirmaciones para verificar a mano

Comandos de reproducción para un checkout separado. Los pasos de clone/checkout preparan
la copia; el resto solo lee. Se fija el commit antes de interpretar números de línea:

```bash
git clone https://github.com/tmux/tmux tmux-exploracion
cd tmux-exploracion
git checkout --detach 5e4b8cc39e635f8e2c4d9c95c205e987a618d50b
git rev-parse HEAD
git status --short                                    # sin cambios
rg -n 'spawn_pane\(' --glob '*.c'                     # definición y los cinco sitios de llamada
rg -n -F 'fdforkpty(ptm_fd' spawn.c                    # 478
sed -n '597,623p' window.c                            # ioctl 612, fatal 622
sed -n '354,429p' server-fn.c                          # cierre antes del return 382; remain-on-exit 420
sed -n '207,209p' server.c                            # pledge sin inet/dns
sed -n '84,97p' configure.ac                          # usa host_os
sed -n '2071,2104p' window.c                          # teclado, no pegado
sed -n '398,418p' input-keys.c                        # conversión y bufferevent_write
sed -n '3,6p;25,37p' .github/workflows/regress.yml      # disparadores y plataformas, no resultados
git diff --exit-code                                 # código de la copia sin modificaciones
```

## Registro de verificación de referencias del paso 1 — 2026-09-30

Registro histórico del contenido consolidado en el commit `28cc9fd`, **antes** de
los ajustes del paso 2. Sus conteos no describen las referencias agregadas después.

| Chequeo | Resultado de esa revisión documental |
|---|---|
| Base | Checkout en el hash completo del encabezado; `git status --short` vacío y `git diff --exit-code` con salida 0 |
| Rutas (M2) | 49 archivos concretos citados existen en tmux; los 9 patrones de archivos existentes tienen coincidencias. Las rutas de documentos locales también resuelven |
| Propuestas | Dos fuentes nuevas, un patrón de scripts nuevos y una ruta alternativa descartada están identificados como tales; no se cuentan como archivos existentes |
| Funciones (M2) | Las funciones internas nombradas se localizaron en su definición; las llamadas a APIs del sistema/libevent se distinguieron de las APIs externas propuestas y del nuevo identificador de comando |
| Líneas (M3), notas + spec | 182 apariciones de citas explícitas con línea, correspondientes a 139 anclas distintas: 182 exactas, 0 desplazadas dentro de ±5 y 0 incorrectas. En rangos se leyó el bloque completo, no solo sus extremos |
| Consistencia de la capsule | 30 citas adicionales revisadas; se corrigieron las afirmaciones heredadas sobre I/O, resize, estado de salida, CI y lectura del parser |
| Límites | Sin resultados de build, regresión ni SSH. La revisión de contratos, invariantes y dependencias de los pasos siguientes sigue abierta; estos conteos no son un veredicto general de la entrega |

Se cuentan apariciones repetidas para M3 y se informa también la cantidad de anclas
distintas. Los patrones, las rutas nuevas/descartadas, los headers externos y las rutas
del repositorio externo de OpenBSD no se presentan como archivos concretos de esta copia.

## Validación externa y cierre de decisiones del paso 2 — 2026-09-30

Fuentes primarias: [archivo oficial de libssh 0.9.0](https://www.libssh.org/files/0.9/libssh-0.9.0.tar.xz),
[guía de enlace de libssh](https://api.libssh.org/stable/libssh_linking.html) y
[compatibilidad de eventos de libevent](https://libevent.org/libevent-book/Ref4_event.html#_obsolete_event_manipulation_functions).
El archivo descargado tiene SHA-256
`25303c2995e663cd169fdd902bae88106f48242d7e96311d74f812023482c7a5`.
Se extrajo en una copia temporal y solo se leyeron fuentes y headers. Las rutas de la
siguiente tabla pertenecen **a libssh 0.9.0, no a tmux**:

| Evidencia externa | Resultado y consecuencia para la spec |
|---|---|
| `include/libssh/libssh.h`, declaraciones de opciones y funciones; `include/libssh/callbacks.h`, callbacks de canal | Existen las APIs elegidas: sesión no bloqueante, fd/poll flags, importación de clave, auth por clave, known hosts, PTY/shell, lectura no bloqueante, resize, poller con timeout y callback de exit status. Comprobar declaraciones no demuestra integración ni funcionamiento |
| Cabecera de `include/libssh/libssh.h` y `COPYING` | LGPL 2.1 o posterior; se precisa LGPL-2.1-or-later y enlace dinámico. La distribución deberá cumplir sus condiciones; no se afirma que cambiar solo el nombre de licencia pruebe ese cumplimiento |
| `src/agent.c`, `atomicio`, `agent_talk`; `src/auth.c`, `ssh_userauth_agent` | El agent usa lectura/escritura síncrona y ante `EAGAIN` espera con `ssh_poll(..., -1)`. `ssh_set_blocking(session, 0)` y un fd de agent no bloqueante no eliminan esa espera. Se descarta agent para la v1, por decisión explícita del usuario, en favor de `-i` |
| `src/connect.c`, `getai` | `getaddrinfo` sigue siendo síncrono; para IP literal se usa `AI_NUMERICHOST`. Se conserva la limitación DNS y la prueba de event loop con IP literal; la lectura de archivos también queda fuera de esa garantía de latencia |
| `src/client.c`, `ssh_connect`; `src/options.c`, opción `SSH_OPTIONS_PROCESS_CONFIG` | libssh procesa configuración automáticamente si no se desactiva. La spec exige desactivar esa opción antes de conectar, para respetar la exclusión de configuración SSH/ProxyCommand y no incorporar capacidades por defecto |
| `src/pki_crypto.c`, `pki_private_key_from_base64`; `src/pki_container_openssh.c`, `pki_private_key_decrypt` | Importar con frase y callback nulos puede solicitar una frase por terminal. La spec exige importación sin interacción y fallo de autenticación para clave con frase, ilegible o inválida |
| `src/channels.c`, `ssh_channel_get_exit_status` y su advertencia | El getter puede bloquear. Se elige el callback de exit status en el loop del server, sin esa llamada |

No se exige una nueva versión de libevent: su documentación confirma que `event_new`
no existe antes de 2.0 y describe `event_set`, ya usado por tmux. La superficie se amplía
solo con `server-fn.c` para cubrir `remain-on-exit` y la baja utempter; el contrato de
propiedad/cierre se centraliza en la spec. No se agrega implementación, hilos, workers,
resolución DNS asíncrona ni nuevos jobs de CI. El mínimo libssh 0.9 es de **API**, no una
recomendación de desplegar esa versión histórica. Build, regresión y rendimiento siguen
sin ejecutar; los VCs de invariantes y el resto del plan requieren sus pasos posteriores.

## Revisión documental de invariantes del paso 3 — 2026-09-30

Se contrastaron los ocho invariantes con la base y los criterios de ejemplo. El
protocolo de la spec incorpora VC-19 a VC-26: todos comparan contra el hash tmux
fijado, cubren off/on y distinguen herramientas/flags por plataforma. Se corrigen
el `configure` mínimo de macOS, la equivalencia binaria no justificada, los diffs
contra un working tree que podría estar limpio y la inspección de enlace con `strings`.

Se leyeron el runner `regress/Makefile`, sus logs y entorno, y los scripts reales
`regress/pane-ops.sh`, `regress/window-ops.sh` y `regress/respawn-pane-control-lag.sh`.
La baseline usa ese runner y conserva los scripts/fixtures existentes: exige cero
fallos nuevos, en vez de rechazar una mejora porque cambie el conjunto de fallos.
Las comprobaciones de panes locales incluyen PTY, resize, respawn, cierre y el par
utempter. **No se ejecutaron** build, preprocesado, inspección de binarios, wrappers
de pkg-config, regresiones ni esos escenarios de panes; son el protocolo verificable
para una implementación posterior. Esta revisión no es un veredicto global de la spec:
contratos del bridge y el resto de FRs/NFRs/VCs tienen sus pasos siguientes.

## Contrato del bridge del paso 4 — 2026-09-30

Se mantiene comando nuevo, Linux opt-in y transporte fd + `bufferevent`. La spec
centraliza estados conceptuales, copia de parámetros/TERM, apertura diferida, I/O
parcial, contrapresión, resize pendiente y cierre/cancelación. No son interfaces
existentes de tmux ni una implementación entregada. Se precisó NFR-2 como un único
deadline de apertura hasta shell activa; FR-11b cubre kill durante apertura, FR-14
pérdida activa y NFR-4 las dos colas propias. No se agrega una cota global de buffers
que la interfaz común de teclado/pegado no podría garantizar sin ampliar el alcance.

Evidencia adicional de tmux: `environ.c:264-269` fija TERM a partir de default-terminal;
`window.c:495-512` comprueba datos pendientes y `PANE_EXITED` antes de permitir
la destrucción. `window.c:1660-1669` recibe EOF/error del fd y llama al cierre común.
La contrapresión de clientes control puede deshabilitar la lectura del pane
(`server-client.c:1978-1981`): esperar al consumidor conserva el comportamiento común,
no equivale a esperar red dentro del callback SSH.

Fuentes externas primarias: el mismo archivo libssh 0.9.0 registrado arriba y
[RFC 4254, §5.3 y §6.10](https://www.rfc-editor.org/rfc/rfc4254.html).
La [documentación de canales actual](https://api.libssh.org/stable/group__libssh__channel.html)
es complemento; la comprobación de compatibilidad se hace contra 0.9.0, no contra
su versión actual. Las siguientes rutas son **de libssh 0.9.0**:

| Fuente leída | Hallazgo utilizado |
|---|---|
| `src/channels.c`, `ssh_channel_read_nonblocking` / `ssh_channel_is_eof` | 0 puede significar ausencia de datos; EOF se comprueba aparte y no se considera drenado mientras haya buffers de stdout/stderr |
| `src/channels.c`, `channel_write_common` / `ssh_channel_window_size` | La escritura puede aceptar parte o 0 bytes; una ventana grande no prueba que el socket esté escribible. Se limitan bloques propios y se espera avance de red antes de seguir alimentando la biblioteca |
| `src/channels.c`, `channel_rcv_close` / `channel_rcv_request` | CLOSE puede conservar datos en buffers; el callback de exit status es una señal independiente. No se libera al primer callback de fin |
| `src/channels.c`, `ssh_channel_request_pty_size`, `ssh_channel_request_shell` | Las solicitudes conservan estado pendiente en modo no bloqueante; se repite la misma operación tras AGAIN sin recrear el canal |
| `src/poll.c`, `ssh_event_add_session`, `ssh_event_dopoll`, `ssh_event_remove_session`, `ssh_event_free` | El poller se crea/registra con el contexto de conexión válido, se llama con timeout 0 y se separa de la sesión antes de liberar esta; no se usa una espera infinita |
| `src/client.c`, `ssh_disconnect`; `src/session.c`, `ssh_free` | La desconexión administra socket/canales y los invalida. La spec evita close del fd TCP por fuera de libssh y un segundo free del canal tras desconectar |
| `include/libssh/callbacks.h`, callbacks EOF/CLOSE/exit status/exit signal y `ssh_remove_channel_callbacks` | El contexto mantiene la estructura de callbacks viva; se retiran antes de liberarlo. Señales remotas sin exit status normal se representan como error 255 |

La spec añade pruebas de datos finales/cierres repetidos a VC-10a, cancelación a
VC-28, pérdida activa a VC-29 y colas a VC-27. Los datos recibidos en un cierre normal
se drenan antes del EOF local; kill es cancelación explícita y puede descartarlos.
Cierre sin metadatos completos tiene plazo de 2 s una vez drenada la salida; un
consumidor local bloqueado difiere ese drenaje, con datos acotados en las colas propias
y cancelación disponible. Una partición silenciosa de una sesión activa no tiene
plazo de detección: no se agregan keepalives ni reconexión a esta v1.

**Verificación realizada:** lectura de fuentes/protocolo y revisión de consistencia
documental. **Sin ejecutar** sesiones SSH, fixtures de red/contrapresión, ASan,
medición de RSS ni tests de estados. Los máximos/deadlines son requisitos propuestos,
no mediciones. El siguiente paso sigue siendo cerrar los FRs/argumentos y sus fixtures;
la revisión completa de VCs de rendimiento y del plan de iteraciones se hace después.
