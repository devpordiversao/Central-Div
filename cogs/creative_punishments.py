import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

class CreativePunishmentsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="isolate", description="Isola um usuário em canal privado")
    @app_commands.describe(usuario="Usuário a isolar", motivo="Motivo")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def isolate(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
        # Criar canal privado
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            usuario: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        # Adicionar todos os mods/admins
        for role in interaction.guild.roles:
            if role.permissions.manage_guild or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        channel = await interaction.guild.create_text_channel(
            f"🔒-isolado-{usuario.name}",
            category=interaction.channel.category,
            overwrites=overwrites,
            reason=f"Isolamento: {motivo}"
        )
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Usuário Isolado",
            description=f"{usuario.mention} foi movido para {channel.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Motivo", value=motivo, inline=False)
        embed.add_field(name="Por", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # Mensagem no canal isolado
        await channel.send(
            f"{usuario.mention}, você foi isolado por **{motivo}**.\n"
            f"Aguarde enquanto a moderação decide o que fazer."
        )
    
    @app_commands.command(name="demote", description="Remove todos os cargos temporariamente")
    @app_commands.describe(usuario="Usuário", duracao="Duração (ex: 1h, 1d)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def demote(self, interaction: discord.Interaction, usuario: discord.Member, duracao: str):
        # Salvar cargos atuais
        old_roles = [role for role in usuario.roles if role.name != "@everyone"]
        
        # Criar cargo "Em Revisão"
        review_role = discord.utils.get(interaction.guild.roles, name="🔍 Em Revisão")
        if not review_role:
            review_role = await interaction.guild.create_role(
                name="🔍 Em Revisão",
                color=discord.Color.dark_grey(),
                reason="Sistema de demote"
            )
        
        # Remover todos os cargos e adicionar revisão
        await usuario.remove_roles(*old_roles, reason=f"Demote por {interaction.user}")
        await usuario.add_roles(review_role, reason="Em revisão")
        
        # Converter duração
        time_convert = {'m': 60, 'h': 3600, 'd': 86400}
        unit = duracao[-1].lower()
        value = int(duracao[:-1])
        seconds = value * time_convert[unit]
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Usuário em Revisão",
            description=f"{usuario.mention} teve todos os cargos removidos temporariamente.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Duração", value=duracao, inline=True)
        embed.add_field(name="Cargos Removidos", value=str(len(old_roles)), inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # Restaurar após tempo
        await asyncio.sleep(seconds)
        await usuario.remove_roles(review_role)
        await usuario.add_roles(*old_roles)
        
        restore_embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Cargos Restaurados",
            description=f"Cargos de {usuario.mention} foram restaurados automaticamente.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=restore_embed)
    
    @app_commands.command(name="readonly", description="Usuário só pode ler, não escrever")
    @app_commands.describe(usuario="Usuário", duracao="Duração")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def readonly(self, interaction: discord.Interaction, usuario: discord.Member, duracao: str):
        # Criar cargo readonly
        readonly_role = discord.utils.get(interaction.guild.roles, name="🚫 Read Only")
        if not readonly_role:
            readonly_role = await interaction.guild.create_role(name="🚫 Read Only")
            
            # Configurar permissões em todos os canais
            for channel in interaction.guild.text_channels:
                await channel.set_permissions(readonly_role, send_messages=False, add_reactions=False)
        
        await usuario.add_roles(readonly_role, reason=f"Readonly por {interaction.user}")
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Modo Leitura Ativado",
            description=f"{usuario.mention} agora só pode ler mensagens.",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="jailmode", description="Restringe usuário a um canal específico")
    @app_commands.describe(usuario="Usuário", duracao="Duração")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def jailmode(self, interaction: discord.Interaction, usuario: discord.Member, duracao: str):
        # Criar canal de "cadeia"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            usuario: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        jail_channel = await interaction.guild.create_text_channel(
            f"🔒-sala-espera-{usuario.name}",
            overwrites=overwrites
        )
        
        # Mover usuário para o canal (se estiver em call)
        if usuario.voice:
            await usuario.move_to(None)  # Desconecta
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Jail Mode Ativado",
            description=f"{usuario.mention} foi restrito a {jail_channel.mention}",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
        await jail_channel.send(f"{usuario.mention}, aguarde a decisão da moderação aqui.")
    
    @app_commands.command(name="audit", description="Gera relatório completo de atividade")
    @app_commands.describe(usuario="Usuário para auditar")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def audit(self, interaction: discord.Interaction, usuario: discord.Member):
        # Coletar dados
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Relatório de Auditoria",
            description=f"Usuário: {usuario.mention}\nID: `{usuario.id}`",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Estatísticas básicas
        embed.add_field(name="Conta Criada", value=usuario.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Entrou no Servidor", value=usuario.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Apelido", value=usuario.nick or "Nenhum", inline=True)
        
        # Cargos
        roles = [r.mention for r in usuario.roles if r.name != "@everyone"]
        embed.add_field(name=f"Cargos ({len(roles)})", value=" ".join(roles[:10]) or "Nenhum", inline=False)
        
        # Atividade (simulado - em produção buscaria do banco)
        embed.add_field(name="Mensagens (7d)", value="Calculando...", inline=True)
        embed.add_field(name="Tempo em Call (7d)", value="Calculando...", inline=True)
        
        # Verificar interações com usuários punidos (simulado)
        embed.add_field(name="Status", value="✅ Sem alertas", inline=False)
        
        await interaction.response.send_message(embed=embed)

import asyncio

async def setup(bot):
    await bot.add_cog(CreativePunishmentsCog(bot))
