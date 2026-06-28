from enum import Enum


class AgentRole(str, Enum):
    SUPERVISOR = "SUPERVISOR"
    ANALYTIC   = "ANALYTIC"
    CODER      = "CODER"
    REVIEWER   = "REVIEWER"
    MCP        = "MCP"


class EventType(str, Enum):
    NOPE     = "nope"
    PENDING  = "pending"
    INFO     = "info"
    MARKDOWN = "markdown"
    TOOL     = "tool"
    AGENT    = "agent"
    REPORT   = "report"
    ERROR    = "error"
    HTML     = "html"
    END      = "end"
    FILES    = "files"
    STATUS   = "status"
    WARNING  = "warning"
    EXIT    = "exit"
    CONTEXT = "context"


class ToolOperation(str, Enum):
    READ    = 'READ'
    CREATE  = 'CREATE'
    UPDATE  = 'UPDATE'
    SHELL   = 'SHELL'
    MCP     = 'MCP'
    OTHER   = 'OTHER'
    REPORT  = 'REPORT'

class ToolPrefixes:
    SHELL   = 'shell'