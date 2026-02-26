from dataclasses import asdict

from flask import Flask, render_template, request, Response
import json
import time
import os
from dotenv import load_dotenv
import hashlib
import signal

import logging

from dto.dto_instruction import DTOInstruction

logger = logging.getLogger('APP')

from algorythm import Copilot
from conversation import get_terminal, agent_result_of_all_active_tpl, agent_tool_tpl

app = Flask(__name__)

load_dotenv()
HTTP_PORT = int(os.getenv('HTTP_PORT', 5000))
MODEL = os.getenv('MODEL')
IS_DEBUG = int(os.environ.get('DEBUG', 0)) == 1
VERSION_TAG = 2

if IS_DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

class SessionsManaged:
    def __init__(self):
        self.sessions = {}

    def _init_session(self, session_id: str):
        self.sessions[session_id] = {'message': None, 'command': None, 'data': {}}

    def add_session_parameter(self, session_id: str, key: str, value):
        if session_id in self.sessions:
            self._init_session(session_id)

        self.sessions[session_id]['data'][key] = value

    def get_session_data(self, session_id: str) -> dict:
        return self.sessions.get(session_id, {}).get('data', {})

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

    def commit_command(self, session_id):
        if session_id not in self.sessions:
            return None

        self.sessions[session_id]['command'] = None

    def commit_message(self, session_id):
        if session_id not in self.sessions:
            self._init_session(session_id)

        self.sessions[session_id]['message'] = None

    def destroy(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

SESSION_MANAGER_INSTANCE = SessionsManaged()


def process_task(user_request: str, session_id: str):
    session = Copilot(user_request, SESSION_MANAGER_INSTANCE.get_session_data(session_id))

    active_responses = []
    force_stop = False
    for message in session.run():
        command = SESSION_MANAGER_INSTANCE.get_command(session_id)
        if command == 'stop':
            force_stop = True
            SESSION_MANAGER_INSTANCE.commit_command(session_id)
            break

        try:
            message = agent_tool_tpl(message)
        except Exception as e:
            logger.error(f"Error translate message: {e}")
            logger.error(message)
            message = asdict(message)
            message['hidden'] = True # workaround for prevent lost files' list

        if 'tool_name' in message.get('result', {}):
            active_responses.append({'type': 'files', 'message': message.copy()})

        if message.get('hidden', False):
            message = {'type': 'nope'}

        yield f"data: {json.dumps(message)}\n\n"

    if active_responses:
        msg = agent_result_of_all_active_tpl(active_responses)
        if msg:
            yield f"data: {json.dumps(agent_result_of_all_active_tpl(active_responses))}\n\n"

    if force_stop:
        yield f"data: {json.dumps({'role': 'system', 'type': 'warning', 'message': '[BREAK]', 'timestamp': time.time()})}\n\n"

    yield f"data: {json.dumps(get_terminal())}\n\n"


@app.route('/')
def index():
    project_base_path = request.args.get('project')
    if not project_base_path:
        return 'Empty ?project=', 400

    if not os.path.exists(project_base_path):
        return f'Wrong ?project={project_base_path}', 400

    ui_version_tag = int(request.args.get('versionTag', 0))
    if ui_version_tag != VERSION_TAG:
        return Response(render_template('error.html', core_version=VERSION_TAG, ui_version=ui_version_tag), mimetype='text/html', headers={
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        })

    session_id = hashlib.sha256(project_base_path.encode()).hexdigest()
    template_app_data = {
        'session_id': session_id,
    }

    start_stop = time.time()
    while not SESSION_MANAGER_INSTANCE.acquire(session_id):
        if not SESSION_MANAGER_INSTANCE.get_message(session_id):
            SESSION_MANAGER_INSTANCE.destroy(session_id)
            continue

        SESSION_MANAGER_INSTANCE.send_command(session_id, 'stop')
        time.sleep(1)

        if time.time() - start_stop > 60:
            logger.error("system processes failure: cant acquire session")
            os.kill(os.getpid(), signal.SIGINT)

    SESSION_MANAGER_INSTANCE.add_session_parameter(session_id, 'project_base_path', project_base_path)

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


@app.route('/api/agent', methods=['POST'])
def agent_api():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        project_base_path = data.get('project_base_path', '').strip()
        max_working_time = data.get('max_working_time')

        if not project_base_path:
            return json.dumps({'status': 'error', 'message': 'project_base_path is required and must be non-empty'}), 400

        if not os.path.exists(project_base_path):
            return json.dumps({'status': 'error', 'message': 'project_base_path is not exists'}), 400

        if not user_message:
            return json.dumps({'status': 'error', 'message': 'message is required and must be non-empty'}), 400

        if max_working_time is None:
            return json.dumps({'status': 'error', 'message': 'max_working_time is required'}), 400

        if not isinstance(max_working_time, int) or max_working_time <= 0:
            return json.dumps({'status': 'error', 'message': 'max_working_time must be a positive integer'}), 400

        session_data = {'project_base_path': project_base_path}
        copilot = Copilot(user_message, session_data)

        start_time = time.time()
        results = []
        timeout_occurred = False

        for message in copilot.run():
            elapsed = time.time() - start_time
            if elapsed > max_working_time:
                timeout_occurred = True
                break

            if isinstance(message, DTOInstruction):
                message = asdict(message)

            results.append(message)

        return json.dumps({
            'status': 'success',
            'results': results,
            'timeout': timeout_occurred,
            'elapsed_time': time.time() - start_time
        })

    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)}), 500


@app.route('/send_message', methods=['POST'])
def message_action():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        user_session_id = data.get('session_id', '').strip()

        if not user_message:
            return json.dumps({'status': 'error', 'message': 'Empty message'}), 400

        if SESSION_MANAGER_INSTANCE.get_message(user_session_id):
            return json.dumps({'status': 'error', 'message': 'Session is locked'}), 400

        SESSION_MANAGER_INSTANCE.send_message(user_session_id, user_message)

        return json.dumps({'status': 'success'})

    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)}), 500

def _get_heartbeat():
    return f"data: {json.dumps({'role': 'system', 'type': 'heartbeat'})}\n\n"

def _get_project_status(session: dict):
    try:
        session_id = session['id']
        project_path = SESSION_MANAGER_INSTANCE.get_session_data(session_id)['project_base_path']
        return f"data: {json.dumps({'role': 'system', 'type': 'status', 'message': project_path})}\n\n"
    except:
        return f"data: {json.dumps({'role': 'system', 'type': 'status', 'message': 'unknown project'})}\n\n"

def event_stream(session: dict):
    session_id = session['id']
    last_heartbeat_time = time.time()
    heartbeat_time = 30.0
    yield _get_heartbeat()
    yield _get_project_status(session)

    while True:
        message = SESSION_MANAGER_INSTANCE.get_message(session_id)

        try:
            if message:
                yield from process_task(message, session_id)

                # finished work:
                SESSION_MANAGER_INSTANCE.commit_message(session_id)
            else:
                # Send heartbeat to keep connection alive
                now = time.time()
                if now - last_heartbeat_time >= heartbeat_time:
                    yield _get_heartbeat()
                    yield _get_project_status(session)
                    last_heartbeat_time = now

                time.sleep(1)

        except Exception as e:
            SESSION_MANAGER_INSTANCE.commit_message(session_id)

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