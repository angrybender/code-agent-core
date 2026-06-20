from dataclasses import dataclass, field
from typing import Optional, Union

from dto.enums import ToolOperation

@dataclass
class DTOTool:
    tool_name: str
    result: str
    error: bool = False
    operation: Union[ToolOperation, str] = ToolOperation.OTHER

    file_path: Optional[str] = None
    output: Optional[str] = None

    meta: dict = field(default_factory=dict)


@dataclass
class LLMToolDescription:
    function: str
    id: str
    args: dict = field(default_factory=dict)