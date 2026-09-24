"""Pseudo-terminal para o terminal web do sandbox (terminal_handler.js).

Uso: python3 terminal_pty.py <cols> <rows>
- stdin  → teclado do shell
- stdout ← saída do shell (bytes crus do terminal)
- fd 3   ← controle, uma linha por redimensionamento: "<cols> <rows>\\n"
Sai com o código do shell quando ele termina.
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios

CONTROL_FD = 3


def set_size(fd: int, cols: int, rows: int) -> None:
    cols, rows = max(20, min(cols, 500)), max(5, min(rows, 200))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def main() -> int:
    cols, rows = (int(v) for v in sys.argv[1:3]) if len(sys.argv) >= 3 else (120, 32)
    pid, master = pty.fork()
    if pid == 0:
        os.execvp("bash", ["bash", "-l"])
    set_size(master, cols, rows)
    readers = [master, sys.stdin.fileno(), CONTROL_FD]
    control = b""
    while True:
        ready, _, _ = select.select(readers, [], [])
        if master in ready:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if not data:
                break
            os.write(sys.stdout.fileno(), data)
        if sys.stdin.fileno() in ready:
            data = os.read(sys.stdin.fileno(), 65536)
            if not data:
                readers.remove(sys.stdin.fileno())
            else:
                os.write(master, data)
        if CONTROL_FD in ready:
            chunk = os.read(CONTROL_FD, 1024)
            if not chunk:
                readers.remove(CONTROL_FD)
            control += chunk
            while b"\n" in control:
                line, control = control.split(b"\n", 1)
                parts = line.split()
                if len(parts) == 2 and all(p.isdigit() for p in parts):
                    set_size(master, int(parts[0]), int(parts[1]))
                    os.kill(pid, signal.SIGWINCH)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
