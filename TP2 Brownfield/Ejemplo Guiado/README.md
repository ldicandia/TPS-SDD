# Ejemplo guiado — Lección 2 · `clear-history` en `fzf`

**El caso:** agregar una acción `clear-history` a [`fzf`](https://github.com/junegunn/fzf),
el buscador difuso de terminal. Un cambio brownfield real sobre 33.000 líneas de Go que no
escribimos nosotros.

**Lo mejor de este ejemplo:** `fzf` es público. Cloná una copia y **verificá cada
afirmación de las notas vos mismo**, línea por línea. Unas notas de exploración que no se
pueden chequear no sirven de nada — así que chequealas.

```bash
git clone --depth 1 https://github.com/junegunn/fzf.git
```

Tu tarea es otra (`tmux` con SSH nativo), a propósito. Acá venís por la forma.

## Los tres archivos, en orden

| # | Archivo | Paso SDD | Qué mirar |
|---|---|---|---|
| 1 | [`notas-exploracion.md`](./notas-exploracion.md) | Descubrir | Archivos y funciones **reales**, producidos en modo solo lectura |
| 2 | [`spec-brownfield.md`](./spec-brownfield.md) | Especificar | Fuera de alcance con paths, invariantes, línea de base de regresión |
| 3 | [`context-capsule.md`](./context-capsule.md) | Congelar | Descubrimiento destilado para el próximo cambio |

## El recorrido guiado

### Paso 1 · Verificá las notas contra el repo

Cloná `fzf` y elegí **dos afirmaciones al azar** de `notas-exploracion.md`. Abrí los
archivos que citan. ¿Está la función donde dice? ¿Hace lo que dice?

Empezá por el hallazgo 3, el del enum generado:

```bash
head -1 src/actiontype_string.go     # ¿dice "DO NOT EDIT"?
grep -n "go:generate" src/terminal.go
```

Esto no es un ejercicio de desconfianza: es exactamente lo que se corrige en la tarea.
Unas notas que describen un repo imaginario son peores que no tener notas, porque el
agente las va a creer.

> Las notas se escribieron sobre el commit `b1be3a8`. Los números de línea pueden haberse
> corrido; los nombres de archivo y de función son lo estable. Si un número no coincide,
> eso también es un hallazgo: las referencias frágiles envejecen.

### Paso 2 · Seguí el camino de una acción

El corazón del descubrimiento es un solo mapa: **cómo viaja una acción** desde
`--bind 'tecla:accion'` hasta que se ejecuta. Son cuatro lugares.

Recorrelo vos con una acción que ya existe, `prev-history`:

```bash
grep -n '"prev-history"' src/options.go      # el parseo
grep -n 'actPrevHistory' src/terminal.go     # la constante y el dispatch
```

Cuando podés recorrer ese camino solo, entendiste el repo lo suficiente para cambiarlo. Y
solo eso: las otras 8.800 líneas de `terminal.go` siguen siendo terreno desconocido, y
está bien.

### Paso 3 · Las tres secciones que no existen en greenfield

Abrí `spec-brownfield.md` y buscalas. Son la diferencia entre la Lección 1 y la 2:

- **Fuera de alcance** — con *paths concretos*. No "no tocamos el resto": los archivos que
  el agente no puede abrir.
- **Invariantes** — qué no puede cambiar pase lo que pase, cada uno **con su forma de
  comprobarlo**. Un invariante que no se chequea no es un invariante.
- **Línea de base de regresión** — `make test`, `make lint` y el test de integración del
  historial, corridos *antes* de tocar nada. Sin eso no podés afirmar que no rompiste nada.

**La pregunta:** si le pasás esta spec a un agente y lo dejás solo, ¿qué es lo peor que
podría hacer? Si la respuesta es "nada grave", el alcance está bien acotado.

### Paso 4 · Mirá el tamaño de la capsule

`context-capsule.md` tiene ~70 líneas. La spec tiene ~150 y las notas ~190: juntas, más de
300.

Eso no es descuido: es el punto. La capsule entra en la ventana de contexto de la próxima
tarea **junto con todo lo demás**. Si fuera tan larga como la spec, nadie la cargaría y el
descubrimiento se pagaría de nuevo.

Comparala con las notas: fijate qué sobrevivió y qué se tiró.

## Hacelo vos

Elegí un repo que **no** escribiste vos. Cualquier proyecto open source chico sirve. No
uses `tmux`: eso es la tarea.

```
1. Poné al agente en modo SOLO LECTURA. Que no edite nada todavía.
2. Pedile notas de exploración de un cambio chico y concreto.
3. Verificá dos afirmaciones vos mismo. Si fallan, las notas no sirven.
4. Escribí la spec: alcance dentro/fuera con paths, invariantes, línea de base.
5. Parate ahí. No implementes.
```

**Señal de que te salió:** otro equipo podría construirlo desde tu spec sin hablar con
vos.

**Señal de que no:** el fuera de alcance dice algo genérico como "no se incluye UI", o las
notas describen el repo en abstracto, sin nombrar un archivo.

## El error más común

Ponerse a implementar. El valor de esta clase está en descubrir y acotar, y el músculo que
entrena es el de aguantarse las ganas de escribir código. En la tarea eso se corrige
explícitamente.
