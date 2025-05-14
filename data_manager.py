"""
Data manager for the Aula MCP integration
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from client import AulaClient
from models.base import (
    AulaChild, 
    AulaMessage, 
    AulaGalleryResponse, 
    AulaAlbumResponse, 
)
from aula_calendar import AulaCalendar

_LOGGER = logging.getLogger(__name__)

class AulaDataManager:
    """Class for managing data from Aula"""
    
    def __init__(self, client: AulaClient, calendar: Optional[AulaCalendar] = None):
        """Initialize the data manager
        
        Args:
            client: Authenticated Aula client
            calendar: AulaCalendar instance (optional, will be created if not provided)
        """
        self.client = client
        self.calendar = calendar or AulaCalendar(client)
        self._children = []
        self._child_data = {}
        self._unread_messages = 0
        self._gallery_items = []
        self._calendar_events = {}
        self._last_update = datetime.min

    def update_data(self) -> None:
        """Update all data from Aula"""
        self._last_update = datetime.now()
        self._update_children()
        self._update_messages()
        self._update_gallery()
        
    def _update_children(self) -> None:
        """Update child data"""
        # Reset child data
        self._children = []
        self._child_data = {
            "names": {},
            "institutions": {},
            "user_ids": [],
            "ids": [],
            "child_objects": []
        }
        
        # Check if we have profiles
        if not self.client.session_data.profiles:
            _LOGGER.error("No profiles found in session data")
            return
            
        # Process each profile to extract child information
        for profile in self.client.session_data.profiles:
            for child in profile.children:
                # Create a child object with ID as string
                child_obj = AulaChild(
                    id=str(child.id),
                    name=child.name,
                    userId=child.user_id,
                    institution_name=child.institution_profile.get("institutionName") if child.institution_profile else None
                )
                
                # Add to collections with ID as string
                self._children.append(child_obj)
                self._child_data["names"][str(child.id)] = child.name
                self._child_data["institutions"][str(child.id)] = child_obj.institution_name
                self._child_data["ids"].append(str(child.id))
                self._child_data["user_ids"].append(child.user_id)
                self._child_data["child_objects"].append(child_obj.model_dump())
                
        _LOGGER.debug(f"Found {len(self._children)} children")
        
        # Get daily overview (presence data)
        self._update_presence_data()
        
    def _update_presence_data(self) -> None:
        """Update presence data for all children"""
        presence_data = {}
        daily_overview = {}
        
        for child in self._children:
            try:
                response = self.client.api_call(
                    method="presence.getDailyOverview",
                    params={"childIds[]": child.id}
                )
                
                if response.get("status", {}).get("message") == "OK" and len(response.get("data", [])) > 0:
                    presence_data[child.id] = 1
                    daily_overview[child.id] = response["data"][0]
                else:
                    _LOGGER.debug(f"Unable to retrieve presence data for child {child.id}")
                    presence_data[child.id] = 0
            except Exception as e:
                _LOGGER.error(f"Error fetching presence data for child {child.id}: {e}")
                presence_data[child.id] = 0
                
        # Update child data with presence information
        self._child_data["presence"] = presence_data
        self._child_data["daily_overview"] = daily_overview
        
    def _update_messages(self) -> None:
        """Update message information"""
        try:
            # Get message threads
            messages_response = self.client.api_call(
                method="messaging.getThreads",
                params={
                    "sortOn": "date",
                    "orderDirection": "desc",
                    "page": "0"
                }
            )
            
            self._unread_messages = 0
            # Store messages in a list instead of a single object
            self._messages = []
            
            # Process threads to find messages (up to 5 most recent)
            max_messages = 5
            message_count = 0
            
            for message_thread in messages_response.get("data", {}).get("threads", []):
                # Check if we've reached the limit
                if message_count >= max_messages:
                    break
                    
                thread_id = message_thread.get("id")
                thread_is_unread = not message_thread.get("read", True)
                
                # Get message details
                thread_response = self.client.api_call(
                    method="messaging.getMessagesForThread",
                    params={
                        "threadId": thread_id,
                        "page": "0"
                    }
                )
                
                # Handle response
                if thread_response.get("status", {}).get("code") == 403:
                    # Sensitive message requiring MitID
                    if thread_is_unread:
                        self._unread_messages += 1
                    
                    self._messages.append({
                        "message": None,
                        "thread_id": thread_id,
                        "thread_subject": "Følsom besked",
                        "requires_mitid": True,
                        "text": "Log ind på Aula med MitID for at læse denne besked.",
                        "sender": "Ukendt afsender",
                        "is_unread": thread_is_unread
                    })
                    message_count += 1
                else:
                    # Process normal message thread
                    thread_subject = thread_response.get("data", {}).get("subject", "")
                    
                    # Get the first message in the thread (most recent first)
                    if thread_response.get("data", {}).get("messages"):
                        for message in thread_response.get("data", {}).get("messages", []):
                            if message.get("messageType") == "Message":
                                try:
                                    # Validate message with pydantic model
                                    aula_message = AulaMessage.model_validate(message)
                                    
                                    # Add to our messages list
                                    self._messages.append({
                                        "message": aula_message,
                                        "thread_id": thread_id,
                                        "thread_subject": thread_subject,
                                        "text": aula_message.get_text_content(),
                                        "sender": aula_message.sender.full_name,
                                        "is_unread": thread_is_unread
                                    })
                                    
                                    if thread_is_unread:
                                        self._unread_messages += 1
                                    
                                    message_count += 1
                                    break
                                except Exception as e:
                                    _LOGGER.error(f"Error validating message: {e}")
                                    # Fallback to basic info
                                    try:
                                        message_text = message.get("text", {}).get("html", "")
                                    except AttributeError:
                                        message_text = message.get("text", "intet indhold...")
                                    
                                    self._messages.append({
                                        "message": None,
                                        "thread_id": thread_id,
                                        "thread_subject": thread_subject,
                                        "text": message_text,
                                        "sender": message.get("sender", {}).get("fullName", "Ukendt afsender"),
                                        "is_unread": thread_is_unread
                                    })
                                    
                                    if thread_is_unread:
                                        self._unread_messages += 1
                                        
                                    message_count += 1
                                    break
            
            # For backward compatibility - use the first unread message for the child data
            self._child_data["messages"] = {}
            
            for message_data in self._messages:
                if message_data.get("is_unread", False):
                    self._child_data["messages"] = {
                        "text": message_data.get("text", ""),
                        "sender": message_data.get("sender", ""),
                        "subject": message_data.get("thread_subject", "")
                    }
                    break
                
        except Exception as e:
            _LOGGER.error(f"Error fetching messages: {e}")
            
    def _update_gallery(self) -> None:
        """Update gallery items from Aula"""
        try:
            # Get all institution profile IDs
            inst_profile_ids = []
            for child in self._children:
                inst_profile_ids.append(child.id)
            
            # Join the IDs for the API call
            profile_ids = ",".join(inst_profile_ids)
            
            # Get all albums
            albums_response = self.client.api_call(
                method="gallery.getAlbums",
                params={"institutionProfileIds": profile_ids, "page": "0"}
            )
            
            # Reset gallery items
            self._gallery_items = []
            
            # Handle response
            if albums_response.get("status", {}).get("message") == "OK":
                try:
                    # Validate album data with Pydantic
                    gallery_data = AulaGalleryResponse.model_validate(albums_response.get("data", {}))
                    
                    # Process each album
                    for album in gallery_data.root:
                        # Get album details with pictures
                        album_response = self.client.api_call(
                            method="gallery.getAlbum",
                            params={"id": album.id}
                        )
                        
                        if album_response.get("status", {}).get("message") == "OK":
                            try:
                                # Validate album response with Pydantic
                                __import__("ipdb").set_trace()
                                album_data = AulaAlbumResponse.model_validate(album_response.get("data", {}))
                                
                                # Add pictures directly to gallery items
                                self._gallery_items.extend(album_data.pictures)
                            except Exception as e:
                                _LOGGER.error(f"Error processing album {album.id}: {e}")
                    
                    # Sort by created date (newest first)
                    self._gallery_items.sort(key=lambda x: x.created, reverse=True)
                    _LOGGER.debug(f"Found {len(self._gallery_items)} gallery items")
                except Exception as e:
                    _LOGGER.error(f"Error validating gallery data: {e}")
            else:
                _LOGGER.warning(f"Failed to get gallery albums: {albums_response}")
                
        except Exception as e:
            _LOGGER.error(f"Error fetching gallery items: {e}")
        
    def get_children(self) -> List[Dict[str, Any]]:
        """Get list of children
        
        Returns:
            List[Dict[str, Any]]: List of child data dictionaries
        """
        if not self._children:
            self.update_data()
        return self._child_data["child_objects"]
        
    def get_child_by_id(self, child_id: str) -> Optional[Dict[str, Any]]:
        """Get child data by ID
        
        Args:
            child_id: ID of the child
            
        Returns:
            Optional[Dict[str, Any]]: Child data or None if not found
        """
        if not self._children:
            self.update_data()
            
        for child in self._child_data["child_objects"]:
            if str(child.get("id")) == child_id:
                return child
                
        return None
        
    def get_unread_messages(self) -> Dict[str, Any]:
        """Get unread messages data
        
        Returns:
            Dict[str, Any]: Dictionary containing unread message information
        """
        result = {
            "count": self._unread_messages,
            "messages": []
        }
        
        # Add all messages if available
        if hasattr(self, "_messages") and self._messages:
            for message_data in self._messages:
                message_entry = {
                    "text": message_data.get("text", ""),
                    "sender": message_data.get("sender", ""),
                    "subject": message_data.get("thread_subject", ""),
                    "thread_id": message_data.get("thread_id", ""),
                    "is_unread": message_data.get("is_unread", False),
                    "requires_mitid": message_data.get("requires_mitid", False)
                }
                
                # Add validated message details if available
                if message_data.get("message"):
                    message_entry["message"] = message_data["message"].model_dump()
                
                result["messages"].append(message_entry)
        # For backward compatibility
        elif hasattr(self, "_message_data") and self._message_data:
            message_entry = {
                "text": self._message_data.get("text", ""),
                "sender": self._message_data.get("sender", ""),
                "subject": self._message_data.get("thread_subject", ""),
                "is_unread": self._unread_messages > 0,
                "requires_mitid": self._message_data.get("requires_mitid", False)
            }
            
            if self._message_data.get("message"):
                message_entry["message"] = self._message_data["message"].model_dump()
                
            result["messages"].append(message_entry)
        
        return result
        
    def get_presence_data(self, child_id: str) -> Dict[str, Any]:
        """Get presence data for a child
        
        Args:
            child_id: ID of the child
            
        Returns:
            Dict[str, Any]: Dictionary containing presence information
        """
        if not self._children:
            self.update_data()
            
        return {
            "has_presence": self._child_data.get("presence", {}).get(child_id, 0) == 1,
            "overview": self._child_data.get("daily_overview", {}).get(child_id, {})
        }
        
    def get_gallery_items(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get gallery items
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            List[Dict[str, Any]]: List of gallery items
        """
        if not self._gallery_items:
            self._update_gallery()
            
        # Return the top N items
        return [item.model_dump() for item in self._gallery_items[:limit]] 
        
    def get_summary(self, force_update: bool = False) -> Dict[str, Any]:
        """Get a comprehensive summary of all Aula data
        
        This method returns the cached data by default to be more efficient.
        Data will only be refreshed if:
        - force_update is True
        - This is the first time requesting data
        - Data is more than 15 minutes old
        
        Args:
            force_update: Whether to force a fresh data update
            
        Returns:
            Dict[str, Any]: Dictionary containing summary of children, messages, presence, and gallery data
        """
        # Check if we need to update data
        current_time = datetime.now()
        time_since_update = current_time - self._last_update
        
        if force_update or not hasattr(self, "_children") or not self._children or time_since_update > timedelta(minutes=15):
            _LOGGER.info(f"Updating data (force={force_update}, time_since_update={time_since_update})")
            self.update_data()
            self._last_update = current_time
        else:
            _LOGGER.debug("Using cached data for summary")
            
        # Get all children
        children = self.get_children()
        
        # Get messages
        message_data = self.get_unread_messages()
        
        # Get presence data for each child
        presence_data = {}
        calendar_events = {}
        for child in children:
            child_id = child.get("id")
            presence_data[child_id] = self.get_presence_data(child_id)
            # Get calendar events for the next 14 days
            calendar_events[child_id] = self.calendar.get_events_for_child(child_id, days=14)
        
        # Get gallery items
        gallery_items = self.get_gallery_items(limit=5)
        
        # Compile the summary
        summary = {
            "children": children,
            "messages": message_data,
            "presence": presence_data,
            "calendar": calendar_events,
            "gallery": gallery_items,
            "last_updated": self._last_update.isoformat()
        }
        
        return summary 