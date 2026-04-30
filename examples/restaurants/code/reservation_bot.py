import os
import sys
from typing import Any, Tuple
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Ensure we can import wa_toolkit from parent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from wa_toolkit.ai_extractor import AIExtractor
from wa_toolkit.state_machine import StateMachine
from wa_toolkit.session import SessionManager
from wa_toolkit.simulator import run
from supabase import create_client

load_dotenv('replate/.env')

# --- 1. Define the Data Schema ---
class ReservationDetails(BaseModel):
    date: str = Field(description="The requested date for the reservation")
    time: str = Field(description="The requested time")
    guests: int = Field(description="Number of people in the party", default=0)
    confirmed: bool = Field(description="True if the user explicitly confirmed the details", default=False)

# --- 2. Initialize Toolkit Components ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

extractor = AIExtractor(api_key=GEMINI_KEY)
# Note: For a real run, you'd need the whatsapp_sessions table in Supabase
# sessions = SessionManager(create_client(SUPABASE_URL, SUPABASE_KEY))
# sm = StateMachine(sessions, initial_state="AWAITING_DETAILS", welcome_message="Welcome to Blue Bistro! How can I help you today?")

# --- 3. Define State Handlers ---

def handle_details(phone: str, message: Any, data: dict) -> Tuple[str, str, dict]:
    """Extracts date, time, and guests from natural language."""
    
    prompt = f"""
    The user said: "{message}"
    Current reservation data: {data}
    
    Extract or update the 'date', 'time', and 'guests'. 
    If the user confirms the details shown to them, set 'confirmed' to True.
    """
    
    # Use AI to extract structured data
    result = extractor.extract(prompt, response_model=ReservationDetails)
    data.update(result)
    
    # Check what's missing
    if not data.get('date'):
        return "Sure! What date would you like to visit us?", "AWAITING_DETAILS", data
    if not data.get('time'):
        return f"Got it for {data['date']}. What time works for you?", "AWAITING_DETAILS", data
    if not data.get('guests'):
        return f"And how many people will be in your party?", "AWAITING_DETAILS", data
    
    # If we have everything, ask for confirmation
    summary = f"I have a table for {data['guests']} on {data['date']} at {data['time']}. Does that look correct?"
    return summary, "CONFIRMING", data

def handle_confirmation(phone: str, message: Any, data: dict) -> Tuple[str, str, dict]:
    """Finalizes the booking or goes back to fix details."""
    if "yes" in str(message).lower() or "correct" in str(message).lower():
        # Here is where you would call your real booking API or Save to DB
        return f"Perfect! Your table is booked. We'll see you on {data['date']}! 🎉", "COMPLETED", data
    else:
        return "No problem. What would you like to change? (Date, time, or guests?)", "AWAITING_DETAILS", data

# --- 4. Wire it up (Example structure) ---
# sm.register("AWAITING_DETAILS", handle_details)
# sm.register("CONFIRMING", handle_confirmation)

if __name__ == "__main__":
    print("--- Restaurant Reservation Bot (Logic Blueprint) ---")
    print("This script demonstrates how the Toolkit handlers extract data.")
    # To run this, you would use the simulator.run(sm.handle)
