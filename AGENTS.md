This is an **AI-powered development assistant system** that helps developers complete coding tasks through natural language instructions. The system uses a multi-agent architecture where specialized AI agents collaborate to analyze codebases, plan changes, and implement code modifications autonomously.

## Purpose

The project enables developers to:
- Submit development tasks in natural language via a web interface
- Automatically analyze project structure and requirements
- Generate detailed implementation plans
- Create and modify code files automatically
- Receive real-time progress updates through streaming responses

## Architecture

### Multi-Agent Supervisor Pattern

The system follows a hierarchical agent architecture:

```
User Task → SUPERVISOR → Specialized Agents:
                        ├─ ANALYTIC Agent (analysis & planning)
                        └─ CODER Agent (implementation)
```

### Agent Hierarchy

1. **SUPERVISOR** (implemented in `algorythm.py`)
   - Orchestrates the entire workflow
   - Delegates tasks to specialized agents
   - Makes decisions based on agent reports
   - Manages task completion and iteration limits

2. **ANALYTIC Agent** (implemented in `agents.py`)
   - Analyzes project structure
   - Searches and reads relevant files (read-only access)
   - Creates detailed implementation requirements
   - Produces plans specifying which files to change and how

3. **CODER Agent** (implemented in `agents.py`)
   - Implements code changes based on plans
   - Creates new files and modifies existing code
   - Uses precise diff-based replacements
   - Has write access to the filesystem

## Core Components

### Server and API Layer

**`llm_api_server.py`** - Flask-based HTTP server
- Serves web UI for task submission
- Implements Server-Sent Events (SSE) for real-time streaming
- Session-based message queue system
- Endpoints:
  - `/` - Web UI
  - `/send_message` - Task submission
  - `/events` - SSE event stream
- Heartbeat mechanism to maintain connections

### Orchestration Layer

**`algorythm.py`** - Core orchestration engine
- `Copilot` class: Main supervisor implementation
- Reads `.copilot_project.xml` for project manifest
- Manages conversation logs and state
- Iterative execution loop with safety limits (MAX_ITERATION)
- Tool-based LLM interaction pattern
- Provides three tools to LLM:
  - `call_agent`: Delegate to specialized agents
  - `message`: Send messages to user
  - `exit`: Complete the task

### Agent Layer

**`agents.py`** - Agent implementations
- `BaseAgent`: Abstract base class with common functionality
- `AnalyticAgent`:
  - Tools: `read_file`, `list_in_directory`, `report`
  - Read-only filesystem access
  - Analyzes and plans work
- `CoderAgent`:
  - Tools: `read_file`, `write_file`, `replace_code_in_file`, `report`
  - Read-write filesystem access
  - Implements code changes
  - Filters duplicate file reads to optimize performance
- Optional "deep thinking" mode for complex reasoning

### Command Execution Layer

**`command_interpreter.py`** - Tool execution bridge
- `CommandInterpreter` class executes agent tools
- Translates tool calls to MCP operations
- Handles:
  - File reading/writing
  - Directory listing
  - Diff-based code patching
  - Error handling and validation
- Strips code fence markers from LLM outputs

### LLM Integration Layer

**`llm.py`** - Language model integration
- OpenAI-compatible API client (works with any OpenAI-compatible endpoint)
- Supports function calling (tool use)
- Retry logic with exponential backoff (5 attempts)
- Debug logging to `conversations_log/full_log.log`
- Configurable reasoning effort for o1/o3 models
- Environment-based configuration

**`llm_parser.py`** - Response parsing utilities
- Extracts XML-style tags from LLM responses
- Regex-based pattern matching
- Handles tags with/without attributes

### Helper Modules

**`diff_helper.py`** - Smart code patching
- `apply_patch()`: Finds and replaces code fragments
- Handles exact and whitespace-normalized matching
- Prevents multiple match errors
- Supports adding/removing lines

**`path_helper.py`** - Path utilities
- `get_relative_path()`: Normalizes paths to project-relative format
- Cross-platform path handling

**`mcp_helper.py`** - IDE integration
- Two modes: `legacy` (REST API) and `sse` (MCP protocol)
- Async SSE client using MCP library
- Communicates with IDE's MCP server for file operations
- Adapts method names between modes

**`conversation.py`** - Message formatting
- Standardized message structure with timestamps
- Role-based messaging (user/assistant/system/tool)
- Terminal signal generation

## Technology Stack

### Backend
- **Python 3.12**
- **Flask 3.1.1** - Web framework
- **OpenAI SDK 1.99** - LLM API client
- **python-dotenv 1.1.1** - Environment configuration
- **requests 2.32** - HTTP client
- **mcp 1.15** - Model Context Protocol for IDE integration

### Frontend
- Vanilla JavaScript with SSE
- Markdown rendering
- Custom CSS chat interface

### Integration
- **MCP (Model Context Protocol)** - Connects to IDE (typically port 63342)
- Environment-based configuration via `.env`

## Workflow

### 1. Task Submission
```
User enters task → Flask server receives → Creates Copilot instance
→ Reads .copilot_project.xml → Initializes conversation
```

### 2. Supervisor Loop
```
SUPERVISOR analyzes task → Calls tool (call_agent/message/exit)
→ Agent executes → Returns report → SUPERVISOR decides next step
→ Repeat until complete or MAX_ITERATION reached
```

### 3. Agent Execution
```
Agent receives instruction → Builds conversation context
→ LLM query with tools → Tool calls returned
→ CommandInterpreter executes → Results added to conversation
→ Repeat until 'report' tool called → Return to SUPERVISOR
```

### 4. File Operations
```
Agent tool call → CommandInterpreter → MCP call to IDE
→ IDE performs operation → Result returned → Agent continues
```

### 5. Real-time Updates
```
Browser SSE connection → Event stream → Incremental messages
→ Progress updates → [DONE] signal on completion
```

## Key Patterns and Conventions

### Tool-Calling Pattern
- All agents use OpenAI function calling
- Tools defined as JSON schemas in `prompts/*_tools.py`
- Each agent has specialized tool sets

### Conversation Management
- Full conversation history maintained for context
- Role-based messages: system, user, assistant, tool
- Logs stored in `conversations_log/`
- CoderAgent filters duplicate reads

### Error Handling
- Retry logic in LLM calls
- PatchError for diff failures
- Graceful degradation
- MAX_ITERATION safeguard (default: 20)

### Configuration-Driven
- `.env` for API keys, model selection, timeouts
- `.copilot_project.xml` for project metadata
- Prompt templates in `prompts/` directory
- Model-specific reasoning effort settings

### Separation of Concerns
- **SUPERVISOR**: Task delegation only
- **ANALYTIC**: Read-only analysis and planning
- **CODER**: Write operations only
- Clear agent boundaries

### Iterative Refinement
- Step-by-step execution with feedback
- SUPERVISOR reviews reports before next step
- Small, isolated sub-tasks preferred
- Optional deep thinking mode for complex tasks

### Safety Features
- CODER cannot create utility scripts (prevents arbitrary code execution)
- Directory paths must end with `/` (validation)
- Immediate post-modification reads discouraged
- File content returned in tool responses

## Project Configuration

### Environment Variables (`.env`)
- **OPENAI_API_URL**: LLM endpoint URL
- **OPENAI_API_KEY**: API authentication key
- **MODEL**: Model identifier (gpt-4, claude-3, etc.)
- **REASONING_EFFORT**: For o1/o3 models (low/medium/high)
- **IDE_MCP_HOST**: IDE MCP server URL (default: http://localhost:63342)
- **MCP_CLIENT_TYPE**: `sse` or `legacy`
- **MAX_ITERATION**: Safety iteration limit
- **DEEPTHINKING_AGENTS**: Comma-separated agent names for deep thinking mode
- **DEBUG**: Enable verbose logging

## Directory Structure

```
project_root/
├── agents.py                  # Agent implementations
├── algorythm.py              # SUPERVISOR orchestration
├── command_interpreter.py    # Tool execution layer
├── conversation.py           # Message formatting
├── conversations_log/        # Session and debug logs
├── diff_helper.py           # Code patching utilities
├── llm.py                   # LLM API integration
├── llm_api_server.py        # Flask web server
├── llm_parser.py            # Response parsing
├── mcp_helper.py            # IDE integration
├── path_helper.py           # Path utilities
├── prompts/                 # Agent prompts and tools
├── templates/               # Web UI templates
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
├── AGENTS.md                # Project manifest
└── .env                     # Configuration (not in repo)
```

## Logging and Observability

- **Session logs**: `conversations_log/log.log` - User-facing messages
- **Debug logs**: `conversations_log/full_log.log` - Full LLM interactions
- **Real-time streaming**: SSE message stream to browser
- **Timestamp-based IDs**: Conversation tracking

## Common Development Tasks

- **Add new agent**: Extend `BaseAgent` in `agents.py`, define tools in `prompts/`
- **Modify prompts**: Edit Jinja2 templates in `prompts/` directory
- **Change LLM provider**: Update `OPENAI_API_URL` and `OPENAI_API_KEY` in `.env`
- **Adjust iteration limits**: Set `MAX_ITERATION` in `.env`

## Testing

- **Unit tests**: Located in `tests/` directory