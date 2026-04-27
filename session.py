from typing import Any, Dict, Optional
from supabase import Client
from postgrest import APIResponse
from .errors import SessionError
from .logger import logger

class SessionManager:
    """
    Manages session persistence using Supabase.
    Ensures atomic single-write updates for both state and temp_data.
    """

    def __init__(self, client: Client, table_name: str = "whatsapp_sessions", phone_column: str = "phone"):
        self.client = client
        self.table_name = table_name
        self.phone_column = phone_column

    def get(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the session for a given phone number.
        Returns a dictionary or None if not found.
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .eq(self.phone_column, phone)
                .maybe_single()
                .execute()
            )
            return response.data if response else None
        except Exception as e:
            logger.error(f"Failed to get session for {phone}: {str(e)}")
            raise SessionError(f"Database error during get: {str(e)}") from e

    def create(self, phone: str, state: str) -> Dict[str, Any]:
        """
        Initializes a session using upsert.
        """
        try:
            payload = {
                self.phone_column: phone,
                "state": state,
                "temp_data": {}
            }
            response = (
                self.client.table(self.table_name)
                .upsert(payload)
                .execute()
            )
            if not response or not response.data:
                raise SessionError("No data returned from create (upsert)")
            
            return response.data[0]
        except Exception as e:
            logger.error(f"Failed to create session for {phone}: {str(e)}")
            raise SessionError(f"Database error during create: {str(e)}") from e

    def update(self, phone: str, state: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persists both state and temp_data in a single update call for consistency.
        """
        try:
            payload = {
                "state": state,
                "temp_data": data
            }
            response = (
                self.client.table(self.table_name)
                .update(payload)
                .eq(self.phone_column, phone)
                .execute()
            )
            if not response or not response.data:
                raise SessionError(f"No session found to update for phone: {phone}")
            
            return response.data[0]
        except Exception as e:
            logger.error(f"Failed to update session for {phone}: {str(e)}")
            raise SessionError(f"Database error during update: {str(e)}") from e

    def delete(self, phone: str) -> None:
        """
        Removes the session from the database.
        """
        try:
            self.client.table(self.table_name).delete().eq(self.phone_column, phone).execute()
        except Exception as e:
            logger.error(f"Failed to delete session for {phone}: {str(e)}")
            raise SessionError(f"Database error during delete: {str(e)}") from e
