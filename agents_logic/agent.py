import os
import json
import hashlib
import shutil
import glob
import uuid
import datetime
import logging

from jinja2 import Environment, BaseLoader
from dotenv import load_dotenv

from logger_mixin import LoggerMixin
from conversation_mixin import ConversationMixin
from tools_mixin import ToolsMixin


load_dotenv()
logger = logging.getLogger('APP')


class BaseAgent(LoggerMixin, ConversationMixin, ToolsMixin):
    def __init__(self, role: str):
        pass