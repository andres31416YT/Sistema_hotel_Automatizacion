"""
MCP Server McpWhatsApp
Consulta información de contacto e historial de WhatsApp
"""

class McpWhatsapp:
    def __init__(self):
        pass
    
    def get_contact_info(self, sender_id):
        """
        Get contact information for a WhatsApp user
        
        Args:
            sender_id: The WhatsApp number of the user
            
        Returns:
            Dictionary with contact information
        """
        # In a real implementation, this would query WhatsApp Business API
        # or a local cache/database of contact information
        return {
            "name": f"Usuario {sender_id[-4:]}" if len(sender_id) >= 4 else "Usuario",
            "profile_pic": None,
            "status": "disponible",
            "verified": False
        }
    
    def get_message_history(self, sender_id, limit=50):
        """
        Get message history for a WhatsApp user
        
        Args:
            sender_id: The WhatsApp number of the user
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message objects
        """
        # In a real implementation, this would query message history
        # from WhatsApp Business API or local storage
        return [
            {
                "id": f"msg_{i}",
                "from": sender_id,
                "timestamp": "2026-05-16T10:00:00Z",
                "content": f"Mensaje de ejemplo {i}",
                "direction": "inbound"
            }
            for i in range(1, min(limit, 6))  # Return up to 5 messages for example
        ]