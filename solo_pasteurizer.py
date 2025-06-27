import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
import csv
import os
import socket
import serial
import serial.tools.list_ports


class WiFiArduinoInterface:
    def __init__(self, host='127.0.0.1', port=12345):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port))
            return True
        except Exception as e:
            print(f"[WiFiArduinoInterface] Connection failed: {e}")
            return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def read_temperatures(self):
        try:
            data = self.sock.recv(1024).decode().strip()
            parts = {}
            for kv in data.split(","):
                if ":" in kv:
                    key, val = kv.split(":", 1)
                    try:
                        parts[key] = float(val)
                    except ValueError:
                        pass
            return parts.get("T_CORE", 0.0), parts.get("T_WATER", 0.0)
        except Exception as e:
            print(f"[WiFiArduinoInterface] Read error: {e}")
            return 0.0, 0.0

    def write_command(self, command):
        try:
            self.sock.sendall((command + "\n").encode())
        except Exception as e:
            print(f"[WiFiArduinoInterface] Write error: {e}")


class ArduinoSerialInterface:
    def __init__(self, port='/dev/tty.usbmodem12345', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.core_temp = 0.0
        self.water_temp = 0.0

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            return True
        except Exception as e:
            print(f"[ArduinoSerialInterface] Connection failed: {e}")
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_temperatures(self):
        try:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"[USB DEBUG] Raw: {line}")  # Debug output

                # Extract substring with temperature info, e.g., T_CORE:25.5,T_WATER:25.9
                if "T_CORE:" in line and "T_WATER:" in line:
                    parts = {}
                    # Optional: if your data is always like "[Arduino] Sent: T_CORE:...,T_WATER:..." you can just extract the substring after the colon
                    payload = line.split(
                        "Sent:", 1)[-1].strip() if "Sent:" in line else line

                    for kv in payload.split(","):
                        if ":" in kv:
                            key, val = kv.split(":", 1)
                            key = key.strip()
                            val = val.strip()

                            if key in ("T_CORE", "T_WATER"):  # Only parse known float keys
                                try:
                                    parts[key] = float(val)
                                except ValueError:
                                    print(
                                        f"[USB DEBUG] Invalid float in: {kv}")
                    if "T_CORE" in parts and "T_WATER" in parts:
                        self.core_temp = parts["T_CORE"]
                        self.water_temp = parts["T_WATER"]
                return self.core_temp, self.water_temp

            return self.core_temp, self.water_temp

        except Exception as e:
            print(f"[ArduinoSerialInterface] Read error: {e}")
            return self.core_temp, self.water_temp

    def write_command(self, command):
        try:
            self.ser.write((command + "\n").encode())
        except Exception as e:
            print(f"[ArduinoSerialInterface] Write error: {e}")


class SoloPasteurizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Solo Pasteurizer Control")
        self.root.geometry("850x700")

        self.client = None
        self.connected = False
        self.monitoring = False
        self.connection_mode = tk.StringVar(value="wifi")

        self.core_temp = 0.0
        self.water_temp = 0.0
        self.unit = "C"

        # Create logs directory and set up file path
        self.logs_dir = "pasteurizer_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file = os.path.join(
            self.logs_dir, f"pasteurizer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        self.process_state = "IDLE"
        self.process_type = tk.StringVar(value="HEAT_COOL")
        self.start_time = None
        self.hold_time = 30
        self.hold_start = None

        self.heat_setpoint = tk.DoubleVar(value=72.0)
        self.cool_setpoint = tk.DoubleVar(value=32.0)

        self.setup_ui()
        self.setup_logging()

    def setup_ui(self):
        main = ttk.Frame(self.root, padding="10")
        main.grid(row=0, column=0, sticky="nsew")

        conn = ttk.LabelFrame(main, text="Connection")
        conn.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(conn, text="Mode:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(conn, text="WiFi", variable=self.connection_mode,
                        value="wifi", command=self.toggle_mode).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(conn, text="USB", variable=self.connection_mode, value="usb",
                        command=self.toggle_mode).grid(row=0, column=2, sticky="w")

        self.wifi_host_entry = ttk.Entry(conn)
        self.wifi_host_entry.insert(0, "127.0.0.1")
        self.wifi_port_entry = ttk.Entry(conn, width=6)
        self.wifi_port_entry.insert(0, "12345")

        self.port_combo = ttk.Combobox(
            conn, values=self.get_serial_ports(), state="readonly")

        self.wifi_host_entry.grid(row=1, column=0)
        self.wifi_port_entry.grid(row=1, column=1)
        self.port_combo.grid(row=1, column=0, columnspan=2)
        self.toggle_mode()

        self.connect_btn = ttk.Button(
            conn, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=1, column=2)
        self.status_label = ttk.Label(
            conn, text="Disconnected", foreground="red")
        self.status_label.grid(row=1, column=3)

        temp = ttk.LabelFrame(main, text="Temperatures")
        temp.grid(row=1, column=0, sticky="nsew")
        self.core_label = ttk.Label(temp, text="Core: --", font=("Arial", 14))
        self.core_label.grid(row=0, column=0, sticky="w")
        self.water_label = ttk.Label(
            temp, text="Water: --", font=("Arial", 14))
        self.water_label.grid(row=1, column=0, sticky="w")

        unit_frame = ttk.LabelFrame(main, text="Units")
        unit_frame.grid(row=1, column=1, sticky="nsew")
        self.unit_toggle = ttk.Combobox(
            unit_frame, values=["Celsius", "Fahrenheit"], state="readonly")
        self.unit_toggle.set("C")
        self.unit_toggle.bind("<<ComboboxSelected>>", self.change_unit)
        self.unit_toggle.grid(row=0, column=0)

        sp = ttk.LabelFrame(main, text="Setpoints")
        sp.grid(row=2, column=0, sticky="nsew")
        ttk.Label(sp, text="Heat Setpoint:").grid(row=0, column=0)
        ttk.Entry(sp, textvariable=self.heat_setpoint).grid(row=0, column=1)
        ttk.Label(sp, text="Cool Setpoint:").grid(row=1, column=0)
        ttk.Entry(sp, textvariable=self.cool_setpoint).grid(row=1, column=1)

        mode = ttk.LabelFrame(main, text="Cycle Mode")
        mode.grid(row=2, column=1, sticky="nsew")
        for i, m in enumerate(["HEAT", "COOL", "HEAT_COOL"]):
            ttk.Radiobutton(mode, text=m, variable=self.process_type, value=m).grid(
                row=i, column=0, sticky="w")

        process = ttk.LabelFrame(main, text="Process")
        process.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.status = ttk.Label(process, text="IDLE", font=("Arial", 14))
        self.status.grid(row=0, column=0, columnspan=2)
        ttk.Label(process, text="Hold Time (s):").grid(row=1, column=0)
        self.hold_var = tk.IntVar(value=self.hold_time)
        ttk.Entry(process, textvariable=self.hold_var).grid(row=1, column=1)
        ttk.Button(process, text="Start",
                   command=self.start_process).grid(row=2, column=0)
        ttk.Button(process, text="Stop", command=self.stop_process).grid(
            row=2, column=1)

        log = ttk.LabelFrame(main, text="Logs")
        log.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.log_text = tk.Text(log, height=8)
        self.log_text.pack(expand=True, fill="both")

    def toggle_mode(self):
        if self.connection_mode.get() == "wifi":
            self.wifi_host_entry.grid()
            self.wifi_port_entry.grid()
            self.port_combo.grid_remove()
        else:
            self.wifi_host_entry.grid_remove()
            self.wifi_port_entry.grid_remove()
            self.port_combo['values'] = self.get_serial_ports()
            if self.port_combo['values']:
                self.port_combo.set(self.port_combo['values'][0])
            self.port_combo.grid()

    def get_serial_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def change_unit(self, event):
        self.unit = self.unit_toggle.get()
        self.update_display()

    def c_to_f(self, c):
        return c * 9 / 5 + 32

    def display_temp(self, temp):
        return f"{self.c_to_f(temp):.1f} °F" if self.unit == "F" else f"{temp:.1f} °C"

    def update_display(self):
        self.core_label.config(
            text=f"Core: {self.display_temp(self.core_temp)}")
        self.water_label.config(
            text=f"Water: {self.display_temp(self.water_temp)}")

    def setup_logging(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Core_Temp_C', 'Water_Temp_C', 'Process_State',
                                'Heat_Setpoint', 'Cool_Setpoint', 'Process_Type', 'Event'])

    def log_to_csv(self, event=""):
        """Log current state to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    self.core_temp,
                    self.water_temp,
                    self.process_state,
                    self.heat_setpoint.get(),
                    self.cool_setpoint.get(),
                    self.process_type.get(),
                    event
                ])
        except Exception as e:
            print(f"Error writing to CSV: {e}")

    def log(self, msg, log_to_csv=True, event=""):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)

        if log_to_csv:
            self.log_to_csv(event or msg)

    def toggle_connection(self):
        if not self.connected:
            if self.connection_mode.get() == "wifi":
                host = self.wifi_host_entry.get()
                port = int(self.wifi_port_entry.get())
                self.client = WiFiArduinoInterface(host, port)
            else:
                port = self.port_combo.get()
                self.client = ArduinoSerialInterface(port)

            if self.client.connect():
                self.connected = True
                self.status_label.config(text="Connected", foreground="green")
                self.connect_btn.config(text="Disconnect")
                self.log(
                    f"Connected via {self.connection_mode.get().upper()}", event="CONNECTION_ESTABLISHED")
                self.start_monitoring()
            else:
                messagebox.showerror("Error", "Could not connect")
        else:
            self.monitoring = False
            self.client.disconnect()
            self.connected = False
            self.status_label.config(text="Disconnected", foreground="red")
            self.connect_btn.config(text="Connect")
            self.log("Disconnected", event="CONNECTION_LOST")

    def start_monitoring(self):
        self.monitoring = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def monitor_loop(self):
        last_log_time = 0
        while self.monitoring and self.connected:
            self.core_temp, self.water_temp = self.client.read_temperatures()
            self.root.after(0, self.update_display)

            # Log temperature data every 10 seconds during monitoring
            current_time = time.time()
            if current_time - last_log_time >= 10:
                self.log_to_csv("TEMPERATURE_READING")
                last_log_time = current_time

            time.sleep(1)

    def start_process(self):
        self.process_state = "HEATING" if self.process_type.get() in [
            "HEAT", "HEAT_COOL"] else "COOLING"
        self.hold_time = self.hold_var.get()
        self.status.config(text=f"{self.process_state}")
        self.start_time = datetime.now()
        self.hold_start = None

        self.client.write_command(
            "heat" if self.process_state == "HEATING" else "cool")
        threading.Thread(target=self.control_loop, daemon=True).start()
        self.log(f"Started {self.process_state} cycle (Target: {self.heat_setpoint.get() if self.process_state == 'HEATING' else self.cool_setpoint.get()}°C)",
                 event="PROCESS_STARTED")

    def stop_process(self):
        self.process_state = "IDLE"
        self.client.write_command("stop")
        self.status.config(text="IDLE")
        self.log("Process stopped manually", event="PROCESS_STOPPED")

    def control_loop(self):
        while self.process_state != "IDLE":
            if self.process_state == "HEATING" and self.core_temp >= self.heat_setpoint.get():
                self.process_state = "HOLDING"
                self.hold_start = datetime.now()
                self.status.config(text=f"HOLDING {self.hold_time}s")
                self.log(
                    f"Hold started - Target temp {self.heat_setpoint.get()}°C reached", event="HOLD_STARTED")

            elif self.process_state == "HOLDING":
                elapsed = (datetime.now() - self.hold_start).total_seconds()
                remaining = max(0, self.hold_time - elapsed)
                self.status.config(text=f"HOLDING {remaining:.0f}s")

                if elapsed >= self.hold_time:
                    if self.process_type.get() == "HEAT_COOL":
                        self.process_state = "COOLING"
                        self.client.write_command("cool")
                        self.status.config(text="COOLING")
                        self.log(
                            f"Hold complete - Starting cooling to {self.cool_setpoint.get()}°C", event="COOLING_STARTED")
                    else:
                        self.stop_process()
                        self.status.config(text="COMPLETE")
                        self.log("Process completed successfully",
                                 event="PROCESS_COMPLETED")

            elif self.process_state == "COOLING" and self.core_temp <= self.cool_setpoint.get():
                self.stop_process()
                self.status.config(text="COMPLETE")
                self.log(
                    f"Cooling complete - Target temp {self.cool_setpoint.get()}°C reached", event="PROCESS_COMPLETED")

            time.sleep(1)


def main():
    root = tk.Tk()
    SoloPasteurizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
