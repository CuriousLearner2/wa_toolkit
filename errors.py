class WAToolkitError(Exception):
    """Base class for all wa_toolkit exceptions."""
    pass

class AIExtractionError(WAToolkitError):
    """Failed after all retries and fallbacks."""
    pass

class SessionError(WAToolkitError):
    """Database connection or schema mismatch issues."""
    pass

class StateNotFoundError(WAToolkitError):
    """Raised by StateMachine if it attempts to dispatch to a state with no registered handler."""
    pass

class InvalidHandlerOutput(WAToolkitError):
    """Raised if a handler returns an invalid tuple format."""
    pass
