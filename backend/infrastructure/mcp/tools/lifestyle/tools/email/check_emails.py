"""Gmail check emails tool.

This module provides the check_emails tool for retrieving emails
from Gmail using OAuth2 authentication.
"""

import os
from typing import Dict, Any

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.gmail_service import get_gmail_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_check_emails_tool(mcp: FastMCP):
    """Register the check emails tool."""
    
    common_tags = {"email", "gmail", "google", "messaging", "communication"}
    common_annotations = {"category": "email", "tags": ["email", "gmail", "google", "messaging", "communication"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def check_emails(
        max_emails: int = Field(16, ge=1, le=50, description="Maximum number of emails to retrieve (1-50)."),
        unread_only: bool = Field(False, description="Whether to retrieve only unread emails."),
        offset: int = Field(0, ge=0, description="Number of emails to skip from the beginning (for pagination)."),
    ) -> Dict[str, Any]:
        """Retrieve emails from Gmail."""

        try:
            user_email = os.getenv("AI_GMAIL_ADDRESS")
            if not user_email:
                return error_response("AI_GMAIL_ADDRESS environment variable not set")
            
            service = get_gmail_service(user_email)
            
            # Query for emails - fetch extra to handle offset
            query = 'is:unread' if unread_only else ''
            # Need to fetch offset + max_emails to skip the first 'offset' messages
            fetch_count = offset + max_emails
            results = service.users().messages().list(userId='me', maxResults=min(fetch_count, 500), q=query).execute()
            all_messages = results.get('messages', [])
            
            # Apply offset by skipping the first 'offset' messages
            messages = all_messages[offset:offset + max_emails]
            
            email_list = []
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}
                
                subject = headers.get('subject', '')
                from_addr = headers.get('from', '')
                date = headers.get('date', '')
                
                email_list.append({
                    "id": msg['id'],  # Add message ID for read_email tool
                    "subject": subject,
                    "from": from_addr,
                    "date": date
                })
            
            
            # Format emails for LLM content - structured format
            if email_list:
                email_lines = []
                for email in email_list:
                    # Extract just the sender name/email (remove angle brackets if present)
                    sender_name = email['from'].split('<')[0].strip() if '<' in email['from'] else email['from']
                    # Shorten date (remove timezone info for brevity)
                    formatted_date = email['date'].split(',')[-1].strip().split(' +')[0].split(' -')[0].strip() if ',' in email['date'] else email['date']
                    # Structured format without numbering
                    email_lines.append(f"• {email['subject']}")
                    email_lines.append(f"  From: {sender_name}, {formatted_date}")
                    email_lines.append(f"  ID: {email['id']}")
                llm_content = '\n'.join(email_lines)
            else:
                llm_content = "No emails found"
            
            # Build response message
            message = f"Retrieved {len(email_list)} emails"
            if unread_only:
                message += " (unread only)"
            
            return success_response(message, llm_content)
            
        except FileNotFoundError as e:
            return error_response(f"Authentication required: {str(e)}")
        except ValueError as e:
            # Token expired or invalid
            return error_response(f"Authentication error: {str(e)}")
        except Exception as e:
            return error_response(f"Failed to retrieve emails: {str(e)}")