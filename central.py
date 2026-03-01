import discord
from discord.ext import commands
import asyncio
import os
import json
from datetime import datetime, timedelta

# Configurações
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.presences = True
intents.voice_states = True

# Emoji personalizado para todos os embeds
CUSTOM_EMOJI = "<:emoji_4:1477359221623488714>"

# URLs das imagens
BAN_IMAGE = "https://i.imgur.com/trMtxGd.png"
KICK_IMAGE = "https://i.imgur.com/FNRpVoC.jpeg"
MUTE_IMAGE = "https://i.imgur.com/4oAhr1M.png"

# Cores dos embeds
RED_COLOR = discord.Color.red()
GREEN_COLOR = discord.Color.green()
YELLOW_COLOR = discord.Color.gold()
BLUE_COLOR = discord.Color.blue()
GOLD_COLOR = discord.Color.gold()

class CentralDiv(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='/',
            intents=intents,
            help_command=None
        )
        self.CUSTOM_EMOJI = CUSTOM_EMOJI
        self.warns = {}
        self.muted_users = {}
        self.logs_channels = {}
        
    async def setup_hook(self):
        # Carregar cogs
        cogs = [
            'cogs.moderation',
            'cogs.automod',
            'cogs.logs',
            'cogs.economy',
            'cogs.shop',
            'cogs.market',
            'cogs.graphics',
            'cogs.server_management',
            'cogs.creative_punishments'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ {cog} carregado!")
            except Exception as e:
                print(f"❌ Erro em {cog}: {e}")
        
        # Sincronizar comandos
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos sincronizados!")
        except Exception as e:
            print(f"❌ Erro ao sincronizar: {e}")
    
    async def on_ready(self):
        print(f'🤖 {self.user} online!')
        print(f'📊 {len(self.guilds)} servidores')
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="economia & moderação | /help"
            ),
            status=discord.Status.online
        )

    def get_logs_channel(self, guild_id):
        return self.logs_channels.get(guild_id)

    def set_logs_channel(self, guild_id, channel_id):
        self.logs_channels[guild_id] = channel_id

# Instância do bot
bot = CentralDiv()

# Eventos básicos
@bot.event
async def on_member_join(member):
    """Boas-vindas e onboarding"""
    # Criar conta bancária automaticamente
    from database.db import db
    db.get_or_create_user(member.id, member.guild.id)
    
    # Canal de boas-vindas (simplificado)
    for channel in member.guild.text_channels:
        if "bem-vindo" in channel.name or "welcome" in channel.name:
            embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Bem-vindo!",
                description=f"{member.mention} entrou no servidor!\n\nUse `/carteira` para ver seu saldo inicial.",
                color=GREEN_COLOR
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
            break

@bot.tree.command(name="help", description="Painel de ajuda completo")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} CentralDiv - Central de Ajuda",
        description="Bot completo de moderação, economia e gestão",
        color=BLUE_COLOR,
        timestamp=datetime.now()
    )
    
    # Categorias
    categories = {
        "🛡️ Moderação": "`/ban` `/kick` `/mute` `/warn` `/unmute` `/clearwarns`",
        "💰 Economia": "`/banco` `/carteira` `/transferir` `/trabalhar` `/investir` `/missao`",
        "🏪 Loja": "`/loja` `/item` `/comprar` `/estoque`",
        "🔨 Mercado": "`/mercado` `/leilao` `/lance`",
        "📊 Gráficos": "`/grafico` `/ranking`",
        "⚙️ Gestão": "`/onboarding` `/backup` `/cargo_temporario` `/criar_estrutura`",
        "🔒 Punições+": "`/isolate` `/demote` `/readonly` `/jailmode` `/audit`",
        "📋 Utilidades": "`/logs` `/setlogs` `/say` `/embed`"
    }
    
    for name, value in categories.items():
        embed.add_field(name=name, value=value, inline=False)
    
    embed.set_footer(text="CentralDiv v2.0 • Sistema Econômico Completo")
    
    await interaction.response.send_message(embed=embed)

# Iniciar
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN não encontrado!")
        exit(1)
    
    bot.run(token)
