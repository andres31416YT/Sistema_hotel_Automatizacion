"""
AI Agent GuardAgent - Responsible for security
Uses McpSecurity to validate security, detect fraud, block numbers.
"""

from core.prompts.admin_service.agents import PROMPT_GUARD  # noqa

import logging

logger = logging.getLogger(__name__)


class GuardAgent:
    ROLE = PROMPT_GUARD

    def __init__(self, mcp_servers):
        """
        Initialize the GuardAgent (Admin Service).
        """
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.security_server = mcp_servers.get('security')
    
    def validate_message(self, message, sender_id):
        """
        Validate a message for security threats.
        
        Args:
            message: The message text to validate
            sender_id: Identifier of the sender
            
        Returns:
            Boolean indicating if the message is valid (True) or should be blocked (False)
        """
        if not self.security_server:
            # If security server is not available, allow the message through
            # In production, you might want to be more restrictive
            return True
        
        # Check for spam, fraud, or malicious content
        is_valid = self.security_server.validate_message_content(message, sender_id)
        
        # Check if the sender is blocked
        is_blocked = self.security_server.is_sender_blocked(sender_id)
        
        return is_valid and not is_blocked