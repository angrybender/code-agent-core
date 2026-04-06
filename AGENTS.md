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

**Internal class hierarchy in `agents.py`:**
```
BaseAgent(LoggerMixin)         # Abstract base — main run() loop, LLM query, tool dispatch
  ├── AnalyticAgent(BaseAgent) # Handles both ANALYTIC and REVIEWER roles
  └── CoderAgent(BaseAgent)    # Handles the CODER role
Agent                          # Static factory: Agent.create(role), Agent.setUp()
```
Note: The REVIEWER role is implemented by `AnalyticAgent` (not a separate class). `AnalyticAgent.get_tools()` returns `ANALYTIC_TOOLS` for ANALYTIC role, or `get_reviewer_tools(has_shell_commands)` for REVIEWER role. `CoderAgent.get_tools()` returns `get_coder_tools(has_shell_commands)`. These factory functions in `tools/tools.py` conditionally include the `shell_command` tool based on whether shell commands are configured for the project.

1. **SUPERVISOR** (implemented in `algorythm.py`)
   - Orchestrates the entire workflow
   - Delegates tasks to specialized agents via `call_agent` tool
   - Makes decisions based on agent reports
   - Manages conversation logs and state
   - Iterative execution loop with safety limits (`MAX_ITERATION`)
   - Supports forwarding user-attached images to sub-agents via integer image indices in the `call_agent` tool `images` parameter

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
  - `POST /send_message` — Task submission via web interface; accepts optional `images` list (base64 Data URL strings for vision-capable models)
  - `GET /events` — SSE event stream for the web interface
  - `GET /file_content` — Serves a local image file as a base64 Data URL (used by the web UI to forward local images to the LLM); requires `?path=<absolute_path>`; only image files ≤ 5 MB are served
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
    {"message_id": "uuid", "type": "info", "message": "...", "result": {}, "exit": false, "hidden": false, "function": null, "args": {}, "is_success": true, "is_final": true, "metadata": null, "context_window": null}
  ],
  "timeout": false,
  "elapsed_time": 12.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `success` or `error` |
| `results` | array | List of serialized DTOInstruction objects from agent execution |
| `results[].message_id` | string | Unique message identifier |
| `results[].args` | object | Tool arguments (if applicable) |
| `results[].is_final` | boolean | Whether this is the final message |
| `results[].metadata` | object/null | Agent artifacts metadata (files created/modified, commands run) |
| `results[].context_window` | object/null | Token usage info (`{"used": N, "limit": N}`) |
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
- Error logging: `llm_query()` logs to `conversations_log/llm.error`, `llm_query_stream()` logs to `conversations_log/llm.error.log` — both after 5 failed retry attempts

**`context_helper.py`** — Conversation context optimization
- Provides `compact_conversation_remove_redundant()` function
- Three optimization phases:
  1. Removes reads invalidated by subsequent writes (`write_file` / `replace_code_in_file`)
  2. Deduplicates multiple `read_file` calls for the same path (keeps only the last full read)
  3. Deduplicates identical `shell_command` calls with identical output
- Used by `BaseAgent.conversation_filter()` in `agents.py`

### Logging Mixin

**`logger_mixin.py`** — Logging mixin
- Provides `LoggerMixin` base class with `log(data, to_file=False)` method
- Used by `Copilot` (`algorythm.py`) and `BaseAgent` (`agents.py`)
- Formats output via `pretty_format()` from `log_helper.py`
- When `to_file=True`, appends structured output to the agent's designated log file

## Technology Stack

### Backend
- **Python 3.12**
- **Flask 3.1.1** — Web framework
- **OpenAI SDK 1.99** — LLM API client (OpenAI-compatible)
- **python-dotenv 1.1.1** — Environment configuration
- **requests 2.32.2** — HTTP client
- **mcp 1.15** — Model Context Protocol for IDE integration

### Frontend
- Vanilla JavaScript with SSE (`templates/assets/app.js` — SSE client, message rendering, UI logic)
- Markdown rendering (`templates/assets/markdown.js`)
- Custom CSS chat interface (`templates/assets/main.css`)

### Integration
- **MCP (Model Context Protocol)** — Connects to JetBrains IDE (default port 63342)
- Environment-based configuration via `.env`

## Workflow

### 1. Task Submission
```
User enters task → Flask server receives → Creates Copilot instance
→ Reads project manifest (AGENTS.md) directly from disk
→ Loads shell commands from .agent-commands/
→ Optionally attaches user-submitted images (base64 Data URLs) for multimodal LLM input
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
- Shell commands support **positional arguments** via `$1`, `$2`, ... placeholders in the command Markdown file. Argument descriptions are parsed from lines matching `$N - description` format. The `shell_command` tool accepts an optional `args` list; `$1` maps to `args[0]`, `$2` to `args[1]`, etc. `commands_helper.py` validates that the correct number of arguments is provided before execution.

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
- `LLMRequestFormat` exception signals malformed tool calls or API format errors; agents retry up to 3 times — each retry strips the last message(s) and injects a prompt asking for a `report` tool call; after 3 failed attempts the agent emits `EventType.ERROR` and exits

### Configuration-Driven
- `.env` for API keys, model selection, timeouts, modes
- Project manifest (`AGENTS.md`) for project metadata

### Separation of Concerns
- **SUPERVISOR**: Task delegation and orchestration only
- **ANALYTIC**: Read-only analysis and planning
- **CODER**: Write operations and implementation
- **REVIEWER**: Verification and testing (read + shell)

### Safety Features
- Agents can only execute shell commands from a predefined whitelist
- `MAX_ITERATION` prevents runaway execution

### Agent Artifacts Tracking
- Agents track artifacts during execution: `files_read`, `files_created`, `files_modified`, `commands_run`
- Artifacts are passed as `metadata` in the report `DTOInstruction`
- The SUPERVISOR enriches agent reports with structured artifact summaries

### Conversation Context Filtering
- `BaseAgent.conversation_filter()` applies two-stage context reduction for ALL agents:
  1. Merges consecutive assistant messages (`_merge_assistant_messages()` in `agents.py`)
  2. Removes redundant tool call/response pairs via `compact_conversation_remove_redundant()` from `context_helper.py` — removes reads invalidated by subsequent writes, deduplicates full reads of the same file, and deduplicates identical shell commands with identical output

### Context Overflow Handling
- When total context size exceeds `MAX_CONTEXT_WINDOW_SIZE`, agents inject a user message prompting the use of the `summarize` tool
- The `summarize` tool collapses the conversation to 2 base messages plus a structured summary covering files read/written, commands run, key findings, current status, and remaining work
- Summarization is tracked by `_summarize_count` and can be triggered multiple times per agent run
- `TOOL_SUMMARIZE` is defined in `tools/tools.py` and is injected only when context overflow is detected

## Project Configuration

### Environment Variables (see `env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_URL` | — | LLM endpoint URL |
| `OPENAI_API_KEY` | — | API authentication key |
| `OPENAI_API_TIMEOUT` | 1200 | LLM request timeout in seconds |
| `MODEL` | claude-sonnet-4.5 | Default model identifier |
| `REASONING_EFFORT` | low | For o1/o3 models: `low` / `medium` / `high` |
| `IDE_MCP_HOST` | http://127.0.0.1:63342/ | JetBrains IDE MCP server URL |
| `HTTP_PORT` | 5000 | Flask server port |
| `AGENT_FILE_TOOLS` | mcp | File operations mode: `mcp` or `pure` |
| `MAX_ITERATION` | 20 | Max agent iteration safety limit |
| `SHELL_COMMAND_TIMEOUT` | 30 | Timeout for shell commands in seconds |
| `SHELL_COMMAND_DIRECTORY` | .agent-commands | Directory with predefined shell commands |
| `DEBUG` | 0 | Enable verbose LLM logging to `full_log.log` |
| `DEEPTHINKING_AGENTS` | — | Comma-separated agent names for deep thinking mode (does **not** affect CODER — CODER always runs with `thinking=False`) |
| `MAX_CONTEXT_WINDOW_SIZE` | 100000 | Maximum context window size in tokens for prompt usage tracking |

## Directory Structure

```
project_root/
├── agents.py                    # Agent implementations (ANALYTIC, CODER, REVIEWER) — class hierarchy: BaseAgent → AnalyticAgent / CoderAgent; Agent factory
├── algorythm.py                 # SUPERVISOR orchestrator (Copilot class)
├── commands_helper.py           # .agent-commands/ parser and shell executor (supports $N positional args)
├── context_helper.py            # Conversation context optimization — removes redundant tool calls to reduce token usage
├── conversation.py              # UI message formatting (DTOInstruction → HTML/text)
├── conversations_log/           # Session and LLM debug logs (not in git)
├── diff_helper.py               # Code patching utilities (apply_patch, PatchError)
├── dto/
│   ├── dto_instruction.py       # DTOInstruction dataclass (universal message object)
│   └── enums.py                 # AgentRole and EventType enumerations
├── env.example                  # Example environment configuration
├── LICENSE                      # Project license
├── llm.py                       # OpenAI-compatible LLM client; errors logged to conversations_log/llm.error and llm.error.log
├── llm_api_server.py            # Flask HTTP server (Web UI + REST API)
├── llm_parser.py                # XML tag parsing from LLM responses
├── logger_mixin.py              # LoggerMixin base class — structured logging for agents and Copilot
├── log_helper.py                # Formatting all objects for pretty-print
├── mcp_helper.py                # File operations abstraction (reads always pure; writes: mcp or pure mode)
├── path_helper.py               # Path normalization utilities
├── prompts/                     # Prompts for agent and sub-agents
│   ├── analytic_system.txt      # System prompt for ANALYTIC agent
│   ├── coder_system.txt         # System prompt for CODER agent (Jinja2 templated)
│   ├── reviewer_system.txt      # System prompt for REVIEWER agent (Jinja2 templated)
│   ├── supervisor_system.txt    # System prompt for SUPERVISOR agent
│   └── step.txt                 # Shared project-context sub-prompt (injected into all agents)
├── requirements.txt             # Python dependencies
├── run_tests.sh                 # Test runner: sets AGENT_FILE_TOOLS=pure, runs unittest discover on tests/
├── search_code.py               # In-project code search engine (SearchCode)
├── storage/                     # Temp file cache (not in git)
├── templates/                   # Web UI (SSE client, markdown rendering)
│   ├── app.html                 # Main Jinja2 template for web UI
│   ├── error.html               # Version mismatch error page
│   └── assets/
│       ├── app.js               # SSE client, message rendering, UI interaction logic
│       ├── main.css             # Chat interface styles
│       └── markdown.js          # Markdown rendering library
├── tests/                       # Unit tests
├── tools/
│   └── tools.py                 # Agent tool schema definitions and factory functions get_coder_tools() / get_reviewer_tools() for conditional shell command inclusion
├── tools_interpreter.py         # Agent tool executor (ToolsInterpreter)
├── utils/                       # Utility modules
├── AGENTS.md                    # This file — project reference for AI agents
```

## Logging and Observability

- **Session logs**: `conversations_log/log.log` — user-facing messages
- **Debug logs**: `conversations_log/full_log.log` — full LLM request/response log (when `DEBUG=1`)
- **LLM error log**: `conversations_log/llm.error` — from `llm_query()` after 5 failed retry attempts (contains last request and error details)
- **LLM stream error log**: `conversations_log/llm.error.log` — from `llm_query_stream()` after 5 failed retry attempts
- **Real-time streaming**: SSE message stream to browser via `GET /events`

## Common Development Tasks

- **Add new agent**: Add a new class in `agents.py`, define prompt files in `prompts/`, register the new role in `agents.py` and `dto/enums.py`
- **Add new agent role**: Add to `AgentRole` enum in `dto/enums.py`, create prompt files in `prompts/`, register the role in `agents.py`
- **Add new event type**: Add value to `EventType` in `dto/enums.py` and handle rendering in `conversation.py`. Note: `EventType.CONTEXT` is used for token usage tracking, emitting context window usage information (`used` and `limit` values)
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