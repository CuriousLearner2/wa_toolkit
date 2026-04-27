import sys
from typing import Any, Callable
from .logger import logger

def run(
    handle_fn: Callable[[str, Any], str],
    phone: str = "+1234567890",
    welcome_text: str = "--- WhatsApp Simulator (Type 'EXIT' or 'QUIT' to stop) ---"
) -> None:
    """
    A REPL-based interface for rapid local testing of a bot.
    
    Args:
        handle_fn: A function with signature (phone, message) -> reply_text.
                  Typically StateMachine.handle.
        phone: The mock phone number to use for the session.
        welcome_text: Text displayed when starting the simulator.
    """
    print(welcome_text)
    
    try:
        while True:
            try:
                # Read user input
                message = input(f"[{phone}] > ").strip()
                
                # Check for exit commands
                if not message or message.upper() in ("EXIT", "QUIT"):
                    print("Simulator terminated.")
                    break
                
                # Dispatch to handler
                # Note: We use print here as this IS the UI for the simulator.
                # The toolkit itself still uses logger.
                reply = handle_fn(phone, message)
                
                print(f"  [Bot] > {reply}")
                
            except EOFError:
                print("\nSimulator terminated.")
                break
            except KeyboardInterrupt:
                print("\nSimulator terminated.")
                break
            except Exception as e:
                logger.exception(f"Simulator encountered an error: {str(e)}")
                print(f"  [Error] > {str(e)}")
                
    except Exception as e:
        logger.critical(f"Simulator crashed: {str(e)}")
        print(f"CRITICAL ERROR: {str(e)}")
