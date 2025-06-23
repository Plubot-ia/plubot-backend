import json
import logging
from config.settings import get_session
from models.template import Template

logger = logging.getLogger(__name__)

def load_initial_templates():
    with get_session() as session:
        expected_templates = [
            {
                "name": "Ventas Tienda Online",
                "tone": "amigable",
                "purpose": "vender productos y responder preguntas",
                "description": "Ideal para tiendas online. Incluye flujos para saludar, mostrar catálogo y tomar pedidos.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a mi tienda. ¿Qué te gustaría comprar hoy? 😊"},
                    {"user_message": "precio", "bot_response": "Dime qué producto te interesa y te doy el precio al instante. 💰"}
                ])
            },
            {
                "name": "Soporte Técnico",
                "tone": "profesional",
                "purpose": "resolver problemas técnicos",
                "description": "Perfecto para empresas de tecnología. Ayuda a resolver problemas técnicos paso a paso.",
                "flows": json.dumps([
                    {"user_message": "tengo un problema", "bot_response": "Describe tu problema y te ayudaré paso a paso."},
                    {"user_message": "no funciona", "bot_response": "¿Puedes dar más detalles? Estoy aquí para solucionarlo."}
                ])
            },
            {
                "name": "Reservas de Restaurante",
                "tone": "amigable",
                "purpose": "gestionar reservas y responder consultas",
                "description": "Diseñado para restaurantes. Gestiona reservas y responde preguntas sobre el menú.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a nuestro restaurante. ¿Quieres reservar una mesa? 🍽️"},
                    {"user_message": "reservar", "bot_response": "Claro, dime para cuántas personas y a qué hora. ¡Te ayudo en un segundo!"},
                    {"user_message": "menú", "bot_response": "Tenemos platos deliciosos: pasta, carnes y postres. ¿Te envío el menú completo?"}
                ])
            },
            {
                "name": "Atención al Cliente - Ecommerce",
                "tone": "profesional",
                "purpose": "gestionar pedidos y devoluciones",
                "description": "Para tiendas online grandes. Gestiona pedidos, devoluciones y dudas frecuentes.",
                "flows": json.dumps([
                    {"user_message": "estado de mi pedido", "bot_response": "Por favor, dame tu número de pedido y lo verifico de inmediato."},
                    {"user_message": "devolver producto", "bot_response": "Claro, indícame el producto y el motivo. Te guiaré en el proceso de devolución."},
                    {"user_message": "hola", "bot_response": "Hola, gracias por contactarnos. ¿En qué puedo ayudarte hoy?"}
                ])
            },
            {
                "name": "Promoción de Servicios",
                "tone": "divertido",
                "purpose": "promocionar servicios y captar clientes",
                "description": "Para freelancers y agencias. Promociona servicios con un tono alegre y atractivo.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hey, hola! ¿List@ para descubrir algo genial? Ofrecemos servicios que te van a encantar. 🎉"},
                    {"user_message": "qué ofreces", "bot_response": "Desde diseño épico hasta soluciones locas. ¿Qué necesitas? ¡Te lo cuento todo!"},
                    {"user_message": "precio", "bot_response": "Los precios son tan buenos que te van a hacer saltar de emoción. ¿Qué servicio te interesa?"}
                ])
            },
            {
                "name": "Asistente de Eventos",
                "tone": "amigable",
                "purpose": "gestionar invitaciones y detalles de eventos",
                "description": "Para organizadores de eventos. Gestiona invitaciones y responde dudas sobre fechas y lugares.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! ¿Vienes a nuestro próximo evento? Te cuento todo lo que necesitas saber. 🎈"},
                    {"user_message": "cuándo es", "bot_response": "Dime qué evento te interesa y te paso la fecha y hora exactas."},
                    {"user_message": "registrarme", "bot_response": "¡Genial! Dame tu nombre y te apunto en la lista. ¿Algo más que quieras saber?"}
                ])
            },
            {
                "name": "Soporte de Suscripciones",
                "tone": "serio",
                "purpose": "gestionar suscripciones y pagos",
                "description": "Para servicios de suscripción. Gestiona cancelaciones y problemas de pago con profesionalismo.",
                "flows": json.dumps([
                    {"user_message": "cancelar suscripción", "bot_response": "Lamento que quieras cancelar. Por favor, indícame tu ID de suscripción para proceder."},
                    {"user_message": "pago fallido", "bot_response": "Verifiquemos eso. Proporcióname tu correo o número de suscripción y lo solucionamos."},
                    {"user_message": "hola", "bot_response": "Buenos días, estoy aquí para ayudarte con tu suscripción. ¿En qué puedo asistirte?"}
                ])
            }
        ]

        for template_data in expected_templates:
            template = session.query(Template).filter_by(name=template_data["name"]).first()
            if not template:
                new_template = Template(
                    name=template_data["name"],
                    tone=template_data["tone"],
                    purpose=template_data["purpose"],
                    flows=template_data["flows"],
                    description=template_data["description"]
                )
                session.add(new_template)
                logger.info(f"Plantilla '{template_data['name']}' creada.")
            else:
                template.tone = template_data["tone"]
                template.purpose = template_data["purpose"]
                template.flows = template_data["flows"]
                template.description = template_data["description"]
                logger.info(f"Plantilla '{template_data['name']}' actualizada.")

        session.commit()
        logger.info("Verificación y carga de plantillas completada.")