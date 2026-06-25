"""Payment agent node: handle payment links and status."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.payments import payments_client
from lib.datetime import get_current_datetime_block

logger = logging.getLogger(__name__)


def _load_prompt(is_admin: bool) -> str:
    if is_admin:
        try:
            from agents.prompt.admin import PROMPT_PAYMENT
            return PROMPT_PAYMENT
        except Exception:
            pass
    else:
        try:
            from agents.prompt.customer import PROMPT_PAYMENT
            return PROMPT_PAYMENT
        except Exception:
            pass
    return "Eres el agente de pagos del hotel."


async def payment_node(state: dict) -> dict:
    message = state.get("message", "")
    phone = state.get("phone", "")
    name = state.get("name", "Usuario")
    is_adm = state.get("is_admin", False)

    response = ""
    try:
        if "link" in message.lower() or "pagar" in message.lower() or "abonar" in message.lower():
            link_data = payments_client.generate_payment_link(
                amount=150.0,
                reference=f"WA_{phone}",
                user_id=phone,
                description=f"Reserva Hotel - {name}",
            )
            link = link_data.get("link", "")
            if link:
                response = f"Link de pago generado:\n{link}"
            else:
                response = "No pude generar el link de pago en este momento."
        elif "estado" in message.lower() or "status" in message.lower() or "verificado" in message.lower():
            response = "Para verificar el estado necesito el ID de pago o tu número de reserva."
        else:
            response = "¿Necesitas generar un link de pago o verificar el estado de uno existente?"
    except Exception as exc:
        logger.error("Payment agent error: %s", exc)
        response = "Hubo un error procesando el pago. Por favor intenta más tarde."

    prompt_text = _load_prompt(is_adm)
    tone = "directo" if is_adm else "cálido"

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}\n"
            f"Tono: {tone}.\n"
            "Los montos son en soles peruanos (S/.)."
        )),
        ("user", f"Mensaje del usuario: {message}\n\nAcción ejecutada: {response}"),
    ])

    chain = prompt | get_llm(temperature=0.1) | StrOutputParser()
    final = await chain.ainvoke({})
    logger.info("Payment agent response (%d chars)", len(final))
    return {"agent_response": final}