from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
import os
from backend.nagisa_mcp.tools.google_auth.google_contacts import build_google_contacts_service

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

    @mcp.tool(**common_kwargs)
    def list_contacts(
        max_contacts: int = Field(100, description="Maximum number of contacts to retrieve")
    ) -> List[dict]:
        """
            Retrieve contacts from Google Contacts API using OAuth2 authentication.

            The account is determined by the AI_GMAIL_ADDRESS environment variable.

        Args:
                max_contacts (int): Maximum number of contacts to retrieve. Default is 100.

        Returns:
                List[dict]: A list of contact dictionaries. Each dictionary contains:
                    - id (str): Contact's unique identifier
                    - name (str): Contact's display name
                    - emails (List[str]): List of contact's email addresses
                    - phones (List[str]): List of contact's phone numbers
                If an error occurs, returns a list with a single dictionary containing:
                    - error (str): Error message
                    - timestamp (str): ISO format timestamp
        """
        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return [{"error": "AI_GMAIL_ADDRESS environment variable not set", "timestamp": datetime.now().isoformat()}]
            
            service = build_google_contacts_service(nagisa_email)
            # Get the list of connections (contacts)
            results = service.people().connections().list(
                resourceName='people/me',
                        pageSize=max_contacts,
                personFields='names,emailAddresses,phoneNumbers'
            ).execute()
        
            contacts = []
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
                    
                    # Extract phone numbers
                    if 'phoneNumbers' in person:
                        contact['phones'] = [phone['value'] for phone in person['phoneNumbers']]
                    
                    contacts.append(contact)
                return contacts
        
        except Exception as e:
            return [{
                "error": f"Failed to retrieve contacts: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }]

    @mcp.tool(**common_kwargs)
    def search_contacts(
        query: str = Field(..., description="Search query for contacts (name, relationship, email, or phone)"),
        max_results: int = Field(100, description="Maximum number of results to return")
    ) -> List[dict]:
        """
            Search contacts in Google Contacts API using OAuth2 authentication.

            The account is determined by the AI_GMAIL_ADDRESS environment variable.

        Args:
                query (str): Search query for contacts (name, relationship, email, or phone).
                max_results (int): Maximum number of results to return. Default is 100.

        Returns:
                List[dict]: A list of matching contact dictionaries. Each dictionary contains:
                    - id (str): Contact's unique identifier
                    - name (str): Contact's display name
                    - emails (List[str]): List of contact's email addresses
                    - phones (List[str]): List of contact's phone numbers
                If an error occurs, returns a list with a single dictionary containing:
                    - error (str): Error message
                    - timestamp (str): ISO format timestamp
        """
        try:
            nagisa_email = os.getenv("AI_GMAIL_ADDRESS")
            if not nagisa_email:
                return [{"error": "AI_GMAIL_ADDRESS environment variable not set", "timestamp": datetime.now().isoformat()}]
            
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
            return contacts 
        
        except Exception as e:
            return [{
                "error": f"Failed to search contacts: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }] 