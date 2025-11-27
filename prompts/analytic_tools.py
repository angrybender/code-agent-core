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
            "name": "report",
            "description": "Print short report of you work.\nUse this command when you completely executed instructions and you have decided finish a work.",
            "parameters": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text is a report in the markdowm format. Dont write full content of files - short description is enough!"
                    }
                }
            }
        }
    },
]