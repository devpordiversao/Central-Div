import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from database.db import db

class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="loja", description="Cria ou lista lojas")
    @app_commands.describe(nome="Nome da loja", descricao="Descrição")
    async def loja(self, interaction: discord.Interaction, nome: str = None, descricao: str = ""):
        guild_id = interaction.guild.id
        
        if nome:
            # Criar loja
            shop_id = db.create_shop(guild_id, interaction.user.id, nome, descricao)
            
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Loja Criada!",
                description=f"**{nome}**\nID: `{shop_id}`\n{descricao}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            # Listar lojas
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM shops WHERE guild_id = ?', (guild_id,))
            shops = cursor.fetchall()
            conn.close()
            
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Lojas do Servidor",
                color=discord.Color.blue()
            )
            
            for shop in shops:
                owner = interaction.guild.get_member(shop[2])
                tipo = "🏛️ Oficial" if shop[5] else "🏪 Player"
                embed.add_field(
                    name=f"{tipo} {shop[3]}",
                    value=f"Dono: {owner.mention if owner else 'Desconhecido'}\nID: `{shop[0]}`",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="item", description="Cria um item para venda")
    @app_commands.describe(
        loja="ID da loja",
        nome="Nome do item",
        preco="Preço",
        estoque="Quantidade (-1 = infinito)",
        efeito="Efeito especial (cargo/canal/boost)"
    )
    async def item(self, interaction: discord.Interaction, loja: int, nome: str, preco: int, 
                   estoque: int = -1, efeito: str = None):
        # Verificar se é dono da loja
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT owner_id FROM shops WHERE shop_id = ?', (loja,))
        shop = cursor.fetchone()
        conn.close()
        
        if not shop or (shop[0] != interaction.user.id and not interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message("❌ Você não é dono desta loja!", ephemeral=True)
        
        item_id = db.create_item(loja, nome, preco, stock=estoque, effect_type=efeito)
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Item Criado",
            description=f"**{nome}**\nPreço: {preco:,} moedas",
            color=discord.Color.green()
        )
        if estoque > 0:
            embed.add_field(name="Estoque", value=str(estoque), inline=True)
        if efeito:
            embed.add_field(name="Efeito", value=efeito, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="comprar", description="Compra um item")
    @app_commands.describe(item_id="ID do item")
    async def comprar(self, interaction: discord.Interaction, item_id: int):
        item, msg = db.buy_item(interaction.user.id, interaction.guild.id, item_id)
        
        if not item:
            return await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        
        # Aplicar efeito se tiver
        if item[6]:  # effect_type
            await self.apply_item_effect(interaction, item)
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Compra Realizada",
            description=f"Você comprou **{item[2]}**!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    async def apply_item_effect(self, interaction, item):
        """Aplica efeitos de itens (cargo, canal, etc)"""
        effect_type = item[6]
        effect_data = item[7]
        
        if effect_type == "cargo":
            role = interaction.guild.get_role(int(effect_data))
            if role:
                await interaction.user.add_roles(role)
        
        elif effect_type == "canal":
            channel = interaction.guild.get_channel(int(effect_data))
            if channel:
                await channel.set_permissions(interaction.user, view_channel=True)
        
        elif effect_type == "boost":
            # Boost temporário de XP ou outro benefício
            pass
    
    @app_commands.command(name="estoque", description="Gerencia estoque da loja")
    @app_commands.describe(loja_id="ID da loja", item_id="ID do item", quantidade="Nova quantidade")
    async def estoque(self, interaction: discord.Interaction, loja_id: int, item_id: int, quantidade: int):
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Verificar dono
        cursor.execute('SELECT owner_id FROM shops WHERE shop_id = ?', (loja_id,))
        shop = cursor.fetchone()
        
        if not shop or shop[0] != interaction.user.id:
            conn.close()
            return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
        
        cursor.execute('UPDATE items SET stock = ? WHERE item_id = ? AND shop_id = ?',
                      (quantidade, item_id, loja_id))
        
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"✅ Estoque do item `{item_id}` atualizado para {quantidade}!")

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
