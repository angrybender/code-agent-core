# AI Development Assistant — Project Reference

This is an **AI-powered development assistant system** that helps developers complete coding tasks through natural language instructions. The system uses a multi-agent architecture where specialized AI agents collaborate to analyze codebases, plan changes, implement code modifications, and verify results autonomously.

## Purpose

The project enables developers to:
- Submit development tasks in natural language via a web interface or REST API
- Automatically analyze project structure and requirements
- Generate detailed implementation plans
- Create and modify code files automatically
- Execute predefined shell commands as part of the workflow
- Receive real-time progress updates through streaming responses

## Architecture

### Multi-Agent Supervisor Pattern

The system follows a hierarchical agent architecture:

```
User Task → SUPERVISOR → Specialized Agents:
                        ├─ ANALYTIC Agent (analysis & planning)
                        ├─ CODER Agent (implementation)
                        └─ REVIEWER Agent (verification)
```

Default workflow:
```
ANALYTIC → CODER → REVIEWER → (if issues found) → CODER
```

For simple tasks:
```
CODER → REVIEWER
```

### Agent Hierarchy

1. **SUPERVISOR** (implemented in `algorythm.py`)
   - Orchestrates the entire workflow
   - Delegates tasks to specialized agents via `call_agent` tool
   - Makes decisions based on agent reports
   - Manages conversation logs and state
   - Iterative execution loop with safety limits (`MAX_ITERATION`)

2. **ANALYTIC Agent** (implemented in `agents.py`)
   - Analyzes project structure and files (read-only access)
   - Searches codebases for relevant code fragments
   - Creates detailed implementation requirements and plans

3. **CODER Agent** (implemented in `agents.py`)
   - Implements code changes based on plans from ANALYTIC
   - Creates new files and modifies existing code
   - Can execute predefined shell commands (whitelist-based)

4. **REVIEWER Agent** (implemented in `agents.py`)
   - Verifies correctness of implemented changes
   - Can search files and execute predefined shell commands (e.g., run tests)
   - Returns a report with issues found or approval

## Core Components

### Server and API Layer

**`llm_api_server.py`** — Flask-based HTTP server
- Serves web UI for task submission
- Implements Server-Sent Events (SSE) for real-time streaming
- Endpoints:
  - `GET /` — Web UI (`?project=<path>&versionTag=<int>`)
  - `POST /send_message` — Task submission via web interface
  - `GET /events` — SSE event stream for the web interface
  - `POST /control` — Session control (e.g., `{"command": "stop"}` to interrupt agent)
  - `POST /api/agent` — REST API for programmatic synchronous access

#### REST API: `POST /api/agent`

Synchronous, blocking endpoint — no session management or SSE required.

**Request Body (JSON):**
```json
{
  "message": "Your task description here",
  "project_base_path": "/absolute/path/to/project",
  "max_working_time": 60
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | Task instruction for the agent system |
| `project_base_path` | string | Yes | Absolute path to the target project |
| `max_working_time` | integer | Yes | Maximum execution time in seconds |

**Response (JSON):**
```json
{
  "status": "success",
  "results": [
    {"id": "uuid", "type": "info", "message": "...", "result": {}, "exit": false, "hidden": false, "function": null, "args": [], "is_success": true}
  ],
  "timeout": false,
  "elapsed_time": 12.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `success` or `error` |
| `results` | array | List of serialized DTOInstruction objects from agent execution |
| `timeout` | boolean | Whether execution was terminated due to timeout |
| `elapsed_time` | number | Actual execution time in seconds |

#### Session Control: `POST /control`

Stops a running agent session:
```json
{"session_id": "<sha256_of_project_path>", "command": "stop"}
```

### LLM Integration Layer

**`llm.py`** — Language model integration
- OpenAI-compatible API client (works with any OpenAI-compatible endpoint)
- Supports function calling (tool use)
- Per-agent model selection via `MODEL:<ROLE>` env variables
- Environment-based configuration

## Technology Stack

### Backend
- **Python 3.12**
- **Flask 3.1.1** — Web framework
- **OpenAI SDK 1.99** — LLM API client (OpenAI-compatible)
- **python-dotenv 1.1.1** — Environment configuration
- **requests 2.32.2** — HTTP client
- **mcp 1.15** — Model Context Protocol for IDE integration

### Frontend
- Vanilla JavaScript with SSE
- Markdown rendering (`markdown.js`)
- Custom CSS chat interface (`assets/main.css`)

### Integration
- **MCP (Model Context Protocol)** — Connects to JetBrains IDE (default port 63342)
- Environment-based configuration via `.env`

## Workflow

### 1. Task Submission
```
User enters task → Flask server receives → Creates Copilot instance
→ Reads project manifest (AGENTS.md) directly from disk
→ Loads shell commands from .agent-commands/
→ Initializes conversation
```

### 2. Supervisor Loop
```
SUPERVISOR analyzes task → Calls tool (call_agent / message / exit)
→ Agent executes → Returns report → SUPERVISOR decides next step
→ Repeat until complete or MAX_ITERATION reached
```

### 3. Agent Execution
```
Agent receives instruction → Builds conversation context with system prompt
→ LLM query with tools → Tool calls returned
→ ToolsInterpreter executes tool → Result added to conversation
→ Repeat until 'report' tool called → Return to SUPERVISOR
```

### 4. File Operations
```
Agent tool call → ToolsInterpreter → mcp_helper
→ [read] Always reads directly from disk
→ [mcp mode] MCP call to IDE → IDE performs write operation → Result returned
→ [pure mode] Direct Python file I/O write → Result returned
→ Agent continues
```

### 5. Shell Commands System
```
.agent-commands/my-command.md  →  parse_agent_commands()
→ whitelist of named commands loaded at startup
→ Agent calls shell_command("my-command")
→ ToolsInterpreter executes the command via subprocess
→ Output returned to agent
```

### 6. Real-time Updates
```
Browser SSE connection → GET /events → Incremental messages streamed
→ Progress updates → [DONE] signal on completion
```

## Key Patterns and Conventions

### Tool-Calling Pattern
- All agents use OpenAI function calling
- Each agent has a specialized, minimal tool set

### Shell Commands System
- Agents cannot execute arbitrary shell commands — only whitelisted commands
- Commands defined as Markdown files in `.agent-commands/` (or custom dir via `SHELL_COMMAND_DIRECTORY`)
- Each command file: human-readable description + last fenced code block = shell command
- Timeout enforced per command (`SHELL_COMMAND_TIMEOUT`, default 30 sec)
- CODER uses shell commands for builds/tests during implementation
- REVIEWER uses shell commands to run test suites for verification

### Search System
- ANALYTIC and REVIEWER use `search_file` tool powered by `SearchCode`
- Supports fuzzy token matching — useful when exact code location is unknown
- Results include file path, line numbers, matched content, and relevance score

### Conversation Management
- Full conversation history maintained for context within each agent turn
- Logs stored in `conversations_log/`

### Error Handling
- Retry logic with exponential backoff in LLM calls (5 attempts)
- `MAX_ITERATION` safeguard prevents infinite loops

### Configuration-Driven
- `.env` for API keys, model selection, timeouts, modes
- Project manifest (`AGENTS.md` or `.copilot_project.xml`) for project metadata

### Separation of Concerns
- **SUPERVISOR**: Task delegation and orchestration only
- **ANALYTIC**: Read-only analysis and planning
- **CODER**: Write operations and implementation
- **REVIEWER**: Verification and testing (read + shell)

### Safety Features
- Agents can only execute shell commands from a predefined whitelist
- `MAX_ITERATION` prevents runaway execution

## Project Configuration

### Environment Variables (see `env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_URL` | — | LLM endpoint URL |
| `OPENAI_API_KEY` | — | API authentication key |
| `OPENAI_API_TIMEOUT` | 1200 | LLM request timeout in seconds |
| `MODEL` | claude-sonnet-4.5 | Default model identifier |
| `MODEL:SUPERVISOR` | — | Model override for SUPERVISOR agent |
| `MODEL:ANALYTIC` | — | Model override for ANALYTIC agent |
| `MODEL:CODER` | — | Model override for CODER agent |
| `MAX_PROMPT_OUTPUT` | — | Max output tokens limit |
| `REASONING_EFFORT` | low | For o1/o3 models: `low` / `medium` / `high` |
| `IDE_MCP_HOST` | http://127.0.0.1:63342/ | JetBrains IDE MCP server URL |
| `HTTP_PORT` | 5000 | Flask server port |
| `AGENT_FILE_TOOLS` | mcp | File operations mode: `mcp` or `pure` |
| `MAX_ITERATION` | 20 | Max agent iteration safety limit |
| `SHELL_COMMAND_TIMEOUT` | 30 | Timeout for shell commands in seconds |
| `SHELL_COMMAND_DIRECTORY` | .agent-commands | Directory with predefined shell commands |
| `DEBUG` | 0 | Enable verbose LLM logging to `full_log.log` |
| `DEEPTHINKING_AGENTS` | — | Comma-separated agent names for deep thinking mode |
| `AVOID_EMPTY_RESPONSE` | 0 | Force non-empty LLM responses |

## Directory Structure

```
project_root/
├── agents.py                    # Agent implementations (ANALYTIC, CODER, REVIEWER)
├── algorythm.py                 # SUPERVISOR orchestrator (Copilot class)
├── commands_helper.py           # .agent-commands/ parser and shell executor
├── conversation.py              # UI message formatting (DTOInstruction → HTML/text)
├── diff_helper.py               # Code patching utilities (apply_patch, PatchError)
├── llm.py                       # OpenAI-compatible LLM client
├── llm_api_server.py            # Flask HTTP server (Web UI + REST API)
├── llm_parser.py                # XML tag parsing from LLM responses
├── mcp_helper.py                # File operations abstraction (mcp / pure modes)
├── path_helper.py               # Path normalization utilities
├── search_code.py               # In-project code search engine (SearchCode)
├── tools_interpreter.py         # Agent tool executor (ToolsInterpreter)
├── log_helper.py                # Formatting all objects for pretty-print
├── dto/
│   ├── dto_instruction.py       # DTOInstruction dataclass (universal message object)
│   └── enums.py                 # AgentRole and EventType enumerations
├── prompts/                     # Propmts for agent and sub-agents
├── templates/                   # Web UI (SSE client, markdown rendering)
├── tests/                       # Tests of the project
├── conversations_log/           # Session and LLM debug logs (not in git)
├── storage/                     # Temp file cache (not in git)
├── AGENTS.md                    # This file — project reference for AI agents
├── env.example                  # Example environment configuration
└── requirements.txt             # Python dependencies
```

## Logging and Observability

- **Session logs**: `conversations_log/log.log` — user-facing messages
- **Debug logs**: `conversations_log/full_log.log` — full LLM request/response log (when `DEBUG=1`)
- **Real-time streaming**: SSE message stream to browser via `GET /events`

## Common Development Tasks

- **Add new agent**: Add a new class in `agents.py`, define prompt files in `prompts/`, register the new role in `agents.py` and `dto/enums.py`
- **Add new agent role**: Add to `AgentRole` enum in `dto/enums.py`, create prompt files in `prompts/`, register the role in `agents.py`
- **Add new event type**: Add value to `EventType` in `dto/enums.py` and handle rendering in `conversation.py`
- **Add shell command**: Create a `.md` file in `.agent-commands/` with a fenced code block containing the shell command
- **Modify prompts**: Edit templates in `prompts/` directory (Jinja2 syntax for CODER/REVIEWER)
- **Change LLM provider**: Update `OPENAI_API_URL` and `OPENAI_API_KEY` in `.env`
- **Switch to pure file mode**: Set `AGENT_FILE_TOOLS=pure` in `.env` (no IDE required)
- **Adjust iteration limits**: Set `MAX_ITERATION` in `.env`
- **Enable deep thinking**: Add agent name(s) to `DEEPTHINKING_AGENTS` in `.env`

## Testing

Unit tests are located in `tests/`

## Restrictions:
- Don't list directory `./storage` and read files into
- Don't list directory `./conversations_log` and read files into