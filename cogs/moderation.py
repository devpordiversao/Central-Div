from discord.ext import commands
import discord

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Comandos de prefixo (backup caso slash commands falhem)
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="Não especificado"):
        await member.ban(reason=reason)
        await ctx.send(f"✅ {member.mention} foi banido!")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="Não especificado"):
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.mention} foi expulso!")

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
