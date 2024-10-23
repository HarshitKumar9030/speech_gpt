import threading
import time
import speech_recognition as sr
import os
import psutil
import sqlite3
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from g4f import ChatCompletion
import pyttsx3
import asyncio
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Flask(__name__)
CORS(app)

assistant_active = False
last_activation_time = 0
kill_switch_activated = False
current_speech = ""
tts_lock = threading.Lock()

def init_db():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            wake_word TEXT,
            voice_enabled INTEGER,
            assistant_personality TEXT,
            sensor_enabled INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            assistant TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_text TEXT,
            assistant_response TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS pi_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            cpu_usage REAL,
            memory_usage REAL,
            cpu_temp REAL,
            sensor_distance REAL
        )
    ''')
    c.execute('SELECT COUNT(*) FROM settings')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO settings (id, wake_word, voice_enabled, assistant_personality, sensor_enabled)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'hello', 1, 'Default', 1))
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

def add_to_chat_history(user_text, assistant_response):
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (user, assistant)
        VALUES (?, ?)
    ''', (user_text, assistant_response))
    conn.commit()
    conn.close()

def get_chat_history():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT user, assistant FROM chat_history ORDER BY id DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    chat_history = [{'user': row[0], 'assistant': row[1]} for row in rows]
    return chat_history

def get_system_stats():
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

def ai_process(text):
    try:
        settings = get_settings()
        assistant_personality = settings['assistant_personality']

        personality_prefix = ""
        if assistant_personality == "Friendly":
            personality_prefix = "You are a friendly assistant. "
        elif assistant_personality == "Professional":
            personality_prefix = "You are a professional assistant. "

        if "what's the time" in text.lower() or "what is the time" in text.lower():
            current_time = datetime.now().strftime('%I:%M %p')
            message = f"The current time is {current_time}."
            return message

        # Use AI response using g4f
        response = ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": personality_prefix + "You are an AI assistant."},
                {"role": "user", "content": text}
            ]
        )
        return response.strip()

    except Exception as e:
        logging.error(f"Error in ai_process: {e}")
        return f"Error: {e}"

def ai_process_stream(text):
    try:
        settings = get_settings()
        voice_enabled = settings['voice_enabled']

        full_response = ai_process(text)

        log_request(text, full_response)

        chunk_size = 50
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i+chunk_size]
            yield f"data: {chunk}\n\n"
            time.sleep(0.05)

        if voice_enabled:
            # Split the response into smaller chunks for TTS
            tts_chunk_size = 500  # Adjust based on your needs
            with tts_lock:
                local_tts_engine = pyttsx3.init()
                local_tts_engine.setProperty('rate', 150)
                local_tts_engine.setProperty('volume', 0.9)
                for i in range(0, len(full_response), tts_chunk_size):
                    tts_chunk = full_response[i:i+tts_chunk_size]
                    local_tts_engine.say(tts_chunk)
                local_tts_engine.runAndWait()

        global current_speech, last_activation_time
        current_speech = f"Assistant: {full_response}"
        last_activation_time = time.time()
        add_to_chat_history(text, full_response)

    except Exception as e:
        logging.error(f"Error in ai_process_stream: {e}")
        yield f"data: Error: {e}\n\n"

def process_ai_response(text):
    global current_speech, last_activation_time
    settings = get_settings()
    voice_enabled = settings['voice_enabled']

    ai_response = ai_process(text)
    current_speech = f"Assistant: {ai_response}"
    last_activation_time = time.time()
    add_to_chat_history(text, ai_response)
    log_request(text, ai_response)

    if voice_enabled:
        # Split the response into smaller chunks for TTS
        tts_chunk_size = 500  # Adjust based on your needs
        with tts_lock:
            local_tts_engine = pyttsx3.init()
            local_tts_engine.setProperty('rate', 150)
            local_tts_engine.setProperty('volume', 0.9)
            for i in range(0, len(ai_response), tts_chunk_size):
                tts_chunk = ai_response[i:i+tts_chunk_size]
                local_tts_engine.say(tts_chunk)
            local_tts_engine.runAndWait()

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
                    threading.Thread(target=trigger_greeting).start()
                elif assistant_active:
                    current_speech = f"You said: {text}"
                    threading.Thread(target=process_ai_response, args=(text,)).start()

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                logging.warning("Unintelligible speech.")
            except Exception as e:
                logging.error(f"Error in listen_loop: {e}")

        if assistant_active and (time.time() - last_activation_time) > 300:
            assistant_active = False
            logging.info("Assistant deactivated due to timeout.")

    logging.info("Kill switch activated. Exiting listen loop.")

def sensor_monitor():
    global assistant_active, last_activation_time
    while not kill_switch_activated:
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
            if row:
                distance = row[0]
                settings = get_settings()
                if settings.get('sensor_enabled', True):
                    if distance is not None and 10 <= distance <= 50:
                        if not assistant_active:
                            assistant_active = True
                            threading.Thread(target=trigger_greeting).start()
                        last_activation_time = time.time()
            time.sleep(0.5)
        except Exception as e:
            logging.error(f"Error in sensor_monitor: {e}")
            time.sleep(1)

def trigger_greeting():
    global current_speech, assistant_active, last_activation_time
    greeting_text = "Hello! How can I assist you today?"
    settings = get_settings()
    voice_enabled = settings['voice_enabled']

    current_speech = f"Assistant: {greeting_text}"
    add_to_chat_history("Sensor Triggered", greeting_text)
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

@app.route('/api/status', methods=['GET'])
def get_status():
    stats = get_system_stats()
    chat_history = get_chat_history()
    settings = get_settings()
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, user_text, assistant_response FROM requests ORDER BY id DESC LIMIT 100')
    requests_rows = c.fetchall()
    conn.close()
    requests_history = [{'timestamp': row[0], 'user_text': row[1], 'assistant_response': row[2]} for row in requests_rows]

    latest_pi_data = {}
    try:
        conn = sqlite3.connect('assistant.db')
        c = conn.cursor()
        c.execute('''
            SELECT cpu_usage, memory_usage, cpu_temp, sensor_distance
            FROM pi_data
            ORDER BY id DESC
            LIMIT 1
        ''')
        row = c.fetchone()
        conn.close()
        if row:
            cpu_usage, memory_usage, cpu_temp, sensor_distance = row
            latest_pi_data = {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'cpu_temp': cpu_temp,
                'sensor_distance': sensor_distance
            }
    except Exception as e:
        logging.error(f"Error fetching latest Pi data: {e}")

    return jsonify({
        'current_speech': current_speech,
        'assistant_active': assistant_active,
        'stats': stats,
        'chat_history': chat_history,
        'settings': settings,
        'pi_data': latest_pi_data,
        'requests_history': requests_history
    })

@app.route('/api/kill', methods=['POST'])
def kill():
    global kill_switch_activated
    kill_switch_activated = True
    return jsonify({'status': 'Assistant has been stopped.'})

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

@app.route('/api/pi_data', methods=['POST'])
def receive_pi_data():
    data = request.get_json()
    timestamp = data.get('timestamp')
    cpu_usage = data.get('cpu_usage')
    memory_usage = data.get('memory_usage')
    cpu_temp = data.get('cpu_temp')
    sensor_distance = data.get('sensor_distance')

    if None in (timestamp, cpu_usage, memory_usage, sensor_distance):
        return jsonify({'error': 'Incomplete data received.'}), 400

    try:
        conn = sqlite3.connect('assistant.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO pi_data (timestamp, cpu_usage, memory_usage, cpu_temp, sensor_distance)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, cpu_usage, memory_usage, cpu_temp, sensor_distance))
        conn.commit()
        conn.close()
        return jsonify({'status': 'Data received successfully.'}), 200
    except Exception as e:
        logging.error(f"Error inserting Pi data into database: {e}")
        return jsonify({'error': 'Failed to insert data into database.'}), 500

@app.route('/api/pi_latest_data', methods=['GET'])
def get_latest_pi_data():
    try:
        conn = sqlite3.connect('assistant.db')
        c = conn.cursor()
        c.execute('''
            SELECT cpu_usage, memory_usage, cpu_temp, sensor_distance
            FROM pi_data
            ORDER BY id DESC
            LIMIT 1
        ''')
        row = c.fetchone()
        conn.close()
        if row:
            cpu_usage, memory_usage, cpu_temp, sensor_distance = row
            return jsonify({
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'cpu_temp': cpu_temp,
                'sensor_distance': sensor_distance
            }), 200
        else:
            return jsonify({'error': 'No Pi data available.'}), 404
    except Exception as e:
        logging.error(f"Error fetching latest Pi data: {e}")
        return jsonify({'error': 'Failed to fetch Pi data.'}), 500

def start_server():
    app.run(host='0.0.0.0', port=5000, use_reloader=False, threaded=True)

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    listen_thread = threading.Thread(target=listen_loop, daemon=True)
    listen_thread.start()

    sensor_thread = threading.Thread(target=sensor_monitor, daemon=True)
    sensor_thread.start()

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
        logging.info("Assistant has been stopped.")
