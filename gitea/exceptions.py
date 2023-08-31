from requests import Response


class GiteaException(Exception):
    pass


class NotFoundException(GiteaException):
    pass


class RequestException(GiteaException):
    def __init__(self, response: Response, message: str = None):
        self.response = response
        super().__init__(
            message or f"Received status code: {response.status_code} ({response.url})"
        )


class AlreadyExistsRequestException(RequestException):
    pass


class UnauthorizedRequestException(RequestException):
    def __init__(self, response: Response):
        super().__init__(
            response,
            f"Unauthorized: {response.url} - Check your permissions and try again!",
        )


class NotFoundRequestException(RequestException, NotFoundException):
    pass


class ObjectIsInvalid(Exception):
    pass


class ConflictRequestException(RequestException):
    pass


class ApiValidationRequestException(RequestException):
    pass


class RawRequestEndpointMissing(Exception):
    """This ApiObject can only be obtained through other api objects and does not have
    direct .request method."""

    pass


class MissingEquallyImplementation(Exception):
    """
    Each Object obtained from the gitea api must be able to check itself for equality in
    relation to its fields obtained from gitea.
    Risen if an api object is lacking the proper implementation.
    """

    pass


class UncaughtException(RequestException):
    pass
