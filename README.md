# Aula MCP

A Model Context Protocol (MCP) implementation for the Aula platform, providing programmatic access to school schedules, messages, and other information from Aula.

## Features

- **Authentication**: Secure login to Aula using UniLogin credentials
- **Calendar**: Retrieve and parse calendar/school schedule events
- **Messages**: Check for unread messages
- **Presence Data**: Access presence information for children
- **MCP Server**: FastMCP server implementation for easy integration
- **Pydantic Models**: Strong typing and validation for all data structures

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/aula-mcp.git
cd aula-mcp

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a configuration file with your Aula credentials:

```json
{
    "username": "your_unilogin_username",
    "password": "your_unilogin_password",
    "schoolschedule": true,
    "ugeplan": true,
    "mu_opgaver": true
}
```

## Usage

### Running the MCP Server

```bash
python -m aula_mcp.scripts.run_server --config /path/to/config.json
```

Optional parameters:
- `--host` / `-H`: Host to listen on (default: 0.0.0.0)
- `--port` / `-p`: Port to listen on (default: 8000)
- `--debug` / `-d`: Enable debug logging

### Using the MCP Client

```python
import asyncio
from fastmcp import Client

async def main():
    # Connect to the MCP server
    client = Client("http://localhost:8000/sse")
    
    async with client:
        # Login
        await client.call_tool("login")
        
        # Get children
        children = await client.call_tool("get_children")
        
        # Get calendar events for the first child
        child_id = children[0]["id"]
        events = await client.call_tool("get_calendar_events", {
            "child_id": child_id,
            "days": 7
        })
        
        # Display events
        for event in events:
            print(f"{event['start']}: {event['summary']}")

if __name__ == "__main__":
    asyncio.run(main())
```

See the `examples` directory for more detailed examples.

## Available Tools

The MCP server provides the following tools:

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `login` | Log in to Aula | None |
| `get_children` | Get list of children | None |
| `get_child_by_id` | Get child data by ID | `child_id` |
| `get_calendar_events` | Get calendar events | `child_id`, `days` (optional) |
| `get_events_for_date_range` | Get events for date range | `child_id`, `start_date`, `end_date`, `days` (optional) |
| `get_unread_messages` | Get unread messages | None |
| `get_presence_data` | Get presence data | `child_id` |
| `refresh_data` | Refresh all data | None |

## Library Usage

You can also use the library directly without the MCP server:

```python
from aula_mcp import AulaClient, AulaCalendar, AulaConfig

# Create config
config = AulaConfig(
    username="your_username",
    password="your_password",
    schoolschedule=True
)

# Initialize client
client = AulaClient(config)
client.login()

# Use calendar functionality
calendar = AulaCalendar(client)
events = calendar.get_calendar_events("child_id")

# Format events
formatted_events = calendar.format_calendar_events(events)
```

## Dependencies

- `fastmcp`: For MCP server implementation
- `pydantic`: For data validation
- `requests`: For HTTP communication
- `beautifulsoup4`: For HTML parsing
- `pytz`: For timezone handling

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

Based on the Aula Home Assistant integration (https://github.com/scaarup/aula).
