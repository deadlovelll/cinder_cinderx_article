import subprocess
import sys


def compile_snippet(path: str, modname: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "cinderx.compiler", "--static", path,
         "--modname", modname],
        capture_output=True, text=True, timeout=180,
    )
    diagnostic, kind = "", ""
    for line in reversed(proc.stderr.splitlines()):
        if "Error:" in line:
            diagnostic = line.strip()
            kind = line.split(":", 1)[0].rsplit(".", 1)[-1]
            break
    return {
        "rejected": proc.returncode != 0,
        "exit_code": proc.returncode,
        "diagnostic": diagnostic or "(no diagnostic line found)",
        "error_kind": kind,
    }
