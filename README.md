# Confluence MCP Server

An MCP (Model Context Protocol) server for interacting with Confluence Cloud pages and spaces.

**Configured for**: https://aofoundation.atlassian.net

## Features

- **Spaces**: List, get by ID, get by key
- **Pages**: List, get, create, update, search
- **Search**: Full CQL (Confluence Query Language) support
- **Output formats**: Markdown (human-readable) or JSON

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name (e.g., "MCP Server")
4. Copy the token (you won't see it again!)

### 3. Set Environment Variables

```bash
export CONFLUENCE_EMAIL="your-email@example.com"
export CONFLUENCE_API_TOKEN="your-api-token-here"
```

### 4. Run the Server

```bash
python confluence_mcp.py
```

## Available Tools

| Tool | Description |
|------|-------------|
| `confluence_list_spaces` | List all accessible spaces |
| `confluence_get_space` | Get space by ID |
| `confluence_get_space_by_key` | Get space by key (e.g., 'TEAM') |
| `confluence_list_pages` | List pages (optionally by space) |
| `confluence_get_page` | Get page by ID with content |
| `confluence_search` | Search using CQL |
| `confluence_create_page` | Create a new page |
| `confluence_update_page` | Update existing page |
