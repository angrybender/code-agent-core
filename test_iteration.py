from dto.dto_instruction import SystemPrompt, LLMCallInstruction, ToolResultInstruction, StartInstruction
from core.project import Project
from core.instructions_transition import Transition
from interpreter.llm_nterpreter import LLMInterpreter

from utils.log import pretty_print_as_json

conversation = [
    SystemPrompt().setData({
        'tools': [{
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
            }, {
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
        }],
        'role': 'system',
        'content': "You are LLM agent for calling tools"
    }),
]

fsm = Transition()

instruction = StartInstruction().setRequest('Read the file: readme.md')
conversation.append(instruction)

instruction = conversation[-1]
next_instruction = fsm.generate(instruction)

print(f'From {instruction.getType()} -> {next_instruction.getType()}')
print(f'Execute {next_instruction.getType()}...')

_ = interpreter = LLMInterpreter(Project(), conversation)
interpreter.execute(next_instruction)


instruction = next_instruction
conversation.append(instruction)
next_instruction = fsm.generate(instruction)
conversation.append(next_instruction)
print(f'From {instruction.getType()} -> {next_instruction.getType()}')

print('')
for instruction in conversation:
    print(instruction.getType(), ':')
    print(pretty_print_as_json(instruction.getData()))
    print('')