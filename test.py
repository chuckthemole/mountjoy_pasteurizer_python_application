from pymodbus.client.serial import ModbusSerialClient as ModbusClient

client = ModbusClient(
    port='/dev/tty.usbserial-0001',  # Change to your COM port
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1
)

if client.connect():
    result = client.read_holding_registers(1, 1, slave=1)
    if not result.isError():
        print("Success! Register 1:", result.registers[0])
    else:
        print("Modbus error:", result)
    client.close()
else:
    print("Failed to connect")

