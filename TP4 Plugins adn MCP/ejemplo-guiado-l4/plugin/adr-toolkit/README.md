# Plugin `adr-toolkit`

El toolkit de ADRs de las Lecciones 3 y 4 —skills, subagents, hooks y el server MCP de
Postgres— empaquetado como **un plugin**: se instala como una unidad, con versión.

Es el ejemplo de la slide "¿Qué es un plugin?". Convertirlo es mover archivos, y por eso
acá **no se duplican**: `armar.sh` los copia desde los ejemplos guiados. Lo commiteado es
lo que **cambia** al empaquetar.

| Archivo | Qué cambia respecto del toolkit en `.claude/` |
|---|---|
| `.claude-plugin/plugin.json` | El nombre, que pasa a ser prefijo de todo: `/adr-toolkit:write-adr-con-datos` |
| `.mcp.json` | La credencial ya no viene del entorno: es `userConfig` con `"sensitive": true`. El cliente se la pide a cada usuario y la guarda en su almacén seguro; nunca viaja en el paquete |
| `hooks/hooks.json` | El matcher del muro: `mcp__plugin_adr-toolkit_postgres__.*`, no `mcp__postgres__.*` |
| `armar.sh` | Copia los archivos y renombra las tools MCP en `allowed-tools` y `tools` |

## Armarlo y probarlo

```bash
./armar.sh
claude plugin validate .        # tiene que decir "Validation passed"
claude --plugin-dir .           # lo carga en esta sesión, sin publicarlo
```

Al habilitarlo, Claude Code pide la URI de la base (el rol `turnos_lector`). Después:

1. `/mcp` — aparece el server `postgres` del plugin, con las mismas nueve tools.
2. `/plugin` — muestra los skills, agents, hooks y el server que trae, antes de usarlo.
3. **Repetí la prueba del muro.** Pedí "creá el índice con `execute_sql`": lo tiene que
   vetar el hook, ahora con el nombre nuevo de la tool. Un matcher que no matchea no
   avisa: simplemente no veta. Y aunque fallara, el rol de solo lectura sigue abajo.

## Lo que hay que saber antes de instalar uno ajeno

Un plugin habilitado es parte de **cada sesión**: las descriptions de sus skills y
agents ocupan ventana, su server arranca, sus hooks disparan y todo corre con tus
permisos. Este, por ejemplo, suma el schema de nueve tools —unos 9.500 tokens estimados—
aunque esa sesión no toque la base. Deshabilitado no ocupa nada.
