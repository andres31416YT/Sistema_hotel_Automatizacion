"""Payment agent node: handle payment links, status, history and transactions."""
import logging
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.payments import payments_client
from lib.db import fetch_all
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


@tool
def generate_payment_link(phone: str, name: str) -> str:
    """Generate a MercadoPago payment link for a reservation."""
    try:
        link_data = payments_client.generate_payment_link(
            amount=150.0,
            reference=f"WA_{phone}",
            user_id=phone,
            description=f"Reserva Hotel - {name}",
        )
        link = link_data.get("link", "")
        if link:
            return f"Link de pago generado exitosamente:\n{link}"
        return "No se pudo obtener el link de pago del sistema."
    except Exception as exc:
        logger.error("generate_payment_link failed: %s", exc)
        return f"Error generando link de pago: {exc}"


@tool
async def verify_payment_status(payment_id: str) -> str:
    """Verify the status of a payment by its ID."""
    try:
        result = payments_client.verify_payment(payment_id)
        status = result.get("status", "desconocido")
        amount = result.get("transaction_amount") or result.get("amount")
        return f"Estado del pago {payment_id}: {status}. Monto: S/{amount if amount else 'N/A'}"
    except Exception as exc:
        logger.error("verify_payment failed: %s", exc)
        return f"Error verificando pago: {exc}"


@tool
async def search_payment_history(phone: str = "", limit: int = 10) -> str:
    """Search recent payment transactions by phone/user_id (searches external_reference)."""
    try:
        rows = await fetch_all(
            "SELECT payment_id, amount, status, external_reference, date_created FROM transacciones WHERE external_reference ILIKE $1 ORDER BY date_created DESC LIMIT $2",
            params=[f"%WA_{phone}%", limit],
            connection="payments",
        )
        if not rows:
            return "No se encontraron transacciones recientes."
        lines = [f"Historial de pagos ({len(rows)}):"]
        for r in rows:
            lines.append(f"- {r['payment_id']}: S/{r['amount']} | {r['status']} | {r['date_created']} | ref: {r['external_reference']}")
        return "\n".join(lines)
    except Exception as exc:
        logger.error("search_payment_history failed: %s", exc)
        return f"Error consultando historial: {exc}"


async def payment_node(state: dict) -> dict:
    message = state.get("message", "")
    phone = state.get("phone", "")
    name = state.get("name", "Usuario")
    is_adm = state.get("is_admin", False)

    tools = [generate_payment_link, verify_payment_status, search_payment_history]
    llm = get_llm(temperature=0.0).bind_tools(tools)
    prompt_text = _load_prompt(is_adm)
    tone = "directo" if is_adm else "cálido"

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}\n"
            f"Tono: {tone}.\n"
            "Los montos son en soles peruanos (S/.).\n"
            "Las herramientas disponibles son:\n"
            "- generate_payment_link(phone, name): crea un link de pago MercadoPago\n"
            "- verify_payment_status(payment_id): consulta estado de un pago\n"
            "- search_payment_history(phone, limit): historial de transacciones\n"
        )),
        ("user", f"Mensaje del usuario: {message}"),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({})
    tool_calls = getattr(response, "tool_calls", None)
    tool_results: list[dict] = []

    if tool_calls:
        for tc in tool_calls:
            fn_name = tc["name"]
            args = tc.get("args", {})
            try:
                if fn_name == "generate_payment_link":
                    result = generate_payment_link.invoke({"phone": phone, "name": name})
                elif fn_name == "verify_payment_status":
                    result = await verify_payment_status.ainvoke(args)
                elif fn_name == "search_payment_history":
                    result = await search_payment_history.ainvoke(args)
                else:
                    result = f"Herramienta desconocida: {fn_name}"
            except Exception as exc:
                result = f"Error ejecutando {fn_name}: {exc}"
            tool_results.append({"tool": fn_name, "result": result})

        messages = [
            {"role": "system", "content": prompt.format_messages()[0].content},
            {"role": "user", "content": message},
            {"role": "assistant", "content": "", "tool_calls": tool_calls},
        ]
        for tr in tool_results:
            messages.append({"role": "tool", "tool_call_id": tr["tool"], "content": tr["result"]})

        final_prompt = ChatPromptTemplate.from_messages([
            ("system", "Con los resultados de las herramientas anteriores, responde al usuario de forma clara y concisa. No muestres SQL ni detalles técnicos."),
            ("user", f"Resultados:\n{chr(10).join(t['result'] for t in tool_results)}"),
        ])
        final_chain = final_prompt | get_llm(temperature=0.1) | StrOutputParser()
        final_response = await final_chain.ainvoke({})
    else:
        final_response = getattr(response, "content", "") or "No pude procesar esa consulta."

    logger.info("Payment agent response (%d chars)", len(final_response))
    return {"agent_response": final_response}
