import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

async def setup_hook():
    await bot.load_extension("cogs.music")
    await bot.tree.sync()

    music_cog = bot.cogs["MusicCog"]

    password = os.getenv("WEB_PASSWORD", "")
    port = int(os.getenv("WEB_PORT", "3000"))

    from web.server import WebServer
    web_server = WebServer(music_cog, password=password, port=port)
    await web_server.start()

    music_cog.broadcast_cb = web_server.broadcast_state

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
