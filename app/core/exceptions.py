from fastapi import HTTPException


class APEXError(HTTPException):
    pass


class AuthError(APEXError):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(status_code=401, detail=detail)


class ForbiddenError(APEXError):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(status_code=403, detail=detail)


class NotFoundError(APEXError):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(status_code=404, detail=f"{resource} not found")


class ConflictError(APEXError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, detail=detail)


class RateLimitError(APEXError):
    def __init__(self) -> None:
        super().__init__(status_code=429, detail="Too many requests. Slow down.")


class IntegrationError(APEXError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=502, detail=detail)


class LLMError(APEXError):
    def __init__(self, detail: str = "AI service temporarily unavailable") -> None:
        super().__init__(status_code=503, detail=detail)
