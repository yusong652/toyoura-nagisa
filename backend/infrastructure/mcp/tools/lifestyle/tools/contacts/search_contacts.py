"""Google Contacts search contacts tool.

This module provides the search_contacts tool for searching
contacts in Google Contacts using OAuth2 authentication.
"""

import os
from typing import Dict, Any

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.google_contacts import build_google_contacts_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_search_contacts_tool(mcp: FastMCP):
    """Register the search contacts tool."""
    
    common_tags = {"contact", "google", "people", "search", "directory"}
    common_annotations = {"category": "contact", "tags": ["contact", "google", "people", "search", "directory"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def search_contacts(
        query: str = Field(..., description="Search query for contacts (name, email, or phone number)."),
        max_results: int = Field(100, ge=1, le=500, description="Maximum number of results to return (1-500)."),
    ) -> Dict[str, Any]:
        """Search contacts in Google Contacts API using OAuth2 authentication."""

        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return error_response("AI_GMAIL_ADDRESS environment variable not set")
            
            service = build_google_contacts_service(nagisa_email)
            
            # Search for contacts
            results = service.people().searchContacts(
                query=query,
                pageSize=max_results,
                readMask='names,emailAddresses,phoneNumbers'
            ).execute()
            
            contacts = []
            if 'results' in results:
                for result in results['results']:
                    person = result.get('person', {})
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
                    
                    # Extract phone numbers
                    if 'phoneNumbers' in person:
                        contact['phones'] = [phone['value'] for phone in person['phoneNumbers']]
                    
                    contacts.append(contact)
            
            # Build response
            message = f"Found {len(contacts)} contacts matching '{query}'"
            
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
                llm_content = f"No contacts found matching '{query}'"
            
            return success_response(
                message,
                llm_content,
                contacts=contacts,
                total_matches=len(contacts),
                search_query=query,
                search_limited=len(contacts) >= max_results
            )
        
        except Exception as e:
            return error_response(f"Failed to search contacts: {str(e)}")