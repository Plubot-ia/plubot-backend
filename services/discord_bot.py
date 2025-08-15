# plubot-backend/services/discord_bot.py
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuración ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN_PLUBOT")
FLASK_API_BASE_URL = os.getenv("FLASK_API_URL", "http://127.0.0.1:5000/api")

if not DISCORD_BOT_TOKEN:
    logger.error("CRÍTICO: DISCORD_BOT_TOKEN_PLUBOT no está configurado.")

# --- Intents del Bot ---
intents = discord.Intents.default()
intents.message_content = True  # Para leer mensajes (ej. para XP)
intents.members = True  # Para eventos de miembros, roles

# --- Inicialización del Bot ---
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!plubotadmin_"), intents=intents
)

# --- Eventos del Bot ---
@bot.event
async def on_ready() -> None:
    """Evento que se activa cuando el bot se conecta y está listo."""
    logger.info(
        "Plubot (Discord Bot) conectado como %s (ID: %s)", bot.user, bot.user.id
    )
    logger.info("Latencia con Discord: %.2f ms", bot.latency * 1000)
    try:
        synced = await bot.tree.sync()
        logger.info("Sincronizados %d comandos slash.", len(synced))
        for cmd in synced:
            logger.info("  - Comando '%s' sincronizado.", cmd.name)
    except discord.HTTPException:
        logger.exception("Error HTTP al sincronizar comandos slash:")


@bot.event
async def on_message(message: discord.Message) -> None:
    """Evento que se activa con cada mensaje en un canal que el bot puede ver."""
    if message.author.bot:
        return

    discord_user_id = str(message.author.id)
    xp_to_add = 5  # O una cantidad variable
    api_url = f"{FLASK_API_BASE_URL}/discord/user_xp"

    payload = {
        "discord_user_id": discord_user_id,
        "discord_username": message.author.name,
        "xp_to_add": xp_to_add,
        "guild_id": str(message.guild.id) if message.guild else None,
        "channel_id": str(message.channel.id),
    }

    try:
        async with aiohttp.ClientSession() as session, session.post(
            api_url, json=payload, timeout=10
        ) as response:
            response.raise_for_status()
            response_data = await response.json()
            logger.info(
                "XP update response for %s: %s",
                discord_user_id,
                response_data.get("message"),
            )
    except aiohttp.ClientError:
        logger.exception("Error de red al actualizar XP para %s", discord_user_id)
    except Exception:
        logger.exception("Error inesperado en on_message para %s", discord_user_id)

    await bot.process_commands(message)


# --- Comandos Slash de Ejemplo ---
@bot.tree.command(
    name="plubot_ping",
    description="Verifica la conexión con el bot y el backend de Plubot.",
)
async def plubot_ping(interaction: discord.Interaction) -> None:
    """Verifica la conexión y latencia con el bot y el backend de Plubot."""
    await interaction.response.defer(ephemeral=False)

    bot_latency = bot.latency * 1000
    embed = discord.Embed(
        title="🏓 ¡Pong! - Estado de Plubot", color=discord.Color.blue()
    )
    embed.add_field(
        name="Latencia del Bot de Discord", value=f"{bot_latency:.2f} ms", inline=False
    )

    api_url = f"{FLASK_API_BASE_URL}/discord/status"
    try:
        async with aiohttp.ClientSession() as session, session.get(
            api_url, timeout=5
        ) as response:
            response.raise_for_status()
            backend_data = await response.json()
            backend_status = backend_data.get("message", "No se pudo obtener mensaje.")
            backend_operational = backend_data.get("backend_status") == "ok"

            embed.add_field(
                name="Estado del Backend Flask",
                value=f"{'✅ Operativo' if backend_operational else '⚠️ Problemas'}",
                inline=True,
            )
            embed.add_field(
                name="Mensaje del Backend", value=backend_status, inline=True
            )

    except aiohttp.ClientError:
        embed.add_field(name="Estado del Backend Flask", value="❌ Error", inline=True)
        embed.add_field(
            name="Mensaje del Backend",
            value="No se pudo contactar al backend.",
            inline=True,
        )
        embed.color = discord.Color.red()
        logger.exception("Error en plubot_ping al contactar API")

    embed.set_footer(text=f"Plubot | Solicitado por {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="mi_plubot", description="Muestra información sobre tu Plubot o cómo empezar."
)
async def mi_plubot(interaction: discord.Interaction) -> None:
    """Muestra información sobre el Plubot del usuario o cómo empezar."""
    await interaction.response.defer(ephemeral=True)

    description_text = (
        f"¡Hola {interaction.user.mention}! Parece que estás listo para explorar el "
        "mundo de Plubot.\nAquí podrás ver el estado de tu Plubot personal, "
        "su progreso y más.\n\n**Próximamente:**\n- Estadísticas detalladas de tu "
        "Plubot.\n- Acceso rápido a tus flujos.\n- ¡Y mucho más!"
    )

    embed = discord.Embed(
        title="Tu Aventura con Plubot",
        description=description_text,
        color=discord.Color.purple(),
    )
    embed.set_footer(text="Plubot - Creando Asistentes Inteligentes")
    await interaction.followup.send(embed=embed)


# --- Función para Iniciar el Bot ---
def run_discord_bot_service() -> None:
    """Inicia el servicio del bot de Discord."""
    if not DISCORD_BOT_TOKEN:
        logger.critical(
            "El bot de Discord no puede iniciar sin DISCORD_BOT_TOKEN_PLUBOT."
        )
        return

    logger.info("Iniciando el servicio del bot de Discord de Plubot...")
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)  # Usamos nuestro propio logger
    except discord.LoginFailure:
        logger.critical(
            "Fallo de inicio de sesión en Discord. Verifica el token del bot."
        )
    except discord.DiscordException:
        logger.critical("Error crítico de Discord al ejecutar el bot", exc_info=True)


if __name__ == "__main__":
    # Esto permite correr el bot directamente para pruebas,
    # pero en producción lo manejarías con tu app Flask o un gestor de procesos.
    logger.info("Ejecutando discord_bot.py directamente para pruebas...")
    run_discord_bot_service()
