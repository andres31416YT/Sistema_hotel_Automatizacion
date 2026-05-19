"""
AI Agent QueryAgent — consultas a la base de datos del hotel.
Lee la estructura de la DB desde McpDatabase.get_db_schema() sin tenerla
hardcodeada en el prompt.
"""

from core.prompts.customer_service.agents import PROMPT_QUERY  # noqa
from customer_service.mcp_servers.mcp_database import get_schema_short  # noqa

logger = __import__('logging').getLogger(__name__)


class QueryAgent:
    ROLE = PROMPT_QUERY

    def __init__(self, mcp_servers):
        self.mcp_servers = mcp_servers
        self.database_server = mcp_servers.get('database')
        # Cargar esquema al inicializar (una sola vez, desde el .sql)
        self._schema_summary = get_schema_short()

    def get_schema_context(self) -> str:
        """Devuelve el esquema de la DB listo para inyectar en un prompt."""
        return self._schema_summary

    def check_availability(self, fecha, tipo_habitacion, huespedes, db_adapter=None):
        """
        Consulta habitaciones disponibles (sin hardcodear tablas).
        Construye la consulta en base al esquema cargado desde 00_schema.sql.

        Args:
            fecha:         Fecha de check-in (YYYY-MM-DD).
            tipo_habitacion: Código o nombre del tipo de habitación.
            huespedes:     Número de huéspedes.
            db_adapter:    Adaptador de DB con método .execute(sql, params).

        Returns:
            Lista de habitaciones disponibles o mensaje de error.
        """
        if not db_adapter:
            return "Error: adaptador de base de datos no disponible. Contacta a recepción."

        try:
            sql = (
                "SELECT r.id, r.room_number, th.nombre, eh.nombre "
                "FROM rooms r "
                "JOIN tipo_habitacion th  ON r.id_tipo_hab   = th.id "
                "JOIN estado_habitacion eh ON r.id_estado_hab = eh.id "
                "WHERE th.codigo = $1 AND th.capacidad >= $2 "
                "AND eh.codigo = 'DISPONIBLE'"
            )
            return db_adapter.execute(sql, [tipo_habitacion.upper(), int(huespedes)])
        except Exception as exc:
            logger.warning("[QueryAgent] check_availability error: %s", exc)
            return "Error consultando disponibilidad. Intenta de nuevo en unos minutos."

    def get_guest_info(self, guest_id, db_adapter=None):
        """
        Obtiene información del huésped por número de WhatsApp.
        Consulta la estructura del esquema para armar la query correctamente.
        """
        if not db_adapter:
            return None

        try:
            sql = (
                "SELECT c.id, c.name, c.doc_identidad, td.nombre AS tipo_doc, "
                "       c.created_at "
                "FROM clients c "
                "LEFT JOIN tipo_documento td ON c.id_tipo_documento = td.id "
                "WHERE c.whatsapp_number = $1"
            )
            return db_adapter.execute(sql, [str(guest_id)])
        except Exception as exc:
            logger.warning("[QueryAgent] get_guest_info error: %s", exc)
            return None

    def get_active_reservation(self, client_wa, db_adapter=None):
        """Devuelve la reserva activa (PENDIENTE o CONFIRMADA) del huésped."""
        if not db_adapter:
            return None

        try:
            sql = (
                "SELECT res.id, res.check_in_date, res.check_out_date, "
                "       res.total_amount, er.codigo AS estado, "
                "       r.room_number, th.nombre AS tipo_habitacion, "
                "       cl.name, cl.doc_identidad "
                "FROM reservations res "
                "JOIN clients    cl ON res.client_id      = cl.id "
                "JOIN rooms      r  ON res.room_id         = r.id "
                "JOIN tipo_habitacion th ON r.id_tipo_hab  = th.id "
                "JOIN estado_reserva er ON res.id_estado   = er.id "
                "WHERE cl.whatsapp_number = $1 "
                "  AND er.codigo IN ('PENDIENTE', 'CONFIRMADA') "
                "ORDER BY res.created_at DESC LIMIT 1"
            )
            return db_adapter.execute(sql, [str(client_wa)])
        except Exception as exc:
            logger.warning("[QueryAgent] get_active_reservation error: %s", exc)
            return None
