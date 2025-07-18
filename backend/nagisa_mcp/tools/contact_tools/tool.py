"""
Contact Tools Module - Google Contacts integration for directory access
"""

from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
import os

from backend.nagisa_mcp.tools.google_auth.google_contacts import build_google_contacts_service
from backend.nagisa_mcp.utils.tool_result import ToolResult

class Contact(BaseModel):
    """Contact model for validation"""
    id: str = Field(..., description="Contact's unique identifier")
    name: str = Field(..., description="Contact's display name")
    emails: List[EmailStr] = Field(default_factory=list, description="List of contact's email addresses")
    phones: List[str] = Field(default_factory=list, description="List of contact's phone numbers")

def register_contact_tools(mcp: FastMCP):
    """Register Google Contacts API based tools with proper tags synchronization."""
    
    common_kwargs = dict(
        tags={"contact", "google", "people", "search", "directory"}, 
        annotations={"category": "contact", "tags": ["contact", "google", "people", "search", "directory"]}
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
    def list_contacts(
        max_contacts: int = Field(100, ge=1, le=500, description="Maximum number of contacts to retrieve (1-500).")
    ) -> Dict[str, Any]:
        """Retrieve contacts from Google Contacts API using OAuth2 authentication.
        
        Fetches contacts via People API and returns structured contact data with names, emails, and phone numbers.
        Uses OAuth2 authentication from AI_GMAIL_ADDRESS environment variable.
        """
        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return _error("AI_GMAIL_ADDRESS environment variable not set")
            
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
                    
                    # Extract email addresses
                    if 'emailAddresses' in person:
                        contact['emails'] = [email['value'] for email in person['emailAddresses']]
                        if contact['emails']:
                            contacts_with_email += 1
                    
                    # Extract phone numbers
                    if 'phoneNumbers' in person:
                        contact['phones'] = [phone['value'] for phone in person['phoneNumbers']]
                        if contact['phones']:
                            contacts_with_phone += 1
                    
                    contacts.append(contact)
            
            # Build structured response
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "list_contacts",
                    "max_contacts": max_contacts,
                    "account": nagisa_email,
                    "timestamp": timestamp
                },
                "result": {
                    "contacts": contacts,
                    "total_contacts": len(contacts),
                    "contacts_with_email": contacts_with_email,
                    "contacts_with_phone": contacts_with_phone
                },
                "summary": {
                    "operation_type": "list_contacts",
                    "success": True
                }
            }
            
            message = f"Retrieved {len(contacts)} contacts from {nagisa_email}"
            
            return _success(
                message,
                llm_content,
                contacts=contacts,
                total_contacts=len(contacts),
                account=nagisa_email
            )
        
        except Exception as e:
            return _error(f"Failed to retrieve contacts: {str(e)}")

    @mcp.tool(**common_kwargs)
    def search_contacts(
        query: str = Field(..., description="Search query for contacts (name, email, or phone number)."),
        max_results: int = Field(100, ge=1, le=500, description="Maximum number of results to return (1-500).")
    ) -> Dict[str, Any]:
        """Search contacts in Google Contacts API using OAuth2 authentication.
        
        Searches contacts using Google People API search functionality. Matches against names,
        emails, and phone numbers with relevance-based ordering.
        """
        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return _error("AI_GMAIL_ADDRESS environment variable not set")
            
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
                    
                    # Extract email addresses
                    if 'emailAddresses' in person:
                        contact['emails'] = [email['value'] for email in person['emailAddresses']]
                    
                    # Extract phone numbers
                    if 'phoneNumbers' in person:
                        contact['phones'] = [phone['value'] for phone in person['phoneNumbers']]
                    
                    contacts.append(contact)
            
            # Build structured response
            timestamp = datetime.now().isoformat()
            
            llm_content = {
                "operation": {
                    "type": "search_contacts",
                    "query": query,
                    "max_results": max_results,
                    "account": nagisa_email,
                    "timestamp": timestamp
                },
                "result": {
                    "contacts": contacts,
                    "total_matches": len(contacts),
                    "search_limited": len(contacts) >= max_results
                },
                "summary": {
                    "operation_type": "search_contacts",
                    "success": True
                }
            }
            
            message = f"Found {len(contacts)} contacts matching '{query}'"
            
            return _success(
                message,
                llm_content,
                contacts=contacts,
                total_matches=len(contacts),
                search_query=query
            )
        
        except Exception as e:
            return _error(f"Failed to search contacts: {str(e)}") 