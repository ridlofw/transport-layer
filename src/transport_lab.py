#!/usr/bin/env python3
"""Small TCP/UDP telemetry experiment. Python 3 standard library only."""
import argparse
import csv
import json
import socket
import time
import uuid

def encode(obj):
    return (json.dumps(obj) + "\n").encode()

def serve(a):
    seen, attempted = set(), set()
    def process(raw):
        msg = json.loads(raw)
        key = (msg["run"], msg["seq"])
        first = key not in attempted
        attempted.add(key)
        fault = (a.protocol == "udp" and a.drop_every > 0
                  and msg["seq"] % a.drop_every == 0 and first)
        if fault and a.fault == "data":
            print("SIMULATED_DATA_DROP", key, flush=True)
            return None
        duplicate = key in seen
        seen.add(key)
        print("DUPLICATE" if duplicate else "STORE", key,
              "total_unique=", len(seen), flush=True)
        if fault and a.fault == "ack":
            print("SIMULATED_ACK_DROP", key, flush=True)
            return None
        return encode({"run": msg["run"], "seq": msg["seq"]})

    kind = socket.SOCK_DGRAM if a.protocol == "udp" else socket.SOCK_STREAM
    with socket.socket(socket.AF_INET, kind) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((a.host, a.port))
        print("READY", a.protocol, a.host, a.port, flush=True)
        if a.protocol == "udp":
            while True:
                raw, peer = s.recvfrom(4096)
                reply = process(raw)
                if reply is not None:
                    s.sendto(reply, peer)
        else:
            s.listen(1)
            while True:
                conn, _ = s.accept()
                with conn, conn.makefile("rb") as stream:
                    for raw in stream:  # Newline framing, not recv boundaries.
                        conn.sendall(process(raw))

def send(a):
    run = uuid.uuid4().hex[:8]
    kind = socket.SOCK_DGRAM if a.protocol == "udp" else socket.SOCK_STREAM
    rows = []
    with socket.socket(socket.AF_INET, kind) as s:
        s.settimeout(a.timeout)
        s.connect((a.host, a.port))
        stream = s.makefile("rb") if a.protocol == "tcp" else None
        try:
            for seq in range(1, a.count + 1):
                raw = encode({"run": run, "seq": seq,
                              "temperature_c": round(24 + seq / 10, 1)})
                start = time.perf_counter()
                acknowledged = False
                limit = a.retries + 1 if a.protocol == "udp" else 1
                for attempt in range(1, limit + 1):
                    if a.protocol == "tcp":
                        s.sendall(raw)
                        reply = stream.readline()
                        if not reply:
                            raise ConnectionError("Server closed the connection")
                        ack = json.loads(reply)
                        acknowledged = (ack["run"], ack["seq"]) == (run, seq)
                    else:
                        s.send(raw)
                        deadline = time.perf_counter() + a.timeout
                        while time.perf_counter() < deadline:
                            s.settimeout(max(0.001, deadline - time.perf_counter()))
                            try:
                                ack = json.loads(s.recv(4096))
                            except socket.timeout:
                                break
                            if (ack["run"], ack["seq"]) == (run, seq):
                                acknowledged = True
                                break
                    if acknowledged:
                        break
                elapsed = 1000 * (time.perf_counter() - start)
                rows.append([seq, attempt, int(acknowledged), round(elapsed, 3)])
                time.sleep(a.interval)
        finally:
            if stream:
                stream.close()
    with open(a.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seq", "attempts", "acknowledged", "elapsed_ms"])
        writer.writerows(rows)
    ok = sum(row[2] for row in rows)
    print(f"run={run} acknowledged={ok}/{a.count}")
    print("application_sends=", sum(row[1] for row in rows))
    print("CSV:", a.out)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=["server", "client"])
    p.add_argument("--protocol", choices=["tcp", "udp"], default="udp")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5005)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--retries", type=int, default=0)
    p.add_argument("--timeout", type=float, default=0.25)
    p.add_argument("--interval", type=float, default=0.02)
    p.add_argument("--drop-every", type=int, default=0)
    p.add_argument("--fault", choices=["data", "ack"], default="data")
    p.add_argument("--out", default="results.csv")
    a = p.parse_args()
    if a.count < 1 or a.retries < 0 or a.timeout <= 0 or a.interval < 0:
        p.error("Use positive count/timeout and nonnegative retries/interval")
    try:
        serve(a) if a.role == "server" else send(a)
    except KeyboardInterrupt:
        print("Stopped")
    except (OSError, ConnectionError) as error:
        p.exit(1, f"Communication failed: {error}\n")

if __name__ == "__main__":
    main()
