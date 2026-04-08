"""Domain exception raised by service layer.

A single class with a status_code parameter. The global handler in main.py
reads .status_code and .detail to build the HTTP response.
"""


class ServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
