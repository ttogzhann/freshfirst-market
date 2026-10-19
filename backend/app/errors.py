class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def invalid(message: str):
    return ServiceError(422, "VALIDATION_ERROR", message)


def missing(what: str):
    return ServiceError(404, "NOT_FOUND", f"{what} not found")
