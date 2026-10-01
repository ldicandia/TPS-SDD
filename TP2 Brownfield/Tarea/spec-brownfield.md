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

### Dentro (feature opcional, excluido de builds sin SSH)

En C, las incorporaciones a archivos compartidos se protegen con
`#ifdef ENABLE_SSH_PANE`; las fuentes nuevas se excluyen mediante `AM_CONDITIONAL`
en `Makefile.am`. Las reglas de `configure.ac` son Autoconf, no código bajo un
`#ifdef`: solo consultan y agregan libssh al activar `--enable-ssh`.

| Archivo | Cambio |
|---|---|
| `configure.ac` | Opción `--enable-ssh` (default **off**), `PKG_CHECK_MODULES(LIBSSH, libssh >= 0.9)` y propagación de sus CFLAGS/LIBS solo al activarlo, `AC_DEFINE(ENABLE_SSH_PANE)`, `AM_CONDITIONAL(ENABLE_SSH_PANE, …)`, y **aborta si el host no es Linux** (mirando `$host_os`, no `$PLATFORM`) |
| `Makefile.am` | `if ENABLE_SSH_PANE` → `dist_tmux_SOURCES += cmd-ssh-pane.c ssh-pane.c` (patrón de `Makefile.am:253-254`) |
| `cmd-ssh-pane.c` (**nuevo**) | `cmd_ssh_pane_entry` y su `exec`: valida argumentos, resuelve target y layout como `cmd_split_window_exec`, filtra los argumentos de geometría y llama a `spawn_pane` con `SPAWN_SSH` |
| `ssh-pane.c` (**nuevo**) | El *bridge*: sesión `libssh` no bloqueante, `socketpair`, integración con `libevent` |
| `cmd.c` | `extern` y fila en `cmd_table`, ambas entre `#ifdef` |
| `tmux.h` | `SPAWN_SSH 0x2000`, campos `ssh` en `struct spawn_context` y en `struct window_pane`, prototipos |
| `spawn.c` | Rama SSH junto a `SPAWN_EMPTY` (`spawn.c:459`), sin `fdforkpty`; rechazo de respawn antes de `spawn.c:312-349`; exclusión SSH del alta utempter (`spawn.c:581`) |
| `window.c` | Resize SSH sin ioctl de PTY (`window.c:597`); liberación idempotente en `window_pane_destroy` (`window.c:1567`) y exclusión SSH de utempter (`window.c:1581`) |
| `server-fn.c` | Liberación del transporte en `server_destroy_pane` (`server-fn.c:354`), incluso con `remain-on-exit`; exclusión SSH de utempter (`server-fn.c:367`) |
| `tmux.1` | Documentar `ssh-pane` con el formato mdoc usado por los comandos existentes |
| `regress/ssh-pane-*.sh` (**nuevos; patrón de nombres propuesto**) | Pruebas de los VCs, con un `sshd` aislado en loopback |

### Contrato del bridge

Los estados de abajo son **etiquetas conceptuales propuestas**, no enums ni funciones
que existan en tmux. Un contexto pertenece a un único pane y se ejecuta únicamente
en el loop del server; no hay hilos, workers ni reconexión.

#### Creación y estados

`spawn_pane` crea el pane y `socketpair`, copia host/puerto/usuario/ruta de identidad,
`TERM` y dimensiones al contexto, y publica el pane con `pid = -1` y `tty` vacío.
El `TERM` se toma del entorno construido por `environ_for_session(s, 0)`
(`spawn.c:408`, `environ.c:264-269`); no se conserva un puntero al entorno que
`complete` libera. Se restauran señales y se instalan evento/hook normalmente
(`spawn.c:589-592`). La primera llamada SSH se difiere hasta después de retornar del
spawn: DNS/archivos no se procesan con las señales bloqueadas ni dentro de ese hook.
No se marca `PANE_EMPTY`; una identidad SSH independiente del transporte sobrevive
al cierre, para excluir utempter y rechazar respawn incluso en un pane muerto.

| Estado | Operación / salida |
|---|---|
| Creado | Recursos locales disponibles; programar avance diferido y deadline de apertura |
| Conectando | Configuración explícita y `ssh_set_blocking(session, 0)` antes de `ssh_connect`; con `SSH_OK`, verificar host |
| Verificando host | Solo una clave de host aceptada por la política de FR-6a/FR-6b permite autenticar |
| Autenticando | Importar una vez la identidad de `-i` sin interacción; `ssh_userauth_publickey`; éxito permite abrir canal |
| Abriendo canal | Crear un único canal `session` con `ssh_channel_open_session`; éxito permite pedir PTY |
| Pidiendo PTY | `ssh_channel_request_pty_size` con `TERM` y tamaño real del pane; éxito permite pedir shell |
| Pidiendo shell | `ssh_channel_request_shell`; éxito entra a Activo y cancela el deadline de apertura |
| Activo | Transferencia bidireccional y resize; señales de fin llevan a Cerrando |
| Cerrando | Detener entrada hacia el remoto, continuar salida y reunir EOF/CLOSE/exit status antes de publicar fin |
| Finalizado | Transporte liberado; entregar EOF a tmux y dejar que aplique `remain-on-exit`; solo resta liberar la conexión local al destruir el pane |

`SSH_AGAIN`/`SSH_AUTH_AGAIN` mantienen la operación pendiente y sus argumentos; se
reanuda sin recrear sesión/canal ni volver a importar la clave. Se distinguen de
éxito, rechazo y error. Cualquier error termina esa apertura: no se prueban passwords,
agents, otro host ni identidades automáticas. Fallas de canal/PTY/shell usan los
literales de la tabla de diagnósticos y estado 255. Las fallas de host key y
autenticación conservan los textos literales de sus FRs.

El deadline de **10 s de NFR-2** se arma al publicar el pane y cubre apertura hasta
Activo, incluyendo handshake, auth, canal, PTY y shell; no se reinicia con cada etapa
ni con cada `AGAIN`. La garantía medible usa IP literal y archivos locales accesibles:
DNS y filesystem siguen síncronos, como se declara en Decisiones. Kill cancela también
una apertura pendiente, sin esperar ese deadline (FR-11b).

Si fallan pane/layout/socketpair/contexto antes de publicar, se deshace lo creado y
el comando devuelve 1 con `create pane failed: ` y la causa, como el contrato de
spawn existente. Una vez publicado, el comando devuelve 0: las fallas posteriores
son asíncronas dentro del pane. No se transfieren recursos al pane en dos pasos que
permitan callbacks sobre un contexto a medio construir.

#### Event loop e I/O

Tmux posee y cierra el extremo `wp->fd`; el bridge posee el otro extremo del
`socketpair`, sus dos colas, eventos/timers y sesión/poller libssh. El socket TCP
es de libssh y nunca se entrega al parser ni se cierra directamente por número de fd.
La clave importada se libera al terminar auth o al cancelar. El contexto conserva los
callbacks de canal inicializados durante toda la vida del canal; no son variables
locales de una función que retorna antes de que libssh los use.

- Observar el fd válido de `ssh_get_fd()` con `event_set`/`event_add`/`event_del`,
  como tmux (`server.c:424-426`); timers con `evtimer_set`, compatibles con la base
  que admite libevent 1.4 (`configure.ac:281-300`). Registrar la sesión en el poller
  libssh después de que su contexto de conexión exista; comprobar el resultado.
  Si cambia el fd durante la apertura, retirar el evento anterior antes de registrarlo
  sobre el nuevo fd. Una sesión por poller; no se reutiliza en otro pane.
- Invocar `ssh_event_dopoll` solo con timeout **0**, rearme de lectura/escritura
  según `ssh_get_poll_flags()` y la operación pendiente. No hay un segundo loop que
  espere red. El evento de escritura del socket local solo se arma con salida
  pendiente; no se vigila permanentemente un socket escribible.
- Procesar como máximo **64 KiB de transferencia y 8 llamadas de avance/I/O por
  callback propio**. Si queda trabajo que puede progresar sin esperar fd, diferir
  una continuación al loop; si no hubo progreso, esperar fd/timer. `AGAIN`, 0 y
  `EAGAIN` no justifican un bucle de reintentos ni una cadena de timers activos sin
  progreso. El presupuesto no acota el coste interno de una llamada libssh; NFR-1
  verifica la latencia observable, no una garantía inferida del nombre de la API.
- Local → remoto: leer el extremo del bridge hasta el espacio disponible de su cola
  de entrada; antes de Activo se conserva ahí sin enviar al canal. En Activo, usar
  bloques de hasta **16 KiB**, limitados también por `ssh_channel_window_size` y la
  cola disponible. Si la ventana remota es 0 o libssh tiene escritura de red pendiente,
  esperar su avance antes de agregar otro bloque. Una escritura parcial retira solo
  los bytes aceptados; 0 conserva la cola, error inicia cierre con estado 255.
- Remoto → local: leer stdout y stderr alternadamente con
  `ssh_channel_read_nonblocking`, hasta **16 KiB** por llamada y el espacio de la cola
  de salida. Ambos se dibujan en el mismo pane; se conserva el orden dentro de cada
  stream. Una shell con PTY normalmente ya entrega su salida combinada. **0 no es
  EOF**: comprobar también callbacks/estado de canal; `SSH_EOF` no es un error de red.
  Un CLOSE ya conocido con buffers vacíos termina el drenaje, sin interpretarlo
  como una nueva pérdida de transporte. Escribir al socket local retira solo los
  bytes efectivamente escritos; `EAGAIN`
  conserva lo pendiente. No se sustituye el parser común ni las entradas de teclado.

Las dos colas propias se limitan a **1 MiB cada una**, con pausa al llenarse y
reanudación al bajar a **512 KiB** (NFR-4). Una cola de entrada llena detiene la
lectura del socket local; una cola de salida llena detiene el avance de recepción
SSH, incluido el poller, hasta poder drenar al pane. Los eventos/timers y otros panes
siguen atendidos. La contrapresión también puede pausar temporalmente el envío SSH;
es el trade-off de mantener un solo contexto/loop y colas acotadas.

Esos límites **no** describen todos los buffers del proceso: libssh tiene buffers de
paquetes/canal, el kernel tiene los de sockets y `wp->event->output` sigue siendo el
buffer común de tmux. No se modifica `input_key_write` ni el pegado para prometer un
límite global ante entrada arbitraria; NFR-3 conserva su medición de RSS en el escenario
específico de salida remota. Se documenta este límite, sin atribuir al bridge una
cota que no controla.

Resize conserva solo el tamaño pendiente más reciente, tomado del pane real. Antes
de pedir PTY se usa ese tamaño; si cambia mientras una solicitud está pendiente, se
completa y luego se aplica el último tamaño. En Activo se envía
`ssh_channel_change_pty_size`, sin `TIOCSWINSZ` sobre el socket (`window.c:612-622`);
al cerrar se descarta lo pendiente. Respawn se rechaza antes de la mutación de
`spawn.c:312-349`, con el literal de FR-12.

#### Fin, drenaje y propiedad de recursos

EOF SSH, CLOSE y exit status son señales distintas. Los callbacks solo guardan las
señales/estado y solicitan avance diferido; **no liberan** canal, sesión, contexto ni
pane mientras se ejecuta una llamada libssh que podría seguir usándolos. Recibir exit
status no publica todavía `PANE_EXITED` ni descarta salida. En Cerrando se marca
`PANE_INPUTOFF`, deshabilita escritura del `bufferevent` local y descarta las teclas
pendientes que ya no tienen destino; la lectura/salida del pane continúa.

Un fin normal requiere salida recibida drenada **y** (CLOSE remoto, o EOF remoto
más exit status). Se lee también la salida que libssh conserva después de recibir
CLOSE; sus callbacks no implican que el buffer esté vacío. Se retiene el primer exit
status y se normaliza a los **8 bits** representables en `WEXITSTATUS`, con una
codificación de espera de salida normal en `wp->status` (`format.c:2293-2294`). No se
asigna crudo el código SSH. CLOSE sin status, exit-signal o fallo de transporte usan
255; la v1 no traduce nombres de señales remotas a señales locales. Un fallo de
transporte ya detectado no espera metadatos del remoto: agrega el diagnóstico de
FR-14 y drena los datos que quedan en su cola propia. No garantiza recuperar datos
que aún no recibió o que libssh ya descartó al fallar.

Si solo llega EOF o status, después de drenar la salida ya disponible se espera la
información restante por un máximo de **2 s**, con timer del mismo loop. Si no llega,
se termina con estado 255 y `ssh-pane: connection failed: incomplete remote close`.
La contrapresión de un consumidor local bloqueado conserva sus datos/colas y difiere
ese plazo hasta poder drenarlos; no se promete un plazo de drenaje independiente del
consumidor. Es un bloqueo de flujo explícito, cancelable por `kill-pane`, no una espera
bloqueante de red dentro de un callback.

Al completar el drenaje, se fija `PANE_STATUSREADY` y el estado antes del EOF local.
Se intenta cerrar el canal en modo no bloqueante sin esperar confirmaciones; el fin
de la conexión libera el transporte. Se usa `shutdown` de escritura en el extremo
del bridge para que tmux reciba EOF **después** de la salida en el socket; ese extremo
permanece vivo hasta que tmux cierre el pane. Así no se cierra completamente un socket
con entrada sin leer, ni se obliga a `server_destroy_pane` a descartar la salida aún
pendiente (`window.c:495-512`, `window.c:1660-1669`). Las entradas pendientes del usuario
no se interpretan como comandos una vez iniciado el cierre.

La liberación compartida es idempotente y cubre contextos parcialmente inicializados:

1. Cancelar continuaciones, eventos de fd y timers antes de liberar sus datos; remover
   callbacks del canal y separar la sesión de su poller mientras ambos existen.
2. Liberar poller y clave importada si quedan; desconectar/liberar la sesión. Libssh
   administra sus canales y socket; invalidar el puntero al canal al desconectar y
   no ejecutar `ssh_channel_free` sobre un puntero que `ssh_disconnect` ya invalidó.
3. Liberar colas y metadatos propios. El pequeño contexto/local fd que entrega EOF
   se termina de liberar en `server_destroy_pane` o `window_pane_destroy`, sin volver
   a liberar la sesión. Tmux libera su `bufferevent` y cierra `wp->fd` una sola vez.

Con `remain-on-exit`, `server_destroy_pane` realiza esa baja **antes** de conservar el
pane (`server-fn.c:420`). El pane muerto mantiene identidad SSH pero ningún transporte
vivo. `window_pane_destroy` cubre además `kill-pane` en cualquier etapa: cancela y
libera inmediatamente, sin drenar ni esperar al remoto; el pane fue eliminado por
el usuario. Ambas rutas excluyen SSH de las tres operaciones utempter
(`spawn.c:581`, `window.c:1581`, `server-fn.c:367`) y preservan el camino local.

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

Obligaciones del cambio propuesto. Cada una tiene un VC explícito; la definición de
la comprobación **no** implica que se haya ejecutado. Todos los diffs siguientes
comparan con el commit base de **tmux**, no con el último commit de esta entrega.

| # | Invariante | Verificación |
|---|---|---|
| **INV-1** | Los builds no-Linux conservan el feature excluido y compilan con las dependencias originales, sin libssh | VC-19 |
| **INV-2** | Pedir `--enable-ssh` en no-Linux falla en `configure`, antes de buscar libssh | VC-20 |
| **INV-3** | Con SSH apagado, las incorporaciones a archivos C compartidos no alteran el código activo de la base | VC-21 |
| **INV-4** | Los comandos existentes conservan nombres, aliases, flags, uso y comportamiento, también en Linux con SSH activado | VC-22 |
| **INV-5** | Los panes locales conservan creación por `fdforkpty`, resize por `TIOCSWINSZ`, respawn y cierre; las ramas SSH no interceptan panes locales | VC-23 |
| **INV-6** | El protocolo cliente/servidor conserva su definición | VC-24 |
| **INV-7** | El pane SSH reutiliza fd + `bufferevent`, parser y entradas de teclado/pegado sin modificar sus funciones comunes | VC-25 |
| **INV-8** | El build por defecto y `--disable-ssh` no consultan, compilan ni enlazan libssh | VC-26 |

### Protocolo común de comparación

Estos comandos son para quien implemente, en checkouts de tmux aislados,
con el candidato registrado en Git (incluidas sus fuentes nuevas). **No se
compiló tmux ni se ejecutaron regresiones en esta entrega.**

```sh
TP2_BASE=5e4b8cc39e635f8e2c4d9c95c205e987a618d50b
git rev-parse "$TP2_BASE"           # debe imprimir ese hash completo
git diff --check "$TP2_BASE"       # incluye cambios ya commiteados y el working tree
```

Se comparan tres variantes: **base** en ese hash, **candidato-off** con el cambio y
SSH apagado, y **candidato-on** con `--enable-ssh`, este último únicamente en Linux.
Antes de implementar se guarda la base por plataforma y configuración; después se
repiten las mismas comprobaciones. Usar mismo SO/arquitectura, compilador y versión,
dependencias, flags, locale y opciones de funcionalidades existentes en cada par.
Cada registro identifica hash del candidato, configuración, comandos, exit codes y
logs. Ejecutar binarios por su ruta en el checkout y sockets de prueba diferentes
(`-L`), sin reutilizar un servidor de otra variante ni la sesión personal.

Matriz mínima, sin agregar workflows de CI:

| Plataforma | Comparaciones | Dependencias SSH |
|---|---|---|
| Linux | base frente a candidato-off por defecto y con `--disable-ssh`; base frente a candidato-on para panes locales | Off en entorno sin headers, biblioteca ni módulo pkg-config de libssh; on con libssh ≥ 0.9 |
| macOS | base frente a candidato-off por defecto y con `--disable-ssh`; prueba negativa con `--enable-ssh` | Sin libssh |
| FreeBSD | base frente a candidato-off por defecto y con `--disable-ssh`; prueba negativa con `--enable-ssh` | Sin libssh |
| Linux con utempter | Repetir base/off/on con `--enable-utempter`, además del caso sin utempter | utempter instalado en este par; libssh solo en on |

Las dependencias originales (libevent, curses y herramientas de Autotools/build) deben
estar disponibles. Se usan `make` en Linux y GNU make (`gmake`) en macOS/FreeBSD.
Para el par mínimo se desactivan utf8proc y jemalloc explícitamente en **ambas**
variantes; la base macOS exige elegir esas opciones (`configure.ac:1033-1055`). El
par utempter añade `--enable-utempter` a ambos lados. No se interpreta un error de
prerrequisitos de la base como una regresión causada por SSH ni como un VC aprobado.

### VCs de invariantes

**VC-19 · INV-1:** en macOS y FreeBSD, base y candidato-off completan `autogen.sh`,
`configure` y el build con exit code 0 usando las opciones anteriores. Candidato-off
pasa además VC-26. La matriz macOS existente (`.github/workflows/regress.yml:34-37`)
se conserva sin edits; no se afirma que un job haya pasado por leer ese archivo.

**VC-20 · INV-2:** en ambos SO no-Linux, desde un checkout candidato limpio de builds
anteriores, ejecutar `./configure --disable-utf8proc --disable-jemalloc --enable-ssh`
y guardar stdout/stderr y exit code. Debe salir con código distinto de 0 y contener
`only supported on Linux`, sin consultas a libssh en el registro de `pkg-config`
definido en VC-26. Si falla por otra dependencia o llega a `make`, el VC no pasa.

**VC-21 · INV-3:** revisar `git diff --function-context "$TP2_BASE" -- spawn.c window.c
cmd.c server-fn.c tmux.h`: todas las incorporaciones específicas de SSH deben estar
bajo `ENABLE_SSH_PANE`, incluyendo campos y prototipos. La rama alternativa conserva
el código local original. Esto cubre también los archivos sincronizados con OpenBSD
(`SYNCING.md:3-22`); no se refactoriza código común fuera del alcance.

Para comprobar el efecto de las guardas, guardar los comandos reales de compilación
de `make V=1` en base y candidato-off. En las cuatro unidades `spawn.c`, `window.c`,
`cmd.c` y `server-fn.c`, repetir el mismo compilador y flags efectivos sustituyendo
la compilación/archivo objeto por `-E -P` y un archivo de salida `.i`. Ejecutar desde
la raíz de cada checkout con el mismo nombre relativo de fuente. Esas unidades
incluyen `tmux.h`, por lo que también comprueban que sus nuevos campos se excluyan.
Eliminar únicamente líneas vacías de ambos `.i` con `sed '/^[[:space:]]*$/d'`
para no atribuir cambios a espacios de las directivas; conservar íntegro el resto.
Comparar cada par normalizado con `cmp`: exit code 0 en los cuatro. Si aparecen
diferencias por rutas/configuración del entorno, corregir el par y repetir; no
eliminar declaraciones, literales o instrucciones para hacerlo pasar. No se exige
identidad byte a byte del binario; la preservación de comportamiento se comprueba
además con comandos y panes locales.

**VC-22 · INV-4:** guardar `list-commands` de base/off/on con `LC_ALL=C`, binario del
checkout, socket exclusivo y `-f /dev/null`. `cmp base.commands off.commands` sale 0.
En on hay exactamente una fila `ssh-pane (sshp)` con el uso de FR-1; al quitar solo
esa fila, `cmp base.commands on-existing.commands` sale 0. Revisar el diff de todos
los `cmd-*.c` frente a `TP2_BASE`: la única incorporación permitida es el archivo
nuevo `cmd-ssh-pane.c`; los archivos existentes no cambian. El registro/extern nuevo
en `cmd.c` queda bajo la guarda de VC-21. El comportamiento se comprueba con los
mismos scripts existentes de la línea de base, no solo con la lista de comandos.

**VC-23 · INV-5:** comparar la suite existente según la línea de base, incluyendo
`regress/pane-ops.sh`, `regress/window-ops.sh` y `regress/respawn-pane-control-lag.sh`
(leídos en el commit base). En Linux se comprueban también panes **locales** en off
y on, con y sin utempter: la incorporación de SSH no habilita un rechazo de respawn
ni una ruta de resize/cierre SSH para esos panes.

Además, en cada variante base/off/on, crear una sesión de prueba desconectada de
80×24 con `/bin/sh`, hacer `split-window -v` y `new-window` con `/bin/sh`, y obtener los IDs de los
panes mediante `-P -F '#{pane_id}'`. En esos panes locales:

- `#{pane_pid}` es positivo y `#{pane_tty}` no está vacío. Escribir
  `test -t 0 && test -t 1 && printf '\nTP2-PTY-OK\n'` mediante `send-keys`; aparece una
  línea exacta `TP2-PTY-OK` en `capture-pane` dentro de 2 s.
- En el pane original de la ventana dividida, guardar sus dimensiones y ejecutar
  `resize-pane -t <pane> -y 8`; exigir que cambie su altura. Comparar `stty size` con
  `display -p -t <pane> '#{pane_height} #{pane_width}'` del pane real, no con un tamaño
  pedido que el layout podría limitar. Deben coincidir dentro de 2 s y el server sigue vivo.
- `respawn-pane -k -t <pane> /bin/sh` sale 0 y el nuevo pane conserva PTY y PID positivo;
  repetir el marcador anterior. Con `remain-on-exit on`, `exit 7` deja `pane_dead=1`
  y `pane_dead_status=7` dentro de 2 s; ese pane local permite después `respawn-pane`.
- `kill-pane` elimina el ID en `list-panes`, conservando otro pane local y el server
  vivo. En Linux, una traza del server iniciada antes de las operaciones
  (`strace -f -e trace=process,ioctl`) registra creación del hijo y `TIOCSWINSZ` exitoso
  durante el resize. La lectura de `spawn.c:478` y `window.c:612` confirma que el
  camino local sigue usando `fdforkpty` y el ioctl original.

**VC-24 · INV-6:** `git diff --exit-code "$TP2_BASE" -- tmux-protocol.h` sale 0 y no
muestra diferencias. Se compara contra la base aunque el cambio ya esté commiteado.

**VC-25 · INV-7:** `git diff --exit-code "$TP2_BASE" -- input.c input-keys.c` sale 0.
Leer `git diff --function-context "$TP2_BASE" -- window.c` y comparar las funciones
completas con la base: firma y cuerpo sin cambios en `window_pane_set_event`
(`window.c:1673`), `window_pane_read_callback` (`window.c:1632`), `window_pane_key`
(`window.c:2071`) y `window_pane_paste` (`window.c:2052`). Son **0 funciones modificadas**
en ese conjunto; teclado, pegado y parser ya están cubiertos por el diff de sus archivos.
El contrato del transporte conserva un extremo del `socketpair` en `wp->fd`; la
verificación end-to-end de ese bridge se realiza con VC-2, VC-7a y VC-7b, sin presentar
la ausencia de diff como prueba de que SSH ya funcione.

**VC-26 · INV-8:** en cada candidato-off de la matriz, ejecutar primero sin opción SSH
y luego con `--disable-ssh`, en checkouts/builds independientes. Guardar:

1. Una traza de las invocaciones de `pkg-config` durante `configure`, mediante un
   wrapper de prueba que registre los argumentos y delegue al ejecutable real
   (`PKG_CONFIG` apunta a ese wrapper solo durante la comprobación). Debe haber
   **0 consultas a `libssh`**, aunque existan consultas a otras dependencias.
2. `config.h`: `ENABLE_SSH_PANE` queda **sin definir**, no definido a 0. El registro
   de `make V=1` contiene **0 compilaciones** de `cmd-ssh-pane.c`/`ssh-pane.c` y
   **0 opciones de enlace** que agreguen libssh. VC-21 comprueba además los includes
   transitivos; no alcanza buscar solamente `-lssh` en el comando de enlace.
3. En binarios de prueba sin strip, `nm -u ./tmux` completa con exit code 0 y no
   contiene símbolos importados cuyo nombre empiece por `ssh_` (admitiendo el prefijo
   `_` de Mach-O). `ldd ./tmux` en Linux/FreeBSD u `otool -L ./tmux` en macOS también
   completa con exit code 0 y contiene **0 dependencias libssh**.

Si la herramienta de inspección falla, no se cuenta como ausencia de dependencia.
No se usa `strings` como prueba de enlace ni se toma el exit code de `grep` sin
coincidencias como fallo de compilación. El build on en Linux es el control positivo:
`ENABLE_SSH_PANE` definido, las dos fuentes nuevas compiladas y enlace dinámico libssh
visible. Estos chequeos definen resultados esperados; no son resultados medidos aquí.

## Línea de base de regresión

**Sin medir.** Los conteos de scripts y referencias provienen de lectura, no de ejecución.
El siguiente protocolo se ejecuta primero en la base y luego por cada variante de la
matriz; los logs/resultados se guardan fuera de `regress/logs` antes de repetir, porque
el runner borra los logs previos (`regress/Makefile:27-29`).

```sh
# Desde la raíz de un checkout aislado; sin SSH en la base.
TP2_MAKE=make                  # gmake en macOS y FreeBSD
sh autogen.sh                  # exigir exit code 0 antes de continuar
./configure --disable-utf8proc --disable-jemalloc  # exigir exit code 0
"$TP2_MAKE" V=1                # exigir exit code 0; guardar salida de build
LC_ALL=C ./tmux -L tp2-base-commands -f /dev/null list-commands > base.commands
"$TP2_MAKE" -C regress         # guardar exit code, salida y logs de fallos
```

Para candidato-off se omite la opción SSH en una corrida y se agrega `--disable-ssh`
en otra; para candidato-on se agrega `--enable-ssh`. En el par utempter se agrega
`--enable-utempter` también a la base. Cambiar el nombre del socket y del archivo
`base.commands` por la variante. Los comandos se ejecutan por pasos: si falla un
prerrequisito, se registra y no se siguen interpretando salidas como comprobaciones válidas.

El runner real es `regress/Makefile`: descubre los `.sh` (`regress/Makefile:1`), ejecuta
cada uno con entorno limpio (`regress/Makefile:35-36`) y resume PASS/FAIL por exit code.
Se contaron **172 scripts existentes** en la base; su manifiesto y los fixtures se
conservan. En 155 scripts aparece `TEST_TMUX=$(readlink -f ../tmux)`, por ejemplo
`regress/new-window-command.sh:8`; los demás usan variantes o helpers. El protocolo
usa el runner, evitando reemplazar su entorno por un loop de `sh` diferente.

Se registra resultado por script y plataforma/configuración. Para los scripts
existentes, el conjunto de fallos del candidato debe ser un subconjunto del de la
base (**0 fallos nuevos**); una mejora no invalida la comparación. Un fallo heredado,
un script omitido o un prerrequisito ausente se declara con su límite de cobertura,
no como un PASS. Si uno de los tres scripts locales exigidos por VC-23 no puede
verificarse, ese VC no se marca aprobado. Los nuevos `regress/ssh-pane-*.sh` se
registran aparte: solo ejecutan SSH en Linux con el feature activo y omiten explícitamente
esos casos en off/no-Linux; sus omisiones no prueban el feature. Comparar también
`git diff --name-status "$TP2_BASE" -- regress`: no se permite modificar o eliminar
scripts/fixtures existentes para hacer pasar las pruebas.

## Requerimientos

Todo FR asume que `tmux` se compiló con `--enable-ssh` en Linux, salvo FR-9.
Los contratos siguientes son requisitos propuestos; ningún VC de ejecución se declara aprobado.

### Contrato de argumentos y diagnósticos

Uso: `ssh-pane [-bdhPv] [-i identity] [-l size] [-p port] [-t target-pane] [-u user] host`.
Alias: `sshp`. Hay **exactamente un** argumento posicional, host; no hay comando
remoto posicional. Las opciones van antes del host; `--` termina el parseo de opciones.
El parser común se conserva (`arguments.c:208-282`, `cmd.c:527-537`); la entrada
propuesta declara mínimo y máximo 1. Opciones con valor repetidas usan el último
valor, como `args_get` (`arguments.c:687-699`); repetir un booleano es idempotente.

| Argumento | Semántica y validación |
|---|---|
| `host` | Nombre para resolver, IPv4 o IPv6 sin corchetes. Se rechazan vacío, espacios/caracteres de control, prefijo `-`, `@`, `/` y corchetes. Si contiene `:`, debe ser una IPv6 válida con `inet_pton`, sin zona; no se acepta `host:port`. No se interpretan URI, `user@host`, alias de ssh_config ni formatos tmux; no se hace conversión IDN. Un nombre que no resuelve falla luego como conexión |
| `-p port` | Puerto decimal de 1 a 65535; default 22. Solo dígitos ASCII, sin signo ni espacios. Validar **antes** de convertir/pasar a libssh: su opción PORT en 0.9.0 enmascara a 16 bits y no rechaza todos los valores fuera de rango |
| `-u user` | Usuario remoto no vacío, sin espacios ni caracteres de control; default nombre de la cuenta local del **server**, obtenido de su UID, sin depender de `$USER` del cliente. No se ejecuta ni se expande como shell/formato |
| `-i identity` | Ruta no vacía a una única clave sin frase. Absoluta o relativa al cwd efectivo de creación del pane, calculado como en `spawn.c:292-306` con `server_client_get_cwd` (`server-client.c:2926-2941`). Se copia como ruta absoluta antes de abrir; no se expande `~`, variables ni formatos. El shell que invoca tmux puede haber expandido su propio `~` antes. Una ruta válida pero ilegible/inválida/con frase falla **asíncronamente**, después de verificar el host; sin `-i` pasa lo mismo. No se buscan otras identidades |
| `-t target-pane` | Target común `CMD_FIND_PANE`, como `cmd-split-window.c:69`; default pane del contexto tmux. El error de target es el del resolver común y ocurre antes de crear recursos SSH |
| `-h`, `-v` | Izquierda/derecha y arriba/abajo respectivamente; default vertical. Son mutuamente excluyentes en este comando nuevo |
| `-b` | Crear antes del target: izquierda con `-h`, arriba con vertical |
| `-l size` | Reutiliza la geometría de `layout_get_tiled_cell` (`layout.c:1640-1700`): celdas o porcentaje, incluido el formato que expande ese helper. Sin `-l`, tamaño elegido por el layout común. La gramática/rangos/clamp son los de esa base (`arguments.c:998-1037`, `arguments.c:1067-1108`), no una promesa de tamaño exacto si no cabe |
| `-d` | Conserva el pane activo; sin `-d`, activa el nuevo pane, como el split común |
| `-P` | Imprime una sola línea `#{session_name}:#{window_index}.#{pane_index}` para el nuevo pane, como el template base (`cmd-split-window.c:33`, `cmd-split-window.c:306-310`). Sin `-P`, no imprime resultado de éxito. No implica esperar autenticación; no se agrega `-F` |

**Separación obligatoria de geometría:** `layout_get_tiled_cell` interpreta `-p`
como porcentaje (`layout.c:1658-1680`). No se le pasa el objeto completo de argumentos
SSH. El comando nuevo construye/libera un objeto de argumentos de layout que conserva
solo `-l`; dirección/posición se pasan con los flags de spawn. Puerto, identidad,
usuario y host quedan en el contexto SSH. No se modifica el helper ni el significado
de `-p` en `split-window`. La representación de la base puede aceptar porcentajes
mayores que 100; se preserva ese comportamiento del layout, sin reutilizarlo para puerto.

La validación específica antecede cualquier mutación de layout. Los errores del
parser/resolver se conservan. Los nuevos errores semánticos devuelven 1 por stderr
al cliente de comandos, con uno de estos literales: `ssh-pane: invalid host`,
`ssh-pane: invalid port`, `ssh-pane: invalid user`, `ssh-pane: invalid identity path`,
`ssh-pane: -h and -v are mutually exclusive`. No se imprime `-P` ni queda un pane
nuevo en esos casos. El layout conserva `invalid tiled geometry <causa>`,
`no space for a new pane` y `can't split a floating pane`; un fallo del spawn conserva
`create pane failed: <causa>`. La falta de memoria que las rutinas comunes tratan
como fatal no se convierte artificialmente en un error recuperable del comando.

Una vez publicado el pane, el comando sale 0 y los fallos SSH son **líneas dentro
del pane**, con status 255. Los textos son estables, sin incluir mensajes libres
que la biblioteca pueda cambiar:

| Etapa / motivo | Línea literal |
|---|---|
| Configuración de sesión o creación de recursos libssh | `ssh-pane: connection failed: setup` |
| Conexión/handshake, incluida resolución fallida | `ssh-pane: connection failed: connect` |
| Host no conocido/cambiado, archivo ausente/ilegible o error de verificación | `ssh-pane: host key verification failed` |
| Sin identidad, importación fallida o rechazo de clave | `ssh-pane: authentication failed` |
| Apertura de canal, solicitud de PTY o shell rechazada | `ssh-pane: connection failed: channel`, `ssh-pane: connection failed: pty` o `ssh-pane: connection failed: shell`, respectivamente |
| Deadline de apertura agotado | `ssh-pane: connection failed: opening timeout` |
| Transporte perdido en Activo / cierre incompleto | Los literales de FR-14 / del contrato de cierre |

La verificación usa `ssh_session_is_known_server` y acepta solo `SSH_KNOWN_HOSTS_OK`.
La fuente de confianza de esta v1 es exclusivamente el `~/.ssh/known_hosts` de la
cuenta del server (home de su UID en la base de cuentas, no un `$HOME` arbitrario).
Se configura `SSH_OPTIONS_GLOBAL_KNOWNHOSTS` a `/dev/null` y
`SSH_OPTIONS_STRICTHOSTKEYCHECK` a verdadero: 0.9.0 puede consultar el archivo global
y aceptar una coincidencia allí aun si el archivo de usuario no coincide. Se mantiene
`SSH_OPTIONS_PROCESS_CONFIG` desactivado antes de conectar. No se usa una API que solo
compruebe si existe alguna entrada, ni se actualiza/escribe el archivo. Importar `-i`
usa frase vacía explícita y callback que rechaza solicitudes sin interacción.

### Entorno de prueba común

Es un **protocolo para una implementación posterior**, sin scripts ejecutados en esta
entrega. Los VCs de invariantes usan la matriz anterior; los de SSH usan Linux on.
No se prueba contra servicios ni archivos SSH personales.

- Usar un contenedor o VM Linux desechable previamente preparado, sin nuevo job de CI.
  La cuenta no privilegiada de pruebas existe realmente, tiene shell `/bin/sh` utilizable
  y home propio en la base de cuentas. `TP2_USER` es su `id -un`; `probe` es solo un
  ejemplo de nombre, no una cuenta que se presupone instalada. Tmux se ejecuta con
  ese UID; sshd acepta esa misma cuenta. Cambiar solo `$HOME` **no** aísla libssh 0.9.0,
  que consulta `getpwuid_r` antes de usar HOME como fallback.
- `TP2_ROOT` es un directorio temporal privado (0700), propio de esa cuenta. Guardar allí
  claves, configuración/logs del fixture y evidencias por corrida. La identidad `K`
  es absoluta, sin frase, con permisos 0600; su pública es la única autorizada.
  `/ruta/K` en los ejemplos representa ese archivo del fixture, no otra ruta.
  Generar también otra clave no autorizada, otra clave de host y una identidad con
  frase solo para pruebas negativas. Preparar `~/.ssh` 0700 y known_hosts 0600 dentro
  del home desechable. No se usa una clave privada real.
- `sshd` solo escucha en `127.0.0.1:2222`; el puerto debe estar libre y se registra
  configuración efectiva con `sshd -T` y validación con `sshd -t`, ambos exit 0.
  Configuración propia con `ListenAddress 127.0.0.1`, `Port 2222`, HostKey/PidFile/
  AuthorizedKeysFile absolutos del fixture, `AllowUsers` igual a TP2_USER,
  `PubkeyAuthentication yes`, `PasswordAuthentication no`,
  `KbdInteractiveAuthentication no`, `UsePAM no`, `UseDNS no`, `PermitTTY yes`,
  `PermitUserRC no` y `LogLevel DEBUG3`. Se ejecuta en primer plano con `-D -e -f`,
  **sin `-d`**, que solo atiende una conexión. Preparación de cuenta/directorios de
  privsep y privilegios de sshd, si la distribución los requiere, ocurre dentro del
  entorno desechable; no se presupone que un sshd sin root pueda autenticar cualquier
  UID. Registrar versión y prerrequisitos. Un servicio que no arranca no es un PASS.
  En versiones con `PerSourcePenalties`, desactivar esas penalizaciones **solo en
  este sshd aislado** (`PerSourcePenalties no`) y confirmarlo en -T, para que los
  rechazos consecutivos no bloqueen los casos siguientes; si la opción no existe,
  registrar esa versión y omitirla. Autenticación efectiva solo publickey; no hay
  métodos/commands adicionales heredados de la configuración del sistema.
- known_hosts se construye desde la **pública de host generada localmente**, no confiando
  en una clave descubierta en la red: `[127.0.0.1]:2222 <tipo> <base64>`. FR-6a usa
  archivo existente vacío; FR-6b otra pública del **mismo tipo**, para obtener CHANGED
  en lugar de OTHER. FR-18 trata archivo ausente/ilegible. La API no crea ese archivo.
- Tmux usa el binario absoluto del checkout (`TP2_TMUX`), un socket absoluto exclusivo
  (`-S <TP2_ROOT/socket>`) y `-f /dev/null` en **todas** las invocaciones, incluyendo
  consultas/capture/kill; `tmux` en los ejemplos significa esa invocación. Crear sesión
  desconectada de 160×48 con `/bin/sh`, fijar `history-limit` a 5000 antes de crear panes
  y conservar un pane local `<local>` cuyo ID `%...` se registra antes del split.
  La shell remota no tiene rc que genere ruido; TERM proviene de `default-terminal`.
- Abrir con `-P -t <local>` y resolver su línea de resultado con `display -p -t <resultado>
  '#{pane_id}'`. Así `<pane>` es el ID nuevo también con `-d`, sin depender del pane activo.
  Guardar código/stdout/stderr **de esa invocación**, antes de otra orden. Cuando se
  prueba sin `-P`, obtener el nuevo ID por diferencia de `list-panes` en ese server sin
  aperturas concurrentes. Para fallos asíncronos, fijar antes `remain-on-exit on`;
  con off el pane se destruye y no se consulta su status después.
- El prompt/eco no prueban auth ni salida. El fixture requiere una línea exacta que
  el comando tecleado no contenga literalmente; por ejemplo, enviar
  `printf '\nTP2-REMOTO-%s:%s\n' OK "$SSH_CONNECTION"`. Validar la línea producida
  con prefijo `TP2-REMOTO-OK:` y los cuatro campos IP/puerto de SSH_CONNECTION, y
  registrar `Accepted publickey` de esa conexión en sshd. El primer campo es
  127.0.0.1, el tercero 127.0.0.1 y el cuarto 2222.
- Guardar logs por conexión/PID y tiempos con reloj monotónico; polling ≤ 100 ms salvo
  VC con umbral menor. Un listener sin banner de FR-11b/FR-13b registra aceptación y
  retiene el socket sin enviar bytes ni cerrarlo por al menos 12 s; informa EOF tras
  kill. No se usa una IP arbitraria como sinónimo de timeout. El socket agent señuelo, cuando un caso lo exige, se configura en el entorno del
  **server al arrancarlo**, no solo en el cliente del comando; el fixture registra
  su ruta y conexiones, acepta sin responder si se lo consulta. Para puerto rechazado
  usar 127.0.0.1:2223 comprobando que no hay listener en el entorno exclusivo.
- Registrar PID del server tmux y su conjunto estable de `/proc/<pid>/fd` antes del
  escenario; excluir fds de herramientas externas y no contar cabeceras de `ss`.
  Filtrar conexiones por PID/tupla de este fixture, no por un puerto global. Trazas
  se adjuntan al **server existente antes** de abrir SSH, con herramientas fuera del
  server. Tras cada caso destruir el pane nuevo y restaurar el pane local/layout.
- Cleanup con trap de salida interrumpe y espera solo PIDs propios del fixture,
  mata solo el server del socket exclusivo y elimina sus archivos temporales.
  No usar `killall sshd`, ni reemplazar archivos de cuentas/SSH del host. Si faltan
  sshd, claves/algoritmos compatibles, strace, /proc, ASan o recursos necesarios,
  registrar el caso no verificado y la causa; un skip no satisface su VC.
  Los scripts futuros deben inicializar su entorno porque el runner lo limpia
  (`regress/Makefile:35-36`); no depender de variables heredadas invisibles.

### FR-1 · El comando existe y se lista

**Dado** un `tmux` compilado con `--enable-ssh`,
**cuando** se ejecuta `tmux list-commands`,
**entonces** una línea empieza con `ssh-pane (sshp)` y muestra el uso
`[-bdhPv] [-i identity] [-l size] [-p port] [-t target-pane] [-u user] host`.

**VC-1:** guardar `tmux list-commands` con exit 0; hay exactamente una fila
`ssh-pane (sshp)` cuyo uso es el literal anterior, y ninguna opción adicional.
Comparar también la invocación por alias en VC-2.

### FR-2 · Abre un pane con una sesión remota

**Dado** el entorno de prueba común, con la clave sin frase de la cuenta `TP2_USER` en `/ruta/K`,
**cuando** se ejecuta `tmux ssh-pane -i /ruta/K -p 2222 -u "$TP2_USER" 127.0.0.1`,
**entonces** el comando sale con código `0`, el pane activo se divide, el pane nuevo muestra
el prompt de la shell remota y `#{pane_dead}` vale `0`.

**VC-2:** guardar exit 0 de la apertura y un ID nuevo; dentro de 5 s obtener la
marca remota del entorno común, `Accepted publickey` para esa conexión y
`display -p -t <pane> '#{pane_dead}'` igual a 0. Repetir por `sshp` con el mismo
resultado. Un prompt o el eco de `$SSH_CONNECTION` no satisfacen la prueba.

### FR-3 · No se ejecuta el binario `ssh`

**Dado** el mismo escenario de FR-2,
**cuando** el pane está abierto,
**entonces** ningún proceso descendiente del server `tmux` tiene `comm` igual a `ssh`.

**VC-3:** adjuntar `strace -f -e trace=process -p <pid del server>` **antes** de
abrir y registrar hasta obtener la marca de VC-2. No hay `execve`/`execveat` en el
server ni sus descendientes durante esa apertura; listar además todos los
descendientes (no solo hijos directos): 0 con comm `ssh`. Una traza ausente, empezada
tarde o denegada por ptrace no pasa. El sshd remoto del fixture no es descendiente
del server tmux y sus procesos no se mezclan con ese resultado.

### FR-4b · Autenticación con clave en archivo

**Dado** el entorno de prueba común, con un `sshd` que acepta solo la clave `K`,
`K` sin frase en `/ruta/K` y un `SSH_AUTH_SOCK` que apunta al socket señuelo del entorno común,
**cuando** se ejecuta `tmux ssh-pane -i /ruta/K -p 2222 -u "$TP2_USER" 127.0.0.1`,
**entonces** la autenticación tiene éxito y el pane muestra la shell remota sin consultar
el agent.

**VC-4b:** se cumple VC-2; una traza de `connect` sobre el server tmux, iniciada antes
del comando, no registra una conexión al socket de ese agent.

### FR-5 · Sin credenciales válidas, falla dentro del pane

**Dado** el entorno de prueba común con `remain-on-exit on`,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u "$TP2_USER" 127.0.0.1` sin `-i`,
**entonces** el comando sale con `0`, el pane muestra la línea literal
`ssh-pane: authentication failed` y queda muerto con estado de salida `255`.

**VC-5:** guardar exit 0 de la apertura. En ≤ 5 s, `capture-pane -p -t <pane>` incluye una línea exacta
`ssh-pane: authentication failed`, `#{pane_dead}` da `1` y `#{pane_dead_status}` da `255`.

### FR-6a · Clave de host desconocida: se rechaza

**Dado** el entorno de prueba común con `remain-on-exit on`, y **sin** la línea
`[127.0.0.1]:2222` en `~/.ssh/known_hosts`,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u "$TP2_USER" 127.0.0.1`,
**entonces** la conexión se corta antes de autenticar, el pane muestra
`ssh-pane: host key verification failed`, queda muerto con estado `255` y `known_hosts`
**no se modifica**.

**VC-6a:** guardar exit 0; dentro de 5 s hay una línea exacta
`ssh-pane: host key verification failed` y `pane_dead=1`, `pane_dead_status=255`.
SHA-256 y metadatos de known_hosts no cambian desde el inicio de la prueba.
En el log DEBUG3 de **esa conexión** no hay mensajes de solicitud
`userauth-request` ni aceptación/rechazo publickey; la ausencia de `Accepted` sola
no demuestra que no se haya intentado autenticar. Conservar traza y log completos.

### FR-6b · Clave de host cambiada: se rechaza

**Dado** el entorno de prueba común con `remain-on-exit on`, y la línea `[127.0.0.1]:2222` de
`~/.ssh/known_hosts` reemplazada por la clave pública de **otro** par del mismo tipo que el host del fixture,
**cuando** se ejecuta `tmux ssh-pane -p 2222 -u "$TP2_USER" 127.0.0.1`,
**entonces** pasa lo mismo que en FR-6a: el pane muestra
`ssh-pane: host key verification failed`, queda muerto con estado `255` y `known_hosts` no se
modifica.

**VC-6b:** todas las comprobaciones de VC-6a, con la variante de clave cambiada.

### FR-7a · Lo tecleado llega al remoto

**Dado** un pane SSH abierto según FR-2 y una ruta nueva `<TP2_ROOT>/fr7a-<corrida>`
inexistente y accesible en la máquina loopback,
**cuando** se envía `touch <ruta>` con `send-keys -t <pane> ... Enter`,
**entonces** la shell remota crea ese archivo.

**VC-7a:** comprobar ausencia antes; dentro de 2 s `test -f <ruta>` sale 0.
El fixture elimina ese archivo después; no se reutiliza `/tmp/ssh-pane-fr7a`, que
podría existir por una corrida anterior y producir un falso positivo.

### FR-7b · La salida remota se dibuja en el pane

**Dado** un pane SSH abierto según FR-2 con el history-limit del entorno común,
**cuando** la shell remota escribe las líneas numeradas de 1 a 1000,
**entonces** aparecen completas y en orden con el parser común `input_parse_pane`.

**VC-7b:** enviar
`printf '\nTP2-INICIO-%s\n' LINEAS; n=1; while [ "$n" -le 1000 ]; do printf 'TP2-LINEA-%s\n' "$n"; n=$((n+1)); done; printf 'TP2-FIN-%s\n' LINEAS`.
Dentro de 5 s, `capture-pane -p -S - -t <pane>` incluye líneas exactas
`TP2-INICIO-LINEAS` y `TP2-FIN-LINEAS`; extraer solo el segmento entre ellas y
compararlo byte a byte con las 1000 líneas esperadas. Las marcas no coinciden con
el eco. Un conteo total de pantalla o hallar solo `1000` no basta.

### FR-8 · El tamaño del pane llega al remoto

**Dado** un pane SSH abierto,
**cuando** cambia su tamaño real con `resize-pane`,
**entonces** `stty size` remoto informa las filas y columnas actuales del pane.

**VC-8:** guardar dimensiones previas, cambiar altura con `resize-pane -y 8` y exigir
que la altura real cambie. Consultar `#{pane_height} #{pane_width}` y enviar
`printf '\nTP2-TAM-%s\n' "$(stty size)"`; en ≤ 2 s la línea producida coincide con
`TP2-TAM-<altura real> <ancho real>`. Repetir cambiando ancho en un split horizontal,
con nuevo fixture. No exigir `30 100` si el layout no lo permite. Server vivo y sin
`TIOCSWINSZ` sobre el socket SSH en la traza (`window.c:597`, `window.c:612-622`).

### FR-9 · Sin la función compilada, el comando no existe

**Dado** un `tmux` compilado **sin** `--enable-ssh` (el default, y el único caso en no-Linux),
**cuando** se ejecuta `tmux ssh-pane host`,
**entonces** falla con `unknown command: ssh-pane` y código de salida `1`.

**VC-9:** `tmux ssh-pane x; echo $?` imprime `unknown command: ssh-pane` y `1`.

### FR-10a · Fin de la sesión remota con `remain-on-exit on`: el pane queda con su estado

**Dado** un pane SSH abierto según FR-2, con `remain-on-exit on`,
**cuando** la shell remota termina con `exit 7`,
**entonces** el pane queda muerto, `#{pane_dead}` da `1` y `#{pane_dead_status}` da `7`.

**VC-10a:** en el fixture de FR-2, con el consumidor local activo, enviar
`printf '\nTP2-CIERRE-%s\n' 7; exit 7` mediante `send-keys`. Dentro de 2 s,
`display -p -t <pane> '#{pane_dead} #{pane_dead_status}'` imprime `1 7` y
`capture-pane -p -t <pane>` conserva una línea exacta `TP2-CIERRE-7`. La marca no
coincide con el eco del comando. Repetir 20 aperturas/cierres consecutivos en el
mismo server: sin caída y sin fds de transporte acumulados tras cada cierre;
comparar con el conteo estable de fds previo a abrir, con otros panes inactivos.
Después de comprobar la baja de transporte **con el pane muerto aún presente**,
eliminar ese pane y repetir desde el pane local original para no agotar el layout.
Esto comprueba estado de salida, datos finales y baja con `remain-on-exit`; el
bridge fija `status`/`PANE_STATUSREADY` antes del EOF local (`server-fn.c:382`).

### FR-10b · Fin de la sesión remota con `remain-on-exit off`: el pane se destruye

**Dado** un pane SSH abierto según FR-2, con `remain-on-exit off` (el default),
**cuando** la shell remota termina con `exit 7`,
**entonces** el pane se destruye y no queda colgado.

**VC-10b:** en ≤ 2 s, `tmux list-panes -a -F '#{pane_id}' | grep -cx '<pane>'` da `0`.

### FR-11 · Matar el pane libera la sesión

**Dado** un pane SSH abierto,
**cuando** se ejecuta `kill-pane`,
**entonces** la conexión TCP se cierra y no quedan fds abiertos del bridge.

**VC-11:** dentro de 2 s del kill, ID ausente, conteo/conjunto de fds del server
restaurado al estable previo a abrir y ninguna conexión de esa tupla/PID en estado
ESTABLISHED. Usar `ss -Htnp` (sin cabecera) y evidencias del listener/sshd del fixture;
no contar todas las conexiones del puerto ni exigir que no exista TIME_WAIT.

### FR-11b · Cancelar una apertura pendiente libera sus recursos

**Dado** un pane SSH conectándose a un listener de prueba en loopback que acepta TCP
pero no envía el banner SSH, con otro pane local abierto,
**cuando** se ejecuta `kill-pane -t <pane>` antes del deadline de apertura,
**entonces** el pane se elimina y la conexión de esa apertura se cierra, sin esperar
los 10 s ni ejecutar después callbacks sobre el pane eliminado.

**VC-28:** el listener registra aceptación antes del kill. Dentro de 2 s, el ID ya no
aparece en `list-panes`, no queda conexión establecida entre el server tmux y ese
listener y los fds vuelven al conteo estable anterior. Esperar hasta 12 s desde la
apertura y emitir `display-message`/`send-keys` al otro pane: ambos comandos salen 0,
el server sigue vivo y no aparece ningún pane nuevo. Repetir 20 veces en el mismo
server, con ASan, sin errores de memoria ni aumento acumulado de fds.

### FR-12 · `respawn-pane` sobre un pane SSH se rechaza

**Dado** un pane SSH,
**cuando** se ejecuta `respawn-pane -k -t <pane>`,
**entonces** falla con `respawn pane failed: cannot respawn an ssh pane` y el pane no cambia.

**VC-12:** repetir sobre un pane abriendo (listener sin banner), uno Activo y uno
muerto conservado con remain-on-exit. Código 1, texto literal; IDs, layout, estado y
fds del pane no cambian por respawn. En Activo, una nueva marca remota prueba que
sigue funcionando; en el muerto se conserva el status anterior. Matar el pane al
terminar cada caso. El rechazo sucede antes de `spawn.c:312-349`.

### FR-13a · Puerto cerrado: se reporta en el pane

**Dado** el entorno de prueba común con `remain-on-exit on`, y nada escuchando en
`127.0.0.1:2223`,
**cuando** se ejecuta `tmux ssh-pane -p 2223 -u "$TP2_USER" 127.0.0.1`,
**entonces** el pane muestra `ssh-pane: connection failed: connect` y queda
muerto con estado `255`.

**VC-13a:** en ≤ 2 s, `capture-pane -p -t <pane>` incluye una línea exacta `ssh-pane: connection failed: connect`,
`#{pane_dead}` da `1` y `#{pane_dead_status}` da `255`.

### FR-13b · Una apertura sin progreso termina por timeout

**Dado** el entorno común con `remain-on-exit on`, y el listener loopback sin banner
(definido en el entorno común) en 127.0.0.1:2224,
**cuando** se ejecuta `tmux ssh-pane -p 2224 -u "$TP2_USER" 127.0.0.1`,
**entonces**, al vencer NFR-2, el pane muestra
`ssh-pane: connection failed: opening timeout` y queda muerto con estado 255.

**VC-13b:** guardar exit 0 y registro de aceptación del listener. Línea exacta y
`pane_dead=1`, `pane_dead_status=255`; medir el plazo con VC-17. Esto verifica
handshake estancado sin depender de rutas/firewall de 10.255.255.1. El deadline
también rige otras etapas pendientes, como exige el contrato; no se afirma haber
probado aquí todas las etapas con un servidor OpenSSH ordinario.

### FR-14 · Pérdida de una conexión activa

**Dado** un pane SSH abierto según FR-2 con `remain-on-exit on` y otro pane local,
**cuando** el fixture corta abruptamente la conexión TCP de ese pane,
**entonces** el pane muestra `ssh-pane: connection failed: transport lost`, queda
muerto con estado 255 y el otro pane sigue atendido.

**VC-29:** cortar únicamente el proceso de conexión del `sshd` aislado de prueba,
identificado por su conexión y PID registrados por el fixture (no un `sshd` global).
Con el consumidor local activo y sin salida pendiente, dentro de 2 s se captura la
línea literal y `display -p -t <pane> '#{pane_dead} #{pane_dead_status}'` imprime
`1 255`; un `send-keys` al otro pane se refleja en ≤ 100 ms. No quedan conexiones/fds
de transporte de ese pane. Una partición de red silenciosa que no genera EOF/error
no tiene detección acotada en esta v1: no se agregan keepalives/reconexión.

### FR-15 · Argumentos inválidos se rechazan antes de crear el pane

**Dado** un server on con un target local válido,
**cuando** el comando tiene aridad, flags o valores inválidos según el contrato,
**entonces** sale 1, informa el error por stderr y no crea pane ni transporte.

**VC-30:** ejecutar cada caso en el mismo estado inicial; guardar status/stdout/stderr,
IDs y fds antes/después. Stdout vacío, exit 1 y 0 panes/fds nuevos en todos:

| Invocación después de `tmux` | Stderr esperado |
|---|---|
| `ssh-pane` / `ssh-pane host extra` | `command ssh-pane: too few arguments (need at least 1)` / `command ssh-pane: too many arguments (need at most 1)` |
| `ssh-pane -X host` / `ssh-pane -p` | `command ssh-pane: unknown flag -X` / `command ssh-pane: -p expects an argument` |
| `ssh-pane ''`, `ssh-pane user@host`, `ssh-pane host:2222`, `ssh-pane ssh://host`, `ssh-pane '[::1]'` | `ssh-pane: invalid host` |
| `ssh-pane -p <valor> host`, valores `0`, `65536`, `-1`, `abc`, vacío y ` 22` | `ssh-pane: invalid port` |
| `ssh-pane -u '' host` / `ssh-pane -i '' host` | `ssh-pane: invalid user` / `ssh-pane: invalid identity path` |
| `ssh-pane -h -v host` | `ssh-pane: -h and -v are mutually exclusive` |

Con remain-on-exit on, casos válidos de parseo (sin prometer conexión): puertos
1 y 65535, `-- ::1` y opciones con valor repetidas. En `-p 0 -p 2222` gana 2222 y VC-2 conecta; inverso rechaza 0.
Exigir exit 0 y pane creado sin diagnóstico de validación para los casos válidos
de parseo; no inferir autenticación de ello. Se cancelan al finalizar.
Añadir host/usuario con espacios y un carácter de control: sus errores semánticos
son los de la tabla. Para default de puerto, omitir `-p` en el entorno exclusivo
sin servicio en 22; la traza de connect del server registra destino 127.0.0.1:22.
No usar el puerto del sshd 2222 como supuesto default.

### FR-16a · Dirección, posición y tamaño usan el layout común

**Dado** un target local tiled con espacio para dividir,
**cuando** `ssh-pane` usa dirección, `-b` o `-l` válidos,
**entonces** la geometría es la de un split local equivalente, sin interpretar el
puerto como porcentaje de tamaño.

**VC-31a:** en sesiones separadas idénticas de 160×48, comparar dimensiones y posiciones
`pane_left`, `pane_top`, `pane_width`, `pane_height` entre split local y SSH para:
default, `-v`, `-h`, `-b -v`, `-b -h`, `-l 8`, `-l 25%`. Usar puerto 2222 **en todos**
los SSH; retirar ese `-p` del equivalente local. Mismo resultado de layout y VC-2
exitoso. Con `-l abc`, exit 1 y `invalid tiled geometry invalid`; con layout sin
espacio, exit 1 y `no space for a new pane`; con target floating, exit 1 y
`can't split a floating pane`. Esos rechazos no dejan pane/transporte nuevo.

### FR-16b · Target identifica la ventana a dividir

**Dado** dos ventanas y un target `<local>` explícito,
**cuando** se crea un pane con `-t <local>`,
**entonces** solo se divide la ventana de ese target.

**VC-31b:** guardar IDs por ventana; la del target añade solo el nuevo pane y la otra
conserva sus IDs. Exit 0 y VC-2 exitoso. Sin `-t`, comprobar el pane del contexto en
una sesión única del fixture. Target ID inexistente: exit 1, error del resolver
común `can't find pane: <id>` y 0 panes nuevos. No redefinir el resolver.

### FR-16c · La selección obedece la opción detached

**Dado** un target local y su pane activo registrado,
**cuando** se abre un pane SSH con o sin `-d`,
**entonces** con `-d` se conserva el activo anterior y sin `-d` se activa el nuevo.

**VC-31c:** dos corridas desde el mismo estado inicial, una por variante; exit 0,
selección esperada y VC-2 exitoso en el nuevo pane. Identificarlo por `-P` aunque no
esté activo. Esta opción no se confunde con una sesión SSH sin PTY.

### FR-16d · Print devuelve la ubicación del nuevo pane

**Dado** un comando de apertura válido,
**cuando** se ejecuta con o sin `-P`,
**entonces** solo con `-P` imprime la ubicación según el template fijo del contrato.

**VC-31d:** cuatro combinaciones de `-d` y `-P`: exit 0; con `-P`, una sola línea
coincide con el template y resuelve al ID nuevo; sin `-P`, stdout vacío. Cada pane
pasa VC-2. Repetir apertura exitosa omitiendo `-u`: log de sshd confirma TP2_USER,
la cuenta del server, y se obtiene la marca remota. FR-15 cubre que un error de
argumentos no imprime ubicación de éxito.

### FR-17 · Una identidad inutilizable o rechazada no dispara fallback

**Dado** host confiable y remain-on-exit on,
**cuando** `-i` apunta a una ruta inexistente, archivo ilegible, contenido inválido,
clave con frase o clave válida no autorizada,
**entonces** el pane termina con `ssh-pane: authentication failed` y status 255,
sin prompt ni intentos con otras identidades o agent.

**VC-32:** corrida separada por cada variante, exit del comando 0, línea exacta y
`pane_dead=1`, `pane_dead_status=255` dentro de 5 s. Tmux es no root para que 0000
sea realmente ilegible. Además repetir sin `-i` (VC-5), con identidad default válida
instalada en el home y un socket agent señuelo: sigue fallando, sin conexión al socket
ni apertura de esa identidad default. Stdin del server no proporciona una frase;
el otro pane sigue atendido. La clave con frase no produce espera ni prompts.
Repetir caso exitoso con ruta relativa a cwd del cliente, incluso con un espacio
en el nombre correctamente entrecomillado; obtiene el mismo resultado de VC-2.

### FR-18 · Falta o error de confianza no autentica ni escribe

**Dado** un host del fixture y remain-on-exit on,
**cuando** known_hosts está ausente o no es legible por el UID del server,
**entonces** falla antes de autenticar con el mismo diagnóstico/status de FR-6a;
no crea, repara ni actualiza known_hosts.

**VC-33:** una corrida por variante, exit 0 de apertura; dentro de 5 s línea exacta,
`pane_dead=1`, status 255 y 0 solicitudes userauth de esa conexión. Ausente permanece
ausente; ilegible conserva bytes/permisos. Repetir FR-6a/6b con una entrada correcta
en `/etc/ssh/ssh_known_hosts` **solo dentro del entorno desechable**: sigue rechazando
el host, porque la v1 no usa esa fuente. VC-14 confirma ausencia de escrituras.

### FR-19 · Rechazar PTY termina la apertura

**Dado** el fixture con clave/host válidos, remain-on-exit on y `PermitTTY no`,
**cuando** se intenta abrir un pane SSH,
**entonces** no se abre shell sin PTY como alternativa; el pane termina con
`ssh-pane: connection failed: pty` y status 255.

**VC-34:** sshd -T confirma PermitTTY no en una corrida separada; guardar exit 0,
aceptación publickey y rechazo de PTY en el log. Dentro de 5 s hay línea exacta,
`pane_dead=1`, status 255; el server sigue vivo y el transporte se libera. Restaurar
PermitTTY yes al terminar. Errores de canal/shell conservan sus etapas de la tabla;
no se presume que este fixture OpenSSH permita inducir todos sus rechazos.

### BR-1 · `known_hosts` es solo lectura

`tmux` nunca escribe en `known_hosts` ni en ningún archivo bajo `~/.ssh`.

**VC-14:** adjuntar `strace -f -e trace=openat,open,creat,rename,renameat,unlink,unlinkat`
al server existente **antes** del escenario y guardar la traza en TP2_ROOT. Ejecutar
FR-2, FR-6a, FR-6b y FR-18, por separado: 0 aperturas en `~/.ssh` con O_WRONLY/O_RDWR/
O_CREAT y 0 creaciones/renombrados/borrados allí. Registrar también inventario,
SHA-256 y permisos antes/después (ausente sigue ausente). La preparación de claves
ocurre antes de iniciar esta traza; trazar solo el cliente tmux no prueba el server.

### BR-2 · Sin secretos en logs ni en argumentos

La ruta de `-i` puede aparecer en logs; **el contenido de una clave y su frase, nunca**.

**VC-15:** con `tmux -vv`, `grep -c 'BEGIN OPENSSH PRIVATE KEY' tmux-server-*.log` da `0`.

### NFR-1 · El event loop no se bloquea por la red

Mientras una conexión SSH está en curso, los demás panes siguen atendidos.

**VC-16:** con `ssh-pane -p 2224 127.0.0.1` contra el listener sin banner del
entorno común (aceptación registrada, IP literal para excluir DNS), un `send-keys`
a otro pane se refleja en `capture-pane` en **≤ 100 ms**,
medido 20 veces.

### NFR-2 · Timeout de apertura

La apertura se abandona a los **10 s** si no alcanzó el estado Activo (conexión,
handshake, auth, canal, PTY y shell). El deadline empieza al publicar el pane y no
se reinicia por etapa. La condición medible usa IP literal y archivos locales
accesibles; no garantiza el tiempo de DNS/filesystem síncronos. FR-13b referencia
este mismo plazo para una apertura que no progresa.

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

### NFR-4 · Colas propias del bridge acotadas

La cola local → remoto y la cola remoto → local del bridge contienen **≤ 1 MiB cada
una**, también con contrapresión; reanudan recepción al bajar a **≤ 512 KiB**.
Son colas propias, no una cota sobre buffers internos de tmux/libssh ni sobre todo
el RSS del server. La pausa conserva el contenido y las escrituras parciales no
lo duplican; `kill-pane` cancela sin esperar al consumidor.

**VC-27:** en el fixture de FR-2, ejecutar dos corridas separadas: bloquear durante
1 s al consumidor de salida con un cliente control que no lee (patrón de
`regress/respawn-pane-control-lag.sh`), con 8 MiB de salida remota; y detener durante
1 s el consumo de entrada del PTY remoto, con 8 MiB de entrada al pane. Los logs de
prueba `-vv` registran máximos `tx_bytes`/`rx_bytes` y transiciones `pause`/`resume`
con dirección y bytes, calculados sobre las **longitudes reales** de ambas colas,
sin contenido de datos/claves. Se exige máximo ≤ 1 MiB, pausa al llenar
y reanudación solo a ≤ 512 KiB, en ambas direcciones. Después de reanudar, la salida
incluye una marca final calculada que no coincide con el eco; el server sigue vivo.
La entrada se verifica en un PTY remoto en modo no canónico y sin eco, con longitud
y hash de los bytes recibidos iguales al payload enviado; no se confunde el límite
de una línea del terminal con una pérdida del bridge. La prueba de RSS sigue siendo
VC-18. Registrar la salida completa mediante `pipe-pane` hacia un archivo temporal
del fixture y comparar longitud/hash del segmento de payload entre marcas, con
postprocesamiento de salida del PTY desactivado para ese segmento. Una marca final
sola no prueba ausencia de pérdidas o duplicados. Durante pausa/reanudación, repetir
en el otro pane local el chequeo de latencia de NFR-1: ≤ 100 ms, 20 veces.

## Plan de iteraciones

| Iteración | Alcance | Cierra |
|---|---|---|
| **1** | Guarda de build: `--enable-ssh`, `AM_CONDITIONAL`, `cmd-ssh-pane.c` vacío que registra el comando y responde "not implemented" | INV-1, INV-2, INV-3, INV-4, INV-8, FR-1, FR-9 |
| **2** | Bridge: apertura, host key, auth, `socketpair`, enganche en `spawn_pane` y cierre/cancelación mínimos de recursos | FR-2, FR-3, FR-4b, FR-5, FR-6a, FR-6b, FR-11b, FR-13a, FR-13b, BR-1, BR-2, NFR-1, NFR-2 |
| **3** | I/O completo: resize, salida, destrucción, `respawn-pane` | FR-7a, FR-7b, FR-8, FR-10a, FR-10b, FR-11, FR-12, FR-14, NFR-3, NFR-4, INV-5, INV-6, INV-7 |
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
