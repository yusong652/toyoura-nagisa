from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
import os
from backend.nagisa_mcp.tools.google_auth.gmail_service import get_gmail_service
from email.mime.text import MIMEText
import base64


class EmailMessage(BaseModel):
    """Email message model for validation"""
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    to: List[EmailStr] = Field(..., description="List of recipient email addresses")
    cc: Optional[List[EmailStr]] = Field(None, description="List of CC email addresses")
    bcc: Optional[List[EmailStr]] = Field(None, description="List of BCC email addresses")

# SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']

# def get_gmail_service():
#     """
#     Initialize and return a Gmail API service using OAuth2 credentials.
#     """
#     # TODO: 实现token加载/刷新/授权流程
#     pass


def register_email_tools(mcp: FastMCP):
    """Register Gmail API based email tools to MCP (OAuth2 version)"""
    
    common_kwargs = dict(tags={"email"}, annotations={"category": "email"})

    @mcp.tool(**common_kwargs)
    def get_user_email() -> dict:
        """
        Get the user's email address from environment variables.

        Returns:
            dict: A dictionary with the following keys:
                - status (str): "success" or "error"
                - email (str): User's email address if found
                - message (str): Success message or error description
                - timestamp (str): ISO format timestamp of the operation
        """
        try:
            user_email = os.getenv("USER_GMAIL_ADDRESS")
            if not user_email:
                return {
                    "status": "error",
                    "message": "USER_GMAIL_ADDRESS environment variable not set",
                    "timestamp": datetime.now().isoformat()
                }
            return {
                "status": "success",
                "email": user_email,
                "message": "Successfully retrieved user email address",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get user email: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    @mcp.tool(**common_kwargs)
    def send_email(
        subject: str = Field(..., description="Email subject"),
        body: str = Field(..., description="Email body content"),
        to: Optional[List[str]] = Field(None, description="List of recipient email addresses. If not provided, will use USER_GMAIL_ADDRESS from environment variable."),
        cc: Optional[List[str]] = Field(None, description="List of CC email addresses"),
        bcc: Optional[List[str]] = Field(None, description="List of BCC email addresses")
    ) -> dict:
        """
        Send an email using the Gmail API and OAuth2 authentication.

        The sender is determined by the AI_GMAIL_ADDRESS environment variable.
        If the 'to' parameter is not provided, the email will be sent to the address specified by USER_GMAIL_ADDRESS environment variable.

        Args:
            subject (str): The subject line of the email.
            body (str): The main content of the email in plain text.
            to (Optional[List[str]]): List of recipient email addresses. If None, will use USER_GMAIL_ADDRESS from environment variable.
            cc (Optional[List[str]]): Optional list of CC email addresses.
            bcc (Optional[List[str]]): Optional list of BCC email addresses.

        Returns:
            dict: A dictionary with the following keys:
                - status (str): "success" or "error"
                - message (str): Success message or error description
                - timestamp (str): ISO format timestamp of the operation
        """
        try:
            sender = os.getenv("AI_GMAIL_ADDRESS")
            if not sender:
                return {"status": "error", "message": "AI_GMAIL_ADDRESS environment variable not set", "timestamp": datetime.now().isoformat()}
            # 默认收件人逻辑
            if to is None:
                user_addr = os.getenv("USER_GMAIL_ADDRESS")
                if not user_addr:
                    return {"status": "error", "message": "USER_GMAIL_ADDRESS environment variable not set and no 'to' provided", "timestamp": datetime.now().isoformat()}
                to = [user_addr]
            service = get_gmail_service(sender)
            message = MIMEText(body, 'plain', 'utf-8')
            message['to'] = ', '.join(to)
            message['from'] = sender
            message['subject'] = subject
            if cc:
                message['cc'] = ', '.join(cc)
            # Gmail API expects base64url encoded message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            msg_body = {'raw': raw}
            sent = service.users().messages().send(userId='me', body=msg_body).execute()
            return {
                "status": "success",
                "message": f"Email sent. Gmail id: {sent.get('id')}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to send email: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    @mcp.tool(**common_kwargs)
    def check_emails(
        max_emails: int = Field(5, description="Maximum number of emails to retrieve"),
        unread_only: bool = Field(False, description="Whether to retrieve only unread emails")
    ) -> List[dict]:
        """
        Retrieve emails from Gmail using the Gmail API and OAuth2 authentication.

        The account is determined by the AI_GMAIL_ADDRESS environment variable.

        Args:
            max_emails (int): Maximum number of emails to retrieve. Default is 5.
            unread_only (bool): If True, only retrieve unread emails. Default is False.

        Returns:
            List[dict]: A list of email dictionaries. Each dictionary contains:
                - subject (str): Email subject
                - from (str): Sender's email address
                - date (str): Email date
                - body (str): Email body content (truncated to 200 characters)
            If an error occurs, returns a list with a single dictionary containing:
                - error (str): Error message
                - timestamp (str): ISO format timestamp
        """
        try:
            user_email = os.getenv("AI_GMAIL_ADDRESS")
            if not user_email:
                return [{"error": "AI_GMAIL_ADDRESS environment variable not set", "timestamp": datetime.now().isoformat()}]
            service = get_gmail_service(user_email)
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
                # 获取正文
                body = ""
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            break
                else:
                    body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')
                email_list.append({
                    "subject": subject,
                    "from": from_addr,
                    "date": date,
                    "body": body[:200] + ("..." if len(body) > 200 else "")
                })
            return email_list
        except Exception as e:
            return [{
                "error": f"Failed to retrieve emails: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }] 