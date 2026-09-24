"""Shell falso para os testes do terminal_handler: ecoa stdin e o redimensionamento."""

import os
import select
import sys

readers = [sys.stdin.fileno(), 3]
while readers:
    ready, _, _ = select.select(readers, [], [])
    for fd in ready:
        data = os.read(fd, 1024)
        if not data:
            readers.remove(fd)
            continue
        text = data.decode().strip()
        label = "eco" if fd != 3 else "tamanho"
        sys.stdout.write(f"{label}: {text.replace(' ', 'x')}\n")
        sys.stdout.flush()
