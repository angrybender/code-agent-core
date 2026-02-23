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
   - Reads `AGENTS.md` for project manifest
   - Loads predefined shell commands from `.agent-commands/` directory

2. **ANALYTIC Agent** (implemented in `agents.py`)
   - Role: `SystemAnalyst`
   - Analyzes project structure and files (read-only access)
   - Searches codebases for relevant code fragments
   - Creates detailed implementation requirements and plans
   - Tools: `read_file`, `list_in_directory`, `search_file`, `report`

3. **CODER Agent** (implemented in `agents.py`)
   - Role: `DevPilot`
   - Implements code changes based on plans from ANALYTIC
   - Creates new files and modifies existing code
   - Can execute predefined shell commands (whitelist-based)
   - Filters duplicate file reads/writes to optimize performance
   - Tools: `read_file`, `list_in_directory`, `write_file`, `replace_code_in_file`, `shell_command`, `report`

4. **REVIEWER Agent** (implemented in `agents.py`, same class as ANALYTIC)
   - Role: `DevPilot` (reviewer mode)
   - Verifies correctness of implemented changes
   - Can search files and execute predefined shell commands (e.g., run tests)
   - Returns a report with issues found or approval
   - Tools: `read_file`, `search_file`, `shell_command`, `report`

Agent instantiation is handled by the `Agent.fabric(role)` factory method.
`Agent.setUp()` clears the `./storage` temp folder before each run.

## Core Components

### Server and API Layer

**`llm_api_server.py`** — Flask-based HTTP server
- Serves web UI for task submission
- Implements Server-Sent Events (SSE) for real-time streaming
- Session ID is computed as `sha256(project_base_path)`
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
  "status": "success" | "error",
  "results": [{"role": "assistant", "content": "..."}, ...],
  "timeout": true | false,
  "elapsed_time": 45.23
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `success` or `error` |
| `results` | array | List of message objects from agent execution |
| `timeout` | boolean | Whether execution was terminated due to timeout |
| `elapsed_time` | number | Actual execution time in seconds |

#### Session Control: `POST /control`

Stops a running agent session:
```json
{"session_id": "<sha256_of_project_path>", "command": "stop"}
```

### Orchestration Layer

**`algorythm.py`** — Core orchestration engine
- `Copilot` class: Main SUPERVISOR implementation
- Reads project manifest via `get_manifest()` (via MCP or pure mode)
- Loads shell commands from `.agent-commands/` at startup
- Manages full conversation history and state
- Iterative loop with `MAX_ITERATION` safeguard (default: 20)
- Tool-based LLM interaction — provides three tools to LLM:
  - `call_agent` — delegate to a specialized agent
  - `message` — send a message to the user
  - `exit` — signal task completion

### Agent Layer

**`agents.py`** — Agent implementations
- `BaseAgent` / `Agent`: Base class with common functionality
- Factory: `Agent.fabric(role)` → returns configured agent instance
- `Agent.setUp()` → clears `./storage` temp directory
- Per-agent system prompts loaded from `prompts/` (Jinja2 templating for CODER and REVIEWER — shell commands injected at runtime)
- **`CoderAgent`** applies `conversation_filter()` to deduplicate read/write operations across turns

### Tool Execution Layer

**`tools_interpreter.py`** — Agent tool execution bridge
- `ToolsInterpreter` class executes agent tool calls
- Validates all paths (`_validate_path`) — protection against path traversal
- Translates tool calls to filesystem or MCP operations:

| Tool | Method | Description |
|------|--------|-------------|
| `read_file` | `_command_read()` | Reads file content |
| `list_in_directory` | `_command_list()` | Lists directory (shows file sizes and subfolder counts) |
| `write_file` | `_command_write()` | Writes file (strips ``` code fences automatically) |
| `replace_code_in_file` | `_command_write_diff()` | Diff-based code patching |
| `search_file` | `_search_file()` | Delegates to `SearchCode` for code search |
| `shell_command` | `_command_shell()` | Executes whitelisted predefined shell commands |
| `report` | — | Signals task completion, returns result to SUPERVISOR |

### LLM Integration Layer

**`llm.py`** — Language model integration
- OpenAI-compatible API client (works with any OpenAI-compatible endpoint)
- Supports function calling (tool use)
- Retry logic with exponential backoff (5 attempts)
- Debug logging to `conversations_log/full_log.log`
- Configurable reasoning effort for o1/o3 models
- Per-agent model selection via `MODEL:<ROLE>` env variables
- Environment-based configuration

**`llm_parser.py`** — Response parsing utilities
- Extracts XML-style tags from LLM responses
- Regex-based pattern matching
- Handles tags with/without attributes

### Helper Modules

**`diff_helper.py`** — Smart code patching
- `apply_patch()`: Finds and replaces code fragments
- Handles exact and whitespace-normalized matching
- `PatchError` exception for failed patches
- Prevents multiple-match errors
- Supports adding/removing lines

**`path_helper.py`** — Path utilities
- `get_relative_path()`: Normalizes paths to project-relative format
- Cross-platform path handling

**`mcp_helper.py`** — File operations abstraction
- Two modes controlled by `AGENT_FILE_TOOLS` env variable:
  - **`mcp`** (default) — SSE MCP-client via JetBrains IDE (port 63342)
  - **`pure`** — direct Python file operations (no IDE dependency, useful for testing)
- Note: `get_file_text_by_path` always uses `_read_file_pure` to bypass MCP size limitations on large files

**`conversation.py`** — Message formatting
- Standardized message structure with timestamps
- Role-based messaging (user / assistant / system / tool)
- SSE terminal signal generation

**`search_code.py`** — Code search engine
- `SearchCode` class for in-project file search
- Supports exact match and fuzzy token-based search with scoring
- In-memory file content cache (reset via `reset()`)
- Detects file language by extension (30+ languages supported)
- Returns top-10 results with truncation of long lines
- Used by `ToolsInterpreter` for the `search_file` tool

**`commands_helper.py`** — Shell command management
- `parse_agent_commands(directory)` — parses `.md` files from `.agent-commands/`
  - Each `.md` file = one command; filename = command name; last code block = shell command
- `execute_terminal_command(cmd, timeout, cwd)` — executes shell command via `subprocess`
- Timeout controlled by `SHELL_COMMAND_TIMEOUT` env variable (default: 30 sec)

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
→ Reads project manifest (AGENTS.md)
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
→ [mcp mode] MCP call to IDE → IDE performs operation → Result returned
→ [pure mode] Direct Python file I/O → Result returned
→ Agent continues
```

### 5. Shell Commands System
```
.agent-commands/my-command.md  →  parse_agent_commands()
→ whitelist of named commands loaded at startup
→ Agent calls shell_command("my-command")
→ ToolsInterpreter._command_shell() executes via subprocess
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
- Tools defined as JSON schemas in `prompts/*_tools.py`
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
- Role-based messages: system, user, assistant, tool
- CoderAgent applies `conversation_filter()` to remove duplicate read/write operations
- Logs stored in `conversations_log/`

### Error Handling
- Retry logic with exponential backoff in LLM calls (5 attempts)
- `PatchError` for diff/patch failures
- Path traversal protection in `ToolsInterpreter._validate_path()`
- `MAX_ITERATION` safeguard prevents infinite loops

### Configuration-Driven
- `.env` for API keys, model selection, timeouts, modes
- Project manifest (`AGENTS.md` or `.copilot_project.xml`) for project metadata
- Prompt templates in `prompts/` directory (Jinja2 for CODER and REVIEWER)
- Per-agent model override via `MODEL:<ROLE>` env variables

### Separation of Concerns
- **SUPERVISOR**: Task delegation and orchestration only
- **ANALYTIC**: Read-only analysis and planning
- **CODER**: Write operations and implementation
- **REVIEWER**: Verification and testing (read + shell)

### Safety Features
- Agents can only execute shell commands from a predefined whitelist
- Path validation prevents directory traversal attacks
- `MAX_ITERATION` prevents runaway execution
- `AGENT_FILE_TOOLS=pure` mode allows operation without IDE dependency

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
├── conversation.py              # Message formatting and SSE helpers
├── diff_helper.py               # Code patching utilities (apply_patch, PatchError)
├── llm.py                       # OpenAI-compatible LLM client
├── llm_api_server.py            # Flask HTTP server (Web UI + REST API)
├── llm_parser.py                # XML tag parsing from LLM responses
├── mcp_helper.py                # File operations abstraction (mcp / pure modes)
├── path_helper.py               # Path normalization utilities
├── search_code.py               # In-project code search engine (SearchCode)
├── tools_interpreter.py         # Agent tool executor (ToolsInterpreter)
├── prompts/
│   ├── analytic_system.txt      # ANALYTIC system prompt
│   ├── analytic_tools.py        # ANALYTIC tool definitions (JSON schemas)
│   ├── coder_system.txt         # CODER system prompt (Jinja2 template)
│   ├── coder_tools.py           # CODER tool definitions (JSON schemas)
│   ├── reviewer_system.txt      # REVIEWER system prompt (Jinja2 template)
│   ├── reviewer_tools.py        # REVIEWER tool definitions (JSON schemas)
│   ├── step.txt                 # Shared context block (project info + file tree)
│   ├── supervisor_system.txt    # SUPERVISOR system prompt
│   └── supervisor_tools.py      # SUPERVISOR tool definitions (JSON schemas)
├── templates/
│   ├── app.html                 # Web UI (SSE client, markdown rendering)
│   ├── error.html               # Version mismatch error page
│   └── assets/
│       ├── app.js               # Frontend JS logic
│       ├── markdown.js          # Markdown renderer
│       └── main.css             # UI styles
├── tests/
│   ├── __init__.py
│   ├── testCommandsHelper.py    # Tests for parse_agent_commands
│   ├── testDiffHelper.py        # Tests for apply_patch
│   ├── testLLMParser.py         # Tests for parse_tags
│   ├── testMCPHelperPure.py     # Tests for mcp_helper in pure mode
│   └── testToolsInterpreter.py  # Tests for ToolsInterpreter
├── conversations_log/           # Session and LLM debug logs (not in git)
├── storage/                     # Temp file cache (not in git)
├── AGENTS.md                    # This file — project reference for AI agents
├── env.example                  # Example environment configuration
└── requirements.txt             # Python dependencies
```

## Agent Tool Reference

| Tool | ANALYTIC | CODER | REVIEWER |
|------|----------|-------|----------|
| `read_file` | ✅ | ✅ | ✅ |
| `list_in_directory` | ✅ | ✅ | ❌ |
| `search_file` | ✅ | ❌ | ✅ |
| `write_file` | ❌ | ✅ | ❌ |
| `replace_code_in_file` | ❌ | ✅ | ❌ |
| `shell_command` | ❌ | ✅ | ✅ |
| `report` | ✅ | ✅ | ✅ |

## Logging and Observability

- **Session logs**: `conversations_log/log.log` — user-facing messages
- **Debug logs**: `conversations_log/full_log.log` — full LLM request/response log (when `DEBUG=1`)
- **Real-time streaming**: SSE message stream to browser via `GET /events`
- **Timestamp-based IDs**: Conversation tracking per session

## Common Development Tasks

- **Add new agent**: Extend `Agent` in `agents.py`, define tools in `prompts/`, register in `Agent.PROMPTS`
- **Add shell command**: Create a `.md` file in `.agent-commands/` with a fenced code block containing the shell command
- **Modify prompts**: Edit templates in `prompts/` directory (Jinja2 syntax for CODER/REVIEWER)
- **Change LLM provider**: Update `OPENAI_API_URL` and `OPENAI_API_KEY` in `.env`
- **Switch to pure file mode**: Set `AGENT_FILE_TOOLS=pure` in `.env` (no IDE required)
- **Adjust iteration limits**: Set `MAX_ITERATION` in `.env`
- **Enable deep thinking**: Add agent name(s) to `DEEPTHINKING_AGENTS` in `.env`

## Testing

Unit tests are located in `tests/`:
- `testCommandsHelper.py` — shell command parsing
- `testDiffHelper.py` — code patching
- `testLLMParser.py` — XML tag extraction
- `testMCPHelperPure.py` — file operations in pure mode
- `testToolsInterpreter.py` — tool execution

Run all tests:
```bash
bash run_tests.sh
```