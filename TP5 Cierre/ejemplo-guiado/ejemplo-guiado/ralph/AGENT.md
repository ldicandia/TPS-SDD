# AGENT.md — cómo se construye y se prueba taskcli

## Correr

```bash
python3 -m taskcli add "comprar leche"
python3 -m taskcli list
python3 -m taskcli done 1
```

## Probar

```bash
python3 -m pytest -q
```

Cada test se llama `test_vc_NN_<qué verifica>` y cubre un VC de la spec. La suite es la
**contrapresión** del loop: una vuelta que la deja roja no terminó.

## Estructura

- `taskcli/cli.py` — parseo de argumentos y exit codes
- `taskcli/core.py` — reglas (IDs, títulos, duplicados)
- `taskcli/store.py` — lectura y escritura de `tasks.json`
- El store vive en `~/.taskcli/tasks.json` (spec, VC-7). Los tests corren con `HOME`
  apuntando a un directorio temporal: nunca tocan el store real.

## Aprendizajes de las vueltas anteriores

<!-- Una línea por aprendizaje. Las agrega el agente. -->
