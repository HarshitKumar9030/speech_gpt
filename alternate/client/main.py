import threading
import time
import speech_recognition as sr
import os
import psutil
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import pyttsx3
import requests  # Library to send HTTP requests to the AI server

app = Flask(__name__)
CORS(app)

assistant_active = False
last_activation_time = 0
kill_switch_activated = False
current_speech = ""
tts_lock = threading.Lock()

# Replace this with the IP address and port of your laptop running the AI server
AI_SERVER_URL = 'http://192.168.81.193:8000//process_ai'

def init_db():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            wake_word TEXT,
            voice_enabled INTEGER,
            assistant_personality TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            assistant TEXT
        )
    ''')
    c.execute('SELECT COUNT(*) FROM settings')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO settings (id, wake_word, voice_enabled, assistant_personality)
            VALUES (?, ?, ?, ?)
        ''', (1, 'hello', 1, 'Default'))
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('SELECT wake_word, voice_enabled, assistant_personality FROM settings WHERE id = 1')
    result = c.fetchone()
    conn.close()
    if result:
        wake_word, voice_enabled, assistant_personality = result
        return {
            'wake_word': wake_word,
            'voice_enabled': bool(voice_enabled),
            'assistant_personality': assistant_personality
        }
    else:
        return {
            'wake_word': 'hello',
            'voice_enabled': True,
            'assistant_personality': 'Default'
        }

def update_settings_in_db(wake_word, voice_enabled, assistant_personality):
    conn = sqlite3.connect('assistant.db')
    c = conn.cursor()
    c.execute('''
        UPDATE settings
        SET wake_word = ?, voice_enabled = ?, assistant_personality = ?
        WHERE id = 1
    ''', (wake_word, int(voice_enabled), assistant_personality))
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
    c.execute('SELECT user, assistant FROM chat_history ORDER BY id')
    rows = c.fetchall()
    conn.close()
    chat_history = [{'user': row[0], 'assistant': row[1]} for row in rows]
    return chat_history

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

def ai_process(text):
    try:
        settings = get_settings()
        assistant_personality = settings['assistant_personality']

        # Send a request to the AI server
        response = requests.post(AI_SERVER_URL, json={
            'text': text,
            'assistant_personality': assistant_personality
        })

        if response.status_code == 200:
            ai_response = response.json().get('response', '')
            return ai_response
        else:
            return f"Error from AI server: {response.text}"
    except Exception as e:
        return f"Error: {e}"

def ai_process_stream(text):
    try:
        settings = get_settings()
        voice_enabled = settings['voice_enabled']

        full_response = ai_process(text)

        chunk_size = 50  
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i+chunk_size]
            yield f"data: {chunk}\n\n"
            time.sleep(0.1)  

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
        yield f"data: Error: {e}\n\n"

def process_ai_response(text):
    global current_speech
    settings = get_settings()
    voice_enabled = settings['voice_enabled']

    ai_response = ai_process(text)
    current_speech = f"Assistant: {ai_response}"
    add_to_chat_history(text, ai_response)
    print(f"AI Response: {ai_response}")

    if voice_enabled:
        with tts_lock:
            local_tts_engine = pyttsx3.init()
            local_tts_engine.setProperty('rate', 150)
            local_tts_engine.setProperty('volume', 0.9)
            local_tts_engine.say(ai_response)
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
            print("Listening...")
            try:
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio)
                print(f"Recognized: {text}")

                if not assistant_active and wake_word.lower() in text.lower():
                    assistant_active = True
                    last_activation_time = time.time()
                    print("Wake word detected. Assistant activated.")
                elif assistant_active:
                    current_speech = f"You said: {text}"
                    threading.Thread(target=process_ai_response, args=(text,)).start()

                if assistant_active and (time.time() - last_activation_time) > 120:
                    assistant_active = False
                    print("Assistant deactivated due to timeout.")

            except sr.WaitTimeoutError:
                pass  # No speech detected within timeout
            except sr.UnknownValueError:
                print("Unintelligible speech. Please try again.")
            except Exception as e:
                print(f"Error: {e}")

    print("Kill switch activated. Exiting listen loop.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    stats = get_system_stats()
    chat_history = get_chat_history()
    settings = get_settings()
    return jsonify({
        'current_speech': current_speech,
        'assistant_active': assistant_active,
        'stats': stats,
        'chat_history': chat_history,
        'settings': settings
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
    if wake_word is None or voice_enabled is None or assistant_personality is None:
        return jsonify({'error': 'Invalid settings data'}), 400
    update_settings_in_db(wake_word, voice_enabled, assistant_personality)
    return jsonify({'status': 'Settings updated.'})

def start_server():
    app.run(host='0.0.0.0', port=5000, use_reloader=False)

if __name__ == '__main__':
    init_db()

    listen_thread = threading.Thread(target=listen_loop, daemon=True)
    listen_thread.start()

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        kill_switch_activated = True
        listen_thread.join()
        server_thread.join()
