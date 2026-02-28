from discord.ext import commands
import discord
from datetime import datetime

class LogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_log(self, guild, embed):
        """Envia log para o canal configurado"""
        channel_id = self.bot.get_logs_channel(guild.id)
        
        if not channel_id:
            # Tentar encontrar canal padrão
            for channel in guild.text_channels:
                if "central-logs" in channel.name or "logs" in channel.name:
                    self.bot.set_logs_channel(guild.id, channel.id)
                    channel_id = channel.id
                    break
        
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except:
                    pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log de mensagens deletadas"""
        if message.author.bot or not message.guild:
            return
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Mensagem Deletada",
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Autor", value=message.author.mention, inline=True)
        embed.add_field(name="Canal", value=message.channel.mention, inline=True)
        
        if message.content:
            embed.add_field(name="Conteúdo", value=message.content[:1024] or "Sem conteúdo", inline=False)
        
        if message.attachments:
            embed.add_field(
                name="Anexos", 
                value="\n".join([att.url for att in message.attachments[:5]]),
                inline=False
            )
        
        embed.set_thumbnail(url=message.author.display_avatar.url)
        
        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log de mensagens editadas"""
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Mensagem Editada",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Autor", value=before.author.mention, inline=True)
        embed.add_field(name="Canal", value=before.channel.mention, inline=True)
        embed.add_field(name="Antes", value=before.content[:1024] or "Sem conteúdo", inline=False)
        embed.add_field(name="Depois", value=after.content[:1024] or "Sem conteúdo", inline=False)
        embed.add_field(name="Link", value=f"[Ir para mensagem]({after.jump_url})", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        
        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Log de bans (não via comando)"""
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Usuário Banido (Nativo)",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Usuário", value=f"{user} ({user.mention})", inline=True)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Log de unbans"""
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Usuário Desbanido",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Usuário", value=f"{user}", inline=True)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log de entrada"""
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Novo Membro",
            description=f"{member.mention} entrou no servidor!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Conta criada em", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log de saída"""
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Membro Saiu",
            description=f"{member} saiu do servidor.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await self.send_log(member.guild, embed)

async def setup(bot):
    await bot.add_cog(LogsCog(bot))
