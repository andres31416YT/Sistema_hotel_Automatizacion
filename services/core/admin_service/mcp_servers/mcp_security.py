"""
MCP Server McpSecurity
Valida seguridad, detecta fraude, bloquea numeros
"""

import logging

logger = logging.getLogger(__name__)

class McpSecurity:
    def __init__(self):
        pass
    
    def validate_message_content(self, message, sender_id):
        """
        Validate message content for security threats
        
        Args:
            message: The message text to validate
            sender_id: Identifier of the sender
            
        Returns:
            Boolean indicating if the message content is valid (True) or should be blocked (False)
        """
        if not message or not isinstance(message, str):
            return False
        
        # Basic validation - block messages with certain dangerous patterns
        blocked_patterns = [
            "spam",
            "fraud", 
            "virus",
            "malware",
            "hack",
            "phishing",
            "<script",
            "javascript:",
            "data:text/html",
            "vbscript:",
            "exe",
            "bat",
            "cmd",
            "powershell",
            "wscript",
            "cscript",
            "regsvr32",
            "mshta",
            "rundll32"
        ]
        
        message_lower = message.lower()
        return not any(pattern in message_lower for pattern in blocked_patterns)
    
    def validate_sender(self, sender_id):
        """
        Validate if a sender is allowed to send messages
        
        Args:
            sender_id: Identifier of the sender (e.g., WhatsApp number)
            
        Returns:
            Boolean indicating if the sender is valid (True) or blocked (False)
        """
        if not sender_id or not isinstance(sender_id, str):
            return False
        
        # Example: block senders with certain patterns
        blocked_patterns = [
            "spam",
            "test",
            "xxx",
            "0000000000",
            "1111111111",
            "2222222222",
            "3333333333",
            "4444444444",
            "5555555555",
            "6666666666",
            "7777777777",
            "8888888888",
            "9999999999"
        ]
        
        return sender_id not in blocked_patterns and len(sender_id) >= 10
    
    def is_sender_blocked(self, sender_id):
        """
        Check if a sender is currently blocked
        
        Args:
            sender_id: Identifier of the sender
            
        Returns:
            Boolean indicating if the sender is blocked (True) or not (False)
        """
        # In a real implementation, this would check a blocklist database
        return not self.validate_sender(sender_id)
    
    def block_sender(self, sender_id, reason="spam_or_fraud"):
        """
        Block a sender from sending messages
        
        Args:
            sender_id: Identifier of the sender to block
            reason: Reason for blocking the sender
            
        Returns:
            Boolean indicating success or failure
        """
        # In a real implementation, this would add the sender to a blocklist database
        print(f"[MCP SECURITY] Blocking sender {sender_id} for reason: {reason}")
        return True
    
    def unblock_sender(self, sender_id):
        """
        Unblock a previously blocked sender
        
        Args:
            sender_id: Identifier of the sender to unblock
            
        Returns:
            Boolean indicating success or failure
        """
        # In a real implementation, this would remove the sender from a blocklist database
        print(f"[MCP SECURITY] Unblocking sender {sender_id}")
        return True