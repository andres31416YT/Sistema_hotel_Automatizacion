"""
AI Agent PaymentAgent - Responsible for reviewing and handling payments
Uses McpPayments to generate links, verify and record payments.
"""

from core.prompts.admin_service.agents import PROMPT_PAYMENT  # noqa


class PaymentAgent:
    ROLE = PROMPT_PAYMENT

    def __init__(self, mcp_servers):
        """
        Initialize the PaymentAgent (Admin Service).

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