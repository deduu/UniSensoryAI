class ServiceException(Exception):
    """Base exception for service layer"""
    pass

class NotFoundException(ServiceException):
    def __init__(self, resource: str, identifier: str | int):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} with ID {identifier} not found")

class ValidationException(ServiceException):
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)

class IntegrityException(ServiceException):
    """Database integrity constraint violated"""
    pass
