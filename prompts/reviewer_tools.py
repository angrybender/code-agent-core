tools = [
    {
        "type":"function",
        "function":{
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
    },
    {
        "type":"function",
        "function":{
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
    },
    {
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
    },
    {
        "type":"function",
        "function":{
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
    },
]