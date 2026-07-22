class ApplicationError(RuntimeError):
    code = "application_error"
    status = 500
    safe_message = "The operation could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.safe_message)
        self.safe_message = message or self.safe_message


class ValidationError(ApplicationError):
    code = "validation_error"
    status = 422
    safe_message = "Submitted data is invalid."


class NotFoundError(ApplicationError):
    code = "not_found"
    status = 404
    safe_message = "Requested item was not found."


class ConflictError(ApplicationError):
    code = "conflict"
    status = 409
    safe_message = "The operation conflicts with current state."


class PayloadTooLargeError(ApplicationError):
    code = "payload_too_large"
    status = 413
    safe_message = "Submitted data is too large."


class UnsupportedMediaError(ApplicationError):
    code = "unsupported_media"
    status = 415
    safe_message = "Submitted media format is not supported."


class StorageUnavailableError(ApplicationError):
    code = "storage_unavailable"
    status = 503
    safe_message = "Storage is temporarily unavailable."


class ExternalOperationError(ApplicationError):
    code = "external_operation_failed"
    status = 503
    safe_message = "External operation failed."
