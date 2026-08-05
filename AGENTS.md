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
Note: The REVIEWER role is implemented by `AnalyticAgent` (not a separate class). `AnalyticAgent` has a class dict `AGENT_SUB_TYPE_TOOLS` with both `'ANALYTIC'` and `'REVIEWER'` keys; `AnalyticAgent.get_tools()` does `self.AGENT_SUB_TYPE_TOOLS[self.role]` to get the tool list for the current role — so both the ANALYTIC and REVIEWER roles use `AGENT_SUB_TYPE_TOOLS` (not `CODER_TOOLS`). It filters `ToolsFabric().get_all_tools()` by that list and appends `project.get_commandlets_tools(role)`. `CODER_TOOLS` is a separate constant belonging only to `CoderAgent`; `CoderAgent.get_tools()` returns tools from `ToolsFabric().get_all_tools()` filtered by `CODER_TOOLS` and appends `project.get_commandlets_tools(role)`. Commandlet tools (prefixed `shell__`) are generated dynamically from `.agent-commands/` files.

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
- Error logging: `llm_query()` logs to `conversations_log/llm.error`, `llm_query_stream()` logs to `conversations_log/llm.error.log` — both after 5 failed retry attempts for transient/unexpected exceptions. `APIError` (including `BadRequestError`) is raised immediately as `LLMRequestFormat` without retrying or writing to the log file

**`context_helper.py`** — Conversation context optimization
- Provides `compact_conversation_remove_redundant()` function
- Three optimization phases:
  1. Removes `read_file`, `read_multiply_files`, and `replace_code_in_file` calls that precede a later `write_file` to the same path (only `write_file` is treated as a full-file write that invalidates prior reads and patches; `replace_code_in_file` alone does not invalidate earlier reads)
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
- **python-frontmatter 1.1.0** — YAML frontmatter parsing for `.agent-commands/` files
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
→ Reads project manifest (AGENTS.md) via MCP call to the IDE (`get_file_text_by_path`); returns empty if MCP is unavailable
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

> **Commandlets** are the mechanism behind the shell command system. A commandlet is a "skill" that bundles a human-readable description with a whitelist of shell commands an agent can execute. See **[Commandlets (Skills) Architecture](#commandlets-skills-architecture)** for the full specification.

```
.agent-commands/my-command.md  →  parse_agent_commands()
→ whitelist of named commandlets loaded at startup
→ Agent calls shell__{command}_{block}("my-command", args)
→ ToolsInterpreter → ToolShell → run_commandlet() → subprocess with $N arg substitution
→ Output returned to agent
```

### 6. Real-time Updates
```
Browser SSE connection → GET /events → Incremental messages streamed
→ Progress updates → [DONE] signal on completion
```

## Commandlets (Skills) Architecture

### Concept & Ideology

A **commandlet** is a **"skill"** — it bundles a human-readable description with a whitelist of shell commands that an agent can execute. Commandlets bridge the gap between free-form AI tool use and controlled, safe command execution. Rather than giving an agent unrestricted shell access, each commandlet defines:

1. **What the skill does** — a natural-language description injected into the agent's system prompt so the AI can decide when it's relevant.
2. **What commands it runs** — one or more shell blocks, each becoming a discrete LLM-callable tool.
3. **Who can use it** — per-role filtering (e.g., only `CODER`, or `CODER,REVIEWER,ANALYTIC`).

This design ensures agents can only invoke commands that have been explicitly defined and reviewed by the developer — there is no mechanism to execute arbitrary shell commands.

### File Format

Commandlets are defined as Markdown files (`.md`) in the `.agent-commands/` directory (configurable via `SHELL_COMMAND_DIRECTORY`). Each file has the following structure:

#### YAML Frontmatter

```yaml
---
role: CODER,REVIEWER,ANALYTIC   # Comma-separated list of agent roles that can use this commandlet (optional)
enabled: true                    # If false, the file is skipped entirely (default: true)
mcp: false                       # If true, treated as MCP server config (NOT a shell commandlet) — excluded from shell commandlets (default: false)
description: My skill            # Short description of the skill (REQUIRED) — injected into SUPERVISOR guidance and agent tool awareness
when: Use when...                # Optional guidance on when to use this skill
---
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `role` | string (comma-separated) | `[]` (all roles) | Agent roles allowed to use this commandlet. Valid values: `SUPERVISOR`, `ANALYTIC`, `CODER`, `REVIEWER` (`MCP` is not valid). If omitted, all roles get access. |
| `enabled` | boolean | `true` | If `false`, the file is skipped entirely during parsing. |
| `mcp` | boolean | `false` | If `true`, the file is treated as an MCP server configuration and excluded from shell commandlet parsing. |
| `description` | string | *(required)* | Short description of the skill. Injected into the SUPERVISOR guidance and agent tool awareness. **Required** — a commandlet without `description` is invalid and raises a parsing error. |
| `when` | string | *(none)* | Optional guidance on when to use this skill. When present, combined into the description as: `{description}\n**WHEN USE**{when}`. |

#### Body Structure

The body is split by `---` separators into sections:

- **Section 1 (before the first `---`)**: Extended description — detailed information about the skill, retrievable on-demand via the `skill_description` tool. Not injected into prompts automatically.
- **Sections 2+ (after each `---`)**: Individual **shell blocks**, each containing:
  - A text description of the block (markdown, excluding code fences)
  - A fenced code block (`` ``` ``) containing the actual shell command
  - Optional `$N` argument description lines (e.g., `$1 - description of first argument`)
  - Optional `# alias` comment on the first line of the code block to override the auto-generated tool name

#### Example Commandlet File

```markdown
---
role: ANALYTIC,CODER
description: Git commands
when: Use for interaction with git
---

Git commands
Use for interaction with git

**Rules**
- DONT add to git file, if you hasnt created it!

---

Add file to repository
If you created new file - use this tool for adding to repository

$1 - path to file

```
git add "$1"
```

---

Show all git branches

```
git branch
```
```

#### `$N` Positional Argument Substitution

Shell commands can reference positional arguments using `$1`, `$2`, `$3`, etc. Placeholders must be a **contiguous sequence starting at `$1`** (e.g., `$1`, `$2`, `$3` — not `$1`, `$3`). At parse time:

- Each `$N` placeholder is detected and its description extracted from lines like `$1 - description`.
- At execution time, the agent-supplied `args` array values are substituted into the command in **reverse order** (highest index first) to avoid partial replacements (e.g., `$11` being replaced by `$1`'s value).
- The argument count is **validated** — if the number of provided arguments doesn't match the number of `$N` placeholders, the execution returns an error.

#### Auto-Naming Convention for Tools

Each shell block becomes an LLM tool named `shell__{command}_{block}`, where:

- `{command}` is the filename without `.md` extension (e.g., `git`, `run_tests`)
- `{block}` is derived from the shell command text itself:
  - If the code block starts with `# alias`, the alias text (lowercased, spaces → underscores, truncated to 16 chars) is used, suffixed with `_N` (block index).
  - Otherwise, the first words of the command are normalized (lowercased, non-alphanumeric → spaces → underscores, max 16 chars), suffixed with `_N` (block index).
- Example: `git.md` with a block running `git add "$1"` produces the tool `shell__git_git_add_1`.

#### Parsing Exclusions

- **`mcp: true` files**: Excluded from shell commandlets — treated as MCP server configs instead.
- **`enabled: false` files**: Skipped entirely.
- **Missing `description` frontmatter**: Raises a `ValueError` (commandlet is invalid without it).
- **Files with fewer than 2 sections**: Skipped (a commandlet must have at least a description and one shell block).
- **Shell blocks without a valid code fence**: Skipped.
- **Commandlets with zero valid shell blocks**: The entire commandlet is excluded.

### Calling Algorithm / Pipeline

The full lifecycle of a commandlet from definition to execution:

```
                        ┌─────────────────────────────────────────────────┐
                        │  1. STARTUP                                       │
                        │  .agent-commands/*.md files parsed                │
                        │  via parse_agent_commands() in commands_helper.py │
                        │  → produces list of commandlet definitions        │
                        └──────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                        ┌─────────────────────────────────────────────────┐
                        │  2. TOOL REGISTRATION                             │
                        │  Project.get_commandlets_tools(role) builds       │
                        │  LLM tool schemas (shell__{command}_{block})      │
                        │  for each agent role, filtered by `role` config   │
                        │  → tools appended to agent's get_tools()          │
                        └──────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                        ┌─────────────────────────────────────────────────┐
                        │  3. GUIDANCE INJECTION                            │
                        │  Copilot._get_commands_guidance() generates       │
                        │  <Guidance command_name="..." available_to="..."> │
                        │  XML blocks from commandlet descriptions          │
                        │  → injected into SUPERVISOR system prompt         │
                        └──────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                        ┌─────────────────────────────────────────────────┐
                        │  4. AI DECISION                                   │
                        │  Agent reads descriptions in its tool list /      │
                        │  guidance and decides which commandlet tool       │
                        │  to call (with appropriate arguments)             │
                        └──────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                        ┌─────────────────────────────────────────────────┐
                        │  5. EXECUTION                                     │
                        │  shell__* tool call → ToolsInterpreter detects    │
                        │  SHELL prefix → ToolShell.exec() →                │
                        │  Project.run_commandlet() validates args,         │
                        │  substitutes $N, executes via subprocess          │
                        │  → output returned to agent                       │
                        └───────────────────────────────────────────────────┘
```

#### Startup — Parsing

At `Copilot._init()` time, a `Project` instance is created. The constructor calls `parse_agent_commands(directory)` from `commands_helper.py`, which:

1. Globs all `*.md` files in the `SHELL_COMMAND_DIRECTORY` (default: `.agent-commands/`), sorted alphabetically.
2. Parses each file's YAML frontmatter via `python-frontmatter`.
3. Validates and normalizes the `role` field (comma-separated string → list; rejects `MCP` as a valid role).
4. Skips files where `enabled: false` or `mcp: true`.
5. Validates that `description` is present in frontmatter (raises `ValueError` if missing).
6. Splits the body on `---` separators into sections.
7. Extracts each shell block: fenced code block (the command), optional `# alias` for naming, and `$N` argument descriptions.
8. Returns a list of commandlet definitions, each containing `command`, `description` (from frontmatter, with `when` combined if present), `extended_description` (body section[0]), `shell_blocks[]`, and `config`.

#### Tool Registration

Both `AnalyticAgent.get_tools()` and `CoderAgent.get_tools()` call `self.project.get_commandlets_tools(self.role)`, which:

- Iterates over all parsed commandlets.
- Filters by role: if a commandlet's `role` config is set and the agent's role is not in that list, the commandlet is excluded.
- For each remaining shell block, builds an LLM tool schema:
  - **Name**: `shell__{command}_{block_name}` (e.g., `shell__git_git_add_1`)
  - **Description**: The block's description text
  - **Parameters**: If the block has `$N` args, an `args` array parameter with `minItems`/`maxItems` enforcing exact arg count; otherwise an empty parameter object.
  - **`pre_output: true`**: Set on each tool so the UI shows the command before execution.

#### Guidance Injection

`Copilot._get_commands_guidance()` (in `algorythm.py`) generates `<Guidance>` XML blocks that are injected into the SUPERVISOR's system prompt:

```
<Guidance command_name="git" available_to="ANALYTIC,CODER">
Git commands
Use for interaction with git
...
</Guidance>
```

- The guidance is rendered into the shared step prompt (`system_step.txt`) via Jinja2 (`project_guidance` variable).
- **Short descriptions** (fewer than 2 lines after sanitizing) are **excluded** from guidance — only multi-line descriptions provide enough context for the SUPERVISOR to make delegation decisions.
- Code fences are stripped from descriptions.

#### Execution

When an agent calls a `shell__*` tool:

1. **`ToolsInterpreter.execute()`** detects the `shell` prefix (`ToolPrefixes.SHELL`) and routes to `ToolShell.exec()` instead of loading a standard tool module.
2. **`ToolShell.exec()`** validates that the tool name is in the agent's registered `shell_tools` set; if not, raises `ToolError` listing available commands.
3. **`Project.run_commandlet(tool_name, args)`**:
   - Finds the matching commandlet definition by tool name.
   - **Validates argument count**: must match the number of `$N` placeholders exactly.
   - **Substitutes `$N` placeholders**: iterates args in reverse order (highest index first) and replaces `$1`, `$2`, etc.
   - **Executes via `execute_terminal_command()`**: runs the command via `subprocess.run()` with `shell=True` (on non-Windows) or `shell=False` (on Windows), using the project root as the working directory.
   - Returns a dict with `stdout`, `stderr`, `status` (`ok`/`error`/`timeout`), and the final `cmd` string.
4. **Timeout handling**: Commands are capped at `SHELL_COMMAND_TIMEOUT` (default: 30s). On timeout, partial output is returned with an `error_code: 'timeout'`.
5. The result is formatted by `ToolShell` into a readable output (`$ {cmd}` + stdout/stderr) and returned to the agent.

#### Skill Description Tool

- Agents can call `system__skill_description` with a skill name to retrieve the extended description on-demand.

### Whitelist & Argument Safety Model

The commandlet system enforces strict safety boundaries:

- **Whitelist-only execution**: Agents can **only** execute commands defined in `.agent-commands/*.md` files. There is no mechanism to run arbitrary shell commands. Any tool call with a `shell__` prefix that doesn't match a registered commandlet raises `ToolError`.
- **Argument validation**: Each commandlet declares its expected `$N` arguments at parse time. At execution time:
  - The argument count is validated — a mismatch returns an `error_code: 'arguments'` error.
  - Arguments are substituted as positional `$N` parameters (reverse-order replacement prevents cascading replacements).
  - Arguments are typed as strings in the LLM tool schema (`type: array, items: {type: string}`).
- **Per-role filtering**: Commandlets are only registered as tools for roles specified in their `role` frontmatter. An agent that doesn't have a commandlet in its tool list cannot call it.
- **Timeout enforcement**: All commands are subject to `SHELL_COMMAND_TIMEOUT`, preventing long-running or hung processes.
- **Working directory**: Commands execute with the project root as `cwd`, ensuring consistent paths.

## Key Patterns and Conventions

### Tool-Calling Pattern
- All agents use OpenAI function calling
- Each agent has a specialized, minimal tool set

### Search System
- ANALYTIC and REVIEWER use `search_file` tool powered by `SearchCode`
- Supports fuzzy token matching — useful when exact code location is unknown
- Results include file path, line numbers, matched content, and relevance score

### Conversation Management
- Full conversation history maintained for context within each agent turn
- Logs stored in `conversations_log/`

### Error Handling
- Retry logic in LLM calls (5 attempts): `llm_query()` uses a flat 1-second sleep between retries; `llm_query_stream()` uses exponential backoff
- `MAX_ITERATION` safeguard prevents infinite loops
- `LLMRequestFormat` exception signals malformed tool calls or API format errors; agents retry up to 4 times — each retry strips the last message(s) and injects a prompt asking for a `report` tool call; after 4 failed attempts the agent emits `EventType.ERROR` and exits

### Configuration-Driven
- `.env` for API keys, model selection, timeouts, modes
- Project manifest (`AGENTS.md`) for project metadata

### Separation of Concerns
- **SUPERVISOR**: Task delegation and orchestration only
- **ANALYTIC**: Read-only analysis and planning
- **CODER**: Write operations and implementation
- **REVIEWER**: Verification and testing (read + shell)

### Safety Features
- Agents can only execute shell commands from a predefined whitelist (commandlets — see **[Commandlets (Skills) Architecture](#commandlets-skills-architecture)**)
- `MAX_ITERATION` prevents runaway execution

### Agent Artifacts Tracking
- Agents track artifacts during execution: `files_read`, `files_created`, `files_modified`, `commands_run`
- Artifacts are passed as `metadata` in the report `DTOInstruction`
- The SUPERVISOR enriches agent reports with structured artifact summaries

### Conversation Context Filtering
- `BaseAgent.conversation_filter()` applies two-stage context reduction:
  1. Merges consecutive assistant messages (`_merge_assistant_messages()` in `agents.py`) — always applied
  2. Removes redundant tool call/response pairs via `compact_conversation_remove_redundant()` from `context_helper.py` — only triggered when the number of tool-call messages exceeds `MAX_ITERATION // 2`; removes reads invalidated by subsequent writes, deduplicates full reads of the same file, and deduplicates identical shell commands with identical output

### Context Overflow Handling
- When total context size exceeds `MAX_CONTEXT_WINDOW_SIZE`, agents inject a user message prompting the use of the `summarize` tool
- The `summarize` tool collapses the conversation to 4 messages: the original system prompt and first user message, plus a new assistant summary message (covering files read/written, commands run, key findings, current status, and remaining work) and a new system continuation prompt
- Summarization is tracked by `_summarize_count` and can be triggered multiple times per agent run
- There is no `TOOL_SUMMARIZE` constant in `tools/tools.py`; the summarize tool is the `ToolSummarize` class in `tools/system/tool_summarize.py`, discovered dynamically by `ToolsFabric`, and is injected only when context overflow is detected

## Project Configuration

### Environment Variables (see `env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_URL` | — | LLM endpoint URL |
| `OPENAI_API_KEY` | — | API authentication key |
| `OPENAI_API_TIMEOUT` | 1200 | LLM request timeout in seconds (required — no code-level fallback) |
| `MODEL` | claude-sonnet-4.5 | Default model identifier |
| `REASONING_EFFORT` | low | For o1/o3 models: `low` / `medium` / `high` |
| `IDE_MCP_HOST` | http://127.0.0.1:63342/ | JetBrains IDE MCP server URL |
| `HTTP_PORT` | 5000 | Flask server port |
| `AGENT_FILE_TOOLS` | mcp | File operations mode: `mcp` or `pure` |
| `MAX_ITERATION` | 20 | Max agent iteration safety limit (required — no code-level fallback) |
| `SHELL_COMMAND_TIMEOUT` | 30 | Timeout for shell commands in seconds |
| `SHELL_COMMAND_DIRECTORY` | .agent-commands | Directory with predefined shell commands |
| `DEBUG` | 0 | Enable verbose LLM logging to `full_log.log` |
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
├── llm.py                       # OpenAI-compatible LLM client; errors logged to conversations_log/llm.error and llm.error.log
├── llm_api_server.py            # Flask HTTP server (Web UI + REST API)
├── llm_parser.py                # XML tag parsing from LLM responses
├── logger_mixin.py              # LoggerMixin base class — structured logging for agents and Copilot
├── log_helper.py                # Formatting all objects for pretty-print
├── mcp_helper.py                # File operations abstraction (reads always pure; writes: mcp or pure mode)
├── path_helper.py               # Path normalization utilities
├── prompts/                     # Prompts for agent and sub-agents
├── search_code.py               # In-project code search engine (SearchCode)
├── storage/                     # Temp file cache (not in git)
├── templates/                   # Web UI (SSE client, markdown rendering)
├── tests/                       # Unit tests
├── tools/
│   ├── fabric.py                # Tool factory (ToolsFabric) — discovers and instantiates all tool classes
│   └── tools.py                 # SUPERVISOR tool schema definitions (TOOL_CALL_AGENT, TOOL_MESSAGE, TOOL_EXIT)
├── tools_interpreter.py         # Agent tool executor (ToolsInterpreter)
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
- **Add shell command (commandlet)**: Create a `.md` file in `.agent-commands/` with YAML frontmatter (`role`, `enabled`, `mcp`), a description section, and `---`-separated shell blocks each containing a fenced code block. Use `$N` for positional arguments with `$N - description` lines. See **[Commandlets (Skills) Architecture](#commandlets-skills-architecture)** for the full file format specification
- **Modify prompts**: Edit templates in `prompts/` directory (Jinja2 syntax for CODER/REVIEWER)
- **Adjust iteration limits**: Set `MAX_ITERATION` in `.env`

## Testing

Unit tests are located in `tests/`

## Restrictions:
- Don't list directory `./storage` and read files into
- Don't list directory `./conversations_log` and read files into