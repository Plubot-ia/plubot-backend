# plubot-backend/services/discord_bot.py
import discord
from discord.ext import commands
from discord import app_commands # Para comandos Slash
import os
import requests
import logging
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Configuración ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN_PLUBOT")
FLASK_API_BASE_URL = os.getenv("FLASK_API_URL", "http://localhost:5000/api") # Ajusta si es necesario
# GUILD_ID = os.getenv("DISCORD_GUILD_ID") # Opcional: Para registrar comandos más rápido en un servidor de pruebas

if not DISCORD_BOT_TOKEN:
    logger.error("CRÍTICO: DISCORD_BOT_TOKEN_PLUBOT no está configurado.")
    # Podrías querer que el programa termine aquí si el token no está presente
    # exit() 

# --- Intents del Bot ---
# Define los intents que tu bot necesita. Sé lo más específico posible.
intents = discord.Intents.default()
intents.message_content = True  # Para leer mensajes (ej. para XP)
intents.members = True          # Para eventos de miembros, roles
# intents.presences = False      # Generalmente no necesario a menos que rastrees actividad específica

# --- Inicialización del Bot ---
# Usamos commands.Bot para tener tanto comandos slash como potencialmente comandos de prefijo para admin
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!plubotadmin_"), intents=intents)

# --- Eventos del Bot ---
@bot.event
async def on_ready():
    logger.info(f"Plubot (Discord Bot) conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"Latencia con Discord: {bot.latency*1000:.2f} ms")
    try:
        # Si tienes un GUILD_ID para pruebas, los comandos se actualizan casi instantáneamente
        # if GUILD_ID:
        #     guild = discord.Object(id=GUILD_ID)
        #     synced = await bot.tree.sync(guild=guild)
        # else:
        #     synced = await bot.tree.sync() # Sincronización global, puede tardar hasta 1 hora
        synced = await bot.tree.sync()
        logger.info(f"Sincronizados {len(synced)} comandos slash.")
        for cmd in synced:
            logger.info(f"  - Comando '{cmd.name}' sincronizado.")
    except Exception as e:
        logger.error(f"Error al sincronizar comandos slash: {e}", exc_info=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: # Ignorar mensajes de otros bots (incluido él mismo)
        return

    # Aquí irá la lógica para otorgar XP, procesar contenido, etc.
    # Ejemplo: Otorgar XP por mensaje
    discord_user_id = str(message.author.id)
    xp_to_add = 5 # O una cantidad variable

    try:
        # Preparamos la llamada a nuestro backend Flask
        api_url = f"{FLASK_API_BASE_URL}/discord/user_xp"
        payload = {
            "discord_user_id": discord_user_id,
            "discord_username": message.author.name, # Útil para logs o crear perfil
            "xp_to_add": xp_to_add,
            "guild_id": str(message.guild.id) if message.guild else None,
            "channel_id": str(message.channel.id)
        }
        # Podrías añadir un token de API aquí para seguridad entre bot y backend
        # headers = {"Authorization": f"Bearer {os.getenv('DISCORD_BOT_API_SECRET')}"}
        
        # Deferir la respuesta si vas a enviar un mensaje de confirmación
        # async with message.channel.typing(): # Muestra "Bot está escribiendo..."
        
        response = requests.post(api_url, json=payload, timeout=10) # headers=headers
        response.raise_for_status() # Lanza error para respuestas 4xx/5xx
        
        response_data = response.json()
        logger.info(f"XP update response for {discord_user_id}: {response_data.get('message')}")
        
        # Opcional: Enviar confirmación o feedback al usuario
        # new_xp = response_data.get('new_xp')
        # new_level = response_data.get('new_level')
        # if new_level:
        #    await message.channel.send(f"¡Felicidades {message.author.mention}, has subido al Nivel {new_level} y ahora tienes {new_xp} XP!")
        # elif response_data.get('xp_added'):
        #    await message.channel.send(f"{message.author.mention} ha ganado {xp_to_add} XP. Total: {new_xp} XP.", delete_after=15)


    except requests.exceptions.Timeout:
        logger.warning(f"Timeout al intentar actualizar XP para {discord_user_id} en {api_url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de red al actualizar XP para {discord_user_id}: {e}")
    except Exception as e:
        logger.error(f"Error inesperado en on_message al procesar XP para {discord_user_id}: {e}", exc_info=True)

    # Importante para que los comandos de prefijo (si los usas) sigan funcionando
    await bot.process_commands(message)


# --- Comandos Slash de Ejemplo ---
@bot.tree.command(name="plubot_ping", description="Verifica la conexión con el bot y el backend de Plubot.")
async def plubot_ping(interaction: discord.Interaction):
    """Verifica la conexión y latencia con el bot y el backend de Plubot."""
    await interaction.response.defer(ephemeral=False) # ephemeral=True para solo visible al usuario

    bot_latency = bot.latency * 1000
    embed = discord.Embed(title="🏓 ¡Pong! - Estado de Plubot", color=discord.Color.blue())
    embed.add_field(name="Latencia del Bot de Discord", value=f"{bot_latency:.2f} ms", inline=False)

    try:
        api_url = f"{FLASK_API_BASE_URL}/discord/status"
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        backend_data = response.json()
        backend_status = backend_data.get("message", "No se pudo obtener mensaje.")
        backend_operational = backend_data.get("backend_status", "desconocido") == "ok"
        
        embed.add_field(name="Estado del Backend Flask", 
                        value=f"{'✅ Operativo' if backend_operational else '⚠️ Problemas'}", 
                        inline=True)
        embed.add_field(name="Mensaje del Backend", value=backend_status, inline=True)

    except requests.exceptions.Timeout:
        embed.add_field(name="Estado del Backend Flask", value="❌ Timeout", inline=True)
        embed.add_field(name="Mensaje del Backend", value="El backend no respondió a tiempo.", inline=True)
        embed.color = discord.Color.orange()
    except requests.exceptions.RequestException as e:
        embed.add_field(name="Estado del Backend Flask", value="❌ Error de Conexión", inline=True)
        embed.add_field(name="Mensaje del Backend", value=f"No se pudo contactar al backend: {type(e).__name__}", inline=True)
        embed.color = discord.Color.red()
        logger.error(f"Error en plubot_ping al contactar API: {e}")
    
    embed.set_footer(text=f"Plubot | Solicitado por {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="mi_plubot", description="Muestra información sobre tu Plubot o cómo empezar.")
async def mi_plubot(interaction: discord.Interaction):
    """Muestra información sobre el Plubot del usuario o cómo empezar."""
    await interaction.response.defer(ephemeral=True)
    discord_user_id = str(interaction.user.id)
    
    # Aquí llamarías a tu backend para obtener información del Plubot del usuario
    # Ejemplo:
    # response = requests.get(f"{FLASK_API_BASE_URL}/discord/user/{discord_user_id}/plubot_info")
    # if response.status_code == 200:
    #    plubot_data = response.json()
    #    embed = discord.Embed(title=f"Tu Plubot: {plubot_data.get('name', 'Sin Nombre')}", color=discord.Color.green())
    #    embed.add_field(name="Nivel", value=plubot_data.get('level', 1))
    #    embed.add_field(name="XP", value=plubot_data.get('xp', 0))
    #    embed.add_field(name="Última actividad", value=plubot_data.get('last_active', 'N/A'))
    #    await interaction.followup.send(embed=embed)
    # else:
    #    await interaction.followup.send("No pude encontrar información de tu Plubot. ¿Ya has interactuado con Plubot antes? Puedes empezar enviando mensajes o usando `/entrenar`.")
    
    # Placeholder:
    embed = discord.Embed(
        title="Tu Aventura con Plubot",
        description=(
            f"¡Hola {interaction.user.mention}! Parece que estás listo para explorar el mundo de Plubot.\n"
            "Aquí podrás ver el estado de tu Plubot personal, su progreso y más.\n\n"
            "**Próximamente:**\n"
            "- Estadísticas detalladas de tu Plubot.\n"
            "- Acceso rápido a tus flujos.\n"
            "- ¡Y mucho más!"
        ),
        color=discord.Color.purple()
    )
    embed.set_footer(text="Plubot - Creando Asistentes Inteligentes")
    await interaction.followup.send(embed=embed)


# --- Función para Iniciar el Bot ---
def run_discord_bot_service():
    if not DISCORD_BOT_TOKEN:
        logger.critical("El bot de Discord no puede iniciar sin DISCORD_BOT_TOKEN_PLUBOT.")
        return

    logger.info(f"Iniciando el servicio del bot de Discord de Plubot...")
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None) # Usamos nuestro propio logger
    except discord.LoginFailure:
        logger.critical("Fallo de inicio de sesión en Discord. Verifica el token del bot.")
    except Exception as e:
        logger.critical(f"Error crítico al ejecutar el bot de Discord: {e}", exc_info=True)

if __name__ == "__main__":
    # Esto permite correr el bot directamente para pruebas,
    # pero en producción lo manejarías con tu app Flask o un gestor de procesos.
    logger.info("Ejecutando discord_bot.py directamente para pruebas...")
    run_discord_bot_service()
