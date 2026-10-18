# ¿Lo dejarías correr de noche?

El ejercicio de la Lección 5, en equipo y en clase (20 minutos). Tomen **su** toolkit de
`gcsgrep` —el de las Lecciones 1 a 4— y respondan, con evidencia de su repo, si un agente
podría avanzar la próxima iteración **sin que nadie lo mire**.

Cada fila es una pregunta de la materia. Si la respuesta es "no", anoten qué falta y en qué
clase se vio.

| # | Pregunta | Sí / No | Dónde está (path o comando) | Si no: qué falta |
|---|---|---|---|---|
| 1 | **Intención.** ¿Hay una spec con VCs que el agente lee en cada vuelta, sin depender del chat? (L1) | | | |
| 2 | **Estado.** ¿Hay un plan en disco que diga qué falta, en orden, y que el agente actualice? (L1) | | | |
| 3 | **Contrapresión.** ¿Hay una suite que se corre con un comando y que rechaza lo que no cumple un VC? (L1, L2) | | | |
| 4 | **Tests intocables.** ¿Qué impide que el agente borre o debilite un test para pasar? Una instrucción no alcanza: ¿hay un hook? (L3) | | | |
| 5 | **Alcance.** ¿El agente sabe qué está fuera de alcance y qué no puede tocar (invariantes, paths)? (L2) | | | |
| 6 | **Permisos.** ¿Qué herramientas tiene? ¿Puede instalar, salir a la red, pushear? ¿Por qué cada una? (L3, L4) | | | |
| 7 | **Credenciales.** ¿Con qué cuenta toca el bucket? ¿Es la mínima? ¿Dónde vive? (L4) | | | |
| 8 | **Contenido no confiable.** ¿Lee algo escrito por otros (objetos, issues, docs)? ¿Desde dónde, con qué herramientas? (L4, la trifecta) | | | |
| 9 | **Lo que corre sin preguntar.** En `claude -p`, ¿qué hooks, servers y plugins se cargan solos en su repo? (L4, L5) | | | |
| 10 | **Techo.** ¿Hay límite de vueltas, de gasto y de tiempo? ¿Qué pasa al llegar? (L5) | | | |
| 11 | **Evidencia.** Mañana a la mañana, ¿cómo saben qué hizo, con qué, y por qué? Commits, logs, receipts (L4, L5) | | | |
| 12 | **El gate humano.** ¿Qué decisión **nunca** toma el agente solo? ¿Dónde está escrito y qué la hace cumplir? (L5) | | | |

## La puesta en común

Cada equipo dice en voz alta:

1. Su **peor "no"**: la fila que más miedo da dejar sin resolver.
2. Si es **persuasión o garantía**: ¿lo arreglarían con una línea en el prompt o con algo
   que el agente no puede saltear?
3. La **una cosa** que agregarían antes de soltarlo una noche.

## La vara

Doce "sí" no es la meta. Un equipo que tiene seis "no", sabe cuáles son, y sabe qué capa los
cierra, entendió la materia.
