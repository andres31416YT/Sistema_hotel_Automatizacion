"""
MCP Server McpContext7 - Remote MCP Integration
Conecta al MCP remoto de Context7 para buscar documentation y ejemplos de librerias.
Usa el endpoint publico https://mcp.context7.com/mcp sin credenciales.
"""

import json
import logging
import httpx

logger = logging.getLogger(__name__)

# MCP remoto publico de Context7
MCP_CONTEXT7_URL = "https://mcp.context7.com/mcp"


class McpContext7:
    """
    Cliente MCP para el servidor remoto de Context7.
    Proporciona acceso a documentation de librerias y APIs via MCP.
    No requiere credenciales - es publico.
    """

    def __init__(self):
        self._url = MCP_CONTEXT7_URL

    def _call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """Ejecuta una herramienta MCP en el servidor remoto."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    self._url,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"}
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return result.get("result", {"error": "Sin resultado"})
                logger.warning(f"MCP Context7 call failed: {resp.status_code}")
                return {"error": f"MCP error {resp.status_code}"}
        except Exception as e:
            logger.error(f"MCP Context7 connection error: {e}")
            return {"error": str(e)}

    def _list_tools(self) -> list:
        """Lista las herramientas disponibles en el MCP."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(self._url, json=payload)
                if resp.status_code == 200:
                    return resp.json().get("result", {}).get("tools", [])
        except Exception:
            pass
        return []

    def search_library(self, query: str) -> dict:
        """
        Busca una libreria o framework por nombre.

        Args:
            query: Nombre de la libreria (ej: 'fastapi', 'asyncpg', 'httpx', 'mercadopago')

        Returns:
            Dict con informacion de la libreria encontrada
        """
        result = self._call_tool("search_library", {"query": query})
        if "error" in result:
            return {"error": result["error"]}
        return result

    def get_docs(self, library_id: str) -> dict:
        """
        Obtiene documentation de una libreria.

        Args:
            library_id: ID de la libreria (ej: '/psf/httpx', '/encode/asyncpg')

        Returns:
            Dict con documentation, ejemplos e instalacion
        """
        return self._call_tool("get_docs", {"library_id": library_id})

    def get_code_examples(self, library_id: str, query: str = None) -> list:
        """
        Obtiene ejemplos de codigo para una libreria.

        Args:
            library_id: ID de la libreria
            query: Filtro opcional

        Returns:
            Lista de ejemplos
        """
        args = {"library_id": library_id}
        if query:
            args["query"] = query
        result = self._call_tool("get_code_examples", args)
        return result.get("examples", []) if "examples" in result else [result]

    def query_docs(self, library_id: str, question: str) -> dict:
        """
        Hace una pregunta sobre como usar una libreria.

        Args:
            library_id: ID de la libreria
            question: Pregunta en ingles

        Returns:
            Respuesta con codigo relevante
        """
        return self._call_tool("query_docs", {"library_id": library_id, "question": question})


# Instancia unica para uso global
_context7_instance = None


def _get_instance() -> McpContext7:
    global _context7_instance
    if _context7_instance is None:
        _context7_instance = McpContext7()
    return _context7_instance


def search_library(query: str) -> dict:
    """Busca una libreria via MCP Context7."""
    return _get_instance().search_library(query)


def get_docs(library_id: str) -> dict:
    """Obtiene documentation via MCP Context7."""
    return _get_instance().get_docs(library_id)


def get_code_examples(library_id: str, query: str = None) -> list:
    """Obtiene ejemplos via MCP Context7."""
    return _get_instance().get_code_examples(library_id, query)


def query_docs(library_id: str, question: str) -> dict:
    """Consulta documentation via MCP Context7."""
    return _get_instance().query_docs(library_id, question)