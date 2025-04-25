# app.py
import eventlet
eventlet.monkey_patch()  # Must come before other imports

import json
import logging
import secrets
from flask import Flask, render_template, session, request, redirect, url_for
from flask_socketio import SocketIO, emit
from openai import OpenAI

# -- Logging Setup --
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# -- Flask & Socket.IO Setup --
app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, async_mode='eventlet')

# -- Load Config & Initialize OpenAI --
with open('abc_config.json') as f:
    abc_config = json.load(f)

OPENAI_API_KEY = abc_config.get("openai_api_key", "")
ASSISTANT_ID    = abc_config.get("assistant_id")

client = OpenAI(api_key=OPENAI_API_KEY)
try:
    client.default_headers["OpenAI-Beta"] = "assistants=v2"
    logger.debug("Patched OpenAI-Beta header successfully.")
except Exception as e:
    logger.error("Failed to patch OpenAI-Beta header: %s", e)

astro_assistant = None
if ASSISTANT_ID:
    try:
        astro_assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
        logger.debug("Retrieved Astro assistant: %s", ASSISTANT_ID)
    except Exception as e:
        logger.error("Error retrieving assistant: %s", e)


# -- Routes --
@app.route('/')
def home():
    """Landing page that redirects to /astro."""
    return render_template('index.html')


@app.route('/astro')
def astro_chat():
    """Main chat UI."""
    # Ensure a thread exists
    if 'thread_id' not in session:
        thread = client.beta.threads.create()
        session['thread_id'] = thread.id
        logger.debug("New thread created: %s", thread.id)

    # Initialize to Stage 1 (name capture)
    if 'stage' not in session:
        session['stage'] = 1

    return render_template('astro2.html', config=abc_config)


@app.route('/reset', methods=['POST'])
def reset_conversation():
    """Clear session so a fresh chat starts."""
    session.clear()
    return ('', 204)


# -- Socket Handlers --
@socketio.on('astro_message')
def handle_astro_message(data):
    user_msg = data.get('message', '').strip()
    thread_id = session.get('thread_id')
    stage     = session.get('stage', 1)

    # ---- Stage 1: Name Capture ----
    if stage == 1:
        # If they only said a greeting, re-prompt for name
        if user_msg.lower() in ("hi", "hello", "hey"):
            emit('astro_response', {'message': "May I please know your name?"})
            return

        # Otherwise, take their entire message as their name
        name = user_msg
        session['user_name'] = name[0].upper() + name[1:] if name else "User"
        emit('astro_response', {
            'message': (
                f"Hi {session['user_name']}! It’s so nice to meet you. "
                "How are you feeling today, and what would you like to talk about?"
            )
        })
        session['stage'] = 2
        return

    # ---- Stage 2+: Forward everything to the LLM ----
    if astro_assistant:
        # Kick off a run (user's message is automatically in the thread)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=astro_assistant.id
        )
        # Fetch the latest assistant message
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        if messages.data and messages.data[0].content:
            text = messages.data[0].content[0].text.value
            emit('astro_response', {'message': text})
        else:
            emit('astro_response', {'message': "—"})
    else:
        emit('astro_response', {
            'message': "Sorry, I'm having trouble connecting to my assistant right now."
        })


# -- Main Entry Point --
if __name__ == '__main__':
    logger.info("Starting Flask + SocketIO server on port 5002")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5002,
        debug=True,
        use_reloader=False,           # eventlet-friendly
        allow_unsafe_werkzeug=True    # dev only
    )