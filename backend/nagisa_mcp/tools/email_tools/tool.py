"""
Email Tools Module - Gmail integration for email communication
"""

from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
import os
from email.mime.text import MIMEText
import base64

from backend.nagisa_mcp.tools.google_auth.gmail_service import get_gmail_service
from backend.nagisa_mcp.utils.tool_result import ToolResult

class EmailMessage(BaseModel):
    """Email message model for validation"""
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    to: List[EmailStr] = Field(..., description="List of recipient email addresses")
    cc: Optional[List[EmailStr]] = Field(None, description="List of CC email addresses")
    bcc: Optional[List[EmailStr]] = Field(None, description="List of BCC email addresses")

def register_email_tools(mcp: FastMCP):
    """Register Gmail API based email tools with proper tags synchronization."""
    
    common_kwargs = dict(
        tags={"email", "gmail", "google", "messaging", "communication"}, 
        annotations={"category": "email", "tags": ["email", "gmail", "google", "messaging", "communication"]}
    )

    # Helper functions for consistent responses
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    @mcp.tool(**common_kwargs)
    def get_user_email() -> Dict[str, Any]:
        """Get the configured user email address from environment variables.
        
        Retrieves user email from USER_GMAIL_ADDRESS environment variable and validates
        email configuration for communication setup.
        """
        try:
            user_email = os.getenv("USER_GMAIL_ADDRESS")
            if not user_email:
                return _error("USER_GMAIL_ADDRESS environment variable not set")
            
            llm_content = {
                "operation": {
                    "type": "get_user_email"
                },
                "result": {
                    "user_email": user_email,
                    "email_configured": True
                },
                "summary": {
                    "operation_type": "email",
                    "success": True
                }
            }
            
            message = f"User email configured: {user_email}"
            
            return _success(
                message,
                llm_content,
                user_email=user_email,
                email_configured=True
            )
            
        except Exception as e:
            return _error(f"Failed to get user email: {str(e)}")

    @mcp.tool(**common_kwargs)
    def send_email(
        subject: str = Field(..., description="Email subject line."),
        body: str = Field(..., description="Email body content in plain text."),
        to: Optional[List[str]] = Field(None, description="List of recipient email addresses. If not provided, uses USER_GMAIL_ADDRESS."),
        cc: Optional[List[str]] = Field(None, description="List of CC email addresses."),
        bcc: Optional[List[str]] = Field(None, description="List of BCC email addresses.")
    ) -> Dict[str, Any]:
        """Send an email using Gmail API with OAuth2 authentication.
        
        Sends emails via Gmail API using AI_GMAIL_ADDRESS as sender. Supports TO, CC, and BCC recipients.
        Defaults to USER_GMAIL_ADDRESS if no recipients specified. Returns delivery confirmation with Gmail message ID.
        """
        try:
            sender = os.getenv("AI_GMAIL_ADDRESS")
            if not sender:
                return _error("AI_GMAIL_ADDRESS environment variable not set")
            
            # Handle default recipient logic
            if to is None:
                user_addr = os.getenv("USER_GMAIL_ADDRESS")
                if not user_addr:
                    return _error("USER_GMAIL_ADDRESS environment variable not set and no 'to' provided")
                to = [user_addr]
            
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
            sent = service.users().messages().send(userId='me', body=msg_body).execute()
            
            gmail_id = sent.get('id')
            
            llm_content = {
                "operation": {
                    "type": "send_email",
                    "sender": sender,
                    "subject": subject,
                    "recipients": to,
                    "cc_count": len(cc) if cc else 0,
                    "bcc_count": len(bcc) if bcc else 0
                },
                "result": {
                    "gmail_id": gmail_id,
                    "delivery_status": "sent"
                },
                "summary": {
                    "operation_type": "email",
                    "success": True
                }
            }
            
            message_text = f"Email sent successfully to {len(to)} recipient(s)"
            
            return _success(
                message_text,
                llm_content,
                gmail_id=gmail_id,
                recipients=to,
                cc=cc,
                bcc=bcc,
                subject=subject
            )
            
        except Exception as e:
            return _error(f"Failed to send email: {str(e)}")

    @mcp.tool(**common_kwargs)
    def check_emails(
        max_emails: int = Field(5, ge=1, le=50, description="Maximum number of emails to retrieve (1-50)."),
        unread_only: bool = Field(False, description="Whether to retrieve only unread emails.")
    ) -> Dict[str, Any]:
        """Retrieve emails from Gmail using OAuth2 authentication.
        
        Fetches emails from Gmail API using AI_GMAIL_ADDRESS account. Supports filtering for unread emails only.
        Returns email metadata and truncated body content with email statistics.
        """
        try:
            user_email = os.getenv("AI_GMAIL_ADDRESS")
            if not user_email:
                return _error("AI_GMAIL_ADDRESS environment variable not set")
            
            service = get_gmail_service(user_email)
            
            # Query for emails
            query = 'is:unread' if unread_only else ''
            results = service.users().messages().list(userId='me', maxResults=max_emails, q=query).execute()
            messages = results.get('messages', [])
            
            email_list = []
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}
                
                subject = headers.get('subject', '')
                from_addr = headers.get('from', '')
                date = headers.get('date', '')
                
                # Extract email body
                body = ""
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            break
                elif 'data' in msg_data['payload']['body']:
                    body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')
                
                # Truncate body for preview
                body_preview = body[:200] + ("..." if len(body) > 200 else "")
                
                email_list.append({
                    "subject": subject,
                    "from": from_addr,
                    "date": date,
                    "body": body_preview
                })
            
            # Get unread count for statistics
            unread_results = service.users().messages().list(userId='me', q='is:unread').execute()
            unread_count = len(unread_results.get('messages', []))
            
            llm_content = {
                "operation": {
                    "type": "check_emails",
                    "max_emails": max_emails,
                    "unread_only": unread_only,
                    "account": user_email,
                },
                "result": {
                    "emails": email_list,
                    "total_emails": len(email_list),
                    "unread_count": unread_count,
                    "emails_limited": len(email_list) >= max_emails
                },
                "summary": {
                    "operation_type": "emails",
                    "success": True
                }
            }
            
            message = f"Retrieved {len(email_list)} emails from {user_email}"
            if unread_only:
                message += " (unread only)"
            
            return _success(
                message,
                llm_content,
                emails=email_list,
                total_emails=len(email_list),
                unread_count=unread_count,
                account=user_email
            )
            
        except Exception as e:
            return _error(f"Failed to retrieve emails: {str(e)}") 