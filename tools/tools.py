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

TOOL_ATTACH_IMAGE = {
    "type": "function",
    "function": {
        "name": "attach_image",
        "description": (
            "Read a local image file and attach it to the conversation as a vision input. "
            "Use this when the task references a local image file that needs to be analyzed. "
            "Pass a project-relative file path to the image within the project directory."
        ),
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Project-relative path to the local image file. The path must stay within the project directory."
                }
            }
        }
    }
}


SUPERVISOR_TOOLS = [TOOL_CALL_AGENT, TOOL_MESSAGE, TOOL_EXIT]
