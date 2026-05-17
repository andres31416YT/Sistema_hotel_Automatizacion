"""
AI Agent WriterAgent - Redacts messages
Uses McpMessenger to send messages via WhatsApp.
"""

import logging

logger = logging.getLogger(__name__)

class WriterAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the WriterAgent.
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.messenger_server = mcp_servers.get('messenger')
    
    def redact_message(self, message):
        """
        Format and prepare a message for sending.
        
        Args:
            message: The message text to format
            
        Returns:
            Formatted message ready for sending
        """
        # Basic message formatting
        formatted_message = message.strip()
        
        # Ensure message is not too long for WhatsApp
        if len(formatted_message) > 4096:  # WhatsApp message limit
            formatted_message = formatted_message[:4090] + "..."
        
        return formatted_message
    
    def send_message(self, recipient_id, message):
        """
        Send a message to a recipient via WhatsApp.
        
        Args:
            recipient_id: The recipient's identifier (e.g., WhatsApp number)
            message: The message to send
            
        Returns:
            Boolean indicating success or failure
        """
        if not self.messenger_server:
            logger.error("McpMessenger server not available")
            return False
        
        formatted_message = self.redact_message(message)
        return self.messenger_server.send_message(recipient_id, formatted_message)