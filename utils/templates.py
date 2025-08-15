"""Carga y gestiona las plantillas iniciales del sistema."""

import json
import logging

from config.settings import get_session
from models.template import Template

logger = logging.getLogger(__name__)


def load_initial_templates() -> None:
    """Carga o actualiza las plantillas iniciales en la base de datos."""
    # --- Definición de datos de flujos ---
    ventas_data = [
        {
            "user_message": "hola",
            "bot_response": (
                "¡Hola! Bienvenid@ a mi tienda. "
                "¿Qué te gustaría comprar hoy? 😊"
            ),
        },
        {
            "user_message": "precio",
            "bot_response": (
                "Dime qué producto te interesa y te doy el precio al instante. 💰"
            ),
        },
    ]
    soporte_data = [
        {
            "user_message": "tengo un problema",
            "bot_response": "Describe tu problema y te ayudaré paso a paso.",
        },
        {
            "user_message": "no funciona",
            "bot_response": "¿Puedes dar más detalles? Estoy aquí para solucionarlo.",
        },
    ]
    reservas_data = [
        {
            "user_message": "hola",
            "bot_response": (
                "¡Hola! Bienvenid@ a nuestro restaurante. "
                "¿Quieres reservar una mesa? 🍽️"
            ),
        },
        {
            "user_message": "reservar",
            "bot_response": (
                "Claro, dime para cuántas personas y a qué hora. "
                "¡Te ayudo en un segundo!"
            ),
        },
        {
            "user_message": "menú",
            "bot_response": (
                "Tenemos platos deliciosos: pasta, carnes y postres. "
                "¿Te envío el menú completo?"
            ),
        },
    ]
    ecommerce_data = [
        {
            "user_message": "estado de mi pedido",
            "bot_response": (
                "Por favor, dame tu número de pedido y lo verifico de inmediato."
            ),
        },
        {
            "user_message": "devolver producto",
            "bot_response": (
                "Claro, indícame el producto y el motivo. "
                "Te guiaré en el proceso."
            ),
        },
        {
            "user_message": "hola",
            "bot_response": "Hola, gracias por contactarnos. ¿En qué puedo ayudarte hoy?",
        },
    ]
    servicios_data = [
        {
            "user_message": "hola",
            "bot_response": (
                "¡Hey, hola! ¿List@ para descubrir algo genial? "
                "Ofrecemos servicios que te encantarán. 🎉"
            ),
        },
        {
            "user_message": "qué ofreces",
            "bot_response": (
                "Desde diseño épico hasta soluciones locas. "
                "¿Qué necesitas? ¡Te lo cuento todo!"
            ),
        },
        {
            "user_message": "precio",
            "bot_response": (
                "Los precios son tan buenos que te harán saltar de emoción. "
                "¿Qué servicio te interesa?"
            ),
        },
    ]
    eventos_data = [
        {
            "user_message": "hola",
            "bot_response": (
                "¡Hola! ¿Vienes a nuestro próximo evento? "
                "Te cuento todo lo que necesitas saber. 🎈"
            ),
        },
        {
            "user_message": "cuándo es",
            "bot_response": (
                "Dime qué evento te interesa y te paso la fecha y hora exactas."
            ),
        },
        {
            "user_message": "registrarme",
            "bot_response": (
                "¡Genial! Dame tu nombre y te apunto en la lista. "
                "¿Algo más que quieras saber?"
            ),
        },
    ]
    suscripciones_data = [
        {
            "user_message": "cancelar suscripción",
            "bot_response": (
                "Lamento que quieras cancelar. "
                "Indícame tu ID de suscripción para proceder."
            ),
        },
        {
            "user_message": "pago fallido",
            "bot_response": (
                "Verifiquemos eso. Proporcióname tu correo o número de suscripción."
            ),
        },
        {
            "user_message": "hola",
            "bot_response": (
                "Buenos días, estoy aquí para ayudarte con tu suscripción. "
                "¿En qué puedo asistirte?"
            ),
        },
    ]

    # --- Conversión a JSON ---
    flows_map = {
        "Ventas Tienda Online": json.dumps(ventas_data),
        "Soporte Técnico": json.dumps(soporte_data),
        "Reservas de Restaurante": json.dumps(reservas_data),
        "Atención al Cliente - Ecommerce": json.dumps(ecommerce_data),
        "Promoción de Servicios": json.dumps(servicios_data),
        "Asistente de Eventos": json.dumps(eventos_data),
        "Soporte de Suscripciones": json.dumps(suscripciones_data),
    }

    expected_templates = [
        {
            "name": "Ventas Tienda Online",
            "tone": "amigable",
            "purpose": "vender productos",
            "description": (
                "Ideal para tiendas online. Saluda, muestra catálogo y toma pedidos."
            ),
            "flows": flows_map["Ventas Tienda Online"],
        },
        {
            "name": "Soporte Técnico",
            "tone": "profesional",
            "purpose": "resolver problemas",
            "description": (
                "Perfecto para empresas de tecnología. "
                "Resuelve problemas paso a paso."
            ),
            "flows": flows_map["Soporte Técnico"],
        },
        {
            "name": "Reservas de Restaurante",
            "tone": "amigable",
            "purpose": "gestionar reservas",
            "description": (
                "Diseñado para restaurantes. Gestiona reservas y responde preguntas."
            ),
            "flows": flows_map["Reservas de Restaurante"],
        },
        {
            "name": "Atención al Cliente - Ecommerce",
            "tone": "profesional",
            "purpose": "gestionar pedidos",
            "description": (
                "Para ecommerce. Gestiona pedidos, devoluciones y dudas frecuentes."
            ),
            "flows": flows_map["Atención al Cliente - Ecommerce"],
        },
        {
            "name": "Promoción de Servicios",
            "tone": "divertido",
            "purpose": "promocionar servicios",
            "description": (
                "Para freelancers y agencias. "
                "Promociona servicios con un tono atractivo."
            ),
            "flows": flows_map["Promoción de Servicios"],
        },
        {
            "name": "Asistente de Eventos",
            "tone": "amigable",
            "purpose": "gestionar eventos",
            "description": (
                "Para organizadores. Gestiona invitaciones y responde dudas."
            ),
            "flows": flows_map["Asistente de Eventos"],
        },
        {
            "name": "Soporte de Suscripciones",
            "tone": "serio",
            "purpose": "gestionar suscripciones",
            "description": (
                "Para servicios de suscripción. Gestiona cancelaciones y pagos."
            ),
            "flows": flows_map["Soporte de Suscripciones"],
        },
    ]

    with get_session() as session:
        for template_data in expected_templates:
            template = (
                session.query(Template).filter_by(name=template_data["name"]).first()
            )
            if not template:
                new_template = Template(**template_data)
                session.add(new_template)
                logger.info("Plantilla '%s' creada.", template_data["name"])
            else:
                template.tone = template_data["tone"]
                template.purpose = template_data["purpose"]
                template.flows = template_data["flows"]
                template.description = template_data["description"]
                logger.info("Plantilla '%s' actualizada.", template_data["name"])

        session.commit()
        logger.info("Verificación y carga de plantillas completada.")
