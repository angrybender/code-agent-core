from flask import Flask, render_template, request, Response
import json
import time
import os
from dotenv import load_dotenv
import uuid

import logging
logger = logging.getLogger('APP')

from algorythm import Copilot

app = Flask(__name__)

load_dotenv()
HTTP_PORT = int(os.getenv('HTTP_PORT', 5000))
MODEL = os.getenv('MODEL')
IS_DEBUG = int(os.environ.get('DEBUG', 0)) == 1

if IS_DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

class SessionsManaged:
    def __init__(self):
        self.sessions = {}

    def _init_session(self, session_id: str):
        self.sessions[session_id] = {'message': None, 'command': None}

    def acquire(self, session_id: str):
        if session_id in self.sessions:
            return False

        self._init_session(session_id)
        return True

    def send_message(self, session_id: str, message: str):
        self.sessions[session_id]['message'] = message

    def send_command(self, session_id: str, command: str):
        if not session_id in self.sessions:
            self._init_session(session_id)

        self.sessions[session_id]['command'] = command

    def get_message(self, session_id: str):
        if session_id not in self.sessions:
            return None

        return self.sessions[session_id]['message']

    def get_command(self, session_id: str):
        if session_id not in self.sessions:
            return None

        return self.sessions[session_id]['command']

    def destroy(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

SESSION_MANAGER_INSTANCE = SessionsManaged()


def process_task(user_request: str, session_id: str):
    session = Copilot({'messages' : [{
        'content': user_request,
        'role': 'user',
    }]})

    for message in session.run():
        command = SESSION_MANAGER_INSTANCE.get_command(session_id)
        if command == 'stop':
            yield f"data: {json.dumps({'role': 'system', 'type': 'warning', 'message': '[BREAK]', 'timestamp': time.time()})}\n\n"
            break

        message['timestamp'] = time.time()
        yield f"data: {json.dumps(message)}\n\n"


@app.route('/')
def index():
    template_app_data = {
        'session_id': uuid.uuid4()
    }

    return Response(render_template('app.html', app=template_app_data), mimetype='text/html', headers={
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Access-Control-Allow-Origin': '*'
    })

@app.route('/control', methods=['POST'])
def control_action():
    data = request.get_json()
    command = data.get('command', '').strip()
    user_session_id = data.get('session_id', '').strip()
    if not user_session_id:
        return json.dumps({'status': 'error', 'message': 'empty session'}), 400

    if command not in ['stop']:
        return json.dumps({'status': 'error', 'message': 'invalid command'}), 400

    SESSION_MANAGER_INSTANCE.send_command(user_session_id, command)

    return json.dumps({'status': 'success'})


@app.route('/send_message', methods=['POST'])
def message_action():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        user_session_id = data.get('session_id', '').strip()

        if not user_message:
            return json.dumps({'status': 'error', 'message': 'Empty message'}), 400

        if not SESSION_MANAGER_INSTANCE.acquire(user_session_id):
            return json.dumps({'status': 'error', 'message': 'Session is locked'}), 400

        SESSION_MANAGER_INSTANCE.send_message(user_session_id, user_message)

        return json.dumps({'status': 'success'})

    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)}), 500

def _get_heartbeat():
    return f"data: {json.dumps({'role': 'system', 'type': 'heartbeat'})}\n\n"

def _get_project_status():
    copilot = Copilot({})
    try:
        manifest = copilot.get_manifest()
        return f"data: {json.dumps({'role': 'system', 'type': 'status', 'message': manifest['path']})}\n\n"
    except:
        return f"data: {json.dumps({'role': 'system', 'type': 'status', 'message': 'unknown project'})}\n\n"

def event_stream(session: dict):
    session_id = session['id']
    last_heartbeat_time = time.time()
    heartbeat_time = 30.0
    yield _get_heartbeat()
    yield _get_project_status()

    while True:
        message = SESSION_MANAGER_INSTANCE.get_message(session_id)

        try:
            if message:
                yield from process_task(message, session_id)

                # finished work:
                SESSION_MANAGER_INSTANCE.destroy(session_id)
            else:
                # Send heartbeat to keep connection alive
                now = time.time()
                if now - last_heartbeat_time >= heartbeat_time:
                    yield _get_heartbeat()
                    yield _get_project_status()
                    last_heartbeat_time = now

                time.sleep(1)

        except Exception as e:
            SESSION_MANAGER_INSTANCE.destroy(session_id)

            yield f"data: {json.dumps({'role': 'system', 'type': 'error', 'message': str(e)})}\n\n"
            logging.exception("message")
            break

@app.route('/events')
def events():
    session_id = request.args.get('session_id')
    session = {
        'id': session_id
    }

    return Response(event_stream(session), mimetype='text/event-stream', headers={
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
    })

if __name__ == '__main__':
    app.run(debug=IS_DEBUG, port=HTTP_PORT)
