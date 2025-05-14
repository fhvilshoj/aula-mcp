"""
Aula MCP Server - A Model Context Protocol server for Aula integration
"""

import asyncio
import functools
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ClientError

from aula_calendar import AulaCalendar
from client import AulaClient, AuthenticationError
from data_manager import AulaDataManager
from models import AulaConfig

_LOGGER = logging.getLogger(__name__)


# Simple function to ensure authentication before executing a function
async def ensure_authenticated(client) -> bool:
    """Ensure the client is authenticated

    Args:
        client: The Aula client

    Returns:
        bool: True if successfully authenticated

    Raises:
        AuthenticationError: If authentication fails
    """
    if not client.is_logged_in():
        _LOGGER.info("Not logged in, attempting automatic login")
        success = client.login()
        if not success:
            raise AuthenticationError("Failed to log in automatically")
    return True


class AulaMCPServer:
    """MCP Server for Aula integration"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the MCP Server

        Args:
            config: Configuration dictionary
        """
        self.config = AulaConfig(**config)
        self.server = FastMCP(name="AulaMCP")
        self.client = AulaClient(self.config)
        self.calendar = AulaCalendar(self.client)
        self.data_manager = AulaDataManager(self.client, self.calendar)

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register all tools with the MCP server"""

        # Authentication
        @self.server.tool()
        async def login() -> Dict[str, Any]:
            """Force a new login to Aula (usually not needed as login happens automatically)

            Returns:
                Dict[str, Any]: Login result
            """
            try:
                # Force a fresh login by clearing the session first
                self.client.session_cache.clear_cache()
                self.client._session = None

                # Directly call login without going through api_call to avoid recursion
                success = self.client._direct_login()
                return {"success": success, "forced": True}
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to login: {e}")
                import traceback

                traceback.print_exc()
                raise ClientError(f"Failed to login: {e}")

        @self.server.tool()
        async def clear_session_cache() -> Dict[str, bool]:
            """Clear the session cache and force a new login

            Returns:
                Dict[str, bool]: Clear result
            """
            try:
                success = self.client.session_cache.clear_cache()
                # Reset the client session
                self.client._session = None
                return {"success": success}
            except Exception as e:
                _LOGGER.error(f"Failed to clear session cache: {e}")
                raise ClientError(f"Failed to clear session cache: {e}")

        # Child data
        @self.server.tool()
        async def get_children() -> List[Dict[str, Any]]:
            """Get list of children from Aula

            Returns:
                List[Dict[str, Any]]: List of child data
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                return self.data_manager.get_children()
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get children: {e}")
                raise ClientError(f"Failed to get children: {e}")

        @self.server.tool()
        async def get_child_by_id(child_id: str) -> Dict[str, Any]:
            """Get child data by ID

            Args:
                child_id: ID of the child

            Returns:
                Dict[str, Any]: Child data
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                child = self.data_manager.get_child_by_id(child_id)
                if not child:
                    raise ClientError(f"Child with ID {child_id} not found")
                return child
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except ClientError:
                raise
            except Exception as e:
                _LOGGER.error(f"Failed to get child {child_id}: {e}")
                raise ClientError(f"Failed to get child {child_id}: {e}")

        # Calendar
        @self.server.tool()
        async def get_calendar_events(
            child_id: str, days: int = 14
        ) -> List[Dict[str, Any]]:
            """Get calendar events for a child

            Args:
                child_id: ID of the child
                days: Number of days to fetch

            Returns:
                List[Dict[str, Any]]: List of calendar events
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                return self.calendar.get_events_for_child(child_id, days=days)
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get calendar events: {e}")
                raise ClientError(f"Failed to get calendar events: {e}")

        @self.server.tool()
        async def get_events_for_date_range(
            child_id: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            days: int = 14,
        ) -> List[Dict[str, Any]]:
            """Get events for a specific date range

            Args:
                child_id: ID of the child
                start_date: Start date in ISO format
                end_date: End date in ISO format
                days: Number of days if no date range provided

            Returns:
                List[Dict[str, Any]]: List of calendar events
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Convert dates if provided
                start = datetime.fromisoformat(start_date) if start_date else None
                end = datetime.fromisoformat(end_date) if end_date else None

                # Now get the data
                return self.calendar.get_events_for_child(child_id, start, end, days)
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get calendar events: {e}")
                raise ClientError(f"Failed to get calendar events: {e}")

        # Messages
        @self.server.tool()
        async def get_unread_messages() -> Dict[str, Any]:
            """Get messages from Aula (including unread)

            Returns:
                Dict[str, Any]: Dictionary containing:
                - count: Number of unread messages
                - messages: List of message objects containing:
                  - text: Message text content (HTML)
                  - sender: Sender's full name
                  - subject: Message thread subject
                  - thread_id: ID of the message thread
                  - is_unread: Whether the message is unread
                  - requires_mitid: Whether the message requires MitID authentication
                  - message: Complete message details if available (Pydantic model)
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                return self.data_manager.get_unread_messages()
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get messages: {e}")
                raise ClientError(f"Failed to get messages: {e}")

        # Presence
        @self.server.tool()
        async def get_presence_data(child_id: str) -> Dict[str, Any]:
            """Get presence data for a child

            Args:
                child_id: ID of the child

            Returns:
                Dict[str, Any]: Dictionary containing presence information
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                return self.data_manager.get_presence_data(child_id)
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get presence data: {e}")
                raise ClientError(f"Failed to get presence data: {e}")

        # Gallery
        @self.server.tool()
        async def get_gallery_items(limit: int = 3) -> List[Dict[str, Any]]:
            """Get gallery items

            Args:
                limit: Maximum number of items to return

            Returns:
                List[Dict[str, Any]]: List of gallery items
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now get the data
                return self.data_manager.get_gallery_items(limit=limit)
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get gallery items: {e}")
                raise ClientError(f"Failed to get gallery items: {e}")

        @self.server.tool()
        async def get_summary(force_update: bool = False) -> Dict[str, Any]:
            """Get a comprehensive summary of all Aula data in one call

            This method returns cached data by default if recently updated (within 15 minutes).
            Use force_update=True to explicitly refresh all data.

            Args:
                force_update: Whether to force a fresh data update regardless of cache age

            Returns:
                Dict[str, Any]: Dictionary containing summary of children, messages, presence, and gallery data
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Get the comprehensive summary with the force_update flag
                return self.data_manager.get_summary(force_update=force_update)
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to get summary data: {e}")
                raise ClientError(f"Failed to get summary data: {e}")

        # Refresh data
        @self.server.tool()
        async def refresh_data() -> Dict[str, bool]:
            """Refresh all data from Aula

            Returns:
                Dict[str, bool]: Refresh result
            """
            try:
                # First ensure we're authenticated
                await ensure_authenticated(self.client)

                # Now update the data
                self.data_manager.update_data()
                return {"success": True}
            except AuthenticationError as e:
                _LOGGER.error(f"Authentication error: {e}")
                raise ClientError(f"Authentication error: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to refresh data: {e}")
                raise ClientError(f"Failed to refresh data: {e}")

    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the MCP server

        Args:
            host: Host to listen on
            port: Port to listen on
        """
        await self.server.run(host=host, port=port, transport="sse")

    async def stop(self):
        """Stop the MCP server"""
        await self.server.stop()


def create_server(config_path: str) -> AulaMCPServer:
    """Create an MCP server from a config file

    Args:
        config_path: Path to config file

    Returns:
        AulaMCPServer: MCP server instance
    """
    with open(config_path, "r") as f:
        config = json.load(f)

    return AulaMCPServer(config)


if __name__ == "__main__":
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "./examples/config.json"
    server = create_server(config_path)
    server.server.run(transport="stdio")
