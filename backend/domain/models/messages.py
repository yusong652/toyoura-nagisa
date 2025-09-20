"""
Message Domain Models

Defines core message entities in the chat application, including user messages, assistant messages and image messages.
These are pure domain objects with no infrastructure or presentation layer dependencies.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime


# =====================
# Base Message Model
# =====================
class BaseMessage(BaseModel):
    """
    Base class for all message types.
    
    This is the core entity in the domain layer, representing the basic message concept in chat.
    """
    content: Union[str, List[dict]]
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary format.

        Returns:
            Dict containing message data with role field
        """
        result = self.model_dump()
        return result


# =====================
# Concrete Message Types
# =====================
class UserMessage(BaseMessage):
    """
    User's regular text message.
    
    Represents input messages from the user, one side of the chat conversation.
    """
    role: Literal["user"] = "user"


class AssistantMessage(BaseMessage):
    """
    Assistant's regular text message.
    
    Represents reply messages from the AI assistant, the other side of the chat conversation.
    """
    role: Literal["assistant"] = "assistant"


class ImageMessage(BaseMessage):
    """
    Generated image message.
    
    Represents system-generated or processed image content, containing image path information.
    """
    image_path: str
    role: Literal["image"] = "image"


class VideoMessage(BaseMessage):
    """
    Generated video message.
    
    Represents system-generated or processed video content, containing video path information.
    """
    video_path: str
    role: Literal["video"] = "video"


# =====================
# Type Definitions
# =====================
MessageType = Union[UserMessage, AssistantMessage, ImageMessage, VideoMessage]
Message = MessageType  # Compatible with existing type hints