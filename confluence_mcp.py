"""
Confluence Cloud MCP Server

An MCP server for interacting with Confluence Cloud (pages and spaces).
Connects to: https://aofoundation.atlassian.net

Authentication:
- Set CONFLUENCE_EMAIL environment variable (your Atlassian account email)
- Set CONFLUENCE_API_TOKEN environment variable (from https://id.atlassian.com/manage-profile/security/api-tokens)

Usage:
    python confluence_mcp.py                    # stdio transport (default)
    python confluence_mcp.py --transport http   # HTTP transport on port 8000
"""

import os
import json
import base64
from typing import Optional, List
from enum import Enum

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# =============================================================================
# Configuration
# =============================================================================

CONFLUENCE_BASE_URL = "https://aofoundation.atlassian.net"
CONFLUENCE_API_V2 = f"{CONFLUENCE_BASE_URL}/wiki/api/v2"
CONFLUENCE_API_V1 = f"{CONFLUENCE_BASE_URL}/wiki/rest/api"

# Initialize MCP server
mcp = FastMCP("confluence_mcp")


# =============================================================================
# Authentication & HTTP Client
# =============================================================================

def get_auth_headers() -> dict:
    """Get authentication headers for Confluence API."""
    email = os.environ.get("CONFLUENCE_EMAIL")
    token = os.environ.get("CONFLUENCE_API_TOKEN")
    
    if not email or not token:
        raise ValueError(
            "Missing credentials. Set CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN environment variables. "
            "Get your API token from: https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    
    # Basic auth: base64(email:token)
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


async def make_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    json_data: Optional[dict] = None
) -> dict:
    """Make an authenticated request to Confluence API."""
    headers = get_auth_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data
        )
        
        if response.status_code == 401:
            raise ValueError("Authentication failed. Check your CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN.")
        elif response.status_code == 403:
            raise ValueError("Permission denied. Your account may not have access to this resource.")
        elif response.status_code == 404:
            raise ValueError("Resource not found. Check the ID or key provided.")
        elif response.status_code >= 400:
            error_detail = response.text[:500] if response.text else "No details"
            raise ValueError(f"API error {response.status_code}: {error_detail}")
        
        return response.json() if response.text else {}


# =============================================================================
# Response Formatting
# =============================================================================

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


def format_space(space: dict, fmt: ResponseFormat) -> str:
    """Format a space for output."""
    if fmt == ResponseFormat.JSON:
        return json.dumps(space, indent=2)
    
    return f"""## {space.get('name', 'Unknown')}
- **Key**: {space.get('key', 'N/A')}
- **ID**: {space.get('id', 'N/A')}
- **Type**: {space.get('type', 'N/A')}
- **Status**: {space.get('status', 'N/A')}
- **URL**: {CONFLUENCE_BASE_URL}/wiki/spaces/{space.get('key', '')}"""


def format_page(page: dict, fmt: ResponseFormat) -> str:
    """Format a page for output."""
    if fmt == ResponseFormat.JSON:
        return json.dumps(page, indent=2)
    
    space_id = page.get('spaceId', 'N/A')
    page_id = page.get('id', 'N/A')
    
    result = f"""## {page.get('title', 'Untitled')}
- **ID**: {page_id}
- **Space ID**: {space_id}
- **Status**: {page.get('status', 'N/A')}
- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{page_id}"""
    
    # Add body content if present
    body = page.get('body', {})
    if body:
        storage = body.get('storage', {})
        if storage and storage.get('value'):
            result += f"\n\n### Content\n{storage.get('value', '')[:2000]}"
    
    return result


# =============================================================================
# Input Models
# =============================================================================

class ListSpacesInput(BaseModel):
    """Input for listing spaces."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    limit: int = Field(
        default=25,
        description="Maximum number of spaces to return (1-250)",
        ge=1,
        le=250
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor from previous response"
    )
    type: Optional[str] = Field(
        default=None,
        description="Filter by space type: 'global' or 'personal'"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class GetSpaceInput(BaseModel):
    """Input for getting a specific space."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    space_id: str = Field(
        ...,
        description="The ID of the space to retrieve",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class GetSpaceByKeyInput(BaseModel):
    """Input for getting a space by its key."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    space_key: str = Field(
        ...,
        description="The key of the space (e.g., 'TEAM', 'HR')",
        min_length=1,
        max_length=255
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class ListPagesInput(BaseModel):
    """Input for listing pages."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    space_id: Optional[str] = Field(
        default=None,
        description="Filter by space ID. If not provided, lists pages across all spaces."
    )
    limit: int = Field(
        default=25,
        description="Maximum number of pages to return (1-250)",
        ge=1,
        le=250
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor from previous response"
    )
    title: Optional[str] = Field(
        default=None,
        description="Filter by page title (partial match)"
    )
    status: Optional[str] = Field(
        default="current",
        description="Filter by status: 'current', 'trashed', 'draft', 'archived'"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class GetPageInput(BaseModel):
    """Input for getting a specific page."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    page_id: str = Field(
        ...,
        description="The ID of the page to retrieve",
        min_length=1
    )
    include_body: bool = Field(
        default=True,
        description="Include page content in response"
    )
    body_format: str = Field(
        default="storage",
        description="Body format: 'storage' (raw), 'atlas_doc_format', or 'view' (HTML)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class SearchContentInput(BaseModel):
    """Input for searching Confluence content."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    query: str = Field(
        ...,
        description="Search query (CQL or text). Examples: 'type=page AND space=TEAM', 'meeting notes'",
        min_length=1,
        max_length=500
    )
    limit: int = Field(
        default=25,
        description="Maximum number of results (1-100)",
        ge=1,
        le=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class CreatePageInput(BaseModel):
    """Input for creating a new page."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    space_id: str = Field(
        ...,
        description="The ID of the space to create the page in",
        min_length=1
    )
    title: str = Field(
        ...,
        description="Page title",
        min_length=1,
        max_length=255
    )
    body: str = Field(
        default="",
        description="Page content in Confluence storage format (XHTML-based)"
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="Parent page ID (for nested pages)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class UpdatePageInput(BaseModel):
    """Input for updating a page."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    page_id: str = Field(
        ...,
        description="The ID of the page to update",
        min_length=1
    )
    title: Optional[str] = Field(
        default=None,
        description="New page title"
    )
    body: Optional[str] = Field(
        default=None,
        description="New page content in Confluence storage format"
    )
    version_number: int = Field(
        ...,
        description="Current version number of the page (required for optimistic locking)",
        ge=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


class GetPagesInSpaceInput(BaseModel):
    """Input for getting pages in a specific space."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    space_id: str = Field(
        ...,
        description="The ID of the space",
        min_length=1
    )
    limit: int = Field(
        default=25,
        description="Maximum number of pages to return (1-250)",
        ge=1,
        le=250
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor from previous response"
    )
    depth: Optional[str] = Field(
        default="all",
        description="Depth of pages: 'all' or 'root' (top-level only)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'"
    )


# =============================================================================
# Tools - Spaces
# =============================================================================

@mcp.tool(
    name="confluence_list_spaces",
    annotations={
        "title": "List Confluence Spaces",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_list_spaces(params: ListSpacesInput) -> str:
    """List all Confluence spaces accessible to the authenticated user.
    
    Returns spaces with their keys, names, types, and URLs.
    Use the cursor parameter for pagination through large result sets.
    
    Args:
        params: ListSpacesInput containing:
            - limit: Max results (1-250, default 25)
            - cursor: Pagination cursor
            - type: Filter by 'global' or 'personal'
            - response_format: 'markdown' or 'json'
    
    Returns:
        Formatted list of spaces with pagination info
    """
    query_params = {"limit": params.limit}
    
    if params.cursor:
        query_params["cursor"] = params.cursor
    if params.type:
        query_params["type"] = params.type
    
    data = await make_request("GET", f"{CONFLUENCE_API_V2}/spaces", params=query_params)
    
    spaces = data.get("results", [])
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    if not spaces:
        return "No spaces found."
    
    result = f"# Confluence Spaces ({len(spaces)} results)\n\n"
    for space in spaces:
        result += format_space(space, params.response_format) + "\n\n---\n\n"
    
    # Pagination info
    links = data.get("_links", {})
    if links.get("next"):
        result += f"\n**More results available.** Use cursor to get next page."
    
    return result


@mcp.tool(
    name="confluence_get_space",
    annotations={
        "title": "Get Confluence Space by ID",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_get_space(params: GetSpaceInput) -> str:
    """Get details of a specific Confluence space by its ID.
    
    Args:
        params: GetSpaceInput containing:
            - space_id: The space ID
            - response_format: 'markdown' or 'json'
    
    Returns:
        Space details including name, key, type, and status
    """
    data = await make_request("GET", f"{CONFLUENCE_API_V2}/spaces/{params.space_id}")
    return format_space(data, params.response_format)


@mcp.tool(
    name="confluence_get_space_by_key",
    annotations={
        "title": "Get Confluence Space by Key",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_get_space_by_key(params: GetSpaceByKeyInput) -> str:
    """Get details of a Confluence space by its key (e.g., 'TEAM', 'HR').
    
    Space keys are the short identifiers shown in URLs like /wiki/spaces/TEAM/
    
    Args:
        params: GetSpaceByKeyInput containing:
            - space_key: The space key (e.g., 'TEAM')
            - response_format: 'markdown' or 'json'
    
    Returns:
        Space details including ID, name, type, and status
    """
    # V2 API requires ID, so we search for the space by key
    query_params = {"keys": params.space_key, "limit": 1}
    data = await make_request("GET", f"{CONFLUENCE_API_V2}/spaces", params=query_params)
    
    spaces = data.get("results", [])
    if not spaces:
        return f"Space with key '{params.space_key}' not found."
    
    return format_space(spaces[0], params.response_format)


# =============================================================================
# Tools - Pages
# =============================================================================

@mcp.tool(
    name="confluence_list_pages",
    annotations={
        "title": "List Confluence Pages",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_list_pages(params: ListPagesInput) -> str:
    """List Confluence pages, optionally filtered by space.
    
    Args:
        params: ListPagesInput containing:
            - space_id: Optional space ID filter
            - limit: Max results (1-250, default 25)
            - cursor: Pagination cursor
            - title: Filter by title (partial match)
            - status: 'current', 'trashed', 'draft', or 'archived'
            - response_format: 'markdown' or 'json'
    
    Returns:
        Formatted list of pages with titles, IDs, and URLs
    """
    query_params = {"limit": params.limit}
    
    if params.cursor:
        query_params["cursor"] = params.cursor
    if params.title:
        query_params["title"] = params.title
    if params.status:
        query_params["status"] = params.status
    
    # Use space-specific endpoint if space_id provided
    if params.space_id:
        url = f"{CONFLUENCE_API_V2}/spaces/{params.space_id}/pages"
    else:
        url = f"{CONFLUENCE_API_V2}/pages"
    
    data = await make_request("GET", url, params=query_params)
    
    pages = data.get("results", [])
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    if not pages:
        return "No pages found."
    
    result = f"# Confluence Pages ({len(pages)} results)\n\n"
    for page in pages:
        result += f"### {page.get('title', 'Untitled')}\n"
        result += f"- **ID**: {page.get('id', 'N/A')}\n"
        result += f"- **Space ID**: {page.get('spaceId', 'N/A')}\n"
        result += f"- **Status**: {page.get('status', 'N/A')}\n"
        result += f"- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{page.get('id', '')}\n\n"
    
    # Pagination info
    links = data.get("_links", {})
    if links.get("next"):
        result += "\n**More results available.** Use cursor for next page."
    
    return result


@mcp.tool(
    name="confluence_get_page",
    annotations={
        "title": "Get Confluence Page",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_get_page(params: GetPageInput) -> str:
    """Get a specific Confluence page by ID, optionally including its content.
    
    Args:
        params: GetPageInput containing:
            - page_id: The page ID
            - include_body: Include page content (default True)
            - body_format: 'storage', 'atlas_doc_format', or 'view'
            - response_format: 'markdown' or 'json'
    
    Returns:
        Page details including title, status, and optionally content
    """
    query_params = {}
    if params.include_body:
        query_params["body-format"] = params.body_format
    
    data = await make_request(
        "GET", 
        f"{CONFLUENCE_API_V2}/pages/{params.page_id}",
        params=query_params
    )
    
    return format_page(data, params.response_format)


@mcp.tool(
    name="confluence_get_pages_in_space",
    annotations={
        "title": "Get Pages in Space",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_get_pages_in_space(params: GetPagesInSpaceInput) -> str:
    """Get all pages within a specific Confluence space.
    
    Args:
        params: GetPagesInSpaceInput containing:
            - space_id: The space ID
            - limit: Max results (1-250, default 25)
            - cursor: Pagination cursor
            - depth: 'all' or 'root' (top-level only)
            - response_format: 'markdown' or 'json'
    
    Returns:
        List of pages in the space
    """
    query_params = {"limit": params.limit}
    
    if params.cursor:
        query_params["cursor"] = params.cursor
    if params.depth:
        query_params["depth"] = params.depth
    
    data = await make_request(
        "GET",
        f"{CONFLUENCE_API_V2}/spaces/{params.space_id}/pages",
        params=query_params
    )
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    pages = data.get("results", [])
    if not pages:
        return f"No pages found in space {params.space_id}."
    
    result = f"# Pages in Space ({len(pages)} results)\n\n"
    for page in pages:
        result += f"### {page.get('title', 'Untitled')}\n"
        result += f"- **ID**: {page.get('id', 'N/A')}\n"
        result += f"- **Status**: {page.get('status', 'N/A')}\n"
        result += f"- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{page.get('id', '')}\n\n"
    
    return result


@mcp.tool(
    name="confluence_search",
    annotations={
        "title": "Search Confluence",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_search(params: SearchContentInput) -> str:
    """Search Confluence content using CQL (Confluence Query Language) or text.
    
    CQL Examples:
    - 'type=page AND space=TEAM' - Pages in TEAM space
    - 'title ~ "meeting"' - Pages with 'meeting' in title
    - 'creator = currentUser()' - Content created by you
    - 'lastModified > now("-7d")' - Modified in last 7 days
    
    Args:
        params: SearchContentInput containing:
            - query: CQL query or search text
            - limit: Max results (1-100, default 25)
            - response_format: 'markdown' or 'json'
    
    Returns:
        Search results with titles, types, and URLs
    """
    # Use v1 API for CQL search (v2 doesn't have full CQL support yet)
    query_params = {
        "cql": params.query,
        "limit": params.limit
    }
    
    data = await make_request(
        "GET",
        f"{CONFLUENCE_API_V1}/content/search",
        params=query_params
    )
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    results = data.get("results", [])
    if not results:
        return f"No results found for query: {params.query}"
    
    output = f"# Search Results ({len(results)} found)\n\n"
    output += f"**Query**: `{params.query}`\n\n"
    
    for item in results:
        title = item.get("title", "Untitled")
        content_type = item.get("type", "unknown")
        content_id = item.get("id", "")
        space = item.get("space", {})
        space_key = space.get("key", "N/A") if space else "N/A"
        
        output += f"### {title}\n"
        output += f"- **Type**: {content_type}\n"
        output += f"- **ID**: {content_id}\n"
        output += f"- **Space**: {space_key}\n"
        output += f"- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{content_id}\n\n"
    
    return output


@mcp.tool(
    name="confluence_create_page",
    annotations={
        "title": "Create Confluence Page",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def confluence_create_page(params: CreatePageInput) -> str:
    """Create a new page in a Confluence space.
    
    The body should be in Confluence storage format (XHTML-based).
    Example: '<p>Hello <strong>world</strong></p>'
    
    Args:
        params: CreatePageInput containing:
            - space_id: Target space ID
            - title: Page title
            - body: Content in storage format
            - parent_id: Optional parent page ID
            - response_format: 'markdown' or 'json'
    
    Returns:
        Created page details including ID and URL
    """
    payload = {
        "spaceId": params.space_id,
        "status": "current",
        "title": params.title,
        "body": {
            "representation": "storage",
            "value": params.body
        }
    }
    
    if params.parent_id:
        payload["parentId"] = params.parent_id
    
    data = await make_request("POST", f"{CONFLUENCE_API_V2}/pages", json_data=payload)
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    return f"""# Page Created Successfully

- **Title**: {data.get('title', 'N/A')}
- **ID**: {data.get('id', 'N/A')}
- **Space ID**: {data.get('spaceId', 'N/A')}
- **Status**: {data.get('status', 'N/A')}
- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{data.get('id', '')}"""


@mcp.tool(
    name="confluence_update_page",
    annotations={
        "title": "Update Confluence Page",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def confluence_update_page(params: UpdatePageInput) -> str:
    """Update an existing Confluence page.
    
    Requires the current version number for optimistic locking.
    Get the version from confluence_get_page first.
    
    Args:
        params: UpdatePageInput containing:
            - page_id: Page ID to update
            - title: New title (optional)
            - body: New content (optional)
            - version_number: Current version (required)
            - response_format: 'markdown' or 'json'
    
    Returns:
        Updated page details
    """
    # First get current page to get spaceId and current values
    current = await make_request("GET", f"{CONFLUENCE_API_V2}/pages/{params.page_id}")
    
    payload = {
        "id": params.page_id,
        "status": "current",
        "title": params.title if params.title else current.get("title"),
        "spaceId": current.get("spaceId"),
        "version": {
            "number": params.version_number + 1,
            "message": "Updated via MCP"
        }
    }
    
    if params.body is not None:
        payload["body"] = {
            "representation": "storage",
            "value": params.body
        }
    
    data = await make_request("PUT", f"{CONFLUENCE_API_V2}/pages/{params.page_id}", json_data=payload)
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(data, indent=2)
    
    return f"""# Page Updated Successfully

- **Title**: {data.get('title', 'N/A')}
- **ID**: {data.get('id', 'N/A')}
- **Version**: {data.get('version', {}).get('number', 'N/A')}
- **URL**: {CONFLUENCE_BASE_URL}/wiki/pages/{data.get('id', '')}"""


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Check for transport argument
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]
    
    if transport == "http":
        mcp.run(transport="streamable_http", port=8000)
    else:
        mcp.run()
