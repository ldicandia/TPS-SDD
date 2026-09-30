# Spec — comando `ssh-pane` (cliente SSH nativo) en `tmux`

> Spec **brownfield**, construida sobre [`notas-exploracion.md`](./notas-exploracion.md).
> **No hay implementación**: el entregable es el análisis y esta spec. Las referencias
> `archivo:línea` son del commit base y están explicadas en las notas. Los nombres
> `SPAWN_SSH`, `ENABLE_SSH_PANE` y `cmd_ssh_pane_entry` son incorporaciones propuestas:
> no existen en la base. Las APIs externas se verificaron por lectura de los headers y
> fuentes de libssh 0.9.0; no se compiló ni se probó un bridge SSH. Ver las notas para
> fuentes, licencia y límites de esa verificación.

**Repo:** [`tmux/tmux`](https://github.com/tmux/tmux) · commit base
`5e4b8cc39e635f8e2c4d9c95c205e987a618d50b` · **solo Linux**

## Propósito

Permitir abrir, con un comando de `tmux`, un pane cuyo contenido es una sesión SSH remota
hablada directamente por una biblioteca cliente enlazada, sin ejecutar el binario `ssh`, y
sin alterar cómo funciona `tmux` para quien no active la función.

## Actores

| Actor | Rol |
|---|---|
| Usuario de `tmux` | Ejecuta `ssh-pane` desde un cliente, un binding o un script |
| Servidor SSH remoto | Acepta la conexión, autentica y abre una shell |
| Archivo `known_hosts` del usuario | Fuente de verdad de las claves de host; solo lectura |
| Empaquetador / CI | Compila `tmux` en Linux, macOS y BSD; **los builds no-Linux no pueden romperse** |

## Alcance

### Dentro (todo bajo `#ifdef ENABLE_SSH_PANE`)

| Archivo | Cambio |
|---|---|
| `configure.ac` | Opción `--enable-ssh` (default **off**), `PKG_CHECK_MODULES(LIBSSH, libssh >= 0.9)` y propagación de sus CFLAGS/LIBS solo al activarlo, `AC_DEFINE(ENABLE_SSH_PANE)`, `AM_CONDITIONAL(ENABLE_SSH_PANE, …)`, y **aborta si el host no es Linux** (mirando `$host_os`, no `$PLATFORM`) |
| `Makefile.am` | `if ENABLE_SSH_PANE` → `dist_tmux_SOURCES += cmd-ssh-pane.c ssh-pane.c` (patrón de `Makefile.am:253-254`) |
| `cmd-ssh-pane.c` (**nuevo**) | `cmd_ssh_pane_entry` y su `exec`: resuelve target y layout como `cmd_split_window_exec` y llama a `spawn_pane` con `SPAWN_SSH` |
| `ssh-pane.c` (**nuevo**) | El *bridge*: sesión `libssh` no bloqueante, `socketpair`, integración con `libevent` |
| `cmd.c` | `extern` y fila en `cmd_table`, ambas entre `#ifdef` |
| `tmux.h` | `SPAWN_SSH 0x2000`, campos `ssh` en `struct spawn_context` y en `struct window_pane`, prototipos |
| `spawn.c` | Rama SSH junto a `SPAWN_EMPTY` (`spawn.c:459`), sin `fdforkpty`; rechazo de respawn antes de `spawn.c:312-349`; exclusión SSH del alta utempter (`spawn.c:581`) |
| `window.c` | Resize SSH sin ioctl de PTY (`window.c:597`); liberación idempotente en `window_pane_destroy` (`window.c:1567`) y exclusión SSH de utempter (`window.c:1581`) |
| `server-fn.c` | Liberación del transporte en `server_destroy_pane` (`server-fn.c:354`), incluso con `remain-on-exit`; exclusión SSH de utempter (`server-fn.c:367`) |
| `tmux.1` | Documentar `ssh-pane` con el formato mdoc usado por los comandos existentes |
| `regress/ssh-pane-*.sh` (**nuevos; patrón de nombres propuesto**) | Pruebas de los VCs, con un `sshd` de usuario en loopback |

### Contrato del transporte y del cierre

- `socketpair` no bloqueante: tmux posee y cierra el extremo `wp->fd`; el bridge posee
  el otro extremo, canal/sesión libssh, buffers y eventos. No se entrega el socket TCP
  SSH directamente al parser. La sesión libssh administra su socket de red.
- El bridge observa `ssh_get_fd()` con `event_set`/`event_add`/`event_del` en el loop del
  server; rearma lectura/escritura según `ssh_get_poll_flags()` y los resultados
  `SSH_AGAIN`/`SSH_AUTH_AGAIN`; el procesamiento de paquetes con el poller público
  de libssh (`ssh_event_dopoll`) usa timeout 0 dentro del callback. Usa timers compatibles (`evtimer_set`), sin un segundo
  loop bloqueante ni hilos. Conserva las APIs que tmux usa (`server.c:424-426`), porque
  su build contempla libevent 1.4 (`configure.ac:281-300`).
- La rama de spawn conserva restauración de señales, `window_pane_set_event` y el hook
  de `complete` (`spawn.c:589-592`). Fija `pid = -1` y `tty` vacío. No marca `PANE_EMPTY`
  para evitar utempter: usa una identidad SSH propia, bajo `ENABLE_SSH_PANE`, que sigue
  identificando al pane muerto después de liberar la sesión.
- Resize envía `ssh_channel_change_pty_size` y nunca `TIOCSWINSZ` al socket
  (`window.c:612-622`). Un respawn se rechaza antes de liberar evento/fd o reutilizar
  el pane (`spawn.c:312-349`), tanto vivo como conservado por `remain-on-exit`.
- El estado remoto llega por callback de libssh; no se usa el getter de exit status
  que puede bloquear. Antes del EOF que recibe tmux, el bridge entrega la salida
  pendiente y fija `wp->status` en formato de espera compatible con `WIFEXITED`/
  `WEXITSTATUS` (`format.c:2293-2294`) y `PANE_STATUSREADY`. Un cierre sin estado remoto
  se trata como error SSH con estado 255. El código remoto no se asigna crudo a `status`.
- El cierre normal termina el transporte después de entregar la salida pendiente.
  `server_destroy_pane` libera sus recursos antes de conservar un pane muerto
  (`server-fn.c:420`); `window_pane_destroy` cubre además `kill-pane` y destrucción
  forzada. Comparten una liberación idempotente: retirar eventos/timers antes de
  liberar sus datos y cerrar cada fd una sola vez. Las tres llamadas de utempter
  (`spawn.c:581`, `window.c:1581`, `server-fn.c:367`) quedan excluidas para panes SSH,
  manteniendo el camino de PTY local.

### Fuera de alcance

Explícito, por path y por capacidad:

- **Otros SO.** macOS, FreeBSD, NetBSD, OpenBSD, Solaris/illumos, AIX, HP-UX, Haiku y
  Cygwin no implementan el feature. En OpenBSD además hay una razón técnica: el `pledge` del
  server (`server.c:207`) no incluye `inet` ni `dns`.
- **`compat/`** — no se agrega ni se modifica nada (incluidos `compat/fdforkpty.c`,
  `compat/forkpty-*.c` y `compat.h`). `libssh` no es un reemplazo de portabilidad.
- **`osdep-*.c`** — sin cambios.
- **Los comandos existentes:** `cmd-split-window.c`, `cmd-new-window.c`,
  `cmd-new-session.c`, `cmd-respawn-pane.c` no se editan. **No se agrega ni se reutiliza un
  flag para SSH.** `split-window` ya tiene `-S` para el estilo del borde
  (`cmd-split-window.c:62-67`); no es una opción SSH.
- **El modelo de PTY/panes:** `tty*.c`, `screen*.c`, `grid*.c`, `input.c`, `layout*.c`,
  `window-*.c` (modos), `server-client.c`, `tmux-protocol.h`.
- **Autenticación por agent, contraseña o teclado interactivo**, claves con frase y
  búsqueda automática de identidades; también **agent forwarding**,
  **port forwarding**, **X11**, **SFTP/SCP**, **ProxyJump/ProxyCommand**, **ControlMaster**,
  **compresión** y **reconexión automática**.
- **Lectura de configuración SSH de usuario o sistema** — los parámetros van por
  argumentos; se desactiva `SSH_OPTIONS_PROCESS_CONFIG` antes de conectar para evitar
  la lectura automática de libssh, incluidos `ProxyCommand` y otras opciones externas.
- **Escritura de `known_hosts`** — `tmux` no aprende hosts nuevos.
- **`.github/workflows/`** — no se agrega un job de CI con `libssh`.
- **Persistencia:** un pane SSH no sobrevive a `kill-server` ni a un reinicio; no hay
  reanudación de sesión.

## Invariantes

Verdades que **no pueden cambiar**, con su forma de comprobarlas. Un invariante sin
verificación no es un invariante.

| # | Invariante | Cómo se comprueba |
|---|---|---|
| **INV-1** | **Los builds no-Linux siguen compilando.** El feature se compila afuera: sin `--enable-ssh`, ningún `#include <libssh/…>` ni símbolo de `libssh` entra a la compilación | En macOS y FreeBSD: `sh autogen.sh && ./configure && make` termina con código 0 y `strings tmux \| grep -c libssh` da 0 (**`macos-26` de `.github/workflows/regress.yml` no se rompe**) |
| **INV-2** | **`--enable-ssh` en no-Linux falla en `configure`, no en `make`** | En macOS: `./configure --enable-ssh` sale con código ≠ 0 y el mensaje contiene `only supported on Linux` |
| **INV-3** | **Sin `--enable-ssh`, el binario es el mismo de antes.** Los archivos compartidos, preprocesados, son idénticos a la base | Para `spawn.c`, `window.c`, `cmd.c`: `gcc -E -P <flags de make> <archivo>` da el mismo hash antes y después del cambio (los marcadores se sustituyen por los flags y cada ruta indicada) |
| **INV-4** | **Los comandos existentes no cambian** | `tmux list-commands` con la función apagada es idéntico byte a byte al de la base; con la función prendida, la única diferencia es la línea de `ssh-pane`. `git diff --stat` sobre `cmd-split-window.c`, `cmd-new-window.c`, `cmd-new-session.c`, `cmd-respawn-pane.c` está vacío |
| **INV-5** | **El modelo de PTY/panes no cambia**: un pane local sigue naciendo de `fdforkpty` y sigue redimensionándose con `TIOCSWINSZ` | `git diff -U0 spawn.c window.c` → toda línea agregada o quitada cae dentro de un bloque `#ifdef ENABLE_SSH_PANE`; la suite `regress/` da lo mismo que en la línea de base |
| **INV-6** | **El protocolo cliente/servidor no cambia** | `git diff --exit-code tmux-protocol.h` |
| **INV-7** | **Un pane SSH conserva la interfaz fd + `bufferevent`**: no se modifican `window_pane_set_event` (`window.c:1673`), `window_pane_read_callback` (`window.c:1632`), `window_pane_key` (`window.c:2071`), `input_key_pane` (`input-keys.c:398`), `input_key_write` (`input-keys.c:414`) ni `window_pane_paste` (`window.c:2052`) | `git diff -U0 window.c input-keys.c` no toca esas funciones |
| **INV-8** | **Los builds por default no ganan una dependencia** | `./configure` sin flags no invoca `pkg-config libssh`; `ldd tmux \| grep -c libssh` da 0 |

## Línea de base de regresión

Se mide **antes** de modificar el código de tmux. **No se midió en la entrega ni en la
revisión de referencias del 2026-09-30**: no se ejecutaron compilaciones ni regresiones.
Quien implemente tiene que fijarla como primer paso y registrar los resultados. La falta
de `libssh` no impide por sí sola compilar el tmux base, que no depende de esa biblioteca.

```bash
sh autogen.sh && ./configure --enable-utf8proc && make     # ¿compila limpio?
./tmux list-commands | sha256sum                           # firma de INV-4
for f in regress/*.sh; do (cd regress && sh ../$f) ; done  # 172 scripts; guardar cuáles fallan en la base
```

La suite se ejecuta desde `regress/` (`.github/workflows/regress.yml:79-82`). En 155 de
los 172 scripts aparece `TEST_TMUX=$(readlink -f ../tmux)`; por ejemplo,
`regress/new-window-command.sh:8`. Los demás usan variantes o helpers, por lo que no se
asume un encabezado idéntico para todos. Al cerrar la
iteración, **el conjunto de scripts que fallan tiene que ser el mismo que en la base**.

## Requerimientos

Todo FR asume que `tmux` se compiló con `--enable-ssh` en Linux, salvo FR-9.

### Entorno de prueba común

Salvo que un FR diga otra cosa, todos los VCs corren en este entorno:

- Un `sshd` de usuario en `127.0.0.1:2222`, que acepta solo autenticación por clave pública
  para el usuario `probe` y cuya clave de host está en `~/.ssh/known_hosts` como
  `[127.0.0.1]:2222`.
- Un server `tmux` de prueba (`tmux -L ssh-test -f /dev/null`) con una sesión y un solo pane.
- `<pane>` es el pane que crea `ssh-pane`. Como en `split-window`, pasa a ser el pane activo
  (salvo `-d`), así que se obtiene con `tmux display -p '#{pane_id}'` justo después.
- **`ssh-pane` devuelve `0` en cuanto crea el pane.** La conexión, la verificación de la clave
  de host y la autenticación ocurren después, de forma asíncrona. Por eso un fallo de SSH
  nunca cambia el código de salida del comando: se reporta **dentro del pane** (FR-5, FR-6a,
  FR-6b, FR-13a, FR-13b).
- Para poder observar un pane que termina, los FRs de falla fijan antes
  `tmux set -g remain-on-exit on` (el default es `off`, y con `off` el pane se destruye).
- La clave privada aceptada por el `sshd` está sin frase en `/ruta/K`, legible para el
  server de prueba. Se carga únicamente la identidad indicada con `-i`; no se consulta
  `SSH_AUTH_SOCK` ni se buscan claves por defecto. Sin `-i`, la autenticación falla
  según FR-5, después de comprobar la clave del host.
- La importación de `-i` usa una frase vacía explícita y un callback que rechaza
  solicitudes de frase sin interacción; no se dejan los defaults de la biblioteca
  que pueden pedirla por terminal. Una clave ilegible, inválida o que requiera frase
  produce `ssh-pane: authentication failed` y estado 255, igual que FR-5.

### FR-1 · El comando existe y se lista

**Dado** un `tmux` compilado con `--enable-ssh`,
**cuando** se ejecuta `tmux list-commands`,
**entonces** una línea empieza con `ssh-pane (sshp)` y muestra el uso
`[-bdhPv] [-i identity] [-l size] [-p port] [-t target-pane] [-u user] host`.

**VC-1:** `tmux list-commands | grep -c '^ssh-pane (sshp)'` da `1`.

### FR-2 · Abre un pane con una sesión remota

**Dado** el entorno de prueba común, con la clave sin frase del usuario `probe` en `/ruta/K`,
**cuando** se ejecuta `tmux ssh-pane -i /ruta/K -p 2222 -u probe 127.0.0.1`,
**entonces** el comando sale con código `0`, el pane activo se divide, el pane nuevo muestra
el prompt de la shell remota y `#{pane_dead}` vale `0`.

**VC-2:** `echo $?` tras el comando da `0`. Después de
`tmux send-keys -t <pane> 'echo $SSH_CONNECTION' Enter`, `tmux capture-pane -p -t <pane>`
contiene `127.0.0.1` en la línea de salida en ≤ 5 s, y `display -p -t <pane> '#{pane_dead}'`
da `0`.

### FR-3 · No se ejecuta el binario `ssh`

**Dado** el mismo escenario de FR-2,
**cuando** el pane está abierto,
**entonces** ningún proceso descendiente del server `tmux` tiene `comm` igual a `ssh`.

**VC-3:** `pgrep -P $(tmux display -p '#{pid}') -x ssh | wc -l` da `0`; además `strace -f -e
trace=execve -p <pid del server>` no registra ningún `execve` durante la apertura.

### FR-4b · Autenticación con clave en archivo

**Dado** el entorno de prueba común, con un `sshd` que acepta solo la clave `K`,
`K` sin frase en `/ruta/K` y un `SSH_AUTH_SOCK` que apunta a un agent que no responde,
**cuando** se ejecuta `tmux ssh-pane -i /ruta/K -p 2222 -u probe 127.0.0.1`,
**entonces** la autenticación tiene éxito y el pane muestra la shell remota sin consultar
el agent.

**VC-4b:** se cumple VC-2; una traza de `connect` sobre el server tmux, iniciada antes
del comando, no registra una conexión al socket de ese agent.

### FR-5 · Sin credenciales válidas, falla dentro del pane

**Dado** el entorno de prueba común con `remain-on-exit on`,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u probe 127.0.0.1` sin `-i`,
**entonces** el comando sale con `0`, el pane muestra la línea literal
`ssh-pane: authentication failed` y queda muerto con estado de salida `255`.

**VC-5:** `echo $?` da `0`. En ≤ 5 s, `capture-pane -p -t <pane>` contiene
`ssh-pane: authentication failed`, `#{pane_dead}` da `1` y `#{pane_dead_status}` da `255`.

### FR-6a · Clave de host desconocida: se rechaza

**Dado** el entorno de prueba común con `remain-on-exit on`, y **sin** la línea
`[127.0.0.1]:2222` en `~/.ssh/known_hosts`,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u probe 127.0.0.1`,
**entonces** la conexión se corta antes de autenticar, el pane muestra
`ssh-pane: host key verification failed`, queda muerto con estado `255` y `known_hosts`
**no se modifica**.

**VC-6a:** `sha256sum ~/.ssh/known_hosts` da lo mismo antes y después. `capture-pane -p`
contiene el texto literal y `#{pane_dead_status}` da `255`. En el log del `sshd` no aparece
ningún intento de autenticación (`grep -c 'Accepted\|Failed publickey'` da `0`).

### FR-6b · Clave de host cambiada: se rechaza

**Dado** el entorno de prueba común con `remain-on-exit on`, y la línea `[127.0.0.1]:2222` de
`~/.ssh/known_hosts` reemplazada por la clave pública de **otro** par generado con
`ssh-keygen -t ed25519`,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u probe 127.0.0.1`,
**entonces** pasa lo mismo que en FR-6a: el pane muestra
`ssh-pane: host key verification failed`, queda muerto con estado `255` y `known_hosts` no se
modifica.

**VC-6b:** las mismas tres comprobaciones de VC-6a.

### FR-7a · Lo tecleado llega al remoto

**Dado** un pane SSH abierto según FR-2,
**cuando** se ejecuta `tmux send-keys -t <pane> 'touch /tmp/ssh-pane-fr7a' Enter`,
**entonces** la shell remota ejecuta el comando. En loopback, el remoto es la misma máquina.

**VC-7a:** en ≤ 2 s, `test -f /tmp/ssh-pane-fr7a` sale con `0`.

### FR-7b · La salida remota se dibuja en el pane

**Dado** un pane SSH abierto según FR-2,
**cuando** la shell remota escribe 1000 líneas (`seq 1 1000`),
**entonces** se dibujan en el pane con el mismo parser que un pane local
(`input_parse_pane`).

**VC-7b:** tras `tmux send-keys -t <pane> 'seq 1 1000' Enter`, `capture-pane -p -S -1000`
contiene la línea `1000` y su `wc -l` es ≥ 1000.

### FR-8 · El tamaño del pane llega al remoto

**Dado** un pane SSH abierto,
**cuando** el pane cambia de tamaño (`resize-pane -x 100 -y 30`),
**entonces** `stty size` en la shell remota imprime `30 100` en ≤ 2 s.

**VC-8:** `send-keys 'stty size' Enter` tras el `resize-pane`, y `capture-pane -p` contiene
`30 100`. (La función de `window.c:597` llama `fatal` en `window.c:622` si falla el ioctl;
la rama SSH debe evitar pasar un socket por ese camino de PTY.)

### FR-9 · Sin la función compilada, el comando no existe

**Dado** un `tmux` compilado **sin** `--enable-ssh` (el default, y el único caso en no-Linux),
**cuando** se ejecuta `tmux ssh-pane host`,
**entonces** falla con `unknown command: ssh-pane` y código de salida `1`.

**VC-9:** `tmux ssh-pane x; echo $?` imprime `unknown command: ssh-pane` y `1`.

### FR-10a · Fin de la sesión remota con `remain-on-exit on`: el pane queda con su estado

**Dado** un pane SSH abierto según FR-2, con `remain-on-exit on`,
**cuando** la shell remota termina con `exit 7`,
**entonces** el pane queda muerto, `#{pane_dead}` da `1` y `#{pane_dead_status}` da `7`.

**VC-10a:** después de `send-keys -t <pane> 'exit 7' Enter`, en ≤ 2 s
`display -p -t <pane> '#{pane_dead} #{pane_dead_status}'` imprime `1 7`. Esto cierra el
hallazgo de `server-fn.c:382`: el bridge tiene que fijar `wp->status` y `PANE_STATUSREADY`
antes de cerrar su extremo del `socketpair`.

### FR-10b · Fin de la sesión remota con `remain-on-exit off`: el pane se destruye

**Dado** un pane SSH abierto según FR-2, con `remain-on-exit off` (el default),
**cuando** la shell remota termina con `exit 7`,
**entonces** el pane se destruye y no queda colgado.

**VC-10b:** en ≤ 2 s, `tmux list-panes -a -F '#{pane_id}' | grep -cx '<pane>'` da `0`.

### FR-11 · Matar el pane libera la sesión

**Dado** un pane SSH abierto,
**cuando** se ejecuta `kill-pane`,
**entonces** la conexión TCP se cierra y no quedan fds abiertos del bridge.

**VC-11:** el conteo de `ls /proc/<pid del server>/fd \| wc -l` es el mismo antes de
`ssh-pane` y después de `kill-pane` (±0); `ss -tn state established '( dport = :2222 )' \|
wc -l` da `0`.

### FR-12 · `respawn-pane` sobre un pane SSH se rechaza

**Dado** un pane SSH,
**cuando** se ejecuta `respawn-pane -k -t <pane>`,
**entonces** falla con `respawn pane failed: cannot respawn an ssh pane` y el pane no cambia.

**VC-12:** el código de salida es `1`, el mensaje es literal, y `#{pane_dead}` sigue en `0`.

### FR-13a · Puerto cerrado: se reporta en el pane

**Dado** el entorno de prueba común con `remain-on-exit on`, y nada escuchando en
`127.0.0.1:1`,
**cuando** se ejecuta `tmux ssh-pane -p 1 -u probe 127.0.0.1`,
**entonces** el pane muestra una línea que empieza con `ssh-pane: connection failed: ` y queda
muerto con estado `255`.

**VC-13a:** en ≤ 2 s, `capture-pane -p -t <pane>` contiene `ssh-pane: connection failed: ` y
`#{pane_dead_status}` da `255`.

### FR-13b · Host que no responde: se reporta en el pane al vencer el timeout

**Dado** el entorno de prueba común con `remain-on-exit on`, y `10.255.255.1` como destino
(IP literal que no responde),
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u probe 10.255.255.1`,
**entonces**, al vencer el timeout de NFR-2, el pane muestra una línea que empieza con
`ssh-pane: connection failed: ` y queda muerto con estado `255`.

**VC-13b:** el texto y el estado son los de VC-13a. El tiempo lo mide VC-17 (NFR-2), así que
este VC no fija otro umbral.

### BR-1 · `known_hosts` es solo lectura

`tmux` nunca escribe en `known_hosts` ni en ningún archivo bajo `~/.ssh`.

**VC-14:** `strace -f -e trace=openat,open -o t.log tmux …` sobre FR-2, FR-6a y FR-6b: ninguna línea
abre un archivo de `~/.ssh` con `O_WRONLY`, `O_RDWR` o `O_CREAT`.

### BR-2 · Sin secretos en logs ni en argumentos

La ruta de `-i` puede aparecer en logs; **el contenido de una clave y su frase, nunca**.

**VC-15:** con `tmux -vv`, `grep -c 'BEGIN OPENSSH PRIVATE KEY' tmux-server-*.log` da `0`.

### NFR-1 · El event loop no se bloquea por la red

Mientras una conexión SSH está en curso, los demás panes siguen atendidos.

**VC-16:** con `ssh-pane -p 2222 10.255.255.1` en marcha (destino que no responde, IP literal
para excluir DNS), un `send-keys` a otro pane se refleja en `capture-pane` en **≤ 100 ms**,
medido 20 veces.

### NFR-2 · Timeout de conexión

La conexión se abandona a los **10 s** si no hay respuesta. Es el único umbral de tiempo para
un host que no responde; FR-13b lo referencia.

**VC-17:** en el escenario de FR-13b, el tiempo entre la ejecución de `ssh-pane` y el momento
en que `#{pane_dead}` pasa a `1` está entre **10 y 12 s** (se consulta cada 100 ms).

### NFR-3 · Rendimiento y memoria

Un pane SSH sostiene **≥ 20 MiB/s** de salida remota en loopback, y el pico de memoria
residente del server `tmux` crece **≤ 32 MiB** mientras dura esa transferencia.

**VC-18:** en un pane SSH abierto según FR-2, se lee `VmRSS` de `/proc/<pid del server>/status`
como base. Después se ejecuta `send-keys -t <pane> 'yes | head -c 200M; echo FIN-$((9+9))' Enter`
(exactamente 200 MiB de salida; la marca se calcula para que no coincida con el eco del
comando tecleado). Se cumple si:
(a) una línea igual a `FIN-18` aparece en `capture-pane -p` en **≤ 10 s**, es decir, 200 MiB / 10 s = 20 MiB/s;
y (b) `VmHWM` de `/proc/<pid del server>/status` menos la `VmRSS` base es **≤ 32 MiB**.

## Plan de iteraciones

| Iteración | Alcance | Cierra |
|---|---|---|
| **1** | Guarda de build: `--enable-ssh`, `AM_CONDITIONAL`, `cmd-ssh-pane.c` vacío que registra el comando y responde "not implemented" | INV-1, INV-2, INV-3, INV-4, INV-8, FR-1, FR-9 |
| **2** | Bridge: conexión, host key, auth, `socketpair`, enganche en `spawn_pane` | FR-2, FR-3, FR-4b, FR-5, FR-6a, FR-6b, FR-13a, FR-13b, BR-1, BR-2, NFR-1, NFR-2 |
| **3** | I/O completo: resize, salida, destrucción, `respawn-pane` | FR-7a, FR-7b, FR-8, FR-10a, FR-10b, FR-11, FR-12, NFR-3, INV-5, INV-6, INV-7 |
| **4** | Documentación y `regress/` | `tmux.1`, scripts `regress/ssh-pane-*.sh` |

La Iteración 1 es el camino más angosto: cierra la promesa de compat **antes** de escribir
una línea de SSH.

## Decisiones — resueltas

| Pregunta | Decisión | Por qué |
|---|---|---|
| ¿Entrada nueva en la tabla de comandos? | **Sí**: `ssh-pane` | Un flag en `split-window` cambiaría un comando existente (INV-4) |
| ¿Dónde engancha en el spawn? | En **`spawn_pane`**, junto a `SPAWN_EMPTY`, con `SPAWN_SSH` | Reutiliza layout, entorno y el hook `pane-created` |
| ¿`libssh` u OpenSSH? | **`libssh` ≥ 0.9**, enlace dinámico; LGPL-2.1-or-later | La consigna prohíbe invocar el binario. La API usada existe en 0.9.0 según sus headers; es una dependencia externa solo del build opt-in, siguiendo `configure.ac:512-514`. El mínimo de API no afirma que 0.9.0 sea una versión aconsejada para despliegue |
| ¿Event loop? | `socketpair` + libssh no bloqueante + `event_set` | Reutiliza fd + `bufferevent` (INV-7) y el precedente `server.c:424-426`; descarta TCP crudo como fd del pane y un hilo aparte. Evita exigir libevent 2 para una base que admite 1.4 |
| ¿Auth por claves o agent? | **Solo clave sin frase con `-i`**, sin prompts ni agent | Decisión confirmada en la revisión: la consigna permite elegir claves; el agent de libssh 0.9.0 hace esperas bloqueantes aun con la sesión no bloqueante. Evita ampliar la arquitectura con hilos/adaptadores; verifica el host antes de autenticar y usa `known_hosts` solo lectura |
| ¿Qué guarda saca a no-Linux? | **`--enable-ssh` opt-in** que falla en no-Linux, **más** `#ifdef ENABLE_SSH_PANE` | Es el patrón de `--enable-systemd`/`--enable-cgroups` |
| ¿Se resuelve DNS sin bloquear? | **No.** Se documenta como limitación | Confirmado en la fuente libssh 0.9.0: `getaddrinfo` se ejecuta antes de la conexión asíncrona; por eso NFR-1 mide con IP literal. La lectura de clave y `known_hosts` también es síncrona: no se promete latencia acotada de DNS o del filesystem |
| ¿Se acepta un host desconocido? | **No** | Aceptar sin preguntar es un MITM; no hay TTY para preguntar |
