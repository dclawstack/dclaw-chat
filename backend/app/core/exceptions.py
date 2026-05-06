from fastapi import HTTPException, status


class DClawException(HTTPException):
    pass


class NotFoundException(DClawException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(DClawException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(DClawException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestException(DClawException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class LLMException(DClawException):
    def __init__(self, detail: str = "LLM service error"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
