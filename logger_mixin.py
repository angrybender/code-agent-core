import logging

from log_helper import pretty_format

logger = logging.getLogger('APP')


class LoggerMixin:
    role: str = ''
    log_file: str = ''

    def log(self, data, to_file=False):
        if not isinstance(data, str):
            data = pretty_format(data)

        output = f"[ {self.role} ] {data}"

        if not to_file:
            logger.info(output)
            return

        with open(self.log_file, "a", encoding='utf8') as f:
            f.write(output + "\n\n")