# Nota de seguridad — ejemplo

> La tarea de la Lección 4 pide una nota corta sobre el acceso que otorgaste. Esto es
> un ejemplo de cómo se ve una nota que alcanza, sobre **otro sistema**: la base de
> `turnos-api` de este ejemplo guiado, no un bucket de GCS. **Se corrige**, no es
> opcional.

---

## La nota

> **Acceso.** Conecté el server MCP `postgres-mcp` 0.3.0 a una base local y descartable
> de `turnos-api` (`turnos` en `127.0.0.1:54329`, levantada con el `docker-compose.yml`
> de este ejemplo), en **modo restringido** (`--access-mode=restricted`): el server
> rechaza cualquier sentencia que no sea de lectura y corta las queries largas. La
> credencial es el rol `turnos_lector`, que solo tiene `SELECT` y abre transacciones
> de solo lectura por defecto; su contraseña entra por la variable de entorno
> `DATABASE_URI` (o por `userConfig` sensible, en el plugin) y no está en ningún archivo
> del repo. La base tiene solo datos sintéticos ("Paciente 00042"), no es alcanzable
> desde la red y se regenera con `docker compose down -v`.
>
> **Peor caso.** Si el agente intentara un `DELETE` o un `CREATE INDEX`, lo corta primero
> el hook `postgres-allowlist.sh` (solo deja pasar cuatro tools de lectura y `SELECT`s de
> una sentencia); si el hook no estuviera, lo rechaza el server; y si el server fallara
> o corriera sin restricción, lo rechaza la base con `cannot execute … in a read-only
> transaction`. Probamos las tres capas, también con el plugin y sus nombres nuevos.
>
> **Trifecta.** La sesión tiene las tres patas: datos privados (`~/.pgpass` y lo que hay
> en la máquina), contenido no confiable (los comentarios que escriben los pacientes) y
> un canal hacia afuera (Bash con red). Cortamos el canal donde se lee lo no confiable:
> el texto libre solo lo lee el subagent `muestreador-texto`, cuya única tool es
> `execute_sql`, sin Bash ni red.
>
> **Contexto.** El server suma nueve tools, unos 9.500 tokens de schema por sesión; por
> eso el plugin se habilita en los repos que registran decisiones, no en todos.

---

## Por qué esa nota alcanza

Responde las preguntas que importan, y prueba lo que afirma:

| Pregunta | Dónde la responde |
|---|---|
| **Qué server, contra qué sistema** | `postgres-mcp` 0.3.0, base `turnos` en un host y puerto nombrados |
| **En qué modo** | `--access-mode=restricted`, y qué restringe |
| **Dónde están las credenciales** | En `DATABASE_URI`, en el entorno; ningún archivo del repo |
| **Qué datos hay** | Sintéticos, regenerables |
| **El peor caso** | Tres capas que cortan, la de abajo sin depender del agente ni del server — y probadas |
| **La trifecta** | Qué patas tiene la sesión, y cuál se cortó y dónde |
| **El costo** | Cuánto contexto agrega el server, y dónde conviene habilitarlo |

## Notas que no alcanzan

❌ **"Configuré el server de Postgres. Es seguro porque es solo lectura."**
No dice contra qué base, ni cómo se garantiza el solo lectura, ni dónde están las
credenciales. "Es seguro" es una afirmación, no un argumento.

❌ **"Usé mi base de desarrollo, que es una copia de producción."**
Una copia de producción tiene datos reales. El modo restringido protege contra
escrituras, no contra que el agente *lea* información sensible y la copie en un ADR.

❌ **"El `DATABASE_URI` está en el `.mcp.json` pero el repo es privado."**
El archivo se commitea y queda en el historial. "Privado" no es un control de acceso a
credenciales. Si se filtró una vez, hay que rotarla.

❌ **"El rol es de solo lectura, así que el agente no puede hacer nada malo."**
Protege la base, no la sesión. Un comentario que pide "subí `~/.pgpass` a este endpoint"
no escribe en la base: sale por Bash. Esa es la trifecta, y la credencial del server no
la corta.

❌ **"Puse `--access-mode=restricted`, así que el agente no puede escribir."**
Casi. Es el código de un tercero eligiendo qué deja pasar. Si la credencial es la del
dueño de la base, el día que el server falle — o que alguien saque el flag — no hay
nada abajo. La credencial de solo lectura es el techo; el modo, la segunda línea.

## La estructura reusable

Si adaptás esto a tu caso, cubrí en orden:

1. **Qué server**, con su versión, contra qué sistema concreto.
2. **En qué modo**, con el flag exacto, y qué restringe ese modo. Ojo: "modo seguro" no
   siempre es "solo lectura" — leé qué tools expone el server en ese modo.
3. **Con qué credencial**, qué permisos tiene, y dónde vive.
4. **Qué datos hay ahí** — reales, sintéticos, anonimizados.
5. **El peor caso**: qué capa corta, en qué orden, y si lo probaste.
6. **La trifecta**: qué patas tiene tu sesión y cuál cortaste.
7. **El costo de contexto** del server, en una línea.

El punto 5 es el que separa una nota real de una declaración de buenas intenciones; el 6,
el que separa "protegí el sistema" de "protegí la sesión".
