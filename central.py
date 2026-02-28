import discord
from discord.ext import commands
import asyncio
import os
import json
from datetime import datetime, timedelta
import aiohttp

# Configurações
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True

# Prefixo e configurações
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

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

class CentralDiv(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='/',
            intents=intents,
            help_command=None,
            application_id=None  # Será definido automaticamente
        )
        self.warns = {}  # Sistema de warns {guild_id: {user_id: count}}
        self.muted_users = {}  # Usuários mutados temporariamente
        self.logs_channels = {}  # Canais de logs {guild_id: channel_id}
        
    async def setup_hook(self):
        # Carregar cogs
        await self.load_extension('cogs.moderation')
        await self.load_extension('cogs.automod')
        await self.load_extension('cogs.logs')
        
        # Sincronizar comandos de barra (slash commands)
        try:
            synced = await self.tree.sync()
            print(f"✅ Sincronizados {len(synced)} comandos de barra!")
        except Exception as e:
            print(f"❌ Erro ao sincronizar comandos: {e}")
    
    async def on_ready(self):
        print(f'🤖 Bot {self.user} está online!')
        print(f'📊 Em {len(self.guilds)} servidores')
        print(f'👥 Total de usuários: {sum(g.member_count for g in self.guilds)}')
        
        # Status personalizado
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="servidor | /help"
            ),
            status=discord.Status.online
        )

    async def on_guild_join(self, guild):
        """Cria canal de logs padrão ao entrar em um servidor"""
        try:
            # Tentar criar canal de logs
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            
            logs_channel = await guild.create_text_channel(
                '📋│central-logs',
                overwrites=overwrites,
                reason="Canal de logs automático do CentralDiv"
            )
            
            self.logs_channels[guild.id] = logs_channel.id
            
            # Embed de boas-vindas
            embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} CentralDiv Configurado!",
                description="Obrigado por adicionar o CentralDiv! 🎉",
                color=GREEN_COLOR
            )
            embed.add_field(
                name="📋 Canal de Logs",
                value=f"Canal padrão criado: {logs_channel.mention}\nUse `/setlogs` para mudar.",
                inline=False
            )
            embed.add_field(
                name="🔧 Comandos Principais",
                value="`/ban` `/kick` `/mute` `/warn` `/logs` `/setlogs` `/automod`",
                inline=False
            )
            embed.add_field(
                name="🛡️ Proteções Ativas",
                value="Anti-Spam, Anti-Raid, Filtro de Palavrões, Detecção NSFW",
                inline=False
            )
            
            await logs_channel.send(embed=embed)
            
        except discord.Forbidden:
            print(f"Sem permissão para criar canal em {guild.name}")
        except Exception as e:
            print(f"Erro ao configurar guild: {e}")

    def get_logs_channel(self, guild_id):
        """Retorna o canal de logs do servidor"""
        return self.logs_channels.get(guild_id)

    def set_logs_channel(self, guild_id, channel_id):
        """Define o canal de logs do servidor"""
        self.logs_channels[guild_id] = channel_id

# Instância do bot
bot = CentralDiv()

# ==================== COMANDOS DE MODERAÇÃO ====================

@bot.tree.command(name="ban", description="Bane um usuário do servidor")
@discord.app_commands.describe(
    usuario="Usuário a ser banido",
    motivo="Motivo do banimento"
)
@discord.app_commands.checks.has_permissions(ban_members=True)
async def ban_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
    """Comando /ban - Bane um usuário"""
    
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message(
            "❌ Você não pode banir alguém com cargo igual ou superior ao seu!",
            ephemeral=True
        )
    
    if usuario == interaction.guild.me:
        return await interaction.response.send_message(
            "❌ Não posso me banir!",
            ephemeral=True
        )
    
    try:
        # Criar embed de ban
        embed = discord.Embed(
            title=f"{CUSTOM_EMOJI} Usuário Banido",
            color=RED_COLOR,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="🔨 Banido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 ID do Usuário", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=BAN_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        # Banir o usuário
        await usuario.ban(reason=f"Banido por {interaction.user}: {motivo}")
        
        # Enviar embed
        await interaction.response.send_message(embed=embed)
        
        # Log
        await bot.get_cog('LogsCog').send_log(interaction.guild, embed)
        
        # Tentar DM
        try:
            dm_embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Você foi banido",
                description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}",
                color=RED_COLOR
            )
            await usuario.send(embed=dm_embed)
        except:
            pass
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para banir este usuário!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

@bot.tree.command(name="kick", description="Expulsa um usuário do servidor")
@discord.app_commands.describe(
    usuario="Usuário a ser expulso",
    motivo="Motivo da expulsão"
)
@discord.app_commands.checks.has_permissions(kick_members=True)
async def kick_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
    """Comando /kick - Expulsa um usuário"""
    
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message(
            "❌ Você não pode expulsar alguém com cargo igual ou superior ao seu!",
            ephemeral=True
        )
    
    try:
        embed = discord.Embed(
            title=f"{CUSTOM_EMOJI} Usuário Expulso",
            color=RED_COLOR,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="👢 Expulso por", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 ID do Usuário", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=KICK_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        await usuario.kick(reason=f"Expulso por {interaction.user}: {motivo}")
        await interaction.response.send_message(embed=embed)
        
        # Log
        await bot.get_cog('LogsCog').send_log(interaction.guild, embed)
        
        # DM
        try:
            dm_embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Você foi expulso",
                description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}",
                color=RED_COLOR
            )
            await usuario.send(embed=dm_embed)
        except:
            pass
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para expulsar este usuário!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

@bot.tree.command(name="mute", description="Silencia um usuário temporariamente")
@discord.app_commands.describe(
    usuario="Usuário a ser mutado",
    tempo="Tempo do mute (ex: 10m, 1h, 1d)",
    motivo="Motivo do mute"
)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def mute_command(interaction: discord.Interaction, usuario: discord.Member, tempo: str, motivo: str = "Não especificado"):
    """Comando /mute - Silencia um usuário"""
    
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message(
            "❌ Você não pode mutar alguém com cargo igual ou superior ao seu!",
            ephemeral=True
        )
    
    # Converter tempo para segundos
    time_convert = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    try:
        unit = tempo[-1].lower()
        value = int(tempo[:-1])
        seconds = value * time_convert[unit]
    except:
        return await interaction.response.send_message(
            "❌ Formato de tempo inválido! Use: `10m`, `1h`, `1d`",
            ephemeral=True
        )
    
    try:
        # Criar cargo de mute se não existir
        mute_role = discord.utils.get(interaction.guild.roles, name="🔇 Muted")
        
        if not mute_role:
            mute_role = await interaction.guild.create_role(
                name="🔇 Muted",
                reason="Cargo para usuários mutados",
                color=discord.Color.dark_grey()
            )
            
            # Configurar permissões do cargo em todos os canais
            for channel in interaction.guild.channels:
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(
                        mute_role,
                        send_messages=False,
                        add_reactions=False,
                        speak=False,
                        reason="Configuração do cargo Muted"
                    )
        
        # Adicionar cargo ao usuário
        await usuario.add_roles(mute_role, reason=f"Mutado por {interaction.user}: {motivo}")
        
        # Timeout nativo do Discord (mais eficaz)
        duration = timedelta(seconds=seconds)
        await usuario.timeout(duration, reason=f"Mutado por {interaction.user}: {motivo}")
        
        # Criar embed
        embed = discord.Embed(
            title=f"{CUSTOM_EMOJI} Usuário Mutado",
            color=RED_COLOR,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="🔇 Mutado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Duração", value=tempo, inline=True)
        embed.add_field(name="🆔 ID do Usuário", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=MUTE_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        await interaction.response.send_message(embed=embed)
        
        # Log
        await bot.get_cog('LogsCog').send_log(interaction.guild, embed)
        
        # DM
        try:
            dm_embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Você foi mutado",
                description=f"**Servidor:** {interaction.guild.name}\n**Tempo:** {tempo}\n**Motivo:** {motivo}",
                color=RED_COLOR
            )
            await usuario.send(embed=dm_embed)
        except:
            pass
        
        # Agendar desmute
        await asyncio.sleep(seconds)
        if mute_role in usuario.roles:
            await usuario.remove_roles(mute_role, reason="Tempo do mute expirado")
            unmute_embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Usuário Desmutado",
                description=f"{usuario.mention} foi desmutado automaticamente.",
                color=GREEN_COLOR,
                timestamp=datetime.now()
            )
            await bot.get_cog('LogsCog').send_log(interaction.guild, unmute_embed)
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão suficientes!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

@bot.tree.command(name="unmute", description="Remove o mute de um usuário")
@discord.app_commands.describe(usuario="Usuário a ser desmutado")
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def unmute_command(interaction: discord.Interaction, usuario: discord.Member):
    """Remove o mute de um usuário"""
    try:
        mute_role = discord.utils.get(interaction.guild.roles, name="🔇 Muted")
        
        if mute_role and mute_role in usuario.roles:
            await usuario.remove_roles(mute_role)
            await usuario.timeout(None)  # Remove timeout nativo
        
        embed = discord.Embed(
            title=f"{CUSTOM_EMOJI} Usuário Desmutado",
            color=GREEN_COLOR,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="✅ Desmutado por", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=usuario.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        await bot.get_cog('LogsCog').send_log(interaction.guild, embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

@bot.tree.command(name="warn", description="Adiciona um aviso a um usuário")
@discord.app_commands.describe(
    usuario="Usuário a ser avisado",
    motivo="Motivo do aviso"
)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def warn_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    """Sistema de warns"""
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    
    if guild_id not in bot.warns:
        bot.warns[guild_id] = {}
    
    if user_id not in bot.warns[guild_id]:
        bot.warns[guild_id][user_id] = 0
    
    bot.warns[guild_id][user_id] += 1
    warn_count = bot.warns[guild_id][user_id]
    
    # Embed para o moderador
    mod_embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} Warn Aplicado",
        color=YELLOW_COLOR,
        timestamp=datetime.now()
    )
    mod_embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
    mod_embed.add_field(name="⚠️ Warns Totais", value=f"`{warn_count}/3`", inline=True)
    mod_embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    mod_embed.set_thumbnail(url=usuario.display_avatar.url)
    
    await interaction.response.send_message(embed=mod_embed)
    await bot.get_cog('LogsCog').send_log(interaction.guild, mod_embed)
    
    # Embed para o usuário (DM)
    try:
        user_embed = discord.Embed(
            title=f"{CUSTOM_EMOJI} Você recebeu um aviso",
            description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}\n**Warns:** {warn_count}/3",
            color=YELLOW_COLOR
        )
        
        if warn_count >= 3:
            user_embed.add_field(
                name="🚨 ATENÇÃO",
                value="Você atingiu 3 warns! Próxima infração resultará em mute automático de 1 hora.",
                inline=False
            )
        
        await usuario.send(embed=user_embed)
    except:
        pass
    
    # Auto-mute no 3º warn
    if warn_count >= 3:
        try:
            await usuario.timeout(timedelta(hours=1), reason="3 warns - Mute automático")
            auto_embed = discord.Embed(
                title=f"{CUSTOM_EMOJI} Mute Automático",
                description=f"{usuario.mention} recebeu mute de 1h por atingir 3 warns.",
                color=RED_COLOR
            )
            await interaction.channel.send(embed=auto_embed)
            bot.warns[guild_id][user_id] = 0  # Reset warns
        except:
            pass

@bot.tree.command(name="warns", description="Verifica os warns de um usuário")
@discord.app_commands.describe(usuario="Usuário para verificar warns")
async def warns_command(interaction: discord.Interaction, usuario: discord.Member = None):
    """Ver warns"""
    usuario = usuario or interaction.user
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    
    count = bot.warns.get(guild_id, {}).get(user_id, 0)
    
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} Sistema de Warns",
        color=YELLOW_COLOR
    )
    embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
    embed.add_field(name="⚠️ Warns Atuais", value=f"`{count}/3`", inline=True)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, ephemeral=True if usuario == interaction.user else False)

@bot.tree.command(name="clearwarns", description="Limpa os warns de um usuário")
@discord.app_commands.describe(usuario="Usuário para limpar warns")
@discord.app_commands.checks.has_permissions(administrator=True)
async def clearwarns_command(interaction: discord.Interaction, usuario: discord.Member):
    """Limpa warns"""
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    
    if guild_id in bot.warns and user_id in bot.warns[guild_id]:
        bot.warns[guild_id][user_id] = 0
    
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} Warns Resetados",
        description=f"Todos os warns de {usuario.mention} foram limpos.",
        color=GREEN_COLOR
    )
    await interaction.response.send_message(embed=embed)

# ==================== COMANDOS DE LOGS ====================

@bot.tree.command(name="setlogs", description="Define o canal de logs do servidor")
@discord.app_commands.describe(canal="Canal para enviar os logs")
@discord.app_commands.checks.has_permissions(administrator=True)
async def setlogs_command(interaction: discord.Interaction, canal: discord.TextChannel):
    """Define canal de logs"""
    bot.set_logs_channel(interaction.guild.id, canal.id)
    
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} Canal de Logs Atualizado",
        description=f"Canal de logs definido para: {canal.mention}",
        color=GREEN_COLOR
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="logs", description="Mostra o histórico de moderação recente")
@discord.app_commands.checks.has_permissions(view_audit_log=True)
async def logs_command(interaction: discord.Interaction):
    """Mostra logs de moderação"""
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} Central de Logs",
        description="Use o canal de logs configurado para ver todas as ações.\n\n**Comandos disponíveis:**\n`/ban` `/kick` `/mute` `/warn` `/unmute` `/clearwarns`",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📋 Configuração",
        value=f"Canal atual: <#{bot.get_logs_channel(interaction.guild.id) or 'Não definido'}>",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== COMANDOS EXTRAS ====================

@bot.tree.command(name="say", description="Faz o bot enviar uma mensagem")
@discord.app_commands.describe(mensagem="Mensagem a ser enviada", canal="Canal de destino (opcional)")
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def say_command(interaction: discord.Interaction, mensagem: str, canal: discord.TextChannel = None):
    """Comando say"""
    target = canal or interaction.channel
    await target.send(mensagem)
    await interaction.response.send_message(f"✅ Mensagem enviada em {target.mention}!", ephemeral=True)

@bot.tree.command(name="embed", description="Cria um embed personalizado")
@discord.app_commands.describe(
    titulo="Título do embed",
    descricao="Descrição do embed",
    cor="Cor em hexadecimal (ex: ff0000)",
    canal="Canal de destino"
)
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def embed_command(
    interaction: discord.Interaction, 
    titulo: str, 
    descricao: str, 
    cor: str = "ff0000",
    canal: discord.TextChannel = None
):
    """Cria embed personalizado"""
    target = canal or interaction.channel
    
    try:
        color = int(cor.replace("#", ""), 16)
    except:
        color = RED_COLOR
    
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} {titulo}",
        description=descricao,
        color=color,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Enviado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
    
    await target.send(embed=embed)
    await interaction.response.send_message(f"✅ Embed enviado em {target.mention}!", ephemeral=True)

@bot.tree.command(name="help", description="Mostra todos os comandos disponíveis")
async def help_command(interaction: discord.Interaction):
    """Menu de ajuda"""
    embed = discord.Embed(
        title=f"{CUSTOM_EMOJI} CentralDiv - Painel de Ajuda",
        description="Bot de moderação avançada para servidores Discord",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Moderação
    mod_text = """
    `/ban @user motivo` - Bane permanentemente
    `/kick @user motivo` - Expulsa do servidor  
    `/mute @user tempo motivo` - Silencia temporariamente (ex: 10m, 1h, 1d)
    `/unmute @user` - Remove o mute
    `/warn @user motivo` - Adiciona aviso (3 warns = mute 1h)
    `/warns @user` - Verifica warns do usuário
    `/clearwarns @user` - Limpa todos os warns (Admin)
    """
    embed.add_field(name="🛡️ Moderação", value=mod_text, inline=False)
    
    # Logs
    logs_text = """
    `/setlogs #canal` - Define canal de logs
    `/logs` - Ver configuração atual
    """
    embed.add_field(name="📋 Logs", value=logs_text, inline=False)
    
    # Utilidades
    util_text = """
    `/say mensagem #canal` - Envia mensagem como bot
    `/embed título descrição cor #canal` - Cria embed personalizado
    `/help` - Mostra este painel
    """
    embed.add_field(name="🔧 Utilidades", value=util_text, inline=False)
    
    # AutoMod
    automod_text = """
    🚫 Anti-Spam (bloqueia flood)
    🚫 Anti-Raid (proteção contra raids)
    🚫 Filtro de Palavrões (warn automático)
    🚫 Detecção de NSFW (imagens inapropriadas)
    """
    embed.add_field(name="🤖 AutoMod", value=automod_text, inline=False)
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="CentralDiv • Bot de Moderação Profissional")
    
    await interaction.response.send_message(embed=embed)

# Tratamento de erros
@ban_command.error
@kick_command.error
@mute_command.error
async def mod_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando!", ephemeral=True)

# Iniciar bot
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
        exit(1)
    
    bot.run(token)
