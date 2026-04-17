
class ConversationMixin:
    @staticmethod
    def merge_assistant_messages(conversation: list[dict]) -> list[dict]:
        # merge multiply assistant messages to once

        merged = True
        while merged:
            merged = False
            if len(conversation) >= 2:
                prev = conversation[-2]
                last = conversation[-1]
                if (prev['role'] == 'assistant' and last['role'] == 'assistant'
                        and isinstance(prev.get('content'), str)
                        and isinstance(last.get('content'), str)):
                    prev['content'] += "\n" + last['content']
                    conversation = conversation[:-1]
                    merged = True

        return conversation

    @staticmethod
    def create_report(conversation: list[dict]):
        report = ""
        last_message = ""
        for message in conversation:
            if message['role'] == 'assistant':
                _content = message['content'].strip() if message['content'] else ""
                if _content:
                    last_message = _content

                for tool in message.get('tool_calls', []):
                    if tool['function']['name'] == 'report':
                        report += tool['function']['arguments_parsed'].get('text', '')

        report = report.strip()
        if report:
            return report
        else:
            return last_message