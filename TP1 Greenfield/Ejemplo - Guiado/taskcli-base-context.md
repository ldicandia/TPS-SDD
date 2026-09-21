# taskcli — base context

> **Qué es esto.** La salida de la fase *previa* al pipeline: requerimientos
> refinados, notas de diseño y esquema de arquitectura. **No es la spec.** Es la
> materia prima con la que se construye, y es lo que consume el paso Especificar.
>
> Corresponde a la slide "Idea vaga → base context" de la Lección 1.

## La idea vaga con la que empezó

> "Un CLI que me recuerde tareas."

Eso es todo lo que había. Lo que sigue es el resultado de interrogar esa idea con
el agente, decidiendo nosotros en cada bifurcación.

---

## 1 · Requerimientos refinados

**¿Qué problema resuelve?**
Anotar tareas pendientes sin salir de la terminal y sin abrir una app. El costo de
cambiar de contexto para anotar algo es lo que hace que uno no lo anote.

**¿Para quién?**
Una sola persona, en su propia máquina. No hay equipos, ni cuentas, ni sincronización.

**¿Quién lo ejecuta?**
Una persona desde una shell interactiva, y eventualmente un script (por eso los exit
codes importan).

**¿Qué comandos hacen falta?**
Tres, y ninguno más en la v1: agregar una tarea, listar las tareas, marcar una como
hecha. Editar, priorizar, poner fechas y etiquetar son ideas para después.

**¿Qué persiste, y dónde?**
Las tareas sobreviven entre invocaciones. Un archivo en el home del usuario.

**¿Qué pasa con input inválido?**
Título vacío, título gigante, ID que no existe, ID que no es un número. Cada uno
tiene que fallar de forma predecible, no reventar con un stack trace.

**¿Qué pasa con el store vacío?**
Listar sin tareas no es un error: es una lista vacía. Tiene que decirlo con claridad
y salir con éxito.

**¿Qué pasa la primera vez que corre?**
No hay archivo todavía. Lo tiene que crear solo, sin que el usuario haga un `init`.

**Restricciones**
- Sin servicios externos, sin red.
- Sin base de datos: el archivo lo tiene que poder abrir una persona con un editor.
- Tiene que arrancar rápido; un CLI que tarda un segundo en abrir no se usa.

---

## 2 · Notas de diseño

### Formato de almacenamiento

**Elegido: JSON, un archivo, en `~/.taskcli/tasks.json`.**

Fundamento: legible por humanos, parseable por cualquier lenguaje, y sin
dependencias. El usuario puede abrirlo, entenderlo y arreglarlo a mano si algo se
rompe.

Opciones descartadas, y por qué:

| Opción | Por qué no |
|---|---|
| SQLite | Resuelve concurrencia y queries que no tenemos. Agrega una dependencia binaria y el archivo deja de ser legible. |
| Texto plano, una tarea por línea | Más simple de escribir, pero se rompe apenas un título tenga un salto de línea, y no hay dónde guardar el estado de completado sin inventar un formato. |
| YAML | Legible, pero agrega una dependencia de parseo y su ambigüedad (`no` parsea como booleano) para un beneficio nulo acá. |

### Superficie de comandos

**Elegido: tres subcomandos.**

```
taskcli add "<título>"
taskcli list
taskcli done <id>
```

Fundamento: mapea uno a uno con las tres cosas que se quieren hacer. Un verbo por
comando, sin flags en la v1.

Descartado: un comando único con flags (`taskcli --add "..."`). Se lee peor y no
escala a más operaciones.

### Identificadores

**Elegido: enteros incrementales, asignados al crear, que nunca se reusan.**

Fundamento: hay que poder tipearlos. `taskcli done 3` es usable; `taskcli done
f47ac10b-58cc-4372-a567-0e02b2c3d479` no lo es.

Consecuencia aceptada: si borrás la tarea 3, el ID 3 queda libre para siempre y hay
huecos en la numeración. Preferimos huecos a que un ID cambie de significado.

### Estrategia de errores

**Elegido: mensaje a stderr, exit code distinto de cero, y el store sin tocar.**

Fundamento: un CLI tiene que servir dentro de un script. La regla que queremos es
"si falló, no cambió nada" — nunca una escritura a medias.

Convención de exit codes:

| Código | Significado |
|---|---|
| `0` | La operación salió bien |
| `1` | Error de uso: input inválido, ID inexistente, regla de negocio violada |
| `2` | Error de sistema: no se puede leer o escribir el archivo, JSON corrupto |

### Duplicados

**Elegido: dos tareas pendientes no pueden tener el mismo título.**

Fundamento: si estás anotando "comprar leche" por segunda vez, casi siempre es
porque te olvidaste de que ya estaba, no porque quieras dos. Rechazar y avisar es
más útil que aceptar en silencio.

Excepción decidida: **las tareas completadas no cuentan.** Podés volver a agregar
"comprar leche" la semana que viene.

---

## 3 · Esquema de arquitectura

### Módulos

```
cli        → parsea argv, despacha al subcomando, traduce errores a exit codes
core       → reglas de negocio: validar, agregar, listar, completar
store      → leer y escribir el archivo JSON; nada de reglas de negocio acá
```

La dependencia va en una sola dirección: `cli → core → store`. `core` no sabe que
existe una terminal, y `store` no sabe qué es una regla de negocio. Eso es lo que
hace testeable a `core` sin tocar disco ni argv.

### Flujo de datos

```
argv → cli (parsea) → core (valida + aplica la regla) → store (lee/escribe)
                              ↓
                      resultado o error
                              ↓
                   cli (formatea) → stdout/stderr + exit code
```

### Actores

| Actor | Interacción |
|---|---|
| Persona usuaria | Ejecuta comandos en una shell interactiva y lee la salida |
| Script | Ejecuta comandos y decide en base al **exit code**, no al texto |
| Sistema de archivos | Guarda el store; puede fallar (permisos, disco lleno) |

### Riesgo conocido

Dos invocaciones simultáneas podrían pisarse la escritura. **Decisión: fuera de
alcance en la v1** — es un CLI de un solo usuario y el caso es improbable. Queda
anotado acá para que sea una decisión consciente y no un olvido, y aparece como
no-objetivo explícito en la spec.

---

## Qué sigue

Este documento alimenta el paso **Especificar**. El resultado está en
[`taskcli-spec.md`](./taskcli-spec.md).

Fijate qué cambia al pasar de acá a la spec: acá hay prosa, opciones y fundamentos;
allá hay requerimientos atómicos, cada uno con un chequeo observable. El base
context explica *por qué*; la spec define *qué* y *cómo se verifica*.
