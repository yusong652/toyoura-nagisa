"""Google Contacts list contacts tool.

This module provides the list_contacts tool for retrieving
contacts from Google Contacts using OAuth2 authentication.
"""

import os
from typing import Dict, Any

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.google_contacts import build_google_contacts_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_list_contacts_tool(mcp: FastMCP):
    """Register the list contacts tool."""
    
    common_tags = {"contact", "google", "people", "search", "directory"}
    common_annotations = {"category": "contact", "tags": ["contact", "google", "people", "search", "directory"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def list_contacts(
        max_contacts: int = Field(100, ge=1, le=500, description="Maximum number of contacts to retrieve (1-500)."),
    ) -> Dict[str, Any]:
        """Retrieve contacts from Google Contacts API using OAuth2 authentication."""

        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return error_response("AI_GMAIL_ADDRESS environment variable not set")
            
            service = build_google_contacts_service(nagisa_email)
            
            # Get the list of connections (contacts)
            results = service.people().connections().list(
                resourceName='people/me',
                pageSize=max_contacts,
                personFields='names,emailAddresses,phoneNumbers'
            ).execute()
        
            contacts = []
            contacts_with_email = 0
            contacts_with_phone = 0
            
            if 'connections' in results:
                for person in results['connections']:
                    contact = {
                        'id': person.get('resourceName', ''),
                        'name': '',
                        'emails': [],
                        'phones': []
                    }
                    
                    # Extract names
                    if 'names' in person:
                        for name in person['names']:
                            if 'displayName' in name:
                                contact['name'] = name['displayName']
                                break
                    
                    # Extract email addresses (remove duplicates while preserving order)
                    if 'emailAddresses' in person:
                        email_list = []
                        seen = set()
                        for email in person['emailAddresses']:
                            value = email['value']
                            if value not in seen:
                                email_list.append(value)
                                seen.add(value)
                        contact['emails'] = email_list
                        if contact['emails']:
                            contacts_with_email += 1
                    
                    # Extract phone numbers
                    if 'phoneNumbers' in person:
                        contact['phones'] = [phone['value'] for phone in person['phoneNumbers']]
                        if contact['phones']:
                            contacts_with_phone += 1
                    
                    contacts.append(contact)
            
            # Build response
            message = f"Retrieved {len(contacts)} contacts from {nagisa_email}"
            
            # Format contacts for LLM content
            if contacts:
                contact_lines = []
                for contact in contacts:
                    name = contact['name'] or 'No Name'
                    emails = ', '.join(contact['emails']) if contact['emails'] else 'No Email'
                    phones = ', '.join(contact['phones']) if contact['phones'] else 'No Phone'
                    contact_lines.append(f"• {name} - {emails} - {phones}")
                llm_content = '\n'.join(contact_lines)
            else:
                llm_content = "No contacts found"
            
            return success_response(
                message,
                llm_content={
                    "parts": [
                        {"type": "text", "text": llm_content}
                    ]
                },
                contacts=contacts,
                total_contacts=len(contacts),
                contacts_with_email=contacts_with_email,
                contacts_with_phone=contacts_with_phone,
                account=nagisa_email
            )
        
        except Exception as e:
            return error_response(f"Failed to retrieve contacts: {str(e)}")