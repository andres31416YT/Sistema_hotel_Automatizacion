"""
AI Agent QueryAgent - Consults the database
Uses McpDatabase to read and write data.
"""

class QueryAgent:
    ROLE = "Consulta disponibilidad de habitaciones, precios, tipos de habitación "
    ROLE += "y datos de reservas para responder consultas de huéspedes."

    def __init__(self, mcp_servers):
        """
        Initialize the QueryAgent.
        
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
            
        return self.database_server.get_guest_profile(guest_id)