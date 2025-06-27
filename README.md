# 🧪 Mountjoy Pasteurizer Control Interface

A GUI-based Python application for controlling a pasteurizer via **USB (Serial)** or **WiFi** connection. This tool allows you to monitor core and water temperatures, start and stop heating/cooling cycles, and log the pasteurization process for analysis.

---

## 📦 Features

- Connect to an Arduino-based controller via **WiFi** or **Serial (USB)**
- Real-time temperature monitoring
- Configurable **heat** and **cool** setpoints
- Three process modes: `HEAT`, `COOL`, and `HEAT_COOL`
- Optional temperature **hold time** for compliance-based cycles
- **Live logs** displayed in the GUI and saved to CSV for traceability
- Temperature display in Celsius or Fahrenheit
- Automatically detects available serial ports

---

## 🚀 Getting Started

### 🔧 Requirements

- Python 3.7+
- Compatible with Linux, macOS, or Windows
- An Arduino or device sending data over serial or socket in the format: T_CORE:25.5,T_WATER:26.0


### 🐍 Installation

Clone this repository:
 ```bash
 git clone git@github.com:chuckthemole/mountjoy_pasteurizer_python_application.git
 cd mountjoy_pasteurizer_python_application
 ```
 Create virtual environment and install dependencies:
 ```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
Run:
```bash
python solo_pasteurizer.py
```

## 📝 Data Logging

- Logs are saved to:  
  `pasteurizer_logs/pasteurizer_log_YYYYMMDD_HHMMSS.csv`

- Each log entry includes:
  - Timestamp
  - Core & water temperatures
  - Current process state
  - Heat and cool setpoints
  - Process type (HEAT, COOL, HEAT_COOL)
  - Event description (e.g., CONNECTION_ESTABLISHED, PROCESS_COMPLETED)

---

## 🖧 Protocol Details

- **WiFi Mode**: Expects a TCP server at the given IP/port.
- **USB Mode**: Expects a serial device (e.g., Arduino) sending data in this format:[Arduino] Sent: T_CORE:73.4,T_WATER:68.9


---

## 🛠 Development Notes

- Built using:
- `tkinter` for GUI
- `pyserial` for USB communication
- Python `socket` for TCP
- Threading is used for monitoring and process control to keep the UI responsive.

---

## 🐞 Troubleshooting

- **App won't launch**:
- Check Python 3 is installed: `python --version`
- Verify Tkinter is available: `python -m tkinter`
- **No serial ports shown**:
- Ensure Arduino is plugged in and recognized by your OS
- **WiFi connection fails**:
- Confirm the device is listening at the IP and port you provided

---


---

## ✅ Future Ideas

- Add real-time temperature graphing
- Export to Excel or Google Sheets
- Web-based dashboard alternative
- Buzzer or LED support via GPIO or Arduino feedback

---

## 📄 License

MIT License — free to use, modify, and share for personal or commercial projects.

---

## 🙋‍♂️ Author & Credits

Created by Chuck Thomas.  
Made for Mountjoy enterprises and pasteurization.

