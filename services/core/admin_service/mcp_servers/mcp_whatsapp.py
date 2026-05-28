"""
MCP Server McpWhatsapp - Admin Service
Reexporta las herramientas de WhatsApp del customer_service para uso administrativo.
"""

import sys
import os

# Importar desde customer_service para reutilizar la lógica real
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "customer_service"))

from mcp_whatsapp import McpWhatsapp

# Reexportar
McpWhatsapp = McpWhatsapp