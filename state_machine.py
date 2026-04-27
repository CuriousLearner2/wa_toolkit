from typing import Any, Callable, Dict, Optional, Tuple
from .session import SessionManager
from .errors import StateNotFoundError, InvalidHandlerOutput
from .logger import logger

# Type alias for handler functions
# handler(phone, message, data) -> (reply_text, next_state, updated_data)
HandlerFn = Callable[[str, Any, Dict[str, Any]], Tuple[str, str, Dict[str, Any]]]

class StateMachine:
    """
    Orchestrates message routing, command interception, and session persistence.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        initial_state: str,
        welcome_message: str = "Welcome! How can I help you today?",
        error_message: str = "I'm sorry, I encountered a technical error. Please try again later."
    ):
        self.session_manager = session_manager
        self.initial_state = initial_state
        self.welcome_message = welcome_message
        self.error_message = error_message
        self.handlers: Dict[str, HandlerFn] = {}

    def register(self, state: str, handler: HandlerFn) -> None:
        """
        Registers a handler function for a specific state.
        """
        self.handlers[state] = handler

    def _intercept_commands(self, phone: str, message: Any) -> Optional[str]:
        """
        Intercepts system commands (RESET, STOP, NEW).
        Returns a reply string if a command was intercepted, otherwise None.
        """
        if not isinstance(message, str):
            return None

        cmd = message.strip().upper()
        if cmd in ("RESET", "NEW", "START"):
            logger.info(f"System command {cmd} received for {phone}. Resetting session.")
            self.session_manager.delete(phone)
            self.session_manager.create(phone, self.initial_state)
            return self.welcome_message
        
        if cmd in ("STOP", "CANCEL"):
            logger.info(f"System command {cmd} received for {phone}. Deleting session.")
            self.session_manager.delete(phone)
            return "Session ended. Send any message to start again."
        
        return None

    def handle(self, phone: str, message: Any) -> str:
        """
        Main entry point for processing an incoming message.
        """
        try:
            # 1. Command Interception
            intercept_reply = self._intercept_commands(phone, message)
            if intercept_reply:
                return intercept_reply

            # 2. Session Retrieval
            session = self.session_manager.get(phone)
            if not session:
                logger.info(f"No session found for {phone}. Creating new session.")
                self.session_manager.create(phone, self.initial_state)
                return self.welcome_message
            
            current_state = session["state"]
            temp_data = session.get("temp_data", {})

            # 3. Dispatch to Handler
            if current_state not in self.handlers:
                logger.error(f"StateNotFoundError: No handler registered for state '{current_state}'")
                raise StateNotFoundError(f"No handler for state: {current_state}")

            handler = self.handlers[current_state]
            
            # Execute handler with try/except for robustness
            try:
                result = handler(phone, message, temp_data)
                
                if not isinstance(result, tuple) or len(result) != 3:
                    raise InvalidHandlerOutput(
                        f"Handler for state '{current_state}' returned {type(result)} instead of tuple(str, str, dict)"
                    )
                
                reply_text, next_state, updated_data = result
            except Exception as e:
                logger.exception(f"Error in handler for state '{current_state}': {str(e)}")
                return self.error_message

            # 4. No-Op Write Optimization
            state_changed = next_state != current_state
            data_changed = updated_data != temp_data

            if state_changed or data_changed:
                logger.info(f"Updating session for {phone}: {current_state} -> {next_state}")
                self.session_manager.update(phone, next_state, updated_data)
            else:
                logger.debug(f"No changes for {phone}. Skipping session update (No-Op).")

            return reply_text

        except Exception as e:
            logger.exception(f"Critical error in StateMachine.handle: {str(e)}")
            return self.error_message
