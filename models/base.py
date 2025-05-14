"""
Pydantic models for the Aula MCP integration
"""
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from pydantic import BaseModel, RootModel, Field, field_validator

class AulaConfig(BaseModel):
    """Configuration model for Aula MCP"""
    username: str
    password: str
    schoolschedule: bool = True
    ugeplan: bool = True
    mu_opgaver: bool = True

class AulaChild(BaseModel):
    """Model representing a child in Aula"""
    id: str
    name: str
    user_id: str = Field(alias="userId", default="")
    institution_name: Optional[str] = None
    institution_code: Optional[str] = None
    institution_profile: Optional[Dict[str, Any]] = None
    
    @field_validator("id", mode="before")
    def ensure_string_id(cls, v):
        """Ensure ID is always a string"""
        return str(v) if v is not None else v

class AulaProfile(BaseModel):
    """Model representing a profile in Aula"""
    children: List[AulaChild] = []
    institution_profiles: List[Dict[str, Any]] = Field(alias="institutionProfiles", default=[])
    
    @classmethod
    def model_validate(cls, obj: Any) -> "AulaProfile":
        """Validate a model from an object
        
        Args:
            obj: Object to validate
            
        Returns:
            AulaProfile: Validated model
        """
        if isinstance(obj, dict):
            # Handle children data
            if "children" in obj and isinstance(obj["children"], list):
                for child in obj["children"]:
                    if isinstance(child, dict) and "id" in child:
                        # Ensure child ID is a string
                        child["id"] = str(child["id"])
                
                obj["children"] = [
                    AulaChild.model_validate(child) if isinstance(child, dict) else child
                    for child in obj["children"]
                ]
                
        return super().model_validate(obj)

class AulaToken(BaseModel):
    """Model representing an Aula API token"""
    token: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @field_validator("timestamp", mode="before")
    def set_timestamp_now(cls, v):
        """Set timestamp to current time if not provided"""
        if not v:
            return datetime.now()
        return v
        
    @classmethod
    def model_validate(cls, obj: Any) -> "AulaToken":
        """Validate a model from an object
        
        Args:
            obj: Object to validate
            
        Returns:
            AulaToken: Validated model
        """
        # Handle string timestamps
        if isinstance(obj, dict) and "timestamp" in obj and isinstance(obj["timestamp"], str):
            try:
                obj["timestamp"] = datetime.fromisoformat(obj["timestamp"])
            except ValueError:
                obj["timestamp"] = datetime.now()
                
        return super().model_validate(obj)

class AulaSession(BaseModel):
    """Model representing an active Aula session"""
    api_url: str
    profiles: List[AulaProfile] = []
    tokens: Dict[str, AulaToken] = {}
    csrf_token: Optional[str] = None
    
    @classmethod
    def model_validate(cls, obj: Any) -> "AulaSession":
        """Validate a model from a dictionary
        
        Args:
            obj: Dictionary to validate
            
        Returns:
            AulaSession: Validated session
        """
        if isinstance(obj, dict):
            # Handle token serialization
            if "tokens" in obj and isinstance(obj["tokens"], dict):
                tokens = {}
                for widget_id, token_data in obj["tokens"].items():
                    if isinstance(token_data, dict):
                        tokens[widget_id] = AulaToken.model_validate(token_data)
                    else:
                        tokens[widget_id] = token_data
                obj["tokens"] = tokens
                
            # Handle profiles
            if "profiles" in obj and isinstance(obj["profiles"], list):
                obj["profiles"] = [
                    AulaProfile.model_validate(profile) if isinstance(profile, dict) else profile
                    for profile in obj["profiles"]
                ]
                
        return super().model_validate(obj)

class AulaProfilePicture(BaseModel):
    """Model representing a profile picture in Aula"""
    url: str = ""

class AulaMessageSender(BaseModel):
    """Model representing a message sender in Aula"""
    short_name: str = Field(alias="shortName")
    profile_picture: Optional[AulaProfilePicture] = Field(alias="profilePicture", default=None)
    institution_code: Optional[str] = Field(alias="institutionCode", default=None)
    full_name: str = Field(alias="fullName")
    metadata: Optional[str] = None
    answer_directly_name: Optional[str] = Field(alias="answerDirectlyName", default=None)
    mail_box_owner: Optional[Dict[str, Any]] = Field(alias="mailBoxOwner", default=None)


class AulaMessageText(BaseModel):
    """Model representing message text content in Aula"""
    html: str = ""


class AulaMessage(BaseModel):
    """Model representing a message in Aula"""
    id: str
    send_date_time: datetime = Field(alias="sendDateTime")
    deleted_at: Optional[datetime] = Field(alias="deletedAt", default=None)
    text: Union[AulaMessageText, str, Dict[str, str]]
    has_attachments: bool = Field(alias="hasAttachments", default=False)
    pending_media: bool = Field(alias="pendingMedia", default=False)
    message_type: str = Field(alias="messageType")
    leaver_names: Optional[List[str]] = Field(alias="leaverNames", default=None)
    inviter_name: Optional[str] = Field(alias="inviterName", default=None)
    sender: AulaMessageSender
    new_recipients: Optional[List[Any]] = Field(alias="newRecipients", default=None)
    original_recipients: Optional[List[Any]] = Field(alias="originalRecipients", default=None)
    attachments: Optional[List[Any]] = Field(default=None)
    can_reply_to_message: bool = Field(alias="canReplyToMessage", default=True)

    @field_validator("send_date_time", "deleted_at", mode="before")
    def parse_datetime(cls, value):
        """Parse datetime string with timezone information"""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                try:
                    # Try without timezone
                    dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                    import pytz
                    return dt.replace(tzinfo=pytz.UTC)
                except ValueError:
                    # Return None if we can't parse the date
                    return None
        return value

    @field_validator("text", mode="before")
    def validate_text(cls, value):
        """Ensure text is properly formatted"""
        if isinstance(value, str):
            return {"html": value}
        return value

    def get_text_content(self) -> str:
        """Get the text content from the message
        
        Returns:
            str: The message text content
        """
        if isinstance(self.text, dict):
            return self.text.get("html", "")
        elif isinstance(self.text, AulaMessageText):
            return self.text.html
        return str(self.text)

class AulaAlbumPicture(BaseModel):
    """Model representing a picture in an Aula gallery album"""
    id: str = ""
    title: str = ""
    description: str = ""
    url: str = ""
    thumbnailUrl: str = ""
    created: str = ""
    
class AulaAlbum(BaseModel):
    """Model representing an album in Aula gallery"""
    id: str = ""
    title: str = ""
    institutionName: str = ""
    pictures: List[AulaAlbumPicture] = Field(default_factory=list)

AulaGalleryResponse = RootModel[List[AulaAlbum]]

class AulaAlbumResponse(BaseModel):
    """Model representing the gallery.getAlbum API response"""
    pictures: List[AulaAlbumPicture] = Field(default_factory=list)

class GalleryItem(BaseModel):
    """Model representing a gallery item from Aula"""
    id: str = ""
    title: str = ""
    description: str = ""
    url: str = ""
    thumbnailUrl: str = ""
    created: str = "" 