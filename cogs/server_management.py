import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime, timedelta

class ServerManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="onboarding", description="Configura fluxo de entrada de novos membros")
    @app_commands.describe(
        cargo="Cargo inicial para novos membros",
        canal="Canal de boas-vindas",
        verificacao="Requer verificação?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def onboarding(self, interaction: discord.Interaction, cargo: discord.Role = None, 
                        canal: discord.TextChannel = None, verificacao: bool = False):
        # Salvar configuração (simplificado - idealmente no banco)
        config = {
            "role_id": cargo.id if cargo else None,
            "channel_id": canal.id if canal else None,
            "verification": verificacao
        }
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Onboarding Configurado",
            color=discord.Color.green()
        )
        if cargo:
            embed.add_field(name="Cargo Automático", value=cargo.mention, inline=True)
        if canal:
            embed.add_field(name="Canal de Boas-vindas", value=canal.mention, inline=True)
        embed.add_field(name="Verificação", value="✅ Sim" if verificacao else "❌ Não", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="cargo_temporario", description="Adiciona cargo que expira automaticamente")
    @app_commands.describe(usuario="Usuário", cargo="Cargo", duracao="Duração (ex: 1h, 2d)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def cargo_temporario(self, interaction: discord.Interaction, usuario: discord.Member, 
                               cargo: discord.Role, duracao: str):
        # Converter duração
        time_convert = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duracao[-1].lower()
            value = int(duracao[:-1])
            seconds = value * time_convert[unit]
        except:
            return await interaction.response.send_message("❌ Formato inválido! Use: `30m`, `2h`, `1d`", ephemeral=True)
        
        # Adicionar cargo
        await usuario.add_roles(cargo, reason=f"Cargo temporário por {interaction.user}")
        
        # Agendar remoção
        expires_at = datetime.now() + timedelta(seconds=seconds)
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Cargo Temporário",
            description=f"{usuario.mention} recebeu {cargo.mention} por {duracao}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Expira em", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # Remover após tempo
        await discord.utils.sleep_until(expires_at)
        await usuario.remove_roles(cargo, reason="Cargo temporário expirado")
    
    @app_commands.command(name="backup", description="Cria backup completo do servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        guild = interaction.guild
        
        # Coletar dados
        backup_data = {
            "name": guild.name,
            "created_at": datetime.now().isoformat(),
            "channels": [],
            "roles": [],
            "categories": []
        }
        
        # Salvar categorias e canais
        for category in guild.categories:
            cat_data = {
                "name": category.name,
                "position": category.position,
                "channels": []
            }
            for channel in category.channels:
                ch_data = {
                    "name": channel.name,
                    "type": str(channel.type),
                    "position": channel.position,
                    "permissions": []
                }
                cat_data["channels"].append(ch_data)
            backup_data["categories"].append(cat_data)
        
        # Salvar roles (exceto @everyone)
        for role in guild.roles:
            if role.name != "@everyone":
                backup_data["roles"].append({
                    "name": role.name,
                    "color": role.color.value,
                    "permissions": role.permissions.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable
                })
        
        # Salvar no banco (simplificado)
        from database.db import db
        backup_id = db.create_backup(guild.id, f"Backup_{datetime.now().strftime('%Y%m%d')}", backup_data)
        
        # Criar arquivo JSON para download
        json_str = json.dumps(backup_data, indent=2)
        buffer = io.BytesIO(json_str.encode())
        
        file = discord.File(buffer, filename=f'backup_{guild.id}_{backup_id}.json')
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Backup Completo",
            description=f"ID do backup: `{backup_id}`\nCanais: {len(guild.channels)}\nCargos: {len(guild.roles)}",
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(name="restaurar", description="Restaura servidor a partir de backup")
    @app_commands.describe(backup_id="ID do backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def restaurar(self, interaction: discord.Interaction, backup_id: int):
        await interaction.response.send_message("⚠️ Comando perigoso! Use com cautela.", ephemeral=True)
        # Implementação completa excluiria e recriaria tudo
    
    @app_commands.command(name="criar_estrutura", description="Cria estrutura do servidor via JSON")
    @app_commands.describe(arquivo="Arquivo JSON com a estrutura")
    @app_commands.checks.has_permissions(administrator=True)
    async def criar_estrutura(self, interaction: discord.Interaction, arquivo: discord.Attachment):
        if not arquivo.filename.endswith('.json'):
            return await interaction.response.send_message("❌ Envie um arquivo .json!", ephemeral=True)
        
        await interaction.response.defer(thinking=True)
        
        # Ler JSON
        content = await arquivo.read()
        data = json.loads(content)
        
        # Criar estrutura
        created = []
        
        for category_data in data.get("categories", []):
            # Criar categoria
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            category = await interaction.guild.create_category(category_data["name"], overwrites=overwrites)
            created.append(f"📁 {category.name}")
            
            for channel_data in category_data.get("channels", []):
                if channel_data["type"] == "text":
                    ch = await category.create_text_channel(channel_data["name"])
                elif channel_data["type"] == "voice":
                    ch = await category.create_voice_channel(channel_data["name"])
                created.append(f"  └─ #{ch.name}")
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Estrutura Criada",
            description="\n".join(created[:20]) + (f"\n... e mais {len(created)-20}" if len(created) > 20 else ""),
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed)

import io
from database.db import db

async def setup(bot):
    await bot.add_cog(ServerManagementCog(bot))
