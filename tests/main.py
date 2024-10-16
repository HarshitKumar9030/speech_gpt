import threading
import time
import speech_recognition as sr
import os
import psutil
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from g4f import ChatCompletion
import pyttsx3
import asyncio
import serial  
import logging
import requests 
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BING_API_KEY = ''  # Replace with your actual Bing Search API key
BING_SEARCH_ENDPOINT = 'https://api.bing.microsoft.com/v7.0/search'

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Flask(__name__)
CORS(app)

# Global variables
assistant_active = False
last_activation_time = 0
kill_switch_activated = False
current_speech = ""
last_distance = None  # Store the last distance measurement
tts_lock = threading.Lock()

# Serial port configuration
SERIAL_PORT = 'COM12'  # Replace with your serial port (e.g., 'COM3' on Windows or '/dev/ttyACM0' on Linux)
BAUD_RATE = 9600

# Initialize database and create tables if they don't exist
def init_db():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    # Create the settings table if it does not exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            wake_word TEXT,
            voice_enabled INTEGER,
            assistant_personality TEXT,
            sensor_enabled INTEGER DEFAULT 1
        )
    ''')
    # Check if 'sensor_enabled' column exists
    c.execute("PRAGMA table_info(settings);")
    columns = [info[1] for info in c.fetchall()]
    if 'sensor_enabled' not in columns:
        logging.info("Adding 'sensor_enabled' column to 'settings' table.")
        c.execute("ALTER TABLE settings ADD COLUMN sensor_enabled INTEGER DEFAULT 1;")
        conn.commit()
        logging.info("'sensor_enabled' column added successfully.")
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            assistant TEXT
        )
    ''')
    # Create requests table for logging
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_text TEXT,
            assistant_response TEXT
        )
    ''')
    # Initialize settings if table is empty
    c.execute('SELECT COUNT(*) FROM settings')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO settings (id, wake_word, voice_enabled, assistant_personality, sensor_enabled)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'hello', 1, 'Default', 1))
        logging.info("Default settings inserted into 'settings' table.")
    conn.commit()
    conn.close()

init_db()

def get_settings():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT wake_word, voice_enabled, assistant_personality, sensor_enabled FROM settings WHERE id = 1')
    result = c.fetchone()
    conn.close()
    if result:
        wake_word, voice_enabled, assistant_personality, sensor_enabled = result
        return {
            'wake_word': wake_word,
            'voice_enabled': bool(voice_enabled),
            'assistant_personality': assistant_personality,
            'sensor_enabled': bool(sensor_enabled)
        }
    else:
        return {
            'wake_word': 'hello',
            'voice_enabled': True,
            'assistant_personality': 'Default',
            'sensor_enabled': True
        }

def update_settings_in_db(wake_word, voice_enabled, assistant_personality, sensor_enabled):
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        UPDATE settings
        SET wake_word = ?, voice_enabled = ?, assistant_personality = ?, sensor_enabled = ?
        WHERE id = 1
    ''', (wake_word, int(voice_enabled), assistant_personality, int(sensor_enabled)))
    conn.commit()
    conn.close()
    logging.info("Settings updated in the database.")

def log_request(user_text, assistant_response):
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO requests (timestamp, user_text, assistant_response)
        VALUES (?, ?, ?)
    ''', (timestamp, user_text, assistant_response))
    conn.commit()
    conn.close()
    logging.info(f"Logged request: '{user_text}' with response: '{assistant_response}'")

def add_to_chat_history(user_text, assistant_response):
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (user, assistant)
        VALUES (?, ?)
    ''', (user_text, assistant_response))
    conn.commit()
    conn.close()
    logging.info("Added conversation to chat history.")

def get_chat_history():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT user, assistant FROM chat_history ORDER BY id DESC LIMIT 100')  # Limit to last 100 entries
    rows = c.fetchall()
    conn.close()
    chat_history = [{'user': row[0], 'assistant': row[1]} for row in rows]
    return chat_history

# Fetch system statistics
def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    cpu_temp = 'Unavailable'

    try:
        temp = psutil.sensors_temperatures()
        for name in temp:
            if 'cpu' in name.lower():
                cpu_temp = temp[name][0].current
                break
    except (AttributeError, NotImplementedError):
        cpu_temp = 'Unavailable'

    return {
        'cpu_usage': cpu_usage,
        'memory_usage': memory.percent,
        'cpu_temp': cpu_temp
    }

# Function to process AI responses
def ai_process(text):
    try:
        settings = get_settings()
        assistant_personality = settings['assistant_personality']

        # Modify the assistant's behavior based on personality
        personality_prefix = ""
        if assistant_personality == "Friendly":
            personality_prefix = "You are a friendly assistant. "
        elif assistant_personality == "Professional":
            personality_prefix = "You are a professional assistant. "

        # Handle special queries
        if "what's the time" in text.lower() or "what is the time" in text.lower():
            current_time = datetime.now().strftime('%I:%M %p')
            message = f"The current time is {current_time}."
            return message

        # Fetch real-time information using Bing Search API
        query = text
        headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
        params = {"q": query, "textDecorations": True, "textFormat": "HTML"}

        response = requests.get(BING_SEARCH_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()

        # Extract relevant information from search results
        if 'webPages' in search_results:
            top_result = search_results['webPages']['value'][0]
            snippet = top_result['snippet']
            message = f"{snippet}"
        else:
            message = "I'm sorry, I couldn't find any information on that."

        return message.strip()

    except Exception as e:
        logging.error(f"Error in ai_process: {e}")
        return f"Error: {e}"

# Streaming generator function for AI responses
def ai_process_stream(text):
    try:
        settings = get_settings()
        voice_enabled = settings['voice_enabled']

        full_response = ai_process(text)

        # Log the request and response
        log_request(text, full_response)

        # Stream the response in chunks
        chunk_size = 50
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i+chunk_size]
            yield f"data: {chunk}\n\n"
            time.sleep(0.05)  # Reduced sleep time for faster streaming

        # Speak the response if voice is enabled
        if voice_enabled:
            with tts_lock:
                local_tts_engine = pyttsx3.init()
                local_tts_engine.setProperty('rate', 150)
                local_tts_engine.setProperty('volume', 0.9)
                local_tts_engine.say(full_response)
                local_tts_engine.runAndWait()

        global current_speech
        current_speech = f"Assistant: {full_response}"
        add_to_chat_history(text, full_response)

    except Exception as e:
        logging.error(f"Error in ai_process_stream: {e}")
        yield f"data: Error: {e}\n\n"

# Function to handle AI responses
def process_ai_response(text):
    global current_speech
    settings = get_settings()
    voice_enabled = settings['voice_enabled']

    ai_response = ai_process(text)
    current_speech = f"Assistant: {ai_response}"
    add_to_chat_history(text, ai_response)
    logging.info(f"AI Response: {ai_response}")

    # Log the request and response
    log_request(text, ai_response)

    if voice_enabled:
        with tts_lock:
            local_tts_engine = pyttsx3.init()
            local_tts_engine.setProperty('rate', 150)
            local_tts_engine.setProperty('volume', 0.9)
            local_tts_engine.say(ai_response)
            local_tts_engine.runAndWait()

# Function to continuously listen for voice commands
def listen_loop():
    global assistant_active, last_activation_time, kill_switch_activated, current_speech
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    while not kill_switch_activated:
        settings = get_settings()
        wake_word = settings['wake_word']
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            logging.info("Listening...")
            try:
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio)
                logging.info(f"Recognized: {text}")

                if not assistant_active and wake_word.lower() in text.lower():
                    assistant_active = True
                    last_activation_time = time.time()
                    logging.info("Wake word detected. Assistant activated.")
                    trigger_greeting()
                elif assistant_active:
                    current_speech = f"You said: {text}"
                    threading.Thread(target=process_ai_response, args=(text,)).start()

                if assistant_active and (time.time() - last_activation_time) > 120:
                    assistant_active = False
                    logging.info("Assistant deactivated due to timeout.")

            except sr.WaitTimeoutError:
                pass  # No speech detected within timeout
            except sr.UnknownValueError:
                logging.warning("Unintelligible speech. Please try again.")
            except Exception as e:
                logging.error(f"Error in listen_loop: {e}")

    logging.info("Kill switch activated. Exiting listen loop.")

def sensor_loop():
    global kill_switch_activated, last_distance, assistant_active, last_activation_time
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud.")
        while not kill_switch_activated:
            line = ser.readline().decode('utf-8').strip()
            if line:
                try:
                    distance = float(line)
                    last_distance = distance
                    logging.info(f"Distance: {distance} cm")
                    settings = get_settings()
                    if settings.get('sensor_enabled', True):
                        if 10 <= distance <= 50:
                            if not assistant_active:
                                # Activate assistant
                                assistant_active = True
                                last_activation_time = time.time()
                                threading.Thread(target=trigger_greeting).start()
                    time.sleep(0.1)
                except ValueError:
                    logging.warning(f"Received non-numeric data from sensor: '{line}'")
    except serial.SerialException as e:
        logging.error(f"Serial exception: {e}")

# Function to trigger a greeting when the sensor is activated
def trigger_greeting():
    global current_speech, assistant_active, last_activation_time
    greeting_text = "Hello! How can I assist you today?"
    settings = get_settings()
    voice_enabled = settings['voice_enabled']

    current_speech = f"Assistant: {greeting_text}"
    add_to_chat_history("Sensor Triggered", greeting_text)
    logging.info("Assistant: Hello! How can I assist you today?")

    log_request("Sensor Triggered", greeting_text)

    if voice_enabled:
        with tts_lock:
            local_tts_engine = pyttsx3.init()
            local_tts_engine.setProperty('rate', 150)
            local_tts_engine.setProperty('volume', 0.9)
            local_tts_engine.say(greeting_text)
            local_tts_engine.runAndWait()

    last_activation_time = time.time()

@app.route('/')
def index():
    return render_template('index.html')

# Flask API route to get the current status
@app.route('/api/status', methods=['GET'])
def get_status():
    stats = get_system_stats()
    chat_history = get_chat_history()
    settings = get_settings()
    # Fetch recent requests (last 100)
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, user_text, assistant_response FROM requests ORDER BY id DESC LIMIT 100')
    requests_rows = c.fetchall()
    conn.close()
    requests_history = [{'timestamp': row[0], 'user_text': row[1], 'assistant_response': row[2]} for row in requests_rows]
    return jsonify({
        'current_speech': current_speech,
        'assistant_active': assistant_active,
        'stats': stats,
        'chat_history': chat_history,
        'settings': settings,
        'last_distance': last_distance,
        'requests_history': requests_history
    })

# Flask API route to activate the kill switch
@app.route('/api/kill', methods=['POST'])
def kill():
    global kill_switch_activated
    kill_switch_activated = True
    return jsonify({'status': 'Assistant has been stopped.'})

# Flask API route to handle text input from the control panel
@app.route('/api/text_input', methods=['POST'])
def text_input():
    data = request.get_json()
    user_text = data.get('text', '')
    if user_text:
        def generate():
            yield from ai_process_stream(user_text)
        return Response(generate(), mimetype='text/event-stream')
    else:
        return jsonify({'error': 'No text provided.'}), 400

# Flask API route to update settings
@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    wake_word = data.get('wake_word')
    voice_enabled = data.get('voice_enabled')
    assistant_personality = data.get('assistant_personality')
    sensor_enabled = data.get('sensor_enabled')
    if wake_word is None or voice_enabled is None or assistant_personality is None or sensor_enabled is None:
        return jsonify({'error': 'Invalid settings data'}), 400
    update_settings_in_db(wake_word, voice_enabled, assistant_personality, sensor_enabled)
    return jsonify({'status': 'Settings updated.'})

def start_server():
    app.run(host='0.0.0.0', port=5000, use_reloader=False, threaded=True)

# Main execution
if __name__ == '__main__':
    # Start the voice recognition thread
    listen_thread = threading.Thread(target=listen_loop, daemon=True)
    listen_thread.start()

    # Start the sensor reading thread
    sensor_thread = threading.Thread(target=sensor_loop, daemon=True)
    sensor_thread.start()

    # Start the Flask server thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    logging.info("Audio Assistant is running.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        kill_switch_activated = True
        listen_thread.join()
        sensor_thread.join()
        server_thread.join()
        logging.info("Assistant has been stopped.")
