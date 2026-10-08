"""Clasifica invocaciones directas de git commit, sin ejecutar el comando recibido.

stdin: evento PreToolUse JSON. stdout: commit / otro. Un commit que no se puede
inspeccionar con esta política produce exit 2 y un motivo en stderr.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


class UnsupportedCommit(ValueError):
    pass


def commit_target(words):
    """Devuelve los -C de un commit, o None si es otro comando."""
    args = list(words)
    wrapped = False
    while args and (args[0] in ("command", "exec", "env") or "=" in args[0]):
        wrapped = True
        args.pop(0)
    if not args or args[0].replace("\\", "/").rsplit("/", 1)[-1].lower() not in ("git", "git.exe"):
        return None
    dirs, unsupported = [], wrapped
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in ("-C", "-c"):
            if i + 1 >= len(args):
                return None
            if arg == "-C":
                dirs.append(args[i + 1])
            else:
                unsupported = True
            i += 2
        elif arg.startswith("-C"):
            dirs.append(arg[2:])
            i += 1
        elif arg.startswith("-c"):
            unsupported = True
            i += 1
        elif arg in ("--no-pager", "--paginate", "--literal-pathspecs", "--no-optional-locks"):
            i += 1
        elif arg.startswith("-"):
            if "commit" in args[i + 1:]:
                raise UnsupportedCommit("opción global de Git no soportada; usá git commit con -C opcional y sin overrides de configuración")
            return None
        else:
            if any(c in arg for c in "$`"):
                raise UnsupportedCommit("el subcomando de Git debe ser literal; no se evalúan variables ni escapes de PowerShell")
            if arg != "commit":
                return None
            if unsupported:
                raise UnsupportedCommit("commit con wrapper, variables de entorno u overrides -c; invocá git commit directamente desde el proyecto")
            return dirs
    return None


def command_groups(command):
    """Separa operadores fuera de comillas; conserva los argumentos para shlex."""
    groups, text = [], []
    quote, escaped, comment, separators = None, False, False, False
    for char in command.strip():
        if comment and char != "\n":
            continue
        comment = False
        if escaped:
            text.append(char)
            escaped = False
        elif char == "\\" and quote != "'":
            text.append(char)
            escaped = True
        elif quote:
            text.append(char)
            if char == quote:
                quote = None
        elif char in "'\"":
            text.append(char)
            quote = char
        elif char == "#" and (not text or text[-1].isspace()):
            comment = True
        elif char in ";&|()<>\n":
            groups.append(shlex.split("".join(text)))
            text = []
            separators = True
        else:
            text.append(char)
    groups.append(shlex.split("".join(text)))
    return groups, separators


def classify(command, project, cwd):
    # Esta es una gramática deliberadamente acotada, no un intérprete de shell.
    groups, separators = command_groups(command)
    targets = [target for group in groups if (target := commit_target(group)) is not None]
    if not targets:
        return "otro"
    if separators:
        raise UnsupportedCommit("separá el commit de las demás operaciones: ejecutá git add y después git commit en llamadas distintas; no uses &&, ;, pipes, redirecciones ni cambios de directorio en la misma llamada")
    # Comprobar el destino permite -C con comillas/espacios sin inspeccionar otro repo.
    target = cwd
    for directory in targets[0]:
        if any(c in directory for c in "$`*"):
            raise UnsupportedCommit("-C requiere una ruta literal; no se evalúan variables ni expresiones de shell")
        if not directory:
            continue  # git -C '' no cambia de directorio.
        if os.name == "nt" and len(directory) >= 3 and directory[0] == "/" and directory[1].isalpha() and directory[2] == "/":
            directory = directory[1] + ":" + directory[2:]
        target = (target / directory).resolve()

    def repo_root(directory):
        result = subprocess.run(["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
                                capture_output=True, check=True, timeout=5)
        return Path(os.fsdecode(result.stdout).strip()).resolve()

    if repo_root(target) != repo_root(project):
        raise UnsupportedCommit("el commit apunta a otro repositorio; abrí una sesión en ese proyecto con su propio hook")
    return "commit"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
        event = json.loads(sys.stdin.buffer.read())
        command = event["tool_input"]["command"]
        cwd = event.get("cwd", str(project))
        if not isinstance(command, str) or not isinstance(cwd, str):
            raise UnsupportedCommit("el evento no trae command/cwd legibles")
        print(classify(command, project, Path(cwd).resolve()))
        return 0
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, ValueError) else "no pude comprobar el repositorio de destino"
        if isinstance(error, (KeyError, TypeError)):
            reason = "el evento no trae tool_input.command legible"
        print("spec-gate: commit bloqueado: " + reason + ".", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
