import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime   
import csv
import os
# try:
#     from pymodbus.client.sync import ModbusSerialClient as ModbusClient
#     from pymodbus.constants import Endian
#     from pymodbus.payload import BinaryPayloadDecoder
#     MODBUS_AVAILABLE = True
# except ImportError:
#     MODBUS_AVAILABLE = False
#     print("PyModbus not installed. Install with: pip install pymodbus")

try:
    from pymodbus.client import ModbusSerialClient as ModbusClient
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.constants import Endian
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False
    print("PyModbus not installed. Install with: pip install pymodbus")


class SoloPasteurizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Solo 4896 Pasteurizer Control")
        self.root.geometry("800x600")
        
        # Connection settings
        self.port = "/dev/tty.usbserial-0001"  # Change this to your Mac port
        self.baudrate = 9600
        self.slave_id = 1
        self.client = None
        self.connected = False
        self.monitoring = False
        
        # Temperature data
        self.current_temp = 0.0
        self.setpoint = 72.0
        self.temp_history = []
        self.log_file = f"pasteurizer_log_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Process state
        self.process_state = "IDLE"  # IDLE, HEATING, HOLDING, COOLING
        self.start_time = None
        self.hold_time = 30  # seconds at 72F
        self.hold_start = None
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Connection frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(conn_frame, text="COM Port:").grid(row=0, column=0, padx=(0, 5))
        self.port_var = tk.StringVar(value=self.port)
        port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=10)
        port_combo['values'] = ('/dev/tty.usbserial-0001', '/dev/tty.USB0', '/dev/tty.SLAB_USBtoUART', 
                                '/dev/tty.usbmodem1', '/dev/tty.wchusbserial1', '/dev/tty.usbserial-1')
        port_combo.grid(row=0, column=1, padx=(0, 10))
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=0, column=3)
        
        # Temperature display frame
        temp_frame = ttk.LabelFrame(main_frame, text="Temperature", padding="10")
        temp_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(0, 5), pady=(0, 10))
        
        self.current_temp_label = ttk.Label(temp_frame, text="--°F", font=("Arial", 24, "bold"))
        self.current_temp_label.grid(row=0, column=0, pady=(0, 5))
        
        ttk.Label(temp_frame, text="Current Temperature").grid(row=1, column=0)
        
        # Setpoint frame
        setpoint_frame = ttk.LabelFrame(main_frame, text="Setpoint Control", padding="10")
        setpoint_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(0, 10))
        
        self.setpoint_label = ttk.Label(setpoint_frame, text=f"{self.setpoint}°F", font=("Arial", 20, "bold"))
        self.setpoint_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Button(setpoint_frame, text="Heat (72°F)", command=self.set_heat_temp).grid(row=1, column=0, padx=(0, 5), pady=2)
        ttk.Button(setpoint_frame, text="Cool (32°F)", command=self.set_cool_temp).grid(row=1, column=1, padx=(5, 0), pady=2)
        
        # Manual setpoint entry
        ttk.Label(setpoint_frame, text="Manual Setpoint:").grid(row=2, column=0, columnspan=2, pady=(10, 0))
        self.manual_setpoint = tk.DoubleVar(value=72.0)
        setpoint_entry = ttk.Entry(setpoint_frame, textvariable=self.manual_setpoint, width=10)
        setpoint_entry.grid(row=3, column=0, padx=(0, 5), pady=5)
        ttk.Button(setpoint_frame, text="Set", command=self.set_manual_setpoint).grid(row=3, column=1, padx=(5, 0), pady=5)
        
        # Process control frame
        process_frame = ttk.LabelFrame(main_frame, text="Pasteurization Process", padding="10")
        process_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.process_status = ttk.Label(process_frame, text="Process: IDLE", font=("Arial", 14))
        self.process_status.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        ttk.Label(process_frame, text="Hold Time (seconds):").grid(row=1, column=0, padx=(0, 5))
        self.hold_time_var = tk.IntVar(value=self.hold_time)
        hold_entry = ttk.Entry(process_frame, textvariable=self.hold_time_var, width=10)
        hold_entry.grid(row=1, column=1, padx=(0, 10))
        
        self.start_process_btn = ttk.Button(process_frame, text="Start Pasteurization", command=self.start_pasteurization)
        self.start_process_btn.grid(row=1, column=2, padx=(10, 0))
        
        self.stop_process_btn = ttk.Button(process_frame, text="Stop Process", command=self.stop_process)
        self.stop_process_btn.grid(row=2, column=0, columnspan=3, pady=(10, 0))
        
        # Status and logging frame
        status_frame = ttk.LabelFrame(main_frame, text="Status & Logging", padding="10")
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.log_text = tk.Text(status_frame, height=8, width=70)
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        status_frame.columnconfigure(0, weight=1)
        
    def setup_logging(self):
        """Initialize CSV logging"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Current_Temp', 'Setpoint', 'Process_State'])
    
    def log_message(self, message):
        """Add message to log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def log_data(self):
        """Log data to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    self.current_temp,
                    self.setpoint,
                    self.process_state
                ])
        except Exception as e:
            self.log_message(f"Logging error: {e}")
    
    def toggle_connection(self):
        if not self.connected:
            self.connect_to_solo()
        else:
            self.disconnect_from_solo()
    
    def connect_to_solo(self):
        """Connect to Solo 4896 via Modbus"""
        if not MODBUS_AVAILABLE:
            messagebox.showerror("Error", "PyModbus not installed!\nInstall with: pip install pymodbus")
            print("Error", "PyModbus not installed!\nInstall with: pip install pymodbus")
            return
            
        try:
            self.port = self.port_var.get()
            # self.client = ModbusClient(
            #     method='rtu',
            #     port=self.port,
            #     baudrate=self.baudrate,
            #     timeout=1,
            #     parity='N',
            #     stopbits=1,
            #     bytesize=8
            # )
            self.client = ModbusClient(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity='N',
                stopbits=1,
                bytesize=8
            )

            
            if self.client.connect():
                self.connected = True
                self.status_label.config(text="Connected", foreground="green")
                self.connect_btn.config(text="Disconnect")
                self.log_message(f"Connected to Solo 4896 on {self.port}")
                self.start_monitoring()
            else:
                messagebox.showerror("Connection Error", f"Failed to connect to {self.port}")
                print("Connection Error", f"Failed to connect to {self.port}")
                
        except Exception as e:
            messagebox.showerror("Connection Error", f"Error: {str(e)}")
            print("Connection Error", f"Error: {str(e)}")
    
    def disconnect_from_solo(self):
        """Disconnect from Solo 4896"""
        self.connected = False
        self.monitoring = False
        if self.client:
            self.client.close()
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        self.log_message("Disconnected from Solo 4896")
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        self.monitoring = True
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
    
    def monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring and self.connected:
            try:
                # Read current temperature (adjust register address as needed)
                # This is a placeholder - you'll need the actual Solo register addresses
                # temp_result = self.client.read_holding_registers(1, 1, unit=self.slave_id)
                temp_result = self.client.read_holding_registers(address=1, count=1, slave=self.slave_id)

                if not temp_result.isError():
                    # Convert register value to temperature (adjust scaling as needed)
                    self.current_temp = temp_result.registers[0] / 10.0  # Example: register value / 10
                    
                    # Update UI
                    self.root.after(0, self.update_temperature_display)
                    
                    # Log data
                    self.log_data()
                    
                    # Process control logic
                    self.process_control()
                    
                else:
                    self.log_message("Error reading temperature")
                    
            except Exception as e:
                self.log_message(f"Communication error: {e}")
                
            time.sleep(1)  # Update every second
    
    def update_temperature_display(self):
        """Update temperature display in UI"""
        self.current_temp_label.config(text=f"{self.current_temp:.1f}°F")
        
        # Color coding based on temperature
        if self.setpoint - 2 <= self.current_temp <= self.setpoint + 2:
            self.current_temp_label.config(foreground="green")
        elif abs(self.current_temp - self.setpoint) > 5:
            self.current_temp_label.config(foreground="red")
        else:
            self.current_temp_label.config(foreground="orange")
    
    def write_setpoint(self, value):
        """Write setpoint to Solo 4896"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Solo 4896 first")
            print("Not Connected", "Please connect to Solo 4896 first")
            return False
            
        try:
            # Convert temperature to register value (adjust scaling as needed)
            register_value = int(value * 10)  # Example: temperature * 10
            
            # Write to setpoint register (adjust register address as needed)
            result = self.client.write_single_register(2, register_value, unit=self.slave_id)
            
            if not result.isError():
                self.setpoint = value
                self.setpoint_label.config(text=f"{self.setpoint}°F")
                self.log_message(f"Setpoint changed to {value}°F")
                return True
            else:
                self.log_message("Error writing setpoint")
                return False
                
        except Exception as e:
            self.log_message(f"Error writing setpoint: {e}")
            return False
    
    def set_heat_temp(self):
        """Set heating temperature (72°F)"""
        self.write_setpoint(72.0)
    
    def set_cool_temp(self):
        """Set cooling temperature (32°F)"""
        self.write_setpoint(32.0)
    
    def set_manual_setpoint(self):
        """Set manual setpoint"""
        value = self.manual_setpoint.get()
        if 0 <= value <= 200:  # Safety limits
            self.write_setpoint(value)
        else:
            messagebox.showerror("Invalid Temperature", "Temperature must be between 0°F and 200°F")
            print("Invalid Temperature", "Temperature must be between 0°F and 200°F")
    
    def start_pasteurization(self):
        """Start automated pasteurization process"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Solo 4896 first")
            print("Not Connected", "Please connect to Solo 4896 first")
            return
            
        self.process_state = "HEATING"
        self.start_time = datetime.now()
        self.hold_time = self.hold_time_var.get()
        self.write_setpoint(72.0)
        
        self.process_status.config(text="Process: HEATING TO 72°F")
        self.start_process_btn.config(state="disabled")
        self.log_message("Pasteurization process started - heating to 72°F")
    
    def stop_process(self):
        """Stop pasteurization process"""
        self.process_state = "IDLE"
        self.start_time = None
        self.hold_start = None
        
        self.process_status.config(text="Process: IDLE")
        self.start_process_btn.config(state="normal")
        self.log_message("Pasteurization process stopped")
    
    def process_control(self):
        """Automated process control logic"""
        if self.process_state == "HEATING":
            if self.current_temp >= 71.5:  # Close to 72°F
                self.process_state = "HOLDING"
                self.hold_start = datetime.now()
                self.process_status.config(text=f"Process: HOLDING AT 72°F ({self.hold_time}s)")
                self.log_message(f"Holding temperature at 72°F for {self.hold_time} seconds")
                
        elif self.process_state == "HOLDING":
            if self.hold_start:
                elapsed = (datetime.now() - self.hold_start).total_seconds()
                remaining = max(0, self.hold_time - elapsed)
                self.process_status.config(text=f"Process: HOLDING ({remaining:.0f}s remaining)")
                
                if elapsed >= self.hold_time:
                    self.process_state = "COOLING"
                    self.write_setpoint(32.0)
                    self.process_status.config(text="Process: COOLING TO 32°F")
                    self.log_message("Hold complete - cooling to 32°F")
                    
        elif self.process_state == "COOLING":
            if self.current_temp <= 35.0:  # Close to 32°F
                self.process_state = "COMPLETE"
                self.process_status.config(text="Process: COMPLETE")
                self.start_process_btn.config(state="normal")
                self.log_message("Pasteurization process complete!")

def main():
    root = tk.Tk()
    app = SoloPasteurizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()