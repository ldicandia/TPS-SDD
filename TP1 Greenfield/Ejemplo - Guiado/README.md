# Ejemplo guiado — Lección 1 · `taskcli`

**El caso:** un CLI de tareas para la terminal, resuelto de punta a punta con el
pipeline SDD completo. Es un proyecto **distinto** al de tu tarea (`gcsgrep`), a
propósito: acá venís a ver la *forma* que tiene un pipeline terminado, no a que te
resuelvan el tuyo.

Se puede seguir solo, sin haber empezado la tarea.

## Los cuatro archivos, en orden

Leelos en este orden. Cada uno es la entrada del siguiente — ese encadenamiento
**es** el pipeline.

| # | Archivo | Paso SDD | Qué mirar |
|---|---|---|---|
| 1 | [`taskcli-base-context.md`](./taskcli-base-context.md) | *previo* | Cómo una idea vaga ("un CLI que me recuerde tareas") se vuelve materia prima utilizable |
| 2 | [`taskcli-spec.md`](./taskcli-spec.md) | Especificar → Revisar | 15 requerimientos, 15 VCs, **cero huérfanos** |
| 3 | [`taskcli-plan.md`](./taskcli-plan.md) | Planificar | 4 iteraciones ordenadas por dependencia, no por entusiasmo |
| 4 | [`taskcli-cobertura-vc.md`](./taskcli-cobertura-vc.md) | Verificar | Qué cuenta como evidencia de que un VC pasó |

## El recorrido guiado

### Paso 1 · El base context no es la spec

Abrí `taskcli-base-context.md` y buscá la idea original arriba de todo. Son ocho
palabras. Todo el resto del archivo es lo que hubo que decidir para que esas ocho
palabras fueran construibles.

**La pregunta que te tenés que hacer:** ¿cuántas de esas decisiones las podría haber
tomado el agente por su cuenta sin que nadie se entere? Ese es exactamente el riesgo
que SDD ataca.

### Paso 2 · Seguí un requerimiento de punta a punta

Elegí **un** FR cualquiera de `taskcli-spec.md`. Uno solo. Ahora seguilo:

1. En la spec: ¿cuál es su VC? ¿Se puede observar, o es una intención?
2. En `taskcli-plan.md`: ¿en qué iteración cae? ¿Por qué en esa y no en la primera?
3. En `taskcli-cobertura-vc.md`: ¿con qué se lo ejercitó y qué se observó?

Si podés hacer ese recorrido completo para un requerimiento, entendiste el pipeline.
Hacelo con dos o tres más y ya no lo vas a olvidar.

### Paso 3 · Mirá lo que *no* está

- En la spec, la sección de alcance dice qué queda **afuera**. Sin eso, el agente
  llena el hueco solo.
- En el plan, el alcance diferido vive en el plan, no en la spec. La spec no miente
  sobre lo que se construyó.
- En la cobertura, ninguna fila dice "lo probé". Dicen con qué y qué se vio.

## Hacelo vos

El ejemplo se lee en veinte minutos. Correrlo te enseña diez veces más.

Elegí algo **chico** y tuyo — un script que ya tengas, una utilidad de tres comandos,
lo que sea. No uses `gcsgrep`: eso es la tarea, y conviene llegar ahí con la mano ya
hecha.

```
1. Escribí tu idea vaga en una línea.
2. Pedile a tu agente el base context. Respondé sus preguntas vos, no lo dejes suponer.
3. Pedile la spec. Contá los requerimientos y contá los VCs: tienen que dar igual.
4. Pedile el plan. Mirá si la iteración 1 se puede ejercitar sola de punta a punta.
5. Implementá SOLO la iteración 1 y armá la tabla de cobertura.
```

**Señal de que te salió:** podés borrar el chat entero, abrir la spec sola mañana, y
saber qué falta.

**Señal de que no:** la spec tiene un "TBD", o hay un requerimiento sin VC, o la
tabla de cobertura dice "verificado manualmente".

## El error más común

Escribir una spec preciosa y pasar directo a implementar todo junto. El plan existe
para que no lo hagas: una iteración chica, verificada, y recién ahí la siguiente. Ahí
es donde se contiene el drift del agente.
