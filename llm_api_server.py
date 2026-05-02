from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
import json
import time
import os
import base64
import mimetypes
import threading
from dotenv import load_dotenv
import hashlib
import signal

import logging

logger = logging.getLogger('APP')

from algorythm import Copilot
from commands_helper import parse_agent_commands
from conversation import get_terminal, agent_result_of_all_active_tpl, agent_tool_tpl
from mcp_integration.mcp_helper import parse_mcp_commands

app = FastAPI()
templates = Jinja2Templates(directory="templates")

load_dotenv()
HTTP_PORT = int(os.getenv('HTTP_PORT', 5000))
MODEL = os.getenv('MODEL')
IS_DEBUG = int(os.environ.get('DEBUG', 0)) == 1
STREAM_PENDING_PERIOD = 1
VERSION_TAG = 2
HTML_HEADERS = {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'no-cache',
    'Access-Control-Allow-Origin': '*'
}
SSE_HEADERS = {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
}

if IS_DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

class SessionsManaged:
    def __init__(self):
        self.sessions = {}
        self._lock = threading.Lock()

    def _init_session(self, session_id: str):
        self.sessions[session_id] = {'message': None, 'command': None, 'data': {}}

    def add_session_parameter(self, session_id: str, key: str, value):
        with self._lock:
            if session_id not in self.sessions:
                self._init_session(session_id)
            self.sessions[session_id]['data'][key] = value

    def get_session_data(self, session_id: str) -> dict:
        with self._lock:
            return self.sessions.get(session_id, {}).get('data', {})

    def acquire(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                return False
            self._init_session(session_id)
            return True

    def send_message(self, session_id: str, message: str):
        with self._lock:
            self.sessions[session_id]['message'] = message

    def send_command(self, session_id: str, command: str):
        with self._lock:
            if session_id not in self.sessions:
                self._init_session(session_id)
            self.sessions[session_id]['command'] = command

    def get_message(self, session_id: str):
        with self._lock:
            if session_id not in self.sessions:
                return None
            return self.sessions[session_id]['message']

    def get_command(self, session_id: str):
        with self._lock:
            if session_id not in self.sessions:
                return None
            return self.sessions[session_id]['command']

    def commit_command(self, session_id):
        with self._lock:
            if session_id not in self.sessions:
                return None
            self.sessions[session_id]['command'] = None

    def commit_message(self, session_id):
        with self._lock:
            if session_id not in self.sessions:
                self._init_session(session_id)
            self.sessions[session_id]['message'] = None

    def destroy(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

SESSION_MANAGER_INSTANCE = SessionsManaged()


def json_text_response(data, status_code: int = 200):
    return Response(content=json.dumps(data), status_code=status_code)


def process_task(user_request: str, session_id: str):
    session = Copilot(user_request, SESSION_MANAGER_INSTANCE.get_session_data(session_id))

    active_responses = []
    force_stop = False
    last_pending_sent = 0
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
            message = {'type': 'nope', 'is_final': True}

        if not message['is_final'] and time.time() - last_pending_sent < STREAM_PENDING_PERIOD:
            continue

        if not message['is_final']:
            last_pending_sent = time.time()
        else:
            last_pending_sent = 0

        yield f"data: {json.dumps(message)}\n\n"

    if active_responses:
        msg = agent_result_of_all_active_tpl(active_responses)
        if msg:
            yield f"data: {json.dumps(agent_result_of_all_active_tpl(active_responses))}\n\n"

    if force_stop:
        yield f"data: {json.dumps({'role': 'system', 'type': 'warning', 'message': '[BREAK]', 'timestamp': time.time()})}\n\n"

    yield f"data: {json.dumps(get_terminal())}\n\n"


@app.get('/')
async def index(request: Request):
    project_base_path = request.query_params.get('project')
    if not project_base_path:
        return PlainTextResponse('Empty ?project=', status_code=400)

    if not os.path.exists(project_base_path):
        return PlainTextResponse(f'Wrong ?project={project_base_path}', status_code=400)

    ui_version_tag = int(request.query_params.get('versionTag', 0))
    if ui_version_tag != VERSION_TAG:
        return templates.TemplateResponse(
            'error.html',
            {'request': request, 'core_version': VERSION_TAG, 'ui_version': ui_version_tag},
            headers=HTML_HEADERS
        )

    session_id = hashlib.sha256(project_base_path.encode()).hexdigest()
    shell_cmd_dir = os.getenv('SHELL_COMMAND_DIRECTORY', '.agent-commands')
    full_cmd_dir = os.path.join(project_base_path, shell_cmd_dir)
    commands = parse_agent_commands(full_cmd_dir)
    mcp_commands = parse_mcp_commands(full_cmd_dir)

    template_app_data = {
        'session_id': session_id,
        'commands': commands,
        'mcp_commands': mcp_commands,
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

    return templates.TemplateResponse(
        'app.html',
        {'request': request, 'app': template_app_data},
        headers=HTML_HEADERS
    )


@app.post('/control')
async def control_action(request: Request):
    data = await request.json()
    command = data.get('command', '').strip()
    user_session_id = data.get('session_id', '').strip()
    if not user_session_id:
        return json_text_response({'status': 'error', 'message': 'empty session'}, 400)

    if command not in ['stop']:
        return json_text_response({'status': 'error', 'message': 'invalid command'}, 400)

    SESSION_MANAGER_INSTANCE.send_command(user_session_id, command)

    return json_text_response({'status': 'success'})


@app.get('/file_content')
async def file_content(request: Request):
    file_path = request.query_params.get('path', '').strip()

    if not file_path:
        return json_text_response({'error': 'path parameter is required'}, 400)

    if not os.path.isabs(file_path):
        return json_text_response({'error': 'path must be absolute'}, 400)

    file_path = os.path.realpath(file_path)

    if not os.path.isfile(file_path):
        return json_text_response({'error': 'file not found'}, 404)

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('image/'):
        return json_text_response({'error': 'file is not an image'}, 400)

    max_size = 5 * 1024 * 1024
    if os.path.getsize(file_path) > max_size:
        return json_text_response({'error': 'file exceeds 5 MB limit'}, 400)

    with open(file_path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('ascii')

    data_url = f'data:{mime_type};base64,{encoded}'

    return json_text_response({
        'data_url': data_url,
        'mime_type': mime_type,
        'error': None
    })


@app.post('/api/agent')
async def agent_api(request: Request):
    try:
        data = await request.json()
        user_message = data.get('message', '').strip()
        project_base_path = data.get('project_base_path', '').strip()
        max_working_time = data.get('max_working_time')

        if not project_base_path:
            return json_text_response({'status': 'error', 'message': 'project_base_path is required and must be non-empty'}, 400)

        if not os.path.exists(project_base_path):
            return json_text_response({'status': 'error', 'message': 'project_base_path is not exists'}, 400)

        if not os.path.isabs(project_base_path):
            return json_text_response({'status': 'error', 'message': 'project_base_path must be an absolute path'}, 400)

        project_base_path = os.path.realpath(project_base_path)

        if not user_message:
            return json_text_response({'status': 'error', 'message': 'message is required and must be non-empty'}, 400)

        if max_working_time is None:
            return json_text_response({'status': 'error', 'message': 'max_working_time is required'}, 400)

        if not isinstance(max_working_time, int) or max_working_time <= 0:
            return json_text_response({'status': 'error', 'message': 'max_working_time must be a positive integer'}, 400)

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

            message = asdict(message)
            results.append(message)

        return json_text_response({
            'status': 'success',
            'results': results,
            'timeout': timeout_occurred,
            'elapsed_time': time.time() - start_time
        })

    except Exception as e:
        return json_text_response({'status': 'error', 'message': str(e)}, 500)


@app.post('/send_message')
async def message_action(request: Request):
    try:
        data = await request.json()
        user_message = data.get('message', '').strip()
        user_session_id = data.get('session_id', '').strip()

        if not user_message:
            return json_text_response({'status': 'error', 'message': 'Empty message'}, 400)

        images = data.get('images')
        if images is not None:
            if not isinstance(images, list) or not all(
                isinstance(img, str) and img.startswith('data:image/') for img in images
            ):
                return json_text_response({"status": "error", "message": "Invalid image format"}, 400)

        if SESSION_MANAGER_INSTANCE.get_message(user_session_id):
            return json_text_response({'status': 'error', 'message': 'Session is locked'}, 400)

        SESSION_MANAGER_INSTANCE.send_message(user_session_id, user_message)
        if images:
            SESSION_MANAGER_INSTANCE.add_session_parameter(user_session_id, 'pending_images', images)

        return json_text_response({'status': 'success'})

    except Exception as e:
        return json_text_response({'status': 'error', 'message': str(e)}, 500)


def _get_heartbeat():
    return f"data: {json.dumps({'role': 'system', 'type': 'heartbeat'})}\n\n"


def _get_project_status(session: dict):
    try:
        session_id = session['id']
        project_path = SESSION_MANAGER_INSTANCE.get_session_data(session_id)['project_base_path']
        return f"data: {json.dumps({'role': 'system', 'type': 'status', 'message': project_path})}\n\n"
    except (KeyError, TypeError):
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

                SESSION_MANAGER_INSTANCE.commit_message(session_id)
                SESSION_MANAGER_INSTANCE.add_session_parameter(session_id, 'pending_images', [])
            else:
                now = time.time()
                if now - last_heartbeat_time >= heartbeat_time:
                    yield _get_heartbeat()
                    yield _get_project_status(session)
                    last_heartbeat_time = now

                time.sleep(1)

        except Exception as e:
            SESSION_MANAGER_INSTANCE.commit_message(session_id)
            SESSION_MANAGER_INSTANCE.add_session_parameter(session_id, 'pending_images', [])

            yield f"data: {json.dumps({'role': 'system', 'type': 'error', 'message': str(e)})}\n\n"
            logging.exception("message")
            break


@app.get('/events')
async def events(request: Request):
    session_id = request.query_params.get('session_id')
    session = {
        'id': session_id
    }

    return StreamingResponse(event_stream(session), media_type='text/event-stream', headers=SSE_HEADERS)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=HTTP_PORT, log_level="debug" if IS_DEBUG else "info", timeout_graceful_shutdown=10)