"""
AI Agent QueryAgent — consultas a la base de datos del hotel.
Usa McpDatabase.execute_sql() para ejecutar consultas SQL de lectura.
"""

from core.prompts.customer_service.agents import PROMPT_QUERY  # noqa
from customer_service.mcp_servers.mcp_database import get_schema_short  # noqa

logger = __import__('logging').getLogger(__name__)


class QueryAgent:
    ROLE = PROMPT_QUERY

    def __init__(self, mcp_servers):
        self.mcp_servers = mcp_servers
        self.database_server = mcp_servers.get('database')
        self._schema_summary = get_schema_short()

    def get_schema_context(self) -> str:
        """Devuelve el esquema de la DB listo para inyectar en un prompt."""
        return self._schema_summary

    def check_availability(self, fecha=None, tipo_habitacion=None, huespedes=1):
        """
        Consulta habitaciones disponibles.
        Args:
            fecha:           Fecha de check-in (YYYY-MM-DD) o None.
            tipo_habitacion: Código del tipo (ej: 'DOBLE') o None para todos.
            huespedes:       Número de huéspedes (int, default 1).
        Returns:
            Dict {ok, columns, rows, count} o mensaje de error string.
        """
        if not self.database_server:
            return "Error: servidor de base de datos no disponible. Contacta a recepcion."

        try:
            # Obtener id del estado DISPONIBLE
            est = self.database_server.execute_sql(
                "SELECT id FROM estado_habitacion WHERE codigo = 'DISPONIBLE' LIMIT 1"
            )
            if not est.get("ok") or not est["rows"]:
                return {"ok": False, "error": "No se encontro el estado DISPONIBLE."}
            id_estado_disp = est["rows"][0]["id"]

            sql = (
                "SELECT r.id, r.room_number, th.nombre AS tipo_hab, "
                "       th.capacidad, eh.nombre AS estado_hab "
                "FROM rooms r "
                "JOIN tipo_habitacion th ON r.id_tipo_hab = th.id "
                "JOIN estado_habitacion eh ON r.id_estado_hab = eh.id "
                "WHERE r.id_estado_hab = $1 AND th.capacidad >= $2"
            )
            params = [id_estado_disp, int(huespedes)]

            if tipo_habitacion:
                sql += " AND th.codigo = $3"
                params.append(tipo_habitacion.upper())

            sql += " ORDER BY r.room_number"
            return self.database_server.execute_sql(sql, params)

        except Exception as exc:
            logger.warning("[QueryAgent] check_availability error: %s", exc)
            return "Error consultando disponibilidad. Intenta de nuevo en unos minutos."

    def get_guest_info(self, guest_id):
        """
        Obtiene información del huésped por número de WhatsApp.
        Args:
            guest_id: Número de WhatsApp del huésped.
        Returns:
            Dict con datos del huésped o None si no existe.
        """
        if not self.database_server:
            return None

        try:
            sql = (
                "SELECT c.id, c.name, c.doc_identidad, td.nombre AS tipo_doc, "
                "       c.created_at "
                "FROM clients c "
                "LEFT JOIN tipo_documento td ON c.id_tipo_documento = td.id "
                "WHERE c.whatsapp_number = $1"
            )
            result = self.database_server.execute_sql(sql, [str(guest_id)])
            if result.get("ok") and result["rows"]:
                return result["rows"][0]
            return None
        except Exception as exc:
            logger.warning("[QueryAgent] get_guest_info error: %s", exc)
            return None

    def get_active_reservation(self, client_wa):
        """
        Devuelve la reserva activa (PENDIENTE o CONFIRMADA) del huésped.
        Args:
            client_wa: Número de WhatsApp del cliente.
        Returns:
            Dict con datos de la reserva o None si no existe.
        """
        if not self.database_server:
            return None

        try:
            sql = (
                "SELECT res.id, res.check_in_date, res.check_out_date, "
                "       res.total_amount, er.codigo AS estado, "
                "       r.room_number, th.nombre AS tipo_habitacion, "
                "       cl.name, cl.doc_identidad "
                "FROM reservations res "
                "JOIN clients    cl ON res.client_id       = cl.id "
                "JOIN rooms      r  ON res.room_id          = r.id "
                "JOIN tipo_habitacion th ON r.id_tipo_hab  = th.id "
                "JOIN estado_reserva er ON res.id_estado    = er.id "
                "WHERE cl.whatsapp_number = $1 "
                "  AND er.codigo IN ('PENDIENTE', 'CONFIRMADA') "
                "ORDER BY res.created_at DESC LIMIT 1"
            )
            result = self.database_server.execute_sql(sql, [str(client_wa)])
            if result.get("ok") and result["rows"]:
                return result["rows"][0]
            return None
        except Exception as exc:
            logger.warning("[QueryAgent] get_active_reservation error: %s", exc)
            return None
