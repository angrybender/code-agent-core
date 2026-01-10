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
    },
    {
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