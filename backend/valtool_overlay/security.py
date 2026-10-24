import secrets
import time

from fastapi import Request


class LocalSecurity:
    cookie_name = "valtool_editor"

    def __init__(self, port: int, dev_ui: bool = False):
        self.port, self.dev_ui = port, dev_ui
        self.base_url = f"http://127.0.0.1:{port}"
        self._session = secrets.token_hex(32)
        self._bootstrap: dict[str, float] = {}

    def new_editor_url(self) -> str:
        self._bootstrap = {k: v for k, v in self._bootstrap.items() if v > time.monotonic()}
        token = secrets.token_hex(24)
        self._bootstrap[token] = time.monotonic() + 300
        base = "http://127.0.0.1:5173" if self.dev_ui else self.base_url
        return f"{base}/settings#bootstrap={token}"

    def bootstrap(self, authorization: str) -> bool:
        if not authorization.startswith("Bearer "):
            return False
        return self._bootstrap.pop(authorization[7:], 0) > time.monotonic()

    def is_editor(self, request: Request) -> bool:
        return secrets.compare_digest(request.cookies.get(self.cookie_name, "").encode(), self._session.encode())

    def valid_request(self, request: Request) -> bool:
        if request.headers.get("host") != f"127.0.0.1:{self.port}":
            return False
        origin = request.headers.get("origin")
        if origin is None:
            return request.method in {"GET", "HEAD"}
        return origin == self.base_url or self.dev_ui and origin == "http://127.0.0.1:5173"
