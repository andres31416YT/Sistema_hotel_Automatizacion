"""
AI Agent QueryAgent - Consults the database
Uses McpDatabase to read and write data.
"""

import logging
from core.prompts.admin_service.agents import PROMPT_QUERY  # noqa

logger = logging.getLogger(__name__)


class QueryAgent:
    ROLE = PROMPT_QUERY

    def __init__(self, mcp_servers):
        """
        Initialize the QueryAgent (Admin Service).

        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.database_server = mcp_servers.get('database')
    
    def check_availability(self, fecha, tipo_habitacion, huespedes):
        """
        Check room availability.
        
        Args:
            fecha: Date for check-in
            tipo_habitacion: Type of room
            huespedes: Number of guests
            
        Returns:
            Availability information
        """
        if not self.database_server:
            return "Error: No se pudo acceder a la base de datos"
        
        # Query the database for availability
        result = self.database_server.query_availability(
            fecha, tipo_habitacion, huespedes
        )
        
        return result
    
    def get_guest_info(self, guest_id):
        """
        Get information about a guest.
        
        Args:
            guest_id: Identifier of the guest
            
        Returns:
            Guest information
        """
        if not self.database_server:
            return None
            
        try:
            # Usar execute_sql para obtener información del cliente
            result = self.database_server.execute_sql(
                "SELECT id, name, whatsapp_number, doc_identidad, created_at "
                "FROM clients WHERE whatsapp_number = $1 OR id::text = $1",
                [str(guest_id)]
            )
            if result.get("ok") and result.get("rows"):
                return result["rows"][0]
            return None
        except Exception as e:
            logger.warning(f"[QueryAgent] get_guest_info error: {e}")
            return None