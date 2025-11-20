import json
from typing import Any

from werkzeug import Response
from werkzeug.exceptions import HTTPException, BadRequest, NotFound, InternalServerError


class ProblemDetailError(HTTPException):
    """Subclass of the Werkzeug `HTTPException` class that adds a `params`
    dictionary that `as_problem_detail()` uses to format the response details."""

    name: str
    """Used as the problem detail `title`."""
    description: str
    """Used as the problem detail `details`. The value is treated as a format
    string, and is filled in using the `params` dictionary."""

    def __init__(self, description=None, response=None, **params):
        super().__init__(description, response)
        self.params = params

    def as_problem_detail(self) -> dict[str, Any]:
        """Format the exception information as a dictionary with keys as
        specified in the [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
        JSON Problem Details format.

        | RFC 9457 Key | Attribute |
        |--------------|-----------|
        | `"status"`   | `code`    |
        | `"title"`    | `name`    |
        | `"details"`  | `description`, formatted using the `params` dictionary |

        """
        return {
            'status': self.code,
            'title': self.name,
            'details': self.description.format(**self.params),
        }


def problem_detail_response(e: ProblemDetailError) -> Response:
    """Return a JSON Problem Detail ([RFC 9457](https://www.rfc-editor.org/rfc/rfc9457))
    for HTTP errors.

    This function is mainly intended to be registered as an error handler
    with a Flask app:

    ```python
    from flask import Flask
    from solrizer import problem_detail_response

    app = Flask(__name__)

    ...

    app.register_error_handler(ProblemDetailError, problem_detail_response)
    ```
    """
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps(e.as_problem_detail())
    response.content_type = 'application/problem+json'
    return response


class IdentifierProblem(ProblemDetailError, BadRequest):
    name = 'Invalid identifier'
    description = 'The identifier {iiif_id} is not recognized as a valid IIIF identifier'


class ManifestNotFound(ProblemDetailError, NotFound):
    name = 'Manifest not found'
    description = 'Manifest with identifier "{id}" not found'


class SequenceNotFound(ProblemDetailError, NotFound):
    name = 'Sequence not found'
    description = 'Sequence with name "{sequence_name}" not found in manifest "{manifest_id}"'


class CanvasNotFound(ProblemDetailError, NotFound):
    name = 'Canvas not found'
    description = 'Canvas with name "{canvas_name}" not found in manifest "{manifest_id}"'


class AnnotationNotFound(ProblemDetailError, NotFound):
    name = 'Annotation not found'
    description = 'Annotation with name "{annotation_name}" not found in manifest "{manifest_id}"'


class ServiceProblem(ProblemDetailError, InternalServerError):
    """There is a problem with a backend service (e.g., the IIIF image
    server or the Fedora repository).

    The HTTP status is `500 Internal Server Error`."""
    name = 'Backend service error'
    description = 'Backend service error'


class ConfigurationProblem(ProblemDetailError, InternalServerError):
    """The server is incorrectly configured.

    The HTTP status is `500 Internal Server Error`."""
    name = 'Configuration error'
    description = 'The server is incorrectly configured.'
