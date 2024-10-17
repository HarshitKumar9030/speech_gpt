import threading
import time
import psutil
import sqlite3
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import serial
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Main server configuration
MAIN_SERVER_URL = 'http://192.168.81.193:5000/api/pi_data'  # Replace with your main server's IP address

# Serial port configuration for Arduino
SERIAL_PORT = '/dev/ttyACM0'  # Replace with your serial port (e.g., '/dev/ttyACM0' on Linux)
BAUD_RATE = 9600

# Initialize Flask app (optional, can be used for status checks)
app = Flask(__name__)
CORS(app)

# Function to read sensor data from Arduino
def read_sensor_data():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud.")
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                try:
                    distance = float(line)
                    logging.info(f"Received distance: {distance} cm")
                    return distance
                except ValueError:
                    logging.warning(f"Invalid data received from Arduino: '{line}'")
            time.sleep(0.1)
    except serial.SerialException as e:
        logging.error(f"Serial exception: {e}")
        return None

# Function to gather system stats
def gather_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    cpu_temp = None

    try:
        temp = psutil.sensors_temperatures()
        for name in temp:
            if 'cpu' in name.lower():
                cpu_temp = temp[name][0].current
                break
    except (AttributeError, NotImplementedError):
        cpu_temp = None

    return {
        'cpu_usage': cpu_usage,
        'memory_usage': memory.percent,
        'cpu_temp': cpu_temp
    }

# Function to send data to the main server
def send_data_to_main_server(data):
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(MAIN_SERVER_URL, json=data, headers=headers)
        if response.status_code == 200:
            logging.info("Data sent successfully to the main server.")
        else:
            logging.error(f"Failed to send data to the main server. Status Code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logging.error(f"Exception while sending data to the main server: {e}")

# Function to collect and send data periodically
def collect_and_send_data(interval=10):
    while True:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sensor_distance = read_sensor_data()
        system_stats = gather_system_stats()

        if sensor_distance is not None:
            data = {
                'timestamp': timestamp,
                'cpu_usage': system_stats['cpu_usage'],
                'memory_usage': system_stats['memory_usage'],
                'cpu_temp': system_stats['cpu_temp'],
                'sensor_distance': sensor_distance
            }
            send_data_to_main_server(data)
        else:
            logging.warning("Sensor distance data is unavailable. Skipping data send.")

        time.sleep(interval)

# Flask route for status check (optional)
@app.route('/api/pi_status', methods=['GET'])
def pi_status():
    stats = gather_system_stats()
    sensor_distance = read_sensor_data()
    return jsonify({
        'status': 'Running',
        'cpu_usage': stats['cpu_usage'],
        'memory_usage': stats['memory_usage'],
        'cpu_temp': stats['cpu_temp'],
        'sensor_distance': sensor_distance
    }), 200

if __name__ == '__main__':
    # Start the data collection thread
    data_thread = threading.Thread(target=collect_and_send_data, daemon=True)
    data_thread.start()

    logging.info("Raspberry Pi server is running and collecting data.")

    # Start Flask server (optional, for status checks)
    app.run(host='0.0.0.0', port=5001, use_reloader=False)
