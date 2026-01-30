"""
Confluence Publishing Utility

Publishes EA documentation and reports to Confluence via REST API.
Supports both Confluence Cloud and Confluence Server/Data Center.
"""

import json
import base64
import requests
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime


class ConfluencePublisher:
    """Publish content to Confluence via REST API."""

    def __init__(self, base_url: str, space_key: str, username: str = None,
                 api_token: str = None, personal_access_token: str = None):
        """
        Initialize Confluence publisher.

        Args:
            base_url: Confluence base URL (e.g., https://company.atlassian.net/wiki)
            space_key: Confluence space key to publish to
            username: Username for basic auth (Cloud: email, Server: username)
            api_token: API token for Cloud or password for Server
            personal_access_token: Personal Access Token (Server/DC only, alternative to basic auth)
        """
        self.base_url = base_url.rstrip('/')
        self.space_key = space_key
        self.session = requests.Session()

        # Set up authentication
        if personal_access_token:
            # Personal Access Token (Server/Data Center)
            self.session.headers['Authorization'] = f'Bearer {personal_access_token}'
        elif username and api_token:
            # Basic auth (Cloud or Server)
            auth_string = base64.b64encode(f"{username}:{api_token}".encode()).decode()
            self.session.headers['Authorization'] = f'Basic {auth_string}'
        else:
            raise ValueError("Either personal_access_token or (username + api_token) required")

        self.session.headers['Content-Type'] = 'application/json'
        self.session.headers['Accept'] = 'application/json'

        # Detect API version
        self._api_base = f"{self.base_url}/rest/api"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to Confluence.

        Returns:
            Tuple of (success, message)
        """
        try:
            response = self.session.get(f"{self._api_base}/space/{self.space_key}")
            if response.status_code == 200:
                space_data = response.json()
                return True, f"Connected to space: {space_data.get('name', self.space_key)}"
            elif response.status_code == 401:
                return False, "Authentication failed - check credentials"
            elif response.status_code == 404:
                return False, f"Space '{self.space_key}' not found"
            else:
                return False, f"Connection failed: HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"

    def get_page_by_title(self, title: str, parent_id: str = None) -> Optional[Dict]:
        """
        Find a page by title.

        Args:
            title: Page title to search for
            parent_id: Optional parent page ID to search within

        Returns:
            Page data dict or None if not found
        """
        params = {
            'spaceKey': self.space_key,
            'title': title,
            'expand': 'version,ancestors'
        }

        response = self.session.get(f"{self._api_base}/content", params=params)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]
        return None

    def create_page(self, title: str, content: str, parent_id: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new Confluence page.

        Args:
            title: Page title
            content: Wiki markup or storage format content
            parent_id: Optional parent page ID

        Returns:
            Tuple of (success, message, page_id)
        """
        # Convert wiki markup to storage format if needed
        storage_content = self._convert_to_storage_format(content)

        payload = {
            'type': 'page',
            'title': title,
            'space': {'key': self.space_key},
            'body': {
                'storage': {
                    'value': storage_content,
                    'representation': 'storage'
                }
            }
        }

        if parent_id:
            payload['ancestors'] = [{'id': parent_id}]

        try:
            response = self.session.post(f"{self._api_base}/content", json=payload)
            if response.status_code == 200:
                page_data = response.json()
                page_id = page_data.get('id')
                page_url = f"{self.base_url}/pages/viewpage.action?pageId={page_id}"
                return True, f"Page created: {page_url}", page_id
            else:
                error_msg = response.json().get('message', response.text)
                return False, f"Failed to create page: {error_msg}", None
        except requests.exceptions.RequestException as e:
            return False, f"Request error: {str(e)}", None

    def update_page(self, page_id: str, title: str, content: str, version: int) -> Tuple[bool, str]:
        """
        Update an existing Confluence page.

        Args:
            page_id: Page ID to update
            title: Page title
            content: Wiki markup or storage format content
            version: Current page version (will be incremented)

        Returns:
            Tuple of (success, message)
        """
        storage_content = self._convert_to_storage_format(content)

        payload = {
            'type': 'page',
            'title': title,
            'version': {'number': version + 1},
            'body': {
                'storage': {
                    'value': storage_content,
                    'representation': 'storage'
                }
            }
        }

        try:
            response = self.session.put(f"{self._api_base}/content/{page_id}", json=payload)
            if response.status_code == 200:
                page_url = f"{self.base_url}/pages/viewpage.action?pageId={page_id}"
                return True, f"Page updated: {page_url}"
            else:
                error_msg = response.json().get('message', response.text)
                return False, f"Failed to update page: {error_msg}"
        except requests.exceptions.RequestException as e:
            return False, f"Request error: {str(e)}"

    def create_or_update_page(self, title: str, content: str, parent_id: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Create a page if it doesn't exist, or update it if it does.

        Args:
            title: Page title
            content: Wiki markup content
            parent_id: Optional parent page ID

        Returns:
            Tuple of (success, message, page_id)
        """
        existing = self.get_page_by_title(title)

        if existing:
            page_id = existing['id']
            version = existing['version']['number']
            success, message = self.update_page(page_id, title, content, version)
            return success, message, page_id if success else None
        else:
            return self.create_page(title, content, parent_id)

    def upload_attachment(self, page_id: str, file_path: Path, comment: str = None) -> Tuple[bool, str]:
        """
        Upload an attachment to a page.

        Args:
            page_id: Page ID to attach to
            file_path: Path to file to upload
            comment: Optional comment for the attachment

        Returns:
            Tuple of (success, message)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Remove JSON content type for file upload
        headers = {
            'X-Atlassian-Token': 'no-check'
        }

        # Keep auth headers but change content type
        upload_session = requests.Session()
        upload_session.headers = dict(self.session.headers)
        upload_session.headers.pop('Content-Type', None)
        upload_session.headers['X-Atlassian-Token'] = 'no-check'

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f)}
                data = {}
                if comment:
                    data['comment'] = comment

                response = upload_session.post(
                    f"{self._api_base}/content/{page_id}/child/attachment",
                    files=files,
                    data=data if data else None
                )

                if response.status_code in [200, 201]:
                    return True, f"Uploaded: {file_path.name}"
                else:
                    return False, f"Upload failed: {response.status_code} - {response.text[:200]}"
        except Exception as e:
            return False, f"Upload error: {str(e)}"

    def _convert_to_storage_format(self, wiki_content: str) -> str:
        """
        Convert Confluence wiki markup to storage format.

        For full conversion, this would use the Confluence API's convert endpoint.
        This implementation handles common patterns directly.
        """
        # Try API conversion first
        try:
            response = self.session.post(
                f"{self._api_base}/contentbody/convert/storage",
                json={
                    'value': wiki_content,
                    'representation': 'wiki'
                }
            )
            if response.status_code == 200:
                return response.json().get('value', wiki_content)
        except:
            pass

        # Fallback: wrap as wiki markup in storage format
        # This works because Confluence can render wiki markup in storage format
        # using the wiki macro
        return f'<ac:structured-macro ac:name="unmigrated-wiki-markup"><ac:plain-text-body><![CDATA[{wiki_content}]]></ac:plain-text-body></ac:structured-macro>'


def publish_ea_documentation(config, doc_file: Path, attachments: List[Path] = None) -> Tuple[bool, str]:
    """
    Publish EA documentation to Confluence.

    Args:
        config: Configuration object with Confluence settings
        doc_file: Path to EA documentation file
        attachments: Optional list of files to attach (PDFs, images)

    Returns:
        Tuple of (success, message)
    """
    # Check if Confluence publishing is enabled
    if not getattr(config, 'CONFLUENCE_ENABLED', False):
        return False, "Confluence publishing is disabled"

    # Validate required settings
    required = ['CONFLUENCE_URL', 'CONFLUENCE_SPACE_KEY']
    for setting in required:
        if not getattr(config, setting, None):
            return False, f"Missing required setting: {setting}"

    # Get credentials
    username = getattr(config, 'CONFLUENCE_USERNAME', None)
    api_token = getattr(config, 'CONFLUENCE_API_TOKEN', None)
    pat = getattr(config, 'CONFLUENCE_PAT', None)

    if not pat and not (username and api_token):
        return False, "Missing Confluence credentials"

    # Read documentation content
    if not doc_file.exists():
        return False, f"Documentation file not found: {doc_file}"

    content = doc_file.read_text(encoding='utf-8')

    # Create publisher
    try:
        publisher = ConfluencePublisher(
            base_url=config.CONFLUENCE_URL,
            space_key=config.CONFLUENCE_SPACE_KEY,
            username=username,
            api_token=api_token,
            personal_access_token=pat
        )
    except Exception as e:
        return False, f"Failed to initialize publisher: {e}"

    # Test connection
    connected, conn_msg = publisher.test_connection()
    if not connected:
        return False, conn_msg

    # Get page title and parent
    page_title = getattr(config, 'CONFLUENCE_PAGE_TITLE', 'MQ CMDB - Enterprise Architecture Documentation')
    parent_id = getattr(config, 'CONFLUENCE_PARENT_PAGE_ID', None)

    # Add timestamp to indicate last update
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content_with_timestamp = f"{{note:title=Last Updated}}{timestamp}{{note}}\n\n{content}"

    # Create or update page
    success, message, page_id = publisher.create_or_update_page(
        title=page_title,
        content=content_with_timestamp,
        parent_id=parent_id
    )

    if not success:
        return False, message

    # Upload attachments if provided and page was created/updated
    if page_id and attachments:
        attachment_results = []
        for attachment in attachments:
            if attachment.exists():
                att_success, att_msg = publisher.upload_attachment(page_id, attachment)
                attachment_results.append(f"  {attachment.name}: {'OK' if att_success else att_msg}")

        if attachment_results:
            message += "\nAttachments:\n" + "\n".join(attachment_results)

    return True, message
