tools = [
    {
        "type":"function",
        "function":{
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
    },
    {
        "type":"function",
        "function":{
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
    },
    {
        "type":"function",
        "function":{
            "name": "exit",
            "description": "Stop conversation, only if you full complete a work and achieve the goal",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]