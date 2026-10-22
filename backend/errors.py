"""One simple error type used by every service.

Services raise ApiError(status_code, message). main.py turns it into a JSON
response like {"detail": "message"} with that HTTP status code.
(The Streamlit app prints the "detail" text, so keep messages clear.)
"""


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
