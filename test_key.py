# from flask import Flask

# app = Flask(__name__)

# @app.route('/')
# def hello():
#     return 'Hello, World!'

# if __name__ == '__main__':
#     print("Server should be running at http://127.0.0.1:5002/")
#     app.run(host='0.0.0.0', port=5002, debug=True)

import eventlet
eventlet.monkey_patch()
print("Eventlet patched. Version:", eventlet.__version__)

from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# Explicitly force eventlet async_mode
socketio = SocketIO(app, async_mode='eventlet')

@app.route('/')
def index():
    return "Hello, SocketIO with Eventlet!"

@socketio.on('test_event')
def handle_test_event(data):
    print("Received test_event with data:", data)
    emit('test_response', {'response': 'Message received!'})

if __name__ == '__main__':
    print("Starting SocketIO server on http://127.0.0.1:5002")
    # Disable the reloader as it can interfere with eventlet on some systems
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)