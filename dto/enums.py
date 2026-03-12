from enum import Enum


class AgentRole(str, Enum):
    SUPERVISOR = "SUPERVISOR"
    ANALYTIC   = "ANALYTIC"
    CODER      = "CODER"
    REVIEWER   = "REVIEWER"


class EventType(str, Enum):
    NOPE     = "nope"
    INFO     = "info"
    MARKDOWN = "markdown"
    TOOL     = "tool"
    REPORT   = "report"
    ERROR    = "error"
    HTML     = "html"
    END      = "end"
    FILES    = "files"
    STATUS   = "status"
    WARNING  = "warning"