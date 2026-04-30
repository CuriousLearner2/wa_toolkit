import os
import sys
from typing import Any, Tuple
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Ensure we can import wa_toolkit from parent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from wa_toolkit.ai_extractor import AIExtractor

load_dotenv('replate/.env')

# 1. Schema for extraction
class WaitlistIntent(BaseModel):
    wants_waitlist: bool = Field(description="True if the user wants to be added to the waitlist")
    preferred_window: str = Field(description="Optional time window they are willing to wait for", default="")

# 2. Logic for when a table is FULL
def handle_full_house_scenario(phone: str, message: Any, data: dict):
    """
    Simulates the moment the bot realizes a slot is full.
    Instead of saying 'No', it offers the waitlist.
    """
    reply = "I'm sorry, we're fully booked for 7:30 PM. Would you like to join our **Priority Waitlist**? I'll text you immediately if a table opens up."
    return reply, "AWAITING_WAITLIST_CONFIRMATION", data

# 3. Handling the Waitlist Response
def handle_waitlist_response(phone: str, message: Any, data: dict, extractor: AIExtractor) -> Tuple[str, str, dict]:
    prompt = f"The user said: '{message}'. Do they want to join the waitlist?"
    result = extractor.extract(prompt, response_model=WaitlistIntent)
    
    if result['wants_waitlist']:
        # LOGIC: Save this phone number to a 'waitlist' table in Supabase
        return "You're on the list! 📝 I'll notify you the moment a spot opens up.", "WAITLISTED", data
    else:
        return "No problem. Hopefully we can host you another time!", "COMPLETED", data

# 4. PROACTIVE RECOVERY (The 'Cancellation' Loop)
def notify_waitlist_of_opening(phone: str, time_slot: str):
    """
    This function would be triggered by a Supabase Database Webhook 
    whenever a reservation row is deleted/cancelled.
    """
    outbound_message = f"Good news! A table just opened up for {time_slot}. Do you still want it? Reply YES to claim it in the next 5 minutes!"
    # Call WhatsApp API to send outbound message...
    return outbound_message
