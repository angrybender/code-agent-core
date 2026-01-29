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