"""
MCP Server McpDatabase - Admin Service
Reexporta las herramientas de base de datos del customer_service para uso administrativo.
"""

import sys
import os

# Importar desde customer_service para reutilizar la lógica real
customer_mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "customer_service", "mcp_servers")
sys.path.insert(0, customer_mcp_path)

from mcp_database import McpDatabase as _McpDatabaseBase
from mcp_database import get_db_schema, get_schema_short

# Reexportar la clase principal
McpDatabase = _McpDatabaseBase
get_db_schema = get_db_schema
get_schema_summary = get_schema_short