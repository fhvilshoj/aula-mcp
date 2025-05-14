#!/usr/bin/env python
"""
Example client for Aula MCP server
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
import argparse

from fastmcp import Client
from mcp_server import create_server

async def list_available_tools(client):
    """List all available tools from the server"""
    try:
        tools = await client.list_tools()
        print("\nAvailable tools:")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")
        return tools
    except Exception as e:
        print(f"Error listing tools: {e}")
        return None

async def login_to_aula(client):
    """Login to Aula service"""
    try:
        print("\nLogging in...")
        login_result = await client.call_tool("login")
        print(f"Login result: {login_result}")
        
        success = json.loads(login_result[0].text).get("success")
        if not success:
            print("Login failed. Check your credentials.")
        return success
    except Exception as e:
        print(f"Error during login: {e}")
        return False

async def get_children_data(client):
    """Get information about children"""
    try:
        print("\nGetting children...")
        children_result = await client.call_tool("get_children")
        children = json.loads(children_result[0].text)
        
        if not children:
            print("No children found.")
            return None
        
        print(f"Found {len(children)} children:")
        for child in children:
            print(f"- {child['name']} (ID: {child['id']})")
        
        return children
    except json.JSONDecodeError as e:
        print(f"Error parsing children data: {e}")
        return None
    except Exception as e:
        print(f"Error getting children data: {e}")
        # If we get validation errors like the one about profilePicture, 
        # we still want to continue as we might have partial data
        if "sender.profilePicture" in str(e) and "validation error" in str(e):
            print("Continuing despite validation error in profile picture data")
            # Try to extract children from the error message or response
            try:
                # This is a simple approach - in a real app, you'd use a more robust method
                # to extract the children data when there's a validation error
                return children_result[0].text  # Return raw text for processing in main
            except:
                return None
        return None

async def get_calendar_events(client, child_id, child_name, days=7):
    """Get calendar events for a specific child"""
    try:
        print(f"\nGetting calendar events for {child_name}...")
        
        events_result = await client.call_tool("get_calendar_events", {
            "child_id": child_id,
            "days": days
        })
        
        if events_result:
            events = json.loads(events_result[0].text)
            print(f"Found {len(events)} events in the next {days} days:")

            for event in events:
                start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                formatted_time = start_time.strftime("%Y-%m-%d %H:%M")
                print(f"- {formatted_time}: {event['summary']}")
                if event.get("location"):
                    print(f"  Location: {event['location']}")
            return events
        else:
            print("No events found.")
            return None
    except json.JSONDecodeError as e:
        print(f"Error parsing calendar events: {e}")
        return None
    except Exception as e:
        print(f"Error getting calendar events: {e}")
        return None

async def get_events_for_date_range(client, child_id, start_date=None, end_date=None, days=14):
    """Get events for a specific date range"""
    try:
        print("\nGetting events for a specific date range...")
        
        if start_date is None:
            start_date = datetime.now()
        if end_date is None:
            end_date = start_date + timedelta(days=days)
        
        range_result = await client.call_tool("get_events_for_date_range", {
            "child_id": child_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        })
        
        if range_result:
            range_events = json.loads(range_result[0].text)
            print(f"Found {len(range_events)} events in the specified date range")
            return range_events
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing date range events: {e}")
        return None
    except Exception as e:
        print(f"Error getting events for date range: {e}")
        return None

async def get_unread_messages(client):
    """Get unread messages"""
    try:
        print("\nGetting messages...")
        messages_result = await client.call_tool("get_unread_messages")
        if not messages_result:
            print("Failed to get message information.")
            return None
            
        result = json.loads(messages_result[0].text)
        
        unread_count = result.get("count", 0)
        messages = result.get("messages", [])
        
        if unread_count > 0:
            print(f"You have {unread_count} unread messages")
        else:
            print("You have no unread messages")
            
        if messages:
            print(f"\nShowing {len(messages)} recent messages:")
            
            for i, message_data in enumerate(messages, 1):
                is_unread = message_data.get("is_unread", False)
                print(f"\n{i}. {message_data.get('subject', 'No subject')} {'(UNREAD)' if is_unread else ''}")
                
                # Check if message requires MitID
                if message_data.get("requires_mitid"):
                    print("   Message requires MitID authentication to view")
                    print(f"   Text: {message_data.get('text', 'No content')}")
                # Check if we have the full message object
                elif message_data.get("message"):
                    message = message_data["message"]
                    print(f"   From: {message_data.get('sender', 'Unknown sender')}")
                    
                    # Format the date if available
                    if "send_date_time" in message:
                        try:
                            send_date = message["send_date_time"]
                            # Handle ISO format or datetime object
                            if isinstance(send_date, str):
                                send_datetime = datetime.fromisoformat(send_date.replace("Z", "+00:00"))
                                formatted_date = send_datetime.strftime("%Y-%m-%d %H:%M")
                                print(f"   Sent: {formatted_date}")
                        except (ValueError, TypeError):
                            print(f"   Sent: {message.get('send_date_time', 'Unknown date')}")
                    
                    print(f"   ID: {message.get('id', 'Unknown ID')}")
                    
                    # Display a preview of the content
                    content = message_data.get('text', 'No content')
                    if len(content) > 100:
                        content = content[:97] + "..."
                    print(f"   Preview: {content}")
                    
                    # Show additional message details if available
                    if message.get("has_attachments"):
                        print("   Has attachments: Yes")
                    
                    # Show sender details
                    if "sender" in message and isinstance(message["sender"], dict):
                        sender = message["sender"]
                        if sender.get("metadata"):
                            print(f"   Sender role: {sender.get('metadata')}")
                # Fallback for basic message info
                else:
                    print(f"   From: {message_data.get('sender', 'Unknown sender')}")
                    print(f"   Preview: {message_data.get('text', 'No content')[:100]}")
        else:
            print("No messages found.")
        
        return result
    except json.JSONDecodeError as e:
        print(f"Error parsing messages data: {e}")
        return None
    except Exception as e:
        print(f"Error getting messages: {e}")
        return None

async def get_presence_data(client, child_id, child_name):
    """Get presence data for a child"""
    try:
        print(f"\nGetting presence data for {child_name}...")
        presence_result = await client.call_tool("get_presence_data", {
            "child_id": child_id
        })
        
        if presence_result:
            presence = json.loads(presence_result[0].text)
            if presence.get("has_presence"):
                print("Child has presence data available")
                print(f"Overview: {presence.get('overview', 'No overview available')}")
            return presence
        else:
            print("No presence data available for this child")
            return None
    except json.JSONDecodeError as e:
        print(f"Error parsing presence data: {e}")
        return None
    except Exception as e:
        print(f"Error getting presence data: {e}")
        return None

async def get_gallery_items(client, limit=5):
    """Get gallery items"""
    try:
        print("\nGetting gallery items...")
        gallery_result = await client.call_tool("get_gallery_items", {
            "limit": limit
        })
        
        if not gallery_result:
            print("Failed to get gallery items.")
            return None
            
        gallery_items = json.loads(gallery_result[0].text)
        
        if gallery_items:
            print(f"Found {len(gallery_items)} gallery items:")
            
            for i, item in enumerate(gallery_items, 1):
                print(f"\n{i}. {item.get('title', 'Untitled image')}")
                
                # Display creation date if available
                if item.get('created'):
                    try:
                        # Format creation date
                        created_date = datetime.fromisoformat(item['created'].replace('Z', '+00:00'))
                        formatted_date = created_date.strftime("%Y-%m-%d %H:%M")
                        print(f"   Date: {formatted_date}")
                    except (ValueError, TypeError):
                        print(f"   Date: {item.get('created', 'Unknown')}")
                
                # Show description if available
                if item.get('description'):
                    description = item['description']
                    if len(description) > 100:
                        description = description[:97] + "..."
                    print(f"   Description: {description}")
                
                # Show URLs
                print(f"   Image URL: {item.get('url', 'No URL')}")
                print(f"   Thumbnail: {item.get('thumbnailUrl', 'No thumbnail')}")
        else:
            print("No gallery items found.")
        
        return gallery_items
    except json.JSONDecodeError as e:
        print(f"Error parsing gallery data: {e}")
        return None
    except Exception as e:
        if "validating gallery data" in str(e) and "AulaGalleryResponse" in str(e):
            print("Gallery data format error - likely empty gallery or format change.")
            return [] 
        print(f"Error getting gallery items: {e}")
        return None

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Aula MCP client example')
    parser.add_argument('--server', '-s', default='http://localhost:8000/sse',
                        help='Server URL (default: http://localhost:8000/sse)')
    parser.add_argument('--skip-tools', action='store_true', help='Skip listing available tools')
    parser.add_argument('--skip-children', action='store_true', help='Skip getting children data')
    parser.add_argument('--skip-calendar', action='store_true', help='Skip getting calendar events')
    parser.add_argument('--skip-date-range', action='store_true', help='Skip getting events for date range')
    parser.add_argument('--skip-messages', action='store_true', help='Skip getting messages')
    parser.add_argument('--skip-presence', action='store_true', help='Skip getting presence data')
    parser.add_argument('--skip-gallery', action='store_true', help='Skip getting gallery items')
    args = parser.parse_args()

    try:
        server = create_server("./examples/config.json")
        
        # Initialize client
        client = Client(transport=server.server)
        
        # Use the client
        async with client:
            print("Connected to Aula MCP server")
            
            # Get available tools
            if not args.skip_tools:
                await list_available_tools(client)
            
            # Login
            if not await login_to_aula(client):
                return
            
            # Get children
            if args.skip_children:
                return
                
            children = await get_children_data(client)
            if not children:
                return
            
            # Check if the children data is a string (raw response due to validation error)
            if isinstance(children, str):
                try:
                    # Try to parse it despite the validation error
                    children = json.loads(children)
                except:
                    print("Unable to process children data due to validation errors")
                    return
            
            # Use the first child for subsequent operations
            if not children or len(children) == 0:
                print("No children data available for further operations")
                return
                
            child_id = str(children[0]["id"])
            child_name = children[0]["name"]
            
            # Get calendar events
            if not args.skip_calendar:
                await get_calendar_events(client, child_id, child_name)
            
            # Get events for a specific date range
            if not args.skip_date_range:
                await get_events_for_date_range(client, child_id)
            
            # Get unread messages
            if not args.skip_messages:
                await get_unread_messages(client)
            
            # Get presence data
            if not args.skip_presence:
                await get_presence_data(client, child_id, child_name)
            
            # Get gallery items
            if not args.skip_gallery:
                await get_gallery_items(client)
                
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

if __name__ == "__main__":
    asyncio.run(main()) 