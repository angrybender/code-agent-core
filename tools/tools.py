TOOL_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read file by path and return it content",
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
        "description": "Read file by path and return it content",
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
        "description": "List files and directories from path.\nResult contains list of files and directories (only first level), for directory name end of symbol `/`",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'path, for root of project use `.`'
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
            "Looking for `needle` over all project's files. Using `ast-grep` python lib for understanding language structure and simple string search for text and config files."
            "Support languages: PHP, JS, Java, Scala, C#, Go, Ruby, HTML, CSS, YML, bash."
            "Return file path and lines with contain most relevant needle."
            "Return first 10 results."
        ),
        "parameters": {
            "type": "object",
            "required": ["needle", "extension"],
            "properties": {
                "needle": {
                    "type": "string",
                    "description": 'string for searching'
                },
                "extension": {
                    "type": "string",
                    "description": "extension for filtering files looking for, example: 'py' (will filter only files like '*.py'), empty string for no filtration"
                }
            }
        }
    }
}

TOOL_WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write full data to file.\nUse this command ONLY if:\n1. You edit a file less than 100 lines\n2. You create new file.",
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
"""data for write to the file, YOU MUST WRAP output ```, dont escape quotes (\") and brackets (< >)
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
"""fragment code for replacing, for determinate search - catch 1-2 lines before and after the fragment
- must be small as possible and unique
- save all tab, spaces, comment, block comments etc
- follow format considering for program language that you prints"""
                },
                "str_replace": {
                    "type": "string",
                    "description":
"""fragment code to replace
- save all tab, spaces, comment, block comments etc
- follow format considering for program language that you prints
- can not be empty"""
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
            "Available command names are listed in the system prompt."
        ),
        "parameters": {
            "type": "object",
            "required": ["command_name"],
            "properties": {
                "command_name": {
                    "type": "string",
                    "description": "Name of the predefined command to execute (e.g. 'run-tests'). Must match one of the available shell command names listed in the system prompt."
                }
            }
        }
    }
}

TOOL_REPORT = {
    "type": "function",
    "function": {
        "name": "report",
        "description": "Print short report of you work.\nUse this command when you completely executed instructions and you have decided finish a work.",
        "parameters": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text is a report in the markdown format. Dont write full content of files - short description is enough!"
                }
            }
        }
    }
}

TOOL_CALL_AGENT = {
    "type": "function",
    "function": {
        "name": "call_agent",
        "description": "Calling agent for execute sub-task",
        "parameters": {
            "type": "object",
            "required": ["agent_name", "instruction"],
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "agent_name is a agent name, possible values: ANALYTIC, CODER, REVIEWER"
                },
                "instruction": {
                    "type": "string",
                    "description": "instruction is a prompt for suitable agent, you must put into instruction all data for target agent"
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
                    "description": "text is a message for user in the markdowm format"
                }
            }
        }
    }
}

TOOL_EXIT = {
    "type": "function",
    "function": {
        "name": "exit",
        "description": "Stop conversation, only if you full complete a work and achieve the goal",
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