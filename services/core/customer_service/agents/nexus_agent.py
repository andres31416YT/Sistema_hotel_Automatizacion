"""
AI Agent Nexus - Orchestrator
Coordinates between different agents to process requests.
"""

from .identifier_agent import IdentifierAgent
from .query_agent import QueryAgent
from .knowledge_agent import KnowledgeAgent
from .writer_agent import WriterAgent
from .guard_agent import GuardAgent
from .payment_agent import PaymentAgent
from prompts.customer_service.agents import PROMPT_NEXUS  # noqa

import logging

logger = logging.getLogger(__name__)


class NexusAgent:
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
        elif intent == "check_existing_reservation":
            return self._check_existing_reservation(entities, sender_context)
        elif intent == "create_booking":
            return self._handle_create_booking(entities, sender_context)
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
            "registrar", "crear reserva", "nueva reserva", "quiero reservar",
            "reservar", "hacer una reserva", "reserva", "cita", "agendar",
            "agendada", "mi reserva", "ver mi reserva", "consultar reserva",
            "ya reservé", "ya reserv", "reservé",
        ]):
            # Si pregunta por el estado de una reserva existente
            if any(word in message_lower for word in [
                "mi reserva", "ver mi reserva", "consultar reserva", "ya reservé",
                "agendada", "confirmada", "estado de mi reserva", "quedó agendad",
            ]):
                return "check_existing_reservation", self._extract_booking_entities(message)
            return "create_booking", self._extract_booking_entities(message)
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
        db = self.mcp_servers.get('database')
        if not db:
            return "No pude acceder a la base de datos. Intentá de nuevo."

        fecha = entities.get("fecha", "no especificada")
        tipo  = entities.get("tipo",  "no especificado")
        huespedes = entities.get("huespedes", "1")

        try:
            result = db.query_availability(
                fecha if fecha != "fecha_no_especificada" else None,
                tipo  if tipo  != "tipo_no_especificado" else None,
                int(huespedes) if huespedes not in ("1", "fecha_no_especificada") else 1,
            )
            if result:
                if isinstance(result, list) and len(result) > 0:
                    lines = [f"✅ Hay {len(result)} habitación(es) disponible(s) para {tipo} el {fecha}:\n"]
                    for r in result[:5]:
                        lines.append(f"  • Habitación {r.get('room_number', 'N/A')} — {r.get('tipo', tipo)} — {r.get('estado', 'disponible')}")
                    if len(result) > 5:
                        lines.append(f"\n  ... y {len(result)-5} más.")
                    lines.append("\n\n¿Quieres reservar una de estas habitaciones? Responde con el número de habitación o el tipo que prefieres.")
                    return "\n".join(lines)
                return f"Resultado de disponibilidad: {result}"
            return f"Lo siento, no hay habitaciones {tipo} disponibles para el {fecha}. Podés probar con otra fecha u otro tipo de habitación."
        except Exception as e:
            logger.warning("[Nexus] check_availability error: %s", e)
            return "Hubo un error al consultar la disponibilidad. Intentá de nuevo en unos minutos."

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

    def _check_existing_reservation(self, entities, sender_context):
        """Verifica si el cliente ya tiene una reserva activa."""
        db = self.mcp_servers.get('database')
        if not db:
            return "No pude acceder a la base de datos. Intentá de nuevo."

        phone = sender_context.get("user_id")
        if not phone:
            return "Para buscar tu reserva necesito tu número de WhatsApp registrado."

        try:
            result = db.get_active_reservation(phone)
            if result:
                res = result[0] if isinstance(result, list) else result
                estado = res.get("estado", "pendiente")
                habitacion = res.get("room_number", "sin asignar")
                checkin = res.get("check_in_date", "sin fecha")
                checkout = res.get("check_out_date", "sin fecha")
                monto = res.get("total_amount", "sin monto")
                return (
                    f"✅ Tu reserva está **{estado.upper()}**.\n\n"
                    f"• Habitación: {habitacion}\n"
                    f"• Check-in: {checkin}\n"
                    f"• Check-out: {checkout}\n"
                    f"• Total: S/ {monto}\n\n"
                    f"Si necesitas modificar o cancelar, comunícate con recepción."
                )
            else:
                return "No encontré ninguna reserva activa asociada a tu número de WhatsApp. ¿Deseas hacer una nueva reserva?"
        except Exception as e:
            logger.warning("Error consultando reserva: %s", e)
            return "Hubo un error al consultar tu reserva. Intentá de nuevo o contactá a recepción."

    def _handle_create_booking(self, entities, sender_context):
        """Handle new booking/reservation requests — DNI first, then other fields."""
        # TODO: consultar get_db_schema para confirmar estructura de tabla reservations
        # antes de construir INSERT. Por ahora, delegar al LLM con reglas estrictas.
        # El DNI es el primer dato obligatorio antes de cualquier otro campo de reserva.
        doc_identidad = entities.get("doc_identidad") or sender_context.get("doc_identidad")
        if not doc_identidad:
            return (
                "Para registrar tu reserva, necesito primero tu documento de identidad "
                "(DNI, carnet de extranjeria o pasaporte). "
                "Una vez que lo compartas, te pedire las fechas y el tipo de habitacion."
            )
        return (
            f"Perfecto, ya tengo tu documento de identidad registrado. "
            f"Ahora necesito los siguientes datos para completar la reserva:\n\n"
            f"1. Fecha de check-in (llegada)\n"
            f"2. Fecha de check-out (salida)\n"
            f"3. Tipo de habitacion (simple, doble o suite)\n"
            f"4. Numero de huespedes\n\n"
            f"Ejemplo: 'Check-in el 25 de mayo, check-out el 27 de mayo, habitacion doble, 2 personas'"
        )

    def _handle_admin_request(self, entities, sender_context):
        """Handle admin requests (only for admins)."""
        # This would delegate to admin service agents
        return self.writer_agent.redact_message(
            "Solicitud administrativa procesada. (Implementación del servicio admin pendiente)"
        )