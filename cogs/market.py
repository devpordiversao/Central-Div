import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta

from database.db import db

class MarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_auctions.start()
    
    def cog_unload(self):
        self.check_auctions.cancel()
    
    @app_commands.command(name="mercado", description="Vende um item para outro usuário")
    @app_commands.describe(comprador="Quem vai comprar", item="Nome do item", preco="Preço")
    async def mercado(self, interaction: discord.Interaction, comprador: discord.Member, item: str, preco: int):
        # Criar proposta de venda
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Oferta de Venda",
            description=f"{interaction.user.mention} quer vender **{item}** para você!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Preço", value=f"{preco:,} moedas", inline=True)
        embed.add_field(name="Vendedor", value=interaction.user.mention, inline=True)
        
        # Botões de aceitar/recusar
        class OfferView(discord.ui.View):
            def __init__(self, seller, buyer, item, price):
                super().__init__(timeout=60)
                self.seller = seller
                self.buyer = buyer
                self.item = item
                self.price = price
            
            @discord.ui.button(label="✅ Comprar", style=discord.ButtonStyle.green)
            async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != self.buyer:
                    return await interaction.response.send_message("Não é para você!", ephemeral=True)
                
                # Transferir dinheiro
                if db.transfer_money(self.buyer.id, self.seller.id, interaction.guild.id, self.price):
                    await interaction.response.send_message(
                        f"✅ {self.buyer.mention} comprou **{self.item}** de {self.seller.mention} por {self.price:,} moedas!"
                    )
                else:
                    await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
            
            @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.red)
            async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != self.buyer:
                    return await interaction.response.send_message("Não é para você!", ephemeral=True)
                
                await interaction.response.send_message("❌ Oferta recusada.")
                self.stop()
        
        await interaction.response.send_message(
            content=comprador.mention,
            embed=embed,
            view=OfferView(interaction.user, comprador, item, preco)
        )
    
    @app_commands.command(name="leilao", description="Cria um leilão")
    @app_commands.describe(item="Item para leiloar", lance_inicial="Preço inicial", duracao="Duração em horas")
    async def leilao(self, interaction: discord.Interaction, item: str, lance_inicial: int, duracao: int = 24):
        # Criar embed de leilão
        ends_at = datetime.now() + timedelta(hours=duracao)
        
        embed = discord.Embed(
            title=f"🔨 LEILÃO: {item}",
            description=f"Vendedor: {interaction.user.mention}\nLance inicial: {lance_inicial:,} moedas",
            color=discord.Color.gold()
        )
        embed.add_field(name="Termina em", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Lance atual", value=f"{lance_inicial:,}", inline=True)
        
        # Guardar no banco (simplificado - na prática usaria o ID da mensagem)
        # Aqui seria melhor com um sistema mais robusto
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="lance", description="Dá um lance no leilão")
    @app_commands.describe(valor="Valor do lance")
    async def lance(self, interaction: discord.Interaction, valor: int):
        # Sistema simplificado - em produção usar botões no embed do leilão
        await interaction.response.send_message("Use os botões no embed do leilão!", ephemeral=True)
    
    @tasks.loop(minutes=1)
    async def check_auctions(self):
        """Verifica leilões encerrados"""
        # Implementação de finalização automática
        pass

async def setup(bot):
    await bot.add_cog(MarketCog(bot))
