import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from g4f import ChatCompletion
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Flask(__name__)
CORS(app)

def ai_process(text, assistant_personality):
    try:
        # Modify the assistant's behavior based on personality
        personality_prefix = ""
        if assistant_personality == "Friendly":
            personality_prefix = "You are a friendly assistant. "
        elif assistant_personality == "Professional":
            personality_prefix = "You are a professional assistant. "

        response = ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": personality_prefix + text}
            ],
            temperature=0.7,
        )

        message = response.strip()
        return message
    except Exception as e:
        return f"Error: {e}"

@app.route('/process_ai', methods=['POST'])
def process_ai():
    data = request.get_json()
    text = data.get('text')
    assistant_personality = data.get('assistant_personality', 'Default')
    if not text:
        return jsonify({'error': 'No text provided.'}), 400

    ai_response = ai_process(text, assistant_personality)
    return jsonify({'response': ai_response})

if __name__ == '__main__':
    # Run the AI server on your laptop's local network IP address and a chosen port (e.g., 8000), or on a VM
    app.run(host='0.0.0.0', port=8000)
