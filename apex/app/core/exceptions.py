from typing import Any


class APEXError(Exception):
    """Base exception for all APEX application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class AuthError(APEXError):
    status_code = 401
    error_code = "auth_error"


class ForbiddenError(APEXError):
    status_code = 403
    error_code = "forbidden"


class NotFoundError(APEXError):
    status_code = 404
    error_code = "not_found"


class ConflictError(APEXError):
    status_code = 409
    error_code = "conflict"


class ValidationError(APEXError):
    status_code = 422
    error_code = "validation_error"


class RateLimitError(APEXError):
    status_code = 429
    error_code = "rate_limit_exceeded"


class IntegrationError(APEXError):
    status_code = 502
    error_code = "integration_error"


class LLMError(APEXError):
    status_code = 503
    error_code = "llm_error"
