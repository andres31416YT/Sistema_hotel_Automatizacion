"""
AI Agent KnowledgeAgent - Consults the RAG (Retrieval Augmented Generation)
Uses McpRag to search for relevant information.
"""

from core.prompts.customer_service.agents import PROMPT_KNOWLEDGE  # noqa


class KnowledgeAgent:
    ROLE = PROMPT_KNOWLEDGE

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