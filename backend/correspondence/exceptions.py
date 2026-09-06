"""Correspondence engine exceptions (Phase OF-5).

Each exception maps to an HTTP status at the API layer:
- ``InvalidTransition`` -> 409
- ``NotActorError``    -> 403
- ``CommentRequired``  -> 400
- ``SubmissionBlocked``-> 422 (DQ gate)
"""


class CorrespondenceError(Exception):
    """Base for engine errors."""


class InvalidTransition(CorrespondenceError):
    """Illegal state move (maps to 409)."""


class NotActorError(CorrespondenceError):
    """User is not the current approver (maps to 403)."""


class CommentRequired(CorrespondenceError):
    """reject/send_back requires a comment (maps to 400)."""


class SubmissionBlocked(CorrespondenceError):
    def __init__(self, failures):
        self.failures = failures
        super().__init__('Submission blocked by DQ gate')
