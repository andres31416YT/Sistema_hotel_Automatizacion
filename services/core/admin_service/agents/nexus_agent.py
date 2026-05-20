"""
AI Agent Nexus - Orchestrator
Coordinates between different agents to process requests (Admin Service).
"""

from .identifier_agent import IdentifierAgent
from .query_agent import QueryAgent
from .knowledge_agent import KnowledgeAgent
from .writer_agent import WriterAgent
from .guard_agent import GuardAgent
from .payment_agent import PaymentAgent
from prompts.admin_service.agents import PROMPT_NEXUS  # noqa

import logging

logger = logging.getLogger(__name__)


class AdminNexusAgent:
    ROLE = PROMPT_NEXUS

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
        elif intent == "registrar_cliente":
            return self._handle_register_client(entities, sender_context)
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
        elif any(word in message_lower for word in [
            "registrar cliente", "nuevo cliente", "crear cliente",
            "insertar cliente", "agregar cliente", "cliente nuevo",
            "registrarlo", "ya me pago", "ya pagó", "llegó un cliente",
            "llegar cliente", "ingresó un cliente", "cliente llegó",
        ]):
            return "registrar_cliente", {}
        elif any(word in message_lower for word in ["pago", "pagar", "link de pago"]):
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

    # ── Mapeo de columnas DB → lenguaje simple ─────────────────────────────────
    _CLIENT_FIELD_MAP = {
        "whatsapp_number":   "Número de WhatsApp",
        "name":              "Nombre completo",
        "doc_identidad":     "Número de documento de identidad (DNI, carnet de extranjería o pasaporte)",
        "id_tipo_documento": "Tipo de documento (elige uno: DNI, CE, PASSPORT, OTRO)",
    }

    def _build_client_fields_list(self, db_columns: list[str]) -> str:
        """Construye la lista de campos en lenguaje simple a partir de las columnas de la DB."""
        lines = ["Para registrar al cliente necesito los siguientes datos:\n"]
        idx = 1
        for col in db_columns:
            label = self._CLIENT_FIELD_MAP.get(col)
            if label is None:
                continue  # ignora columnas internas: id, created_at, updated_at
            lines.append(f"  {idx}. {label}")
            idx += 1
        if idx == 1:
            return "No pude leer la estructura de la tabla de clientes. Intentá de nuevo en un momento."
        lines.append(f"\n  {idx}. Monto pagado (si cliente ya pagó)")
        lines.append("     El monto se registra cuando se genere la reserva.")
        lines.append(f"\n  {'Monto pagado' if idx+1==5 else 'Otro'}. Faltan datos?")
        return "\n".join(lines)

    def _handle_register_client(self, entities, sender_context):
        """Registrar un nuevo cliente: lee la estructura de la DB y lista los campos en lenguaje simple."""
        mcp = self.mcp_servers.get('mcp_router') or self.mcp_servers.get('database')
        if not mcp:
            return "No pude acceder a la base de datos. Intentá de nuevo."

        try:
            # Obtener la estructura de la tabla clients sin mencionar herramientas
            schema = mcp.get_db_schema()
            clients_schema = schema.get("clients", {})
            raw_columns = [c["name"] for c in clients_schema.get("columns", [])]
        except Exception:
            raw_columns = []

        if not raw_columns:
            return "No pude leer la estructura de la tabla de clientes. Intentá de nuevo en un momento."

        return self.writer_agent.redact_message(
            self._build_client_fields_list(raw_columns)
        )

    def _handle_admin_request(self, entities, sender_context):
        """Handle admin requests (only for admins)."""
        # This would delegate to admin service agents
        return self.writer_agent.redact_message(
            "Solicitud administrativa procesada. (Implementación del servicio admin pendiente)"
        )