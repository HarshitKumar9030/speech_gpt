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
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

MAIN_SERVER_URL = os.getenv('MAIN_SERVER_URL', 'http://192.168.81.193:5000/api/pi_data') 
API_KEY = os.getenv('API_KEY', 'default_key')  

SERIAL_PORT = '/dev/ttyACM0'  
BAUD_RATE = 9600

app = Flask(__name__)
CORS(app)

def read_sensor_data(ser, data_queue):
    while True:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                try:
                    distance = float(line)
                    logging.info(f"Received distance: {distance} cm")
                    data_queue.append(distance)
                except ValueError:
                    logging.warning(f"Invalid data received from Arduino: '{line}'")
        except Exception as e:
            logging.error(f"Error reading from serial port: {e}")
            time.sleep(1) 

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

def send_data_to_main_server(data):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}' 
        }
        response = requests.post(MAIN_SERVER_URL, json=data, headers=headers)
        if response.status_code == 200:
            logging.info("Data sent successfully to the main server.")
        else:
            logging.error(f"Failed to send data to the main server. Status Code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logging.error(f"Exception while sending data to the main server: {e}")

# Function to collect and send data periodically every second
def collect_and_send_data(ser):
    data_queue = []
    read_thread = threading.Thread(target=read_sensor_data, args=(ser, data_queue), daemon=True)
    read_thread.start()

    while True:
        # Wait until we have at least one distance measurement
        while not data_queue:
            time.sleep(0.1)
        
        # Pop the first distance measurement
        distance = data_queue.pop(0)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        system_stats = gather_system_stats()

        data = {
            'timestamp': timestamp,
            'cpu_usage': system_stats['cpu_usage'],
            'memory_usage': system_stats['memory_usage'],
            'cpu_temp': system_stats['cpu_temp'],
            'sensor_distance': distance
        }
        send_data_to_main_server(data)

        # Sleep to maintain the 1-second interval
        time.sleep(1)

# Flask route for status check (optional)
@app.route('/api/pi_status', methods=['GET'])
def pi_status():
    stats = gather_system_stats()
    # For status check, we can assume the latest distance is the most recent in the queue or fetched from the database
    # Here, we'll fetch the latest data from the database
    try:
        conn = sqlite3.connect('assistant.db')
        c = conn.cursor()
        c.execute('''
            SELECT sensor_distance
            FROM pi_data
            ORDER BY id DESC
            LIMIT 1
        ''')
        row = c.fetchone()
        conn.close()
        sensor_distance = row[0] if row else 'N/A'
    except Exception as e:
        logging.error(f"Error fetching latest Pi data for status: {e}")
        sensor_distance = 'Unavailable'

    return jsonify({
        'status': 'Running',
        'cpu_usage': stats['cpu_usage'],
        'memory_usage': stats['memory_usage'],
        'cpu_temp': stats['cpu_temp'],
        'sensor_distance': sensor_distance
    }), 200

if __name__ == '__main__':
    # Initialize serial connection
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud.")
    except serial.SerialException as e:
        logging.error(f"Failed to connect to Arduino: {e}")
        exit(1)

    # Start the data collection and sending thread
    data_thread = threading.Thread(target=collect_and_send_data, args=(ser,), daemon=True)
    data_thread.start()

    logging.info("Raspberry Pi server is running and collecting data every second.")

    # Start Flask server (optional, for status checks)
    app.run(host='0.0.0.0', port=5001, use_reloader=False)
