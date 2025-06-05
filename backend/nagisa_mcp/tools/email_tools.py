from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from backend.config import get_email_config

class EmailMessage(BaseModel):
    """Email message model for validation"""
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    to: List[EmailStr] = Field(..., description="List of recipient email addresses")
    cc: Optional[List[EmailStr]] = Field(None, description="List of CC email addresses")
    bcc: Optional[List[EmailStr]] = Field(None, description="List of BCC email addresses")

def register_email_tools(mcp: FastMCP):
    """Register email-related tools to MCP"""
    
    @mcp.tool()
    def send_email(
        subject: str = Field(..., description="Email subject"),
        body: str = Field(..., description="Email body content"),
        to: List[str] = Field(..., description="List of recipient email addresses"),
        cc: Optional[List[str]] = Field(None, description="List of CC email addresses"),
        bcc: Optional[List[str]] = Field(None, description="List of BCC email addresses")
    ) -> dict:
        """
        Send an email using the configured SMTP server.

        This tool allows sending emails to multiple recipients with optional CC and BCC.
        The email will be sent using UTF-8 encoding and can include plain text content.

        Args:
            subject: The subject line of the email
            body: The main content of the email in plain text
            to: List of email addresses to send the email to
            cc: Optional list of email addresses to CC
            bcc: Optional list of email addresses to BCC

        Returns:
            dict: A dictionary containing:
                - status: "success" or "error"
                - message: Success message or error description
                - timestamp: ISO format timestamp of the operation
        """
        try:
            config = get_email_config()
            
            # Create email message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = f"{config['sender_name']} <{config['username']}>"
            msg['To'] = ', '.join(to)
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add email body
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Connect to SMTP server
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                if config['use_tls']:
                    server.starttls()
                server.login(config['username'], config['password'])
                
                # Send email
                recipients = to + (cc or []) + (bcc or [])
                server.sendmail(config['username'], recipients, msg.as_string())
            
            return {
                "status": "success",
                "message": "Email sent successfully",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to send email: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    @mcp.tool()
    def check_emails(
        max_emails: int = Field(5, description="Maximum number of emails to retrieve"),
        unread_only: bool = Field(False, description="Whether to retrieve only unread emails")
    ) -> List[dict]:
        """
        Retrieve emails from the configured IMAP server.

        This tool fetches emails from the inbox, with options to limit the number of emails
        and filter for unread messages only. Each email's content is truncated to 200 characters
        for preview purposes.

        Args:
            max_emails: Maximum number of emails to retrieve (default: 5)
            unread_only: If True, only retrieve unread emails (default: False)

        Returns:
            List[dict]: A list of email dictionaries, each containing:
                - subject: Email subject
                - from: Sender's email address
                - date: Email date
                - body: Email body content (truncated to 200 characters)
                If an error occurs, returns a list with a single error dictionary.
        """
        try:
            config = get_email_config()
            
            # Connect to IMAP server
            with imaplib.IMAP4_SSL(config['imap_server'], config['imap_port']) as imap:
                imap.login(config['username'], config['password'])
                imap.select('INBOX')
                
                # Build search criteria
                search_criteria = '(UNSEEN)' if unread_only else 'ALL'
                _, message_numbers = imap.search(None, search_criteria)
                
                # Get the latest emails
                email_list = []
                for num in message_numbers[0].split()[-max_emails:]:
                    _, msg_data = imap.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Parse email information
                    subject = email.header.make_header(email.header.decode_header(email_message['Subject']))
                    from_addr = email.header.make_header(email.header.decode_header(email_message['From']))
                    date = email_message['Date']
                    
                    # Get email body
                    body = ""
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = email_message.get_payload(decode=True).decode()
                    
                    email_list.append({
                        "subject": str(subject),
                        "from": str(from_addr),
                        "date": date,
                        "body": body[:200] + "..." if len(body) > 200 else body
                    })
                
                return email_list
                
        except Exception as e:
            return [{
                "error": f"Failed to retrieve emails: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }] 