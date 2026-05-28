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
        elif intent == "consulta_reserva":
            return self._handle_reserva_query(entities, sender_context)
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
        
        # Check for reservation queries (admin functionality)
        if any(phrase in message_lower for phrase in [
            "reservas para hoy", "reservas de hoy", "todas las reservas hoy",
            "reservas para mañana", "reservas de mañana", "todas las reservas mañana",
            "reservas para", "reservas del", "ver reservas", "mostrar reservas",
            "listar reservas", "consultar reservas"
        ]):
            # Extract date information
            entities = self._extract_date_entities(message)
            return "consulta_reserva", entities
            
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

    def _extract_date_entities(self, message):
        """Extract date-related entities from message."""
        import datetime
        message_lower = message.lower()
        today = datetime.date.today()
        
        # Default to today
        fecha = today.strftime("%Y-%m-%d")
        
        if "mañana" in message_lower or "tomorrow" in message_lower:
            fecha = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        elif "hoy" in message_lower or "today" in message_lower:
            fecha = today.strftime("%Y-%m-%d")
        
        return {
            "fecha": fecha
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

    def _handle_reserva_query(self, entities, sender_context):
        """Handle reservation queries for specific dates."""
        db = self.mcp_servers.get('database')
        if not db:
            return self.writer_agent.redact_message(
                "Error: No se pudo acceder a la base de datos"
            )
        
        try:
            fecha = entities.get("fecha")
            if not fecha:
                return self.writer_agent.redact_message(
                    "Error: No se pudo determinar la fecha para la consulta"
                )
            
            # Query reservations for the specific date
            query = """
            SELECT r.id, c.name as cliente_nombre, c.doc_identidad as dni,
                   r.check_in_date, r.check_out_date, r.total_amount,
                   er.nombre as estado_reserva, t_h.nombre as tipo_habitacion,
                   ro.room_number as numero_habitacion
            FROM reservations r
            JOIN clients c ON r.client_id = c.id
            JOIN estado_reserva er ON r.id_estado = er.id
            JOIN rooms ro ON r.room_id = ro.id
            JOIN tipo_habitacion t_h ON ro.id_tipo_hab = t_h.id
            WHERE r.check_in_date = $1
            ORDER BY r.created_at DESC
            """
            
            result = db.execute_sql(query, [fecha])
            
            if not result.get('ok'):
                return self.writer_agent.redact_message(
                    f"Error al consultar reservas: {result.get('error', 'Error desconocido')}"
                )
            
            rows = result.get('rows', [])
            if not rows:
                return self.writer_agent.redact_message(
                    f"No se encontraron reservas para la fecha {fecha}"
                )
            
            # Format the response
            response_lines = [f"Reservas para el {fecha}:"]
            for i, row in enumerate(rows, 1):
                response_lines.append(
                    f"{i}. Reserva #{row['id']} - {row['cliente_nombre']} "
                    f"(DNI: {row['dni']}) - Habitación {row['numero_habitacion']} "
                    f"({row['tipo_habitacion']}) - {row['estado_reserva']} "
                    f"- Check-in: {row['check_in_date']} - Check-out: {row['check_out_date']} "
                    f"- Total: S/{row['total_amount']:.2f}"
                )
            
            return self.writer_agent.redact_message("\n".join(response_lines))
            
        except Exception as e:
            logger.error(f"Error in _handle_reserva_query: {e}")
            return self.writer_agent.redact_message(
                "Error interno al procesar la consulta de reservas. Inténtelo de nuevo."
            )

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
                continue
            lines.append(f"  {idx}. {label}")
            idx += 1
        if idx == 1:
            return "No pude leer la estructura de la tabla de clientes. Intentá de nuevo en un momento."
        lines.append("\n")
        lines.append(f"  {idx}. Monto pagado (si cliente ya pagó)")
        lines.append("     El monto se registra cuando se genere la reserva.")
        return "\n".join(lines)

    def _handle_register_client(self, entities, sender_context):
        """Registrar un nuevo cliente: lee la estructura de la DB y lista los campos en lenguaje simple."""
        db = self.mcp_servers.get('database')
        if not db:
            return "No pude acceder a la base de datos. Intentá de nuevo."
        
        try:
            schema = db.get_db_schema()
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
        return self.writer_agent.redact_message(
            "Solicitud administrativa procesada. (Implementación del servicio admin pendiente)"
        )