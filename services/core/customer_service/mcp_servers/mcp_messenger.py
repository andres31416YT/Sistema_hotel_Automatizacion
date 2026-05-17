"""
MCP Server McpMessenger
Envia mensajes y links de pago via WhatsApp
"""

class McpMessenger:
    def __init__(self):
        pass
    
    def send_message(self, recipient_id, message):
        """
        Send a text message to a WhatsApp user
        
        Args:
            recipient_id: The recipient's WhatsApp number
            message: The message text to send
            
        Returns:
            Boolean indicating success or failure
        """
        # In a real implementation, this would use WhatsApp Business API
        # to send the message
        print(f"[MCP MESSENGER] Sending to {recipient_id}: {message}")
        return True
    
    def send_template_message(self, recipient_id, template_name, template_params, language_code="es_MX"):
        """
        Send a template message to a WhatsApp user
        
        Args:
            recipient_id: The recipient's WhatsApp number
            template_name: Name of the approved message template
            template_params: List of parameters to fill in the template
            language_code: Language code for the template
            
        Returns:
            Boolean indicating success or failure
        """
        # In a real implementation, this would use WhatsApp Business API
        # to send a template message
        params_str = ", ".join(template_params) if template_params else "ninguno"
        print(f"[MCP MESSENGER] Sending template '{template_name}' to {recipient_id} with params: {params_str}")
        return True
    
    def send_payment_link(self, recipient_id, payment_link, reference):
        """
        Send a payment link to a WhatsApp user
        
        Args:
            recipient_id: The recipient's WhatsApp number
            payment_link: The payment link URL
            reference: Reference for the payment (e.g., reservation ID)
            
        Returns:
            Boolean indicating success or failure
        """
        # In a real implementation, this would use WhatsApp Business API
        # to send the payment link
        message = f"Para completar su pago referenciado como {reference}, por favor visite: {payment_link}"
        print(f"[MCP MESSENGER] Sending payment link to {recipient_id}: {message}")
        return True