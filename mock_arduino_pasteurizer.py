# mock_arduino_pasteurizer.py
import socket
import time
import threading
import select
import sys

# State
T_core = 25.0
T_water = 25.0
mode = "IDLE"  # "HEAT", "COOL", or "IDLE"
running = True

# Default Simulation parameters
HEAT_RATE = 0.3   # degrees/sec
COOL_RATE = 0.25  # degrees/sec

# Parse command-line args for heat and cool rates if provided
if len(sys.argv) > 1:
    try:
        HEAT_RATE = float(sys.argv[1])
    except ValueError:
        print(f"Invalid heat rate '{sys.argv[1]}', using default {HEAT_RATE}")

if len(sys.argv) > 2:
    try:
        COOL_RATE = float(sys.argv[2])
    except ValueError:
        print(f"Invalid cool rate '{sys.argv[2]}', using default {COOL_RATE}")

def simulate_temps():
    global T_core, T_water, mode, running
    while running:
        if mode == "HEAT":
            T_water += HEAT_RATE
            if T_water > T_core:
                T_core += HEAT_RATE * 0.9
        elif mode == "COOL":
            T_water -= COOL_RATE
            if T_water < T_core:
                T_core -= COOL_RATE * 0.8
        # Clamp values
        T_core = max(0, min(T_core, 100))
        T_water = max(0, min(T_water, 100))
        time.sleep(1)

def start_server():
    global mode, running

    HOST = '127.0.0.1'
    PORT = 12345
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[Mock Arduino] Listening on {HOST}:{PORT}")
    print(f"[Mock Arduino] Heat rate: {HEAT_RATE}°/s, Cool rate: {COOL_RATE}°/s")

    conn, addr = server.accept()
    conn.setblocking(False)
    print(f"[Mock Arduino] Connected by {addr}")

    try:
        while running:
            # Send simulated temperature data
            payload = f"T_CORE:{T_core:.1f},T_WATER:{T_water:.1f},MODE:{mode}\n"
            conn.sendall(payload.encode())
            print(f"[Mock Arduino] Sent: {payload.strip()}")

            # Check for readable data without blocking
            ready_to_read, _, _ = select.select([conn], [], [], 1.0)
            if ready_to_read:
                try:
                    data = conn.recv(1024)
                    if data:
                        command = data.decode().strip().lower()
                        print(f"[Mock Arduino] Received: {command}")
                        if command == "cool":
                            mode = "COOL"
                        elif command == "heat":
                            mode = "HEAT"
                        elif command == "stop":
                            mode = "IDLE"
                    else:
                        print("[Mock Arduino] Client disconnected.")
                        break
                except Exception as e:
                    print(f"[Mock Arduino] Receive error: {e}")
    except KeyboardInterrupt:
        print("[Mock Arduino] Shutting down on keyboard interrupt.")
    finally:
        running = False
        conn.close()
        server.close()
        print("[Mock Arduino] Server closed.")

# Start simulating in parallel
threading.Thread(target=simulate_temps, daemon=True).start()
start_server()
