import eventlet
eventlet.monkey_patch()

import json
import logging
import secrets

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from openai import OpenAI
from werkzeug.middleware.proxy_fix import ProxyFix

# ------------------------
# Configuration & Logging
# ------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load user config
with open('abc_config.json', 'r') as cfg:
    abc_config = json.load(cfg)
OPENAI_API_KEY = abc_config.get('openai_api_key', '')

# Your full, final system prompt goes here:
SYSTEM_PROMPT = """
You are ASTRO, a warm, empathic virtual therapist...
( _paste the complete detailed system prompt here_ )
"""

# ------------------------
# Flask & SocketIO Setup
# ------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, async_mode='eventlet')

# ------------------------
# OpenAI Client
# ------------------------
client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------------
# Routes
# ------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/astro')
def astro():
    # Initialize conversation history on first visit
    session.setdefault('history', [])
    return render_template('astro_rag.html', config=abc_config)

@app.route('/reset', methods=['POST'])
def reset():
    session.pop('history', None)
    return ('', 204)

# ------------------------
# Socket Handlers
# ------------------------
@socketio.on('astro_message')
def handle_astro_message(data):
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return

    logger.info(f"User: {user_msg}")

    # Ensure history exists
    history = session.setdefault('history', [])

    # Build the messages payload
    messages = [
        {'role': 'system',    'content': SYSTEM_PROMPT},
    ] + history + [
        {'role': 'user',      'content': user_msg}
    ]

    try:
        # Call the Chat Completions endpoint
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=messages
        )
        assistant_msg = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI API error:", exc_info=e)
        assistant_msg = "Sorry, I'm having trouble thinking right now."

    logger.info(f"Astro: {assistant_msg}")

    # Trim history to last 10 exchanges to avoid runaway sessions
    history.append({'role':'user',      'content': user_msg})
    history.append({'role':'assistant', 'content': assistant_msg})
    session['history'] = history[-20:]

    emit('astro_response', {'message': assistant_msg})

# ------------------------
# Main
# ------------------------
if __name__ == '__main__':
    logger.info("Starting Flask+SocketIO on http://0.0.0.0:5002")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5002,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )