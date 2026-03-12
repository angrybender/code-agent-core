TOOL_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read file by path and return its content",
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

TOOL_READ_FILE_SIMPLE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read file by path and return its content",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                }
            }
        }
    }
}

TOOL_LIST_IN_DIRECTORY = {
    "type": "function",
    "function": {
        "name": "list_in_directory",
        "description": "List files and directories from a path.\nResult contains a list of files and directories (only first level); directory names end with the symbol `/`",
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
            "Returns the first 10 results."
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
        "description": "Print a short report of your work.\nUse this command when you have completely executed the instructions and have decided to finish the work.",
        "parameters": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text is a report in the Markdown format. Don't write the full content of the files — a short description is enough!"
                }
            }
        }
    }
}

TOOL_CALL_AGENT = {
    "type": "function",
    "function": {
        "name": "call_agent",
        "description": "Call an agent to execute a sub-task",
        "parameters": {
            "type": "object",
            "required": ["agent_name", "instruction"],
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "agent_name is an agent name; possible values: ANALYTIC, CODER, REVIEWER"
                },
                "instruction": {
                    "type": "string",
                    "description": "instruction is a prompt for the selected agent; you must put all data needed by the target agent into the instruction"
                }
            }
        }
    }
}

TOOL_MESSAGE = {
    "type": "function",
    "function": {
        "name": "message",
        "description": "Print message for user, show intermediate result or some comment",
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
        "description": "Stop the conversation, only if you have fully completed the work and achieved the goal",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}

ANALYTIC_TOOLS = [TOOL_READ_FILE, TOOL_LIST_IN_DIRECTORY, TOOL_SEARCH_FILE, TOOL_REPORT]
CODER_TOOLS = [TOOL_READ_FILE, TOOL_LIST_IN_DIRECTORY, TOOL_WRITE_FILE, TOOL_REPLACE_CODE_IN_FILE, TOOL_SHELL_COMMAND, TOOL_REPORT]
REVIEWER_TOOLS = [TOOL_READ_FILE_SIMPLE, TOOL_SEARCH_FILE, TOOL_SHELL_COMMAND, TOOL_REPORT]
SUPERVISOR_TOOLS = [TOOL_CALL_AGENT, TOOL_MESSAGE, TOOL_EXIT]