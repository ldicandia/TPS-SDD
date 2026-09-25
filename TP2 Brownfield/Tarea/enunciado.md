# Tarea Lección 2 — `tmux` con SSH nativo

**En equipo de trabajo.** Se entrega antes de la Lección 3 · [cómo se entrega](../../entrega.md)

## Qué hay que hacer

Agregá un **cliente SSH nativo** al codebase real de
[`tmux`](https://github.com/tmux/tmux): que un pane abra una sesión remota **sin
invocar** el binario `ssh`. **Solo Linux.**

| | |
|---|---|
| 🌿 **El repo** | Un proyecto C maduro de ~60k líneas: event loop, modelo de PTY/panes, tabla de comandos y una capa de portabilidad que vos no escribiste |
| 🎯 **El cambio** | Un comando nuevo que abre un pane con SSH de forma nativa (pensá `libssh`) en vez de correr `ssh` en una shell |

> **"Solo Linux" no es un detalle** — es el límite de alcance sobre el que gira toda la
> spec.

## No lo implementes

**El entregable es el análisis y la spec.** Nada de C.

No es una restricción arbitraria: el punto de esta clase es entrar a un repo de 60k
líneas, encontrar la superficie de cambio acotada, y escribir una spec desde la que
otro equipo podría construir sin romper los builds de macOS y BSD. Implementar SSH son
semanas, y no es lo que se evalúa.

Si empezaron a escribir C, se perdieron el ejercicio — y así se corrige.

## Cómo encararlo

### 1 · Explorar (solo lectura, con agente)

Poné al agente en modo solo lectura y mapeá el terreno antes de escribir una línea de
spec:

- Trazá cómo un pane nuevo lanza su proceso hijo, de la tabla de comandos al
  `fork`/`exec`.
- ¿Cómo aísla `tmux` el código específico de plataforma? Buscá la capa `compat/` y los
  chequeos de `configure`.

### 2 · Analizar y acotar

Nombrá la superficie de cambio y dibujá el límite "solo Linux" de forma explícita.
Las decisiones que hay que tomar:

- ¿entrada nueva en la tabla de comandos?
- ¿dónde engancha en el camino de spawn del pane?
- ¿`libssh` u OpenSSH?
- ¿cómo se integra con el event loop?
- ¿auth por claves o por agent?
- ¿qué guarda de build deja afuera a no-Linux?

**Invariantes que la spec tiene que declarar:** los builds no-Linux siguen compilando
(el feature se compila afuera), y ni los comandos existentes ni el modelo de PTY/panes
cambian.

## Qué se entrega

| Artefacto | Qué tiene que contener |
|---|---|
| **Notas de exploración** | Módulos tocados, interfaces reusadas (camino de spawn, tabla de comandos, event loop), riesgos y la historia de compat/build — con archivos y funciones **reales** |
| **Spec brownfield** | Alcance dentro/fuera explícito, el **límite solo-Linux**, invariantes, FRs + VCs, referenciando archivos reales del repo |
| **Sin implementación** | El valor está en el descubrimiento y el acotamiento |

## Antes de entregar

Mirá [`../ejemplo-guiado/README.md`](../ejemplo-guiado/README.md): el mismo flujo sobre
un cambio chico en [`fzf`](https://github.com/junegunn/fzf), que es público — así que
podés clonarlo y verificar cada afirmación de las notas vos mismo.
