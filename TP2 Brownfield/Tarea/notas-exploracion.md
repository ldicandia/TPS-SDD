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

**Hallazgo:** `respawn-window` (`cmd-respawn-window.c:82`) entra por `spawn_window` con
`SPAWN_RESPAWN`. Ahí se toma el primer pane como `wp0`, se destruyen los demás con
`window_destroy_panes` y se reinicia el layout (`spawn.c:143-154`) **antes** de llamar a
`spawn_pane`. Un rechazo puesto solo en `spawn_pane` llegaría con la ventana ya mutada.

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
- `format_cb_current_command` y `format_cb_current_path` llaman `osdep_get_name`
  (`format.c:966`) y `osdep_get_cwd` (`format.c:990`), que en Linux usan `tcgetpgrp(fd)`
  (`osdep-linux.c:38`, `osdep-linux.c:71`). Sobre un socket fallan sin error fatal:
  `#{pane_current_command}` cae al argv o a la shell local configurada (y con ella el
  nombre automático de la ventana) y `#{pane_current_path}` queda vacío.

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
| ¿Auth? | **Solo clave sin frase con `-i`** | Agent, contraseña y teclado interactivo | La consigna permite claves o agent. La fuente externa confirma esperas bloqueantes del agent de 0.9.0; decisión del equipo: claves, para mantener una v1 simple. No cambia la construcción del entorno en `spawn.c:408` |
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
| **`respawn-window` sobre una ventana con pane SSH** | `spawn.c:143-154` destruye los demás panes antes de `spawn_pane`; el rechazo SSH debe ir en `spawn_window`, antes de esa mutación (FR-22) |
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

## Validación externa: libssh 0.9.0 y documentación primaria

Fuentes: [archivo oficial de libssh 0.9.0](https://www.libssh.org/files/0.9/libssh-0.9.0.tar.xz)
(SHA-256 `25303c2995e663cd169fdd902bae88106f48242d7e96311d74f812023482c7a5`),
[guía de enlace de libssh](https://api.libssh.org/stable/libssh_linking.html),
[compatibilidad de eventos de libevent](https://libevent.org/libevent-book/Ref4_event.html#_obsolete_event_manipulation_functions)
y [RFC 4254, §5.3 y §6.10](https://www.rfc-editor.org/rfc/rfc4254.html). El archivo se
extrajo en una copia temporal y solo se leyeron fuentes y headers; no se compiló ni se
ejecutó. Las rutas de esta tabla pertenecen **a libssh 0.9.0, no a tmux**. El mínimo
0.9 es de **API**, no una recomendación de desplegar esa versión histórica.

| Evidencia externa | Consecuencia para la spec |
|---|---|
| `include/libssh/libssh.h`, `include/libssh/callbacks.h` | Existen las APIs elegidas: sesión no bloqueante, fd/poll flags, importación de clave, auth por clave, known hosts, PTY/shell, lectura no bloqueante, resize, poller con timeout y callbacks de canal. Existir no prueba integración |
| Cabecera de `libssh.h` y `COPYING` | LGPL-2.1-or-later; se propone enlace dinámico |
| `src/agent.c` (`agent_talk`), `src/auth.c` (`ssh_userauth_agent`) | El agent espera con `ssh_poll(..., -1)` aun con la sesión no bloqueante: se descarta agent en la v1 y se usa `-i` |
| `src/connect.c`, `getai` | `getaddrinfo` es síncrono; NFR-1 mide con IP literal y declara DNS/filesystem fuera de la cota |
| `src/options.c`, `SSH_OPTIONS_PROCESS_CONFIG`, PORT, `user@host` | La configuración SSH se procesa si no se desactiva; PORT se enmascara a 16 bits y se acepta `user@host`. La spec desactiva la configuración y valida host/puerto antes de pasarlos |
| `src/misc.c`, `ssh_get_user_home_dir`; `src/knownhosts.c` | Se usa `getpwuid_r` antes de HOME y puede aceptarse el archivo global. La spec fija el global en `/dev/null`, verificación estricta y solo `SSH_KNOWN_HOSTS_OK` |
| `src/pki_crypto.c`, `src/pki_container_openssh.c` | Importar con frase/callback nulos puede pedir frase por terminal: se exige importación sin interacción |
| `src/channels.c`: `ssh_channel_get_exit_status`, `ssh_channel_read_nonblocking`, `ssh_channel_is_eof`, `channel_write_common`, `ssh_channel_window_size`, `channel_rcv_close`, solicitudes PTY/shell | El getter de status puede bloquear (se usa callback); 0 bytes no es EOF; escrituras parciales; CLOSE puede conservar datos; las solicitudes se repiten tras AGAIN sin recrear el canal |
| `src/poll.c` (`ssh_event_*`), `src/client.c` (`ssh_disconnect`), `src/session.c` (`ssh_free`) | Poller con timeout 0 y separado antes de liberar la sesión; tras `ssh_disconnect` no se libera de nuevo el canal |
| `SSH_OPTIONS_LOG_VERBOSITY`, `SSH_LOG_NOLOG` en `libssh.h` | Base de BR-2: la biblioteca no vuelca paquetes en los logs |
| Documentación de libevent | `event_new` no existe antes de 2.0: se usa `event_set`, como tmux |

Para el fixture de pruebas se contrastaron, sin ejecutarlos, los manuales oficiales de
[sshd](https://man.openbsd.org/sshd) y [sshd_config](https://man.openbsd.org/sshd_config),
la documentación de [/proc](https://docs.kernel.org/filesystems/proc.html) (VmRSS/VmHWM,
`clear_refs`), [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) y
las APIs de [servidor](https://docs.paramiko.org/en/stable/api/server.html) y
[canal](https://docs.paramiko.org/en/stable/api/channel.html) de Paramiko. El helper
Paramiko es una herramienta de test propuesta; **no existe todavía**.

## Evidencia adicional de tmux usada por la spec

Leída en el mismo commit base, además de lo descrito en las secciones anteriores:

| Ancla | Consecuencia |
|---|---|
| `environ.c:264-269`, `spawn.c:408` | TERM sale de `default-terminal`; se copia al contexto antes de liberar el entorno |
| `window.c:495-512`, `window.c:1660-1669` | El cierre espera datos pendientes y `PANE_EXITED`: el bridge entrega EOF después de la salida |
| `server-client.c:1909-1981`, `control.c:325-345` | Clientes control que no leen pausan la lectura del pane; NFR-1/NFR-4 no prometen salida en ese caso |
| `arguments.c:208-282`, `cmd.c:527-537`, `arguments.c:687-699` | Parser común, mensajes de flags/aridad y "último valor gana" se conservan |
| `layout.c:1640-1700` (`-p` en `layout.c:1658-1680`) | `-p` es porcentaje para el helper: el comando SSH le pasa solo `-l` |
| `arguments.c:998-1037`, `arguments.c:1067-1108` | Gramática y rangos de tamaño de la base |
| `spawn.c:292-306`, `server-client.c:2926-2941` | La identidad relativa se ancla al cwd efectivo del pane |
| `cmd-split-window.c:33`, `cmd-split-window.c:69`, `cmd-split-window.c:306-310` | Target, selección y template `-P` tomados como precedente, sin editar split-window |
| `tmux.c:331-342` | Precedente de reloj monotónico para medir tiempos |
| `options-table.c:845-851` | `history-limit` default 2000, usado en NFR-3 |
| `window.c:1640-1647`, `cmd-pipe-pane.c:128-167` | `pipe-pane -O` permite verificar la salida completa; crea su propio hijo |
| `cmd-paste-buffer.c:87-123` | `paste-buffer -r -S` conserva los bytes; el default cambia LF por CR |
| `spawn.c:143-154`, `cmd-respawn-window.c:82-83` | `respawn-window` muta la ventana antes de `spawn_pane`: FR-22 rechaza antes |
| `regress/Makefile:27-29`, `regress/pane-ops.sh`, `regress/window-ops.sh`, `regress/respawn-pane-control-lag.sh` | El runner borra logs previos; scripts locales usados por VC-23 |

## Qué se verificó y cómo

| Comprobación | Resultado |
|---|---|
| Base tmux | Checkout separado en el hash del encabezado; `git status --short` vacío y `git diff --exit-code` con salida 0 |
| Rutas y funciones (M2) | Todos los archivos tmux citados existen; las funciones internas se localizaron en su definición. Las fuentes nuevas (`cmd-ssh-pane.c`, `ssh-pane.c`), el patrón `regress/ssh-pane-*.sh`, `compat/ssh-pane.c` (descartado) y las rutas de libssh/OpenBSD se identifican como tales y no se cuentan como existentes |
| Líneas (M3) | 284 apariciones de `archivo:línea` en notas, spec y capsule, 169 anclas distintas: todas exactas. En rangos se leyó el bloque completo |
| Conteos de la base | 153 `.c` en la raíz y 101.303 líneas; 46 archivos en `compat/`; 12 `osdep-*.c`; 172 `regress/*.sh`, 155 con `readlink`; definición de `spawn_pane` más cinco sitios de llamada |
| Literales de tmux usados en VCs | `command %s: %s`, `unknown flag`, `too few/many arguments`, `-%c expects an argument`, `unknown command: %s`, `invalid tiled geometry %s`, `no space for a new pane`, `can't split a floating pane`, `can't find pane: %s`, `create pane failed: %s`, `respawn pane failed: %s` y `respawn window failed: %s` existen en el código |
| IDs de la spec | 30 FR, 2 BR, 4 NFR y 8 INV; 44 VCs únicos; cada requisito e invariante tiene VC y fila en la tabla de cobertura; sin referencias a IDs inexistentes. Todo FR tiene Dado/Cuando/Entonces con un solo Cuando |

**No se hizo:** compilar tmux o libssh, correr `regress/`, arrancar tmux/sshd, generar
claves, medir latencia/RSS ni ejecutar ningún VC. Los VCs y presupuestos (100 ms, 10 s,
20 MiB/s, 32 MiB, colas de 1 MiB) son requisitos propuestos, no mediciones.
