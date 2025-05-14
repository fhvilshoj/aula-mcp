#!/usr/bin/env python
"""
Run the Aula MCP server
"""
import os
import sys
import json
import asyncio
import argparse
import logging

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aula_mcp.mcp_server import AulaMCPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_LOGGER = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Run the Aula MCP server')
    parser.add_argument(
        '--config', '-c',
        required=True,
        help='Path to config file'
    )
    parser.add_argument(
        '--host', '-H',
        default='0.0.0.0',
        help='Host to listen on'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8000,
        help='Port to listen on'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()

async def main():
    """Main function"""
    args = parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load config file
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        _LOGGER.error(f"Failed to load config file: {e}")
        sys.exit(1)
    
    # Create and start server
    server = AulaMCPServer(config)
    
    try:
        _LOGGER.info(f"Starting Aula MCP server on {args.host}:{args.port}")
        await server.start(host=args.host, port=args.port)
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down Aula MCP server")
        await server.stop()
    except Exception as e:
        _LOGGER.error(f"Server error: {e}")
        await server.stop()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main()) 