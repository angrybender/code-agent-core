from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class DTOInstruction:
    _id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    type: str
    message: str = ""
    result: dict = field(default_factory=dict)
    exit: bool = False
    hidden: bool = False
    function: Optional[str] = None
    args: list = field(default_factory=list)
    is_success: bool = True

    def get_id(self) -> str:
        return self._id