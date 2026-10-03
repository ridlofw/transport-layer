#!/usr/bin/env python3
"""TCP demonstration: two sendall calls are not two receive records."""
import argparse
import socket

p = argparse.ArgumentParser()
p.add_argument("role", choices=["server", "client"])
a = p.parse_args()

with socket.socket() as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if a.role == "server":
        s.bind(("127.0.0.1", 5006))
        s.listen(1)
        print("READY on port 5006", flush=True)
        conn, _ = s.accept()
        with conn:
            chunks = []
            while True:
                part = conn.recv(4)
                if not part:
                    break
                print("recv:", repr(part))
                chunks.append(part)
            print("records:", b"".join(chunks).splitlines())
    else:
        s.connect(("127.0.0.1", 5006))
        s.sendall(b"temperature=25\n")
        s.sendall(b"humidity=60\n")
        s.shutdown(socket.SHUT_WR)
