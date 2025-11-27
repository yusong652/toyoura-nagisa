"""Gmail send email tool.

This module provides the send_email tool for sending emails
using Gmail API with OAuth2 authentication.
"""

import os
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
import base64

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.gmail_service import get_gmail_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.user import get_user_email as get_user_email_util


def register_send_email_tool(mcp: FastMCP):
    """Register the send email tool."""
    
    common_tags = {"email", "gmail", "google", "messaging", "communication"}
    common_annotations = {"category": "email", "tags": ["email", "gmail", "google", "messaging", "communication"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def send_email(
        subject: str = Field(..., description="Email subject line."),
        body: str = Field(..., description="Email body content in plain text."),
        to: Optional[List[str]] = Field(None, description="Array of recipient email addresses. Provide actual email addresses like ['alice@company.com', 'bob@domain.org']. If not provided, uses USER_GMAIL_ADDRESS."),
        cc: Optional[List[str]] = Field(None, description="Array of CC email addresses. Provide actual email addresses like ['manager@company.com']."),
    ) -> Dict[str, Any]:
        """Send an email using Gmail."""

        try:
            sender = os.getenv("AI_GMAIL_ADDRESS")
            if not sender:
                return error_response("AI_GMAIL_ADDRESS environment variable not set")
            
            # Handle default recipient logic
            if to is None:
                try:
                    user_addr = get_user_email_util()
                    to = [user_addr]
                except ValueError:
                    return error_response("USER_GMAIL_ADDRESS environment variable not set and no 'to' provided")
            
            # Get Gmail service and send email
            service = get_gmail_service(sender)
            
            # Create and configure email message
            message = MIMEText(body, 'plain', 'utf-8')
            message['to'] = ', '.join(to)
            message['from'] = sender
            message['subject'] = subject
            
            if cc:
                message['cc'] = ', '.join(cc)
            
            # Encode and send message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            msg_body = {'raw': raw}
            
            # Send the email
            send_result = service.users().messages().send(userId='me', body=msg_body).execute()
            if not send_result:
                return error_response("Failed to send email: No response from Gmail API")
            
            # Build response
            recipients_text = ', '.join(to)
            message_text = f"Email sent to {recipients_text}"
            llm_content = f"Sent email to {recipients_text} with subject: {subject}"
            
            return success_response(
                message_text,
                llm_content={
                    "parts": [
                        {"type": "text", "text": llm_content}
                    ]
                }
            )
            
        except FileNotFoundError as e:
            return error_response(f"Authentication required: {str(e)}")
        except ValueError as e:
            # Token expired or invalid
            return error_response(f"Authentication error: {str(e)}")
        except Exception as e:
            return error_response(f"Failed to send email: {str(e)}")