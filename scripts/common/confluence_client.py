"""
Generic Confluence REST API client for CRUD operations.

Project-agnostic - accepts all configuration as parameters.
Supports Confluence wiki markup pages, file attachments (SVG, PNG, etc.),
and both PAT (Personal Access Token) and basic auth.

Usage:
    from scripts.common.confluence_client import ConfluenceClient

    client = ConfluenceClient(
        base_url="https://confluence.example.com",
        personal_access_token="your-token",
        certificate_path="/path/to/cert.pem"  # optional
    )

    # Update a page with wiki markup
    client.update_page(page_id="123456", title="My Page", body="h1. Hello")

    # Attach an SVG file
    client.attach_file(page_id="123456", file_path="/path/to/diagram.svg")
"""

import json
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Generic Confluence REST API client for CRUD operations."""

    def __init__(
        self,
        base_url: str,
        personal_access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        certificate_path: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize the Confluence client.

        Auth priority: PAT > basic auth (username/password).

        Args:
            base_url: Confluence base URL (e.g. https://confluence.example.com)
            personal_access_token: PAT for bearer auth
            username: Username for basic auth (fallback)
            password: Password for basic auth (fallback)
            certificate_path: Path to CA bundle (.pem) for SSL server verification.
                              Passed as requests' verify= parameter.
            verify_ssl: Whether to verify SSL certificates. Ignored when
                        certificate_path is provided (certificate_path takes precedence).
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api"
        self.timeout = timeout

        # SSL config: certificate_path is the CA bundle for server verification
        # (same as requests' verify= parameter). NOT a client cert for mTLS.
        self.verify_ssl = certificate_path if certificate_path else verify_ssl

        # Build session with auth
        self.session = requests.Session()

        if personal_access_token:
            self.session.headers["Authorization"] = f"Bearer {personal_access_token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise ValueError("Either personal_access_token or username/password must be provided")

        self.session.headers["Accept"] = "application/json"

    # ------------------------------------------------------------------ #
    #  READ
    # ------------------------------------------------------------------ #

    def get_page(self, page_id: str, expand: str = "version,body.storage,space") -> Dict[str, Any]:
        """
        Get a Confluence page by ID.

        Args:
            page_id: The Confluence page ID
            expand: Comma-separated list of properties to expand

        Returns:
            Page data dictionary

        Raises:
            ConfluenceError: On API failure
        """
        url = f"{self.api_url}/content/{page_id}"
        params = {"expand": expand}

        resp = self._request("GET", url, params=params)
        return resp.json()

    def get_page_body(self, page_id: str) -> str:
        """
        Get the storage-format (XHTML) body of a Confluence page.

        Args:
            page_id: The Confluence page ID

        Returns:
            The page body as an XHTML string

        Raises:
            ConfluenceError: On API failure
        """
        page = self.get_page(page_id, expand="body.storage")
        return page["body"]["storage"]["value"]

    def get_page_by_title(self, space_key: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Find a page by space key and title.

        Args:
            space_key: The Confluence space key
            title: Page title to search for

        Returns:
            Page data dict or None if not found
        """
        url = f"{self.api_url}/content"
        params = {
            "spaceKey": space_key,
            "title": title,
            "expand": "version,body.storage,space",
        }

        resp = self._request("GET", url, params=params)
        results = resp.json().get("results", [])
        return results[0] if results else None

    def get_attachments(self, page_id: str) -> List[Dict[str, Any]]:
        """
        List all attachments on a page.

        Args:
            page_id: The Confluence page ID

        Returns:
            List of attachment metadata dicts
        """
        url = f"{self.api_url}/content/{page_id}/child/attachment"
        resp = self._request("GET", url)
        return resp.json().get("results", [])

    # ------------------------------------------------------------------ #
    #  CREATE
    # ------------------------------------------------------------------ #

    def create_page(
        self,
        space_key: str,
        title: str,
        body: str,
        parent_id: Optional[str] = None,
        representation: str = "wiki",
    ) -> Dict[str, Any]:
        """
        Create a new Confluence page.

        Args:
            space_key: The Confluence space key
            title: Page title
            body: Page content (wiki markup or storage format)
            parent_id: Optional parent page ID for nesting
            representation: Content format - "wiki" or "storage" (XHTML)

        Returns:
            Created page data
        """
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                representation: {
                    "value": body,
                    "representation": representation,
                }
            },
        }

        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        url = f"{self.api_url}/content"
        resp = self._request("POST", url, json=payload)
        page_data = resp.json()
        logger.info(f"Created page '{title}' (ID: {page_data['id']}) in space {space_key}")
        return page_data

    # ------------------------------------------------------------------ #
    #  UPDATE
    # ------------------------------------------------------------------ #

    def update_page(
        self,
        page_id: str,
        title: str,
        body: str,
        representation: str = "wiki",
        version_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing Confluence page (increments version automatically).

        Args:
            page_id: The page ID to update
            title: New page title (or same title to keep it)
            body: New page content
            representation: Content format - "wiki" or "storage" (XHTML)
            version_comment: Optional comment for the version history

        Returns:
            Updated page data
        """
        # Get current version
        current = self.get_page(page_id, expand="version")
        current_version = current["version"]["number"]

        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "body": {
                representation: {
                    "value": body,
                    "representation": representation,
                }
            },
            "version": {
                "number": current_version + 1,
            },
        }

        if version_comment:
            payload["version"]["message"] = version_comment

        url = f"{self.api_url}/content/{page_id}"
        resp = self._request("PUT", url, json=payload)
        page_data = resp.json()
        logger.info(f"Updated page '{title}' (ID: {page_id}) to version {current_version + 1}")
        return page_data

    def update_page_from_file(
        self,
        page_id: str,
        title: str,
        file_path: str,
        representation: str = "wiki",
        version_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a Confluence page from a file on disk.

        Args:
            page_id: The page ID to update
            title: Page title
            file_path: Path to file containing the page content
            representation: Content format - "wiki" or "storage"
            version_comment: Optional comment for version history

        Returns:
            Updated page data
        """
        content = Path(file_path).read_text(encoding="utf-8")
        return self.update_page(
            page_id=page_id,
            title=title,
            body=content,
            representation=representation,
            version_comment=version_comment,
        )

    # ------------------------------------------------------------------ #
    #  DELETE
    # ------------------------------------------------------------------ #

    def delete_page(self, page_id: str) -> bool:
        """
        Delete a Confluence page.

        Args:
            page_id: The page ID to delete

        Returns:
            True if successful
        """
        url = f"{self.api_url}/content/{page_id}"
        self._request("DELETE", url)
        logger.info(f"Deleted page ID: {page_id}")
        return True

    # ------------------------------------------------------------------ #
    #  ATTACHMENTS
    # ------------------------------------------------------------------ #

    def attach_file(
        self,
        page_id: str,
        file_path: str,
        comment: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attach a file (SVG, PNG, PDF, etc.) to a Confluence page.
        If an attachment with the same name already exists, it is updated.

        Args:
            page_id: Target page ID
            file_path: Path to the file to attach
            comment: Optional comment for the attachment
            filename: Override the filename (defaults to file's basename)

        Returns:
            Attachment metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment file not found: {file_path}")

        fname = filename or path.name
        content_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"

        # SVG special handling
        if fname.endswith(".svg"):
            content_type = "image/svg+xml"

        # Check if attachment already exists
        existing = self._find_attachment(page_id, fname)

        if existing:
            url = f"{self.api_url}/content/{page_id}/child/attachment/{existing['id']}/data"
        else:
            url = f"{self.api_url}/content/{page_id}/child/attachment"

        headers = {"X-Atlassian-Token": "nocheck"}

        files = {
            "file": (fname, path.read_bytes(), content_type),
        }

        data = {}
        if comment:
            data["comment"] = comment

        resp = self._request("POST", url, files=files, data=data, extra_headers=headers)
        result = resp.json()

        action = "Updated" if existing else "Attached"
        logger.info(f"{action} '{fname}' on page {page_id}")

        # Return the attachment result (may be in 'results' list or direct)
        if isinstance(result, dict) and "results" in result:
            return result["results"][0]
        return result

    def attach_multiple_files(
        self,
        page_id: str,
        file_paths: List[str],
        comment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Attach multiple files to a Confluence page.

        Args:
            page_id: Target page ID
            file_paths: List of file paths to attach
            comment: Optional comment applied to all attachments

        Returns:
            List of attachment metadata dicts
        """
        results = []
        for fp in file_paths:
            try:
                result = self.attach_file(page_id, fp, comment=comment)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to attach '{fp}': {e}")
                results.append({"error": str(e), "file": fp})
        return results

    def _find_attachment(self, page_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """Find an existing attachment by filename."""
        attachments = self.get_attachments(page_id)
        for att in attachments:
            if att.get("title") == filename:
                return att
        return None

    # ------------------------------------------------------------------ #
    #  INTERNAL
    # ------------------------------------------------------------------ #

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None,
    ) -> requests.Response:
        """
        Execute an HTTP request with error handling.

        Raises:
            ConfluenceError: On any API or connection error
        """
        headers = {}
        if extra_headers:
            headers.update(extra_headers)

        # Don't set Content-Type for multipart (let requests handle it)
        if json is not None:
            headers["Content-Type"] = "application/json"

        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            body = ""
            if e.response is not None:
                try:
                    body = e.response.json().get("message", e.response.text[:500])
                except Exception:
                    body = e.response.text[:500]
            raise ConfluenceError(f"HTTP {status} on {method} {url}: {body}") from e

        except requests.exceptions.ConnectionError as e:
            raise ConfluenceError(f"Connection error to {self.base_url}: {e}") from e

        except requests.exceptions.Timeout as e:
            raise ConfluenceError(f"Request timed out after {self.timeout}s: {e}") from e

        except requests.exceptions.RequestException as e:
            raise ConfluenceError(f"Request failed: {e}") from e


class ConfluenceError(Exception):
    """Raised when a Confluence API operation fails."""
    pass
