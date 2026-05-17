"""
AI Agent Nexus - Orchestrator
Coordinates between different agents to process requests.
"""

class NexusAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the Nexus agent with access to MCP servers.
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.identifier_agent = IdentifierAgent(mcp_servers)
        self.query_agent = QueryAgent(mcp_servers)
        self.knowledge_agent = KnowledgeAgent(mcp_servers)
        self.writer_agent = WriterAgent(mcp_servers)
        self.guard_agent = GuardAgent(mcp_servers)
        self.payment_agent = PaymentAgent(mcp_servers)
    
    def process_request(self, message, sender_id):
        """
        Process an incoming request through the agent pipeline.
        
        Args:
            message: The incoming message text
            sender_id: Identifier of the sender (e.g., WhatsApp number)
            
        Returns:
            Response to be sent back to the user
        """
        # Step 1: Validate security
        if not self.guard_agent.validate_message(message, sender_id):
            return "Lo siento, no puedo procesar este mensaje por razones de seguridad."
        
        # Step 2: Identify the sender and get context
        sender_context = self.identifier_agent.identify(sender_id)
        
        # Step 3: Determine intent and extract entities
        # This would typically involve NLP processing, simplified here
        intent, entities = self._determine_intent_and_entities(message, sender_context)
        
        # Step 4: Route to appropriate handler based on intent
        if intent == "check_availability":
            return self._handle_availability_check(entities, sender_context)
        elif intent == "make_payment":
            return self._handle_payment_request(entities, sender_context)
        elif intent == "query_info":
            return self._handle_info_query(entities, sender_context)
        elif intent == "admin_request" and sender_context.get('is_admin'):
            return self._handle_admin_request(entities, sender_context)
        else:
            return self.writer_agent.redact_message(
                "Lo siento, no entendí su solicitud. ¿Puede intentar de nuevo?"
            )
    
    def _determine_intent_and_entities(self, message, sender_context):
        """
        Determine the intent and extract entities from the message.
        In a real implementation, this would use NLP models.
        """
        # Simplified intent detection
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["disponible", "disponibilidad", "habitación", "room"]):
            return "check_availability", self._extract_booking_entities(message)
        elif any(word in message_lower for word in ["pago", "pagar", "pago", "link de pago"]):
            return "make_payment", self._extract_payment_entities(message)
        elif any(word in message_lower for word in ["información", "info", "detalles", "horario"]):
            return "query_info", self._extract_info_entities(message)
        elif any(word in message_lower for word in ["admin", "administrador", "gestión", "reportes"]):
            return "admin_request", {}
        else:
            return "general_inquiry", {}
    
    def _extract_booking_entities(self, message):
        """Extract booking-related entities from message."""
        # Simplified entity extraction
        return {
            "fecha": "fecha_no_especificada",
            "tipo": "tipo_no_especificado",
            "huespedes": "1"
        }
    
    def _extract_payment_entities(self, message):
        """Extract payment-related entities from message."""
        return {
            "monto": "monto_no_especificado",
            "referencia": "referencia_no_especificada"
        }
    
    def _extract_info_entities(self, message):
        """Extract info-related entities from message."""
        return {
            "tema": "tema_no_especificado"
        }
    
    def _handle_availability_check(self, entities, sender_context):
        """Handle availability check requests."""
        # Query the database for availability
        availability_result = self.query_agent.check_availability(
            entities.get("fecha"),
            entities.get("tipo"),
            entities.get("huespedes")
        )
        
        # Format the response
        return self.writer_agent.redact_message(
            f"Disponibilidad para {entities.get('tipo')} el {entities.get('fecha')}: "
            f"{availability_result}"
        )
    
    def _handle_payment_request(self, entities, sender_context):
        """Handle payment requests."""
        # Generate payment link
        payment_link = self.payment_agent.generate_payment_link(
            entities.get("monto"),
            entities.get("referencia"),
            sender_context.get("user_id")
        )
        
        # Send the payment link
        return self.writer_agent.redact_message(
            f"Para completar su pago, por favor visite el siguiente enlace: {payment_link}"
        )
    
    def _handle_info_query(self, entities, sender_context):
        """Handle general information queries."""
        # Query the knowledge base
        info_result = self.knowledge_agent.query_knowledge(
            entities.get("tema"),
            sender_context.get("user_id")
        )
        
        return self.writer_agent.redact_message(info_result)
    
    def _handle_admin_request(self, entities, sender_context):
        """Handle admin requests (only for admins)."""
        # This would delegate to admin service agents
        return self.writer_agent.redact_message(
            "Solicitud administrativa procesada. (Implementación del servicio admin pendiente)"
        )

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

"""
AI Agent QueryAgent - Consults the database
Uses McpDatabase to read and write data.
"""

class QueryAgent:
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

"""
AI Agent KnowledgeAgent - Consults the RAG (Retrieval Augmented Generation)
Uses McpRag to search for relevant information.
"""

class KnowledgeAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the KnowledgeAgent.
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.rag_server = mcp_servers.get('rag')
    
    def query_knowledge(self, topic, user_id):
        """
        Query the knowledge base for information on a topic.
        
        Args:
            topic: Topic to search for
            user_id: Identifier of the user making the request
            
        Returns:
            Relevant information from the knowledge base
        """
        if not self.rag_server:
            return "Lo siento, no puedo acceder a la base de conocimiento en este momento."
        
        # Search the RAG for relevant documents
        results = self.rag_server.search(topic, limit=3)
        
        if not results:
            return f"No encontré información específica sobre '{topic}'."
        
        # Format the response
        response = f"Información sobre '{topic}':\n\n"
        for i, result in enumerate(results, 1):
            response += f"{i}. {result['content'][:200]}...\n"
        
        return response

"""
AI Agent WriterAgent - Redacts messages
Uses McpMessenger to send messages via WhatsApp.
"""

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

"""
AI Agent GuardAgent - Responsible for security
Uses McpSecurity to validate security, detect fraud, block numbers.
"""

class GuardAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the GuardAgent.
        
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

"""
AI Agent PaymentAgent - Responsible for reviewing and handling payments
Uses McpPayments to generate links, verify and record payments.
"""

class PaymentAgent:
    def __init__(self, mcp_servers):
        """
        Initialize the PaymentAgent.
        
        Args:
            mcp_servers: Dictionary of available MCP servers
        """
        self.mcp_servers = mcp_servers
        self.payments_server = mcp_servers.get('payments')
    
    def generate_payment_link(self, amount, reference, user_id):
        """
        Generate a payment link for a user.
        
        Args:
            amount: Amount to be paid
            reference: Reference for the payment (e.g., reservation ID)
            user_id: Identifier of the user
            
        Returns:
            Payment link URL
        """
        if not self.payments_server:
            return "Error: No se pudo generar el enlace de pago"
        
        # Generate the payment link through the payments MCP server
        payment_link = self.payments_server.generate_payment_link(
            amount, reference, user_id
        )
        
        return payment_link
    
    def verify_payment(self, payment_id):
        """
        Verify the status of a payment.
        
        Args:
            payment_id: Identifier of the payment to verify
            
        Returns:
            Payment status information
        """
        if not self.payments_server:
            return {"status": "error", "message": "Servicio de pagos no disponible"}
        
        return self.payments_server.verify_payment(payment_id)
    
    def record_payment(self, payment_data):
        """
        Record a payment in the database.
        
        Args:
            payment_data: Dictionary containing payment information
            
        Returns:
            Boolean indicating success or failure
        """
        if not self.payments_server:
            return False
        
        return self.payments_server.record_payment(payment_data)

"""
Admin Service Agents
These are identical to the Customer Service agents but operate in the admin context.
"""

# Admin Service Agent Nexus - Orchestrator
class AdminNexusAgent(NexusAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)
        # Override to use admin-specific MCP servers if needed
        # For now, using the same implementation but could be customized

# Admin Service Agent Identifier
class AdminIdentifierAgent(IdentifierAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Admin Service Agent QueryAgent
class AdminQueryAgent(QueryAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Admin Service Agent KnowledgeAgent
class AdminKnowledgeAgent(KnowledgeAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Admin Service Agent WriterAgent
class AdminWriterAgent(WriterAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Admin Service Agent GuardAgent
class AdminGuardAgent(GuardAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Admin Service Agent PaymentAgent
class AdminPaymentAgent(PaymentAgent):
    def __init__(self, mcp_servers):
        super().__init__(mcp_servers)

# Placeholder implementations for MCP Servers
# In a real implementation, these would connect to actual services

class MockMcpServer:
    """Base class for mock MCP servers"""
    def __init__(self, name):
        self.name = name

class MockMcpWhatsapp(McpMcpServer):
    def get_contact_info(self, sender_id):
        return {
            "name": f"Usuario {sender_id[-4:]}",
            "profile_pic": None,
            "status": "disponible"
        }

class MockMcpDatabase(McpMcpServer):
    def get_or_create_user_profile(self, sender_id, contact_info):
        return {
            "user_id": sender_id,
            "is_admin": sender_id.endswith("00"),  # Example: numbers ending in 00 are admins
            "name": contact_info.get("name", "Usuario"),
            "created_at": "2026-01-01"
        }
    
    def query_availability(self, fecha, tipo_habitacion, huespedes):
        # Simplified availability check
        return f"Disponible: 2 habitaciones de tipo {tipo_habitacion} para {huespedes} personas el {fecha}"
    
    def get_guest_profile(self, guest_id):
        return {
            "guest_id": guest_id,
            "name": f"Invitado {guest_id[-4:]}",
            "reservations": []
        }

class MockMcpRag(McpMcpServer):
    def search(self, topic, limit=3):
        return [
            {
                "id": f"doc_{i}",
                "content": f"Información sobre {topic} - resultado {i}"
            }
            for i in range(1, limit+1)
        ]

class MockMcpMessenger(McpMcpServer):
    def send_message(self, recipient_id, message):
        # In a real implementation, this would send via WhatsApp API
        print(f"[MOCK] Sending to {recipient_id}: {message}")
        return True

class MockMcpSecurity(McpMcpServer):
    def validate_message_content(self, message, sender_id):
        # Basic validation - block messages with certain patterns
        blocked_patterns = ["spam", "fraud", "virus"]
        return not any(pattern in message.lower() for pattern in blocked_patterns)
    
    def is_sender_blocked(self, sender_id):
        # Example: block senders with certain patterns
        return sender_id.startswith("blocked_")

class MockMcpPayments(McpMcpServer):
    def generate_payment_link(self, amount, reference, user_id):
        # In a real implementation, this would call Mercado Pago API
        return f"https://mercadopago.com/pay/{reference}?amount={amount}&user={user_id}"
    
    def verify_payment(self, payment_id):
        # Simplified verification
        return {
            "status": "approved" if payment_id.endswith("00") else "pending",
            "payment_id": payment_id,
            "amount": "100.00"
        }
    
    def record_payment(self, payment_data):
        # In a real implementation, this would record to database
        print(f"[MOCK] Recording payment: {payment_data}")
        return True

# Alias for backward compatibility
McpMcpServer = MockMcpServer
McpWhatsapp = MockMcpWhatsapp
McpDatabase = MockMcpDatabase
McpRag = MockMcpRag
McpMessenger = MockMcpMessenger
McpSecurity = MockMcpSecurity
McpPayments = MockMcpPayments