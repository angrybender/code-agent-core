import json

from dto.dto_tools import LLMToolDescription
from llm import llm_query

class ToolsMixin:
    @staticmethod
    def parse_tool_arguments(json_data: str):
        try:
            return json.loads(json_data)
        except json.decoder.JSONDecodeError as e:
            json_data = \
            llm_query(f"fix this JSON: ```{json_data}```\nwrap answer into tag <RESULT>", ['RESULT']).get('RESULT',
                                                                                                          [''])[0]
            if not json_data:
                return {}

            try:
                return json.loads(json_data)
            except json.decoder.JSONDecodeError as e:
                return {}


    #@staticmethod
    #def parse_tool(tool_call: dict) -> LLMToolDescription:
