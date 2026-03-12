from dataclasses import dataclass, field
from typing import Optional, Union

from dto.enums import EventType


@dataclass
class DTOInstruction:
    type: Union[EventType, str]
    message: str = ""
    message_id: str = ""
    result: dict = field(default_factory=dict)
    exit: bool = False
    hidden: bool = False
    function: Optional[str] = None
    args: list = field(default_factory=list)
    is_success: bool = True
    is_final: bool = True