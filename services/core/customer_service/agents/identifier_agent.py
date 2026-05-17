"""
AI Agent Identifier - Identifies who sent the message
Uses McpWhatsapp and McpDatabase to get sender information.
"""

class IdentifierAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the Identifier agent.
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.whatsapp_server = mcp_servers.get('whatsapp')
        self.database_server = mcp_servers.get('database')
    
    def identify(self, sender_id):
        """
        Identify the sender and get their context.
        
        Args:
            sender_id: Identifier of the sender (e.g., WhatsApp number)
            
        Returns:
            Dictionary with sender context information
        """
        # Get contact info from WhatsApp MCP server
        contact_info = {}
        if self.whatsapp_server:
            contact_info = self.whatsapp_server.get_contact_info(sender_id)
        
        # Get or create user profile from database
        user_profile = {}
        if self.database_server:
            user_profile = self.database_server.get_or_create_user_profile(sender_id, contact_info)
        
        # Combine information
        context = {
            "user_id": sender_id,
            "is_admin": user_profile.get("is_admin", False),
            "name": contact_info.get("name", user_profile.get("name", "Usuario")),
            "phone_number": sender_id,
            "profile": user_profile,
            "contact_info": contact_info
        }
        
        return context