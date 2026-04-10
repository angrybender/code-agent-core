TOOL_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read file by path and return its content. Use `offset` and `limit` parameters for large files to avoid loading the entire file into context. Prefer `search_file` when you don't know the exact file location or need to find specific code patterns. For discovering what files exist in a directory, use `list_in_directory` instead.",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                },
                "offset": {
                    "type": "integer",
                    "description": "Start reading from line number N (0-based). Default: 0"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to return. If not specified, returns all lines from offset to end of file"
                }
            }
        }
    }
}

TOOL_READ_MULTIPLY_FILES = {
    "type": "function",
    "function": {
        "name": "read_multiply_files",
        "description": "Read the contents of multiple files from the same directory in a single operation. Returns each file's content with clear separation. Use this tool when you need to examine 2 or more files at once — it is more efficient than multiple individual read_file calls. All files must be in the same directory specified by root_path.",
        "parameters": {
            "type": "object",
            "required": ["root_path", "file_name"],
            "properties": {
                "root_path": {
                    "type": "string",
                    "description": "Parent directory of the files"
                },
                "file_name": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file names to read"
                }
            }
        }
    }
}

TOOL_LIST_IN_DIRECTORY = {
    "type": "function",
    "function": {
        "name": "list_in_directory",
        "description": "List files and directories from a path.\nResult contains a list of files and directories (only first level); directory names end with the symbol `/`.\nUse to discover project structure and find relevant files or directories. For searching code content across files, use `search_file` instead. For reading a known file, use `read_file` directly.",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'path, for the root of the project use `.`'
                }
            }
        }
    }
}

TOOL_SEARCH_FILE = {
    "type": "function",
    "function": {
        "name": "search_file",
        "description": (
            "Searches for `needle` across all project files using fuzzy token matching. "
            "Supports languages: PHP, JS, Java, Scala, C#, Go, Ruby, HTML, CSS, YML, bash. "
            "Returns the file path and lines that contain the most relevant match. "
            "Returns the first 10 results. "
            "Use when searching for code patterns, function names, class definitions, or usages across the project. "
            "For known file locations, use `read_file` directly. "
            "For broad file/directory discovery, use `list_in_directory` first."
        ),
        "parameters": {
            "type": "object",
            "required": ["needle", "extension"],
            "properties": {
                "needle": {
                    "type": "string",
                    "description": 'The string to search for'
                },
                "extension": {
                    "type": "string",
                    "description": "File extension for filtering files to search, example: 'py' (will filter only files like '*.py'), empty string for no filtering"
                }
            }
        }
    }
}

TOOL_WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write full data to a file.\nUse this command ONLY if:\n1. You are editing a file with fewer than 100 lines.\n2. You are creating a new file.",
        "parameters": {
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                },
                "content": {
                    "type": "string",
                    "description":
"""Data to write to the file. YOU MUST WRAP the output in ```, don't escape quotes (\") and brackets (< >)
example:
```json
{
    "id": 1
}```"""
                }
            }
        }
    }
}

TOOL_REPLACE_CODE_IN_FILE = {
    "type": "function",
    "function": {
        "name": "replace_code_in_file",
        "description": "Replace part of code in file. Function locates a specified substring (str_find) in the code and replaces it with the given target string (str_replace).",
        "parameters": {
            "type": "object",
            "required": ["path", "str_find", "str_replace"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                },
                "str_find": {
                    "type": "string",
                    "description":
"""Code fragment to replace. For a deterministic search, include 1–2 lines before and after the fragment.
- Must be as small as possible and unique.
- Preserve all tabs, spaces, comments, block comments, etc.
- Follow the format conventions of the programming language you are working with."""
                },
                "str_replace": {
                    "type": "string",
                    "description":
"""Replacement code fragment.
- Preserve all tabs, spaces, comments, block comments, etc.
- Follow the format conventions of the programming language you are working with.
- Cannot be empty."""
                }
            }
        }
    }
}

TOOL_SHELL_COMMAND = {
    "type": "function",
    "function": {
        "name": "shell_command",
        "description": (
            "Execute a predefined named shell command in the project root directory. "
            "Use for build, test, lint, or install commands. "
            "Pass the command NAME (e.g. 'run-tests', 'build'), not a raw shell string. "
            "Some commands accept positional arguments ($1, $2, ...) — pass them via the 'args' list. "
            "Available command names and their arguments are listed in the system prompt."
        ),
        "parameters": {
            "type": "object",
            "required": ["command_name"],
            "properties": {
                "command_name": {
                    "type": "string",
                    "description": "Name of the predefined command to execute (e.g. 'run-tests'). Must match one of the available shell command names listed in the system prompt."
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional positional arguments for the command. $1 is args[0], $2 is args[1], etc. Only provide if the command definition includes $N placeholders."
                }
            }
        }
    }
}

TOOL_REPORT = {
    "type": "function",
    "function": {
        "name": "report",
        "description": "Print a short report of your work.\nUse this command when you have completely executed the instructions and have decided to finish the work.\nInclude in your report: summary of work done, list of files analyzed/created/modified, and any issues found.",
        "parameters": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text is a report in the Markdown format. Don't write the full content of the files — a short description is enough! Include a '## Files' section listing all files you created or modified."
                }
            }
        }
    }
}

TOOL_CALL_AGENT = {
    "type": "function",
    "function": {
        "name": "call_agent",
        "description": "Call an agent to execute a sub-task. Include ALL necessary context in the instruction — sub-agents have NO access to your conversation history. Always include relevant file paths, task details, and any previous agent findings.",
        "parameters": {
            "type": "object",
            "required": ["agent_name", "instruction"],
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "agent_name is an agent name; possible values: ANALYTIC, CODER, REVIEWER, MCP"
                },
                "instruction": {
                    "type": "string",
                    "description": "A complete, self-contained instruction for the agent. Must include all file paths, context, and requirements — the agent cannot see your conversation."
                },
                "images": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional list of image index numbers (1-based) to forward to the sub-agent. For example, [1, 2] means forward the 1st and 2nd images attached by the user. Do NOT generate, copy, or reconstruct base64 data — only specify the index numbers of the images that are relevant to this sub-task."
                }
            }
        }
    }
}

TOOL_MESSAGE = {
    "type": "function",
    "function": {
        "name": "message",
        "description": "Print message for user, show intermediate result or some comment. Use for progress updates, clarifications, or intermediate findings during long-running tasks. Do NOT use as a substitute for `report` — use `report` when work is fully complete. Do NOT use as a substitute for `exit` — use `exit` when the conversation should end.",
        "parameters": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "text is a message for the user in the Markdown format"
                }
            }
        }
    }
}

TOOL_EXIT = {
    "type": "function",
    "function": {
        "name": "exit",
        "description": "Stop the conversation and signal completion. Use ONLY when you have fully completed the work and achieved the goal. Do NOT use if there are remaining tasks, unresolved issues, or pending agent reports. Do NOT use if the task was only partially completed — instead, continue delegating to agents.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}

TOOL_SUMMARIZE = {
    "type": "function",
    "function": {
        "name": "summarize",
        "description": (
            "CRITICAL: Use this tool ONLY when instructed due to context window overflow. "
            "Provide a comprehensive structured summary of all work done so far. "
            "Your summary MUST follow the required sections listed in the parameter description."
        ),
        "parameters": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "Comprehensive work summary in Markdown. MUST include ALL of these sections:\n"
                        "## Files Read: (list each file path and key findings from it)\n"
                        "## Files Created/Modified: (list each path and what was done)\n"
                        "## Commands Run: (command name and result/output summary)\n"
                        "## Key Findings: (important values, patterns, decisions discovered)\n"
                        "## Current Status: (what has been completed)\n"
                        "## What Remains: (what still needs to be done to complete the task)"
                    )
                }
            }
        }
    }
}

def get_coder_tools(has_shell_commands: bool) -> list:
    """Return CODER_TOOLS with or without shell command support."""
    if has_shell_commands:
        return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_LIST_IN_DIRECTORY, TOOL_WRITE_FILE, TOOL_REPLACE_CODE_IN_FILE, TOOL_SHELL_COMMAND, TOOL_REPORT]
    return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_LIST_IN_DIRECTORY, TOOL_WRITE_FILE, TOOL_REPLACE_CODE_IN_FILE, TOOL_REPORT]


def get_reviewer_tools(has_shell_commands: bool) -> list:
    """Return REVIEWER_TOOLS with or without shell command support."""
    if has_shell_commands:
        return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_SEARCH_FILE, TOOL_SHELL_COMMAND, TOOL_REPORT]
    return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_SEARCH_FILE, TOOL_REPORT]


def get_analytic_tools(has_shell_commands: bool) -> list:
    """Return ANALYTIC tools with or without shell command support."""
    if has_shell_commands:
        return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_LIST_IN_DIRECTORY, TOOL_SEARCH_FILE, TOOL_SHELL_COMMAND, TOOL_REPORT]
    return [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_LIST_IN_DIRECTORY, TOOL_SEARCH_FILE, TOOL_REPORT]


TOOL_SELECT_MCP = {
    "type": "function",
    "function": {
        "name": "select_mcp",
        "description": "Select a specific MCP server from the available list to work with. Call this first to choose which MCP server to use.",
        "parameters": {
            "type": "object",
            "required": ["server_name"],
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "The name of the MCP server to select (e.g. 'mcp_browser'). Must match one of the available MCP server names."
                }
            }
        }
    }
}


ANALYTIC_TOOLS = [TOOL_READ_FILE, TOOL_READ_MULTIPLY_FILES, TOOL_LIST_IN_DIRECTORY, TOOL_SEARCH_FILE, TOOL_REPORT]
CODER_TOOLS = get_coder_tools(True)
REVIEWER_TOOLS = get_reviewer_tools(True)
SUPERVISOR_TOOLS = [TOOL_CALL_AGENT, TOOL_MESSAGE, TOOL_EXIT]
MCP_BASE_TOOLS = [TOOL_SELECT_MCP, TOOL_REPORT]