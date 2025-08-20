"""Gmail read email tool.

This module provides the read_email tool for reading a full email
from Gmail using OAuth2 authentication.
"""

import os
from typing import Dict, Any
import base64

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.gmail_service import get_gmail_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_read_email_tool(mcp: FastMCP):
    """Register the read email tool."""
    
    common_tags = {"email", "gmail", "google", "messaging", "communication"}
    common_annotations = {"category": "email", "tags": ["email", "gmail", "google", "messaging", "communication"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def read_email(
        email_id: str = Field(..., description="Gmail message ID to read."),
    ) -> Dict[str, Any]:
        """Read a full email from Gmail by message ID."""

        try:
            user_email = os.getenv("AI_GMAIL_ADDRESS")
            if not user_email:
                return error_response("AI_GMAIL_ADDRESS environment variable not set")
            
            service = get_gmail_service(user_email)
            
            # Get the full email message
            msg_data = service.users().messages().get(
                userId='me', 
                id=email_id, 
                format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}
            
            subject = headers.get('subject', 'No Subject')
            from_addr = headers.get('from', 'Unknown Sender')
            to_addr = headers.get('to', '')
            cc_addr = headers.get('cc', '')
            date = headers.get('date', '')
            
            # Extract email body (full content)
            body = ""
            html_body = ""
            
            def extract_body_from_parts(parts):
                nonlocal body, html_body
                for part in parts:
                    mime_type = part.get('mimeType', '')
                    
                    # Handle nested parts
                    if 'parts' in part:
                        extract_body_from_parts(part['parts'])
                    
                    # Extract text/plain content
                    if mime_type == 'text/plain' and 'data' in part.get('body', {}):
                        try:
                            text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            if text and not body:  # Prefer first text/plain part
                                body = text
                        except Exception:
                            pass
                    
                    # Extract text/html content as fallback
                    elif mime_type == 'text/html' and 'data' in part.get('body', {}):
                        try:
                            html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            if html and not html_body:
                                html_body = html
                        except Exception:
                            pass
            
            # Try to extract body from parts
            if 'parts' in msg_data['payload']:
                extract_body_from_parts(msg_data['payload']['parts'])
            elif 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
                # Single part message
                try:
                    body = base64.urlsafe_b64decode(
                        msg_data['payload']['body']['data']
                    ).decode('utf-8', errors='ignore')
                except Exception:
                    pass
            
            # Use HTML body if no plain text found
            if not body and html_body:
                # Simple HTML to text conversion (remove tags)
                import re
                body = re.sub('<[^<]+?>', '', html_body)
                body = body.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
            
            if not body:
                body = "No body content found"
            
            # Check for attachments
            attachments = []
            def check_attachments(parts):
                for part in parts:
                    if 'parts' in part:
                        check_attachments(part['parts'])
                    
                    filename = part.get('filename', '')
                    if filename:
                        size = part.get('body', {}).get('size', 0)
                        attachments.append({
                            'filename': filename,
                            'size': size,
                            'mime_type': part.get('mimeType', '')
                        })
            
            if 'parts' in msg_data['payload']:
                check_attachments(msg_data['payload']['parts'])
            
            # Format email for display
            email_lines = [
                f"From: {from_addr}",
                f"To: {to_addr}",
            ]
            
            if cc_addr:
                email_lines.append(f"CC: {cc_addr}")
            
            email_lines.extend([
                f"Date: {date}",
                f"Subject: {subject}",
                "",  # Empty line
                "--- Message ---",
                body.strip()
            ])
            
            if attachments:
                email_lines.extend([
                    "",
                    f"--- Attachments ({len(attachments)}) ---"
                ])
                for att in attachments:
                    email_lines.append(f"• {att['filename']} ({att['size']} bytes, {att['mime_type']})")
            
            llm_content = '\n'.join(email_lines)
            
            # Build response
            message = f"Read email: {subject}"
            
            return success_response(message, llm_content)
            
        except FileNotFoundError as e:
            return error_response(f"Authentication required: {str(e)}")
        except ValueError as e:
            # Token expired or invalid
            return error_response(f"Authentication error: {str(e)}")
        except Exception as e:
            if 'not found' in str(e).lower():
                return error_response(f"Email not found with ID: {email_id}")
            return error_response(f"Failed to read email: {str(e)}")