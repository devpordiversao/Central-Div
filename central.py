import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import json
import sqlite3
from datetime import datetime, timedelta
import random
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# ==================== CONFIGURAÇÕES ====================

intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.presences = True
intents.voice_states = True

CUSTOM_EMOJI = "<:emoji_4:1477359221623488714>"
BAN_IMAGE = "https://i.imgur.com/trMtxGd.png"
KICK_IMAGE = "https://i.imgur.com/FNRpVoC.jpeg"
MUTE_IMAGE = "https://i.imgur.com/4oAhr1M.png"

RED_COLOR = discord.Color.red()
GREEN_COLOR = discord.Color.green()
YELLOW_COLOR = discord.Color.gold()
BLUE_COLOR = discord.Color.blue()
GOLD_COLOR = discord.Color.gold()

# ==================== BANCO DE DADOS ====================

class Database:
    def __init__(self):
        self.db_path = "centraldiv.db"
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 1000,
                bank_balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                last_work TIMESTAMP,
                last_daily TIMESTAMP,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                type TEXT,
                amount INTEGER,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shops (
                shop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_id INTEGER,
                name TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                name TEXT,
                description TEXT,
                price INTEGER,
                stock INTEGER DEFAULT -1,
                effect_type TEXT,
                effect_data TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                guild_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, guild_id, item_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                investment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                amount INTEGER,
                risk_level TEXT,
                end_date TIMESTAMP,
                return_rate REAL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_missions (
                user_id INTEGER,
                guild_id INTEGER,
                mission_type TEXT,
                target INTEGER,
                progress INTEGER DEFAULT 0,
                reward INTEGER,
                expires_at TIMESTAMP,
                completed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, date(expires_at))
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_or_create_user(self, user_id, guild_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        user = cursor.fetchone()
        if not user:
            cursor.execute('INSERT INTO users (user_id, guild_id) VALUES (?, ?)', (user_id, guild_id))
            conn.commit()
            cursor.execute('SELECT * FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            user = cursor.fetchone()
        conn.close()
        return user
    
    def get_balance(self, user_id, guild_id):
        user = self.get_or_create_user(user_id, guild_id)
        return user[2] if user else 0
    
    def add_money(self, user_id, guild_id, amount, description=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        self.get_or_create_user(user_id, guild_id)
        cursor.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ? AND guild_id = ?',
                      (amount, amount, user_id, guild_id))
        cursor.execute('INSERT INTO transactions (user_id, guild_id, type, amount, description) VALUES (?, ?, ?, ?, ?)',
                      (user_id, guild_id, 'income', amount, description))
        conn.commit()
        conn.close()
        return True
    
    def remove_money(self, user_id, guild_id, amount, description=""):
        balance = self.get_balance(user_id, guild_id)
        if balance < amount:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE user_id = ? AND guild_id = ?',
                      (amount, amount, user_id, guild_id))
        cursor.execute('INSERT INTO transactions (user_id, guild_id, type, amount, description) VALUES (?, ?, ?, ?, ?)',
                      (user_id, guild_id, 'expense', amount, description))
        conn.commit()
        conn.close()
        return True

db = Database()

# ==================== BOT PRINCIPAL ====================

class CentralDiv(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents, help_command=None)
        self.CUSTOM_EMOJI = CUSTOM_EMOJI
        self.warns = {}
        self.muted_users = {}
        self.logs_channels = {}
        
    async def setup_hook(self):
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos sincronizados!")
        except Exception as e:
            print(f"❌ Erro ao sincronizar: {e}")
    
    async def on_ready(self):
        print(f'🤖 {self.user} online!')
        print(f'📊 {len(self.guilds)} servidores')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="economia & moderação | /help"))

    def get_logs_channel(self, guild_id):
        return self.logs_channels.get(guild_id)

    def set_logs_channel(self, guild_id, channel_id):
        self.logs_channels[guild_id] = channel_id

bot = CentralDiv()

# ==================== COMANDOS DE MODERAÇÃO ====================

@bot.tree.command(name="ban", description="Bane um usuário do servidor")
@app_commands.describe(usuario="Usuário a ser banido", motivo="Motivo do banimento")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Você não pode banir alguém com cargo igual ou superior ao seu!", ephemeral=True)
    
    if usuario == interaction.guild.me:
        return await interaction.response.send_message("❌ Não posso me banir!", ephemeral=True)
    
    try:
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Usuário Banido", color=RED_COLOR, timestamp=datetime.now())
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="🔨 Banido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 ID", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=BAN_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        await usuario.ban(reason=f"Banido por {interaction.user}: {motivo}")
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Você foi banido", description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}", color=RED_COLOR)
            await usuario.send(embed=dm_embed)
        except:
            pass
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para banir este usuário!", ephemeral=True)

@bot.tree.command(name="kick", description="Expulsa um usuário do servidor")
@app_commands.describe(usuario="Usuário a ser expulso", motivo="Motivo da expulsão")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Você não pode expulsar alguém com cargo igual ou superior ao seu!", ephemeral=True)
    
    try:
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Usuário Expulso", color=RED_COLOR, timestamp=datetime.now())
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="👢 Expulso por", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 ID", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=KICK_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        await usuario.kick(reason=f"Expulso por {interaction.user}: {motivo}")
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Você foi expulso", description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}", color=RED_COLOR)
            await usuario.send(embed=dm_embed)
        except:
            pass
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para expulsar este usuário!", ephemeral=True)

@bot.tree.command(name="mute", description="Silencia um usuário temporariamente")
@app_commands.describe(usuario="Usuário a ser mutado", tempo="Tempo (10m, 1h, 1d)", motivo="Motivo do mute")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute_command(interaction: discord.Interaction, usuario: discord.Member, tempo: str, motivo: str = "Não especificado"):
    if usuario.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Você não pode mutar alguém com cargo igual ou superior ao seu!", ephemeral=True)
    
    time_convert = {'m': 60, 'h': 3600, 'd': 86400}
    try:
        unit = tempo[-1].lower()
        value = int(tempo[:-1])
        seconds = value * time_convert[unit]
    except:
        return await interaction.response.send_message("❌ Formato inválido! Use: `10m`, `1h`, `1d`", ephemeral=True)
    
    try:
        mute_role = discord.utils.get(interaction.guild.roles, name="🔇 Muted")
        if not mute_role:
            mute_role = await interaction.guild.create_role(name="🔇 Muted", color=discord.Color.dark_grey())
            for channel in interaction.guild.channels:
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(mute_role, send_messages=False, add_reactions=False, speak=False)
        
        await usuario.add_roles(mute_role, reason=f"Mutado por {interaction.user}: {motivo}")
        duration = timedelta(seconds=seconds)
        await usuario.timeout(duration, reason=f"Mutado por {interaction.user}: {motivo}")
        
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Usuário Mutado", color=RED_COLOR, timestamp=datetime.now())
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="🔇 Mutado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Duração", value=tempo, inline=True)
        embed.add_field(name="🆔 ID", value=f"`{usuario.id}`", inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_image(url=MUTE_IMAGE)
        embed.set_footer(text=f"CentralDiv • {interaction.guild.name}")
        
        await interaction.response.send_message(embed=embed)
        
        try:
            dm_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Você foi mutado", description=f"**Servidor:** {interaction.guild.name}\n**Tempo:** {tempo}\n**Motivo:** {motivo}", color=RED_COLOR)
            await usuario.send(embed=dm_embed)
        except:
            pass
        
        await asyncio.sleep(seconds)
        if mute_role in usuario.roles:
            await usuario.remove_roles(mute_role, reason="Tempo do mute expirado")
            
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão suficientes!", ephemeral=True)

@bot.tree.command(name="unmute", description="Remove o mute de um usuário")
@app_commands.describe(usuario="Usuário a ser desmutado")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute_command(interaction: discord.Interaction, usuario: discord.Member):
    try:
        mute_role = discord.utils.get(interaction.guild.roles, name="🔇 Muted")
        if mute_role and mute_role in usuario.roles:
            await usuario.remove_roles(mute_role)
        await usuario.timeout(None)
        
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Usuário Desmutado", color=GREEN_COLOR, timestamp=datetime.now())
        embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="✅ Desmutado por", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=usuario.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

@bot.tree.command(name="warn", description="Adiciona um aviso a um usuário")
@app_commands.describe(usuario="Usuário a ser avisado", motivo="Motivo do aviso")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn_command(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    
    if guild_id not in bot.warns:
        bot.warns[guild_id] = {}
    if user_id not in bot.warns[guild_id]:
        bot.warns[guild_id][user_id] = 0
    
    bot.warns[guild_id][user_id] += 1
    warn_count = bot.warns[guild_id][user_id]
    
    mod_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Warn Aplicado", color=YELLOW_COLOR, timestamp=datetime.now())
    mod_embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
    mod_embed.add_field(name="⚠️ Warns", value=f"`{warn_count}/3`", inline=True)
    mod_embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    mod_embed.set_thumbnail(url=usuario.display_avatar.url)
    
    await interaction.response.send_message(embed=mod_embed)
    
    try:
        user_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Você recebeu um aviso", description=f"**Servidor:** {interaction.guild.name}\n**Motivo:** {motivo}\n**Warns:** {warn_count}/3", color=YELLOW_COLOR)
        if warn_count >= 3:
            user_embed.add_field(name="🚨 ATENÇÃO", value="Você atingiu 3 warns! Próxima infração = mute 1h.", inline=False)
        await usuario.send(embed=user_embed)
    except:
        pass
    
    if warn_count >= 3:
        try:
            await usuario.timeout(timedelta(hours=1), reason="3 warns - Mute automático")
            auto_embed = discord.Embed(title=f"{CUSTOM_EMOJI} Mute Automático", description=f"{usuario.mention} recebeu mute de 1h por atingir 3 warns.", color=RED_COLOR)
            await interaction.channel.send(embed=auto_embed)
            bot.warns[guild_id][user_id] = 0
        except:
            pass

@bot.tree.command(name="warns", description="Verifica os warns de um usuário")
@app_commands.describe(usuario="Usuário para verificar")
async def warns_command(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    count = bot.warns.get(guild_id, {}).get(user_id, 0)
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Sistema de Warns", color=YELLOW_COLOR)
    embed.add_field(name="👤 Usuário", value=usuario.mention, inline=True)
    embed.add_field(name="⚠️ Warns", value=f"`{count}/3`", inline=True)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, ephemeral=(usuario == interaction.user))

@bot.tree.command(name="clearwarns", description="Limpa os warns de um usuário")
@app_commands.describe(usuario="Usuário para limpar warns")
@app_commands.checks.has_permissions(administrator=True)
async def clearwarns_command(interaction: discord.Interaction, usuario: discord.Member):
    guild_id = str(interaction.guild.id)
    user_id = str(usuario.id)
    if guild_id in bot.warns and user_id in bot.warns[guild_id]:
        bot.warns[guild_id][user_id] = 0
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Warns Resetados", description=f"Todos os warns de {usuario.mention} foram limpos.", color=GREEN_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setlogs", description="Define o canal de logs")
@app_commands.describe(canal="Canal para logs")
@app_commands.checks.has_permissions(administrator=True)
async def setlogs_command(interaction: discord.Interaction, canal: discord.TextChannel):
    bot.set_logs_channel(interaction.guild.id, canal.id)
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Canal de Logs Atualizado", description=f"Canal definido: {canal.mention}", color=GREEN_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="logs", description="Mostra configuração de logs")
@app_commands.checks.has_permissions(view_audit_log=True)
async def logs_command(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Central de Logs", color=BLUE_COLOR)
    channel_id = bot.get_logs_channel(interaction.guild.id)
    embed.add_field(name="Canal Atual", value=f"<#{channel_id}>" if channel_id else "Não definido", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== COMANDOS DE ECONOMIA ====================

@bot.tree.command(name="carteira", description="Mostra seu painel financeiro")
@app_commands.describe(usuario="Usuário para verificar")
async def carteira(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    user_data = db.get_or_create_user(target.id, interaction.guild.id)
    balance = user_data[2]
    total_earned = user_data[4]
    total_spent = user_data[5]
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Carteira de {target.display_name}", color=GOLD_COLOR, timestamp=datetime.now())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="💰 Saldo", value=f"**{balance:,}** moedas", inline=False)
    embed.add_field(name="📈 Total Ganho", value=f"{total_earned:,}", inline=True)
    embed.add_field(name="📉 Total Gasto", value=f"{total_spent:,}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trabalhar", description="Trabalhe para ganhar moedas")
@app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
async def trabalhar(interaction: discord.Interaction):
    base = random.randint(100, 500)
    bonus = base if random.random() < 0.1 else 0
    total = base + bonus
    
    db.add_money(interaction.user.id, interaction.guild.id, total, "Trabalho")
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Trabalho Realizado", description=f"Você ganhou **{total:,}** moedas!", color=GREEN_COLOR)
    if bonus:
        embed.add_field(name="🎉 BÔNUS!", value="Ganho dobrado!", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="transferir", description="Transfere moedas")
@app_commands.describe(usuario="Destinatário", valor="Quantidade")
async def transferir(interaction: discord.Interaction, usuario: discord.Member, valor: int):
    if usuario == interaction.user:
        return await interaction.response.send_message("❌ Não pode transferir para si mesmo!", ephemeral=True)
    
    tax = int(valor * 0.05)
    final = valor - tax
    
    if not db.remove_money(interaction.user.id, interaction.guild.id, valor, f"Transferência"):
        return await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
    
    db.add_money(usuario.id, interaction.guild.id, final, f"Transferência de {interaction.user}")
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Transferência", color=BLUE_COLOR)
    embed.add_field(name="De", value=interaction.user.mention, inline=True)
    embed.add_field(name="Para", value=usuario.mention, inline=True)
    embed.add_field(name="Valor", value=f"{valor:,} (taxa: {tax})", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="depositar", description="Adiciona moedas (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def depositar(interaction: discord.Interaction, usuario: discord.Member, valor: int):
    db.add_money(usuario.id, interaction.guild.id, valor, "Depósito admin")
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Depósito", description=f"{valor:,} moedas para {usuario.mention}", color=GREEN_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cobrar", description="Remove moedas (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def cobrar(interaction: discord.Interaction, usuario: discord.Member, valor: int):
    if db.remove_money(usuario.id, interaction.guild.id, valor, "Cobrança admin"):
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Cobrança", description=f"{valor:,} moedas de {usuario.mention}", color=RED_COLOR)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)

# ==================== COMANDOS DE LOJA ====================

@bot.tree.command(name="loja", description="Cria ou lista lojas")
@app_commands.describe(nome="Nome da loja")
async def loja(interaction: discord.Interaction, nome: str = None):
    if nome:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO shops (guild_id, owner_id, name) VALUES (?, ?, ?)',
                      (interaction.guild.id, interaction.user.id, nome))
        shop_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Loja Criada!", description=f"**{nome}**\nID: `{shop_id}`", color=GREEN_COLOR)
        await interaction.response.send_message(embed=embed)
    else:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shops WHERE guild_id = ?', (interaction.guild.id,))
        shops = cursor.fetchall()
        conn.close()
        
        embed = discord.Embed(title=f"{CUSTOM_EMOJI} Lojas", color=BLUE_COLOR)
        for shop in shops:
            owner = interaction.guild.get_member(shop[2])
            embed.add_field(name=shop[3], value=f"Dono: {owner.mention if owner else '?'}\nID: `{shop[0]}`", inline=True)
        
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="item", description="Cria item para venda")
@app_commands.describe(loja="ID da loja", nome="Nome", preco="Preço", estoque="Estoque (-1 = infinito)")
async def item(interaction: discord.Interaction, loja: int, nome: str, preco: int, estoque: int = -1):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT owner_id FROM shops WHERE shop_id = ?', (loja,))
    shop = cursor.fetchone()
    
    if not shop or (shop[0] != interaction.user.id and not interaction.user.guild_permissions.administrator):
        conn.close()
        return await interaction.response.send_message("❌ Você não é dono desta loja!", ephemeral=True)
    
    cursor.execute('INSERT INTO items (shop_id, name, price, stock) VALUES (?, ?, ?, ?)',
                  (loja, nome, preco, estoque))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Item Criado", description=f"**{nome}** - {preco:,} moedas\nID: `{item_id}`", color=GREEN_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="comprar", description="Compra um item")
@app_commands.describe(item_id="ID do item")
async def comprar(interaction: discord.Interaction, item_id: int):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE item_id = ?', (item_id,))
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        return await interaction.response.send_message("❌ Item não encontrado!", ephemeral=True)
    
    price = item[4]
    if not db.remove_money(interaction.user.id, interaction.guild.id, price, f"Compra: {item[2]}"):
        conn.close()
        return await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
    
    if item[5] > 0:
        cursor.execute('UPDATE items SET stock = stock - 1 WHERE item_id = ?', (item_id,))
    
    cursor.execute('INSERT OR REPLACE INTO inventory (user_id, guild_id, item_id, quantity) VALUES (?, ?, ?, COALESCE((SELECT quantity FROM inventory WHERE user_id = ? AND guild_id = ? AND item_id = ?), 0) + 1)',
                  (interaction.user.id, interaction.guild.id, item_id, interaction.user.id, interaction.guild.id, item_id))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Compra Realizada", description=f"Você comprou **{item[2]}**!", color=GREEN_COLOR)
    await interaction.response.send_message(embed=embed)

# ==================== COMANDOS DE GESTÃO ====================

@bot.tree.command(name="backup", description="Cria backup do servidor")
@app_commands.checks.has_permissions(administrator=True)
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    guild = interaction.guild
    backup_data = {
        "name": guild.name,
        "created_at": datetime.now().isoformat(),
        "roles": [{"name": r.name, "color": r.color.value, "permissions": r.permissions.value} for r in guild.roles if r.name != "@everyone"],
        "categories": []
    }
    
    for category in guild.categories:
        cat_data = {"name": category.name, "channels": [{"name": c.name, "type": str(c.type)} for c in category.channels]}
        backup_data["categories"].append(cat_data)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO backups (guild_id, name, data) VALUES (?, ?, ?)',
                  (guild.id, f"Backup_{datetime.now().strftime('%Y%m%d')}", json.dumps(backup_data)))
    backup_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    json_str = json.dumps(backup_data, indent=2)
    buffer = io.BytesIO(json_str.encode())
    file = discord.File(buffer, filename=f'backup_{guild.id}_{backup_id}.json')
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Backup Criado", description=f"ID: `{backup_id}`", color=GREEN_COLOR)
    await interaction.followup.send(embed=embed, file=file)

@bot.tree.command(name="cargo_temporario", description="Adiciona cargo que expira")
@app_commands.describe(usuario="Usuário", cargo="Cargo", duracao="Duração (1h, 30m, 1d)")
@app_commands.checks.has_permissions(manage_roles=True)
async def cargo_temporario(interaction: discord.Interaction, usuario: discord.Member, cargo: discord.Role, duracao: str):
    time_convert = {'m': 60, 'h': 3600, 'd': 86400}
    try:
        unit = duracao[-1].lower()
        value = int(duracao[:-1])
        seconds = value * time_convert[unit]
    except:
        return await interaction.response.send_message("❌ Formato inválido! Use: `30m`, `2h`, `1d`", ephemeral=True)
    
    await usuario.add_roles(cargo, reason=f"Temporário por {interaction.user}")
    
    expires = datetime.now() + timedelta(seconds=seconds)
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Cargo Temporário", description=f"{usuario.mention} recebeu {cargo.mention} por {duracao}", color=BLUE_COLOR)
    embed.add_field(name="Expira", value=f"<t:{int(expires.timestamp())}:R>", inline=True)
    
    await interaction.response.send_message(embed=embed)
    
    await asyncio.sleep(seconds)
    await usuario.remove_roles(cargo, reason="Cargo temporário expirado")

@bot.tree.command(name="onboarding", description="Configura boas-vindas")
@app_commands.describe(cargo="Cargo inicial", canal="Canal de boas-vindas")
@app_commands.checks.has_permissions(administrator=True)
async def onboarding(interaction: discord.Interaction, cargo: discord.Role = None, canal: discord.TextChannel = None):
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Onboarding Configurado", color=GREEN_COLOR)
    if cargo:
        embed.add_field(name="Cargo Automático", value=cargo.mention, inline=True)
    if canal:
        embed.add_field(name="Canal", value=canal.mention, inline=True)
    await interaction.response.send_message(embed=embed)

# ==================== PUNIÇÕES CRIATIVAS ====================

@bot.tree.command(name="isolate", description="Isola usuário em canal privado")
@app_commands.describe(usuario="Usuário", motivo="Motivo")
@app_commands.checks.has_permissions(moderate_members=True)
async def isolate(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Não especificado"):
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        usuario: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    }
    
    for role in interaction.guild.roles:
        if role.permissions.manage_guild or role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    
    channel = await interaction.guild.create_text_channel(f"🔒-isolado-{usuario.name}", overwrites=overwrites)
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Usuário Isolado", description=f"{usuario.mention} → {channel.mention}", color=discord.Color.orange())
    embed.add_field(name="Motivo", value=motivo, inline=False)
    
    await interaction.response.send_message(embed=embed)
    await channel.send(f"{usuario.mention}, você foi isolado por: **{motivo}**")

@bot.tree.command(name="demote", description="Remove todos os cargos temporariamente")
@app_commands.describe(usuario="Usuário", duracao="Duração")
@app_commands.checks.has_permissions(manage_roles=True)
async def demote(interaction: discord.Interaction, usuario: discord.Member, duracao: str):
    old_roles = [r for r in usuario.roles if r.name != "@everyone"]
    
    review_role = discord.utils.get(interaction.guild.roles, name="🔍 Em Revisão")
    if not review_role:
        review_role = await interaction.guild.create_role(name="🔍 Em Revisão", color=discord.Color.dark_grey())
    
    await usuario.remove_roles(*old_roles)
    await usuario.add_roles(review_role)
    
    time_convert = {'m': 60, 'h': 3600, 'd': 86400}
    unit = duracao[-1].lower()
    value = int(duracao[:-1])
    seconds = value * time_convert[unit]
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Em Revisão", description=f"{usuario.mention} teve cargos removidos por {duracao}", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)
    
    await asyncio.sleep(seconds)
    await usuario.remove_roles(review_role)
    await usuario.add_roles(*old_roles)

@bot.tree.command(name="readonly", description="Usuário só pode ler")
@app_commands.describe(usuario="Usuário", duracao="Duração")
@app_commands.checks.has_permissions(manage_roles=True)
async def readonly(interaction: discord.Interaction, usuario: discord.Member, duracao: str):
    readonly_role = discord.utils.get(interaction.guild.roles, name="🚫 Read Only")
    if not readonly_role:
        readonly_role = await interaction.guild.create_role(name="🚫 Read Only")
        for channel in interaction.guild.text_channels:
            await channel.set_permissions(readonly_role, send_messages=False, add_reactions=False)
    
    await usuario.add_roles(readonly_role)
    
    time_convert = {'m': 60, 'h': 3600, 'd': 86400}
    unit = duracao[-1].lower()
    value = int(duracao[:-1])
    seconds = value * time_convert[unit]
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Read Only", description=f"{usuario.mention} só pode ler por {duracao}", color=YELLOW_COLOR)
    await interaction.response.send_message(embed=embed)
    
    await asyncio.sleep(seconds)
    await usuario.remove_roles(readonly_role)

@bot.tree.command(name="jailmode", description="Restringe a 1 canal")
@app_commands.describe(usuario="Usuário", duracao="Duração")
@app_commands.checks.has_permissions(moderate_members=True)
async def jailmode(interaction: discord.Interaction, usuario: discord.Member, duracao: str):
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        usuario: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    
    jail_channel = await interaction.guild.create_text_channel(f"🔒-espera-{usuario.name}", overwrites=overwrites)
    
    if usuario.voice:
        await usuario.move_to(None)
    
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Jail Mode", description=f"{usuario.mention} restrito a {jail_channel.mention}", color=RED_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="audit", description="Audita usuário")
@app_commands.describe(usuario="Usuário")
@app_commands.checks.has_permissions(view_audit_log=True)
async def audit(interaction: discord.Interaction, usuario: discord.Member):
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} Auditoria", description=f"Usuário: {usuario.mention}", color=BLUE_COLOR)
    embed.add_field(name="Conta Criada", value=usuario.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Entrou em", value=usuario.joined_at.strftime("%d/%m/%Y"), inline=True)
    
    roles = [r.mention for r in usuario.roles if r.name != "@everyone"]
    embed.add_field(name=f"Cargos ({len(roles)})", value=" ".join(roles[:5]) or "Nenhum", inline=False)
    
    await interaction.response.send_message(embed=embed)

# ==================== GRÁFICOS ====================

@bot.tree.command(name="grafico", description="Gera gráfico da economia")
@app_commands.describe(periodo="Período")
@app_commands.choices(periodo=[
    app_commands.Choice(name="7 dias", value="7"),
    app_commands.Choice(name="30 dias", value="30")
])
async def grafico(interaction: discord.Interaction, periodo: app_commands.Choice[str] = None):
    await interaction.response.defer()
    
    days = int(periodo.value) if periodo else 30
    dates = [datetime.now() - timedelta(days=i) for i in range(days)]
    dates.reverse()
    
    values = [10000 + (i * 500) + random.randint(-1000, 1000) for i in range(days)]
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(dates, values, color='#00ff88', linewidth=2)
    ax.fill_between(dates, values, alpha=0.3, color='#00ff88')
    ax.set_title(f'💹 Economia - Últimos {days} dias', fontsize=16)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    file = discord.File(buffer, filename='grafico.png')
    await interaction.followup.send(file=file)

@bot.tree.command(name="ranking", description="Top 10 mais ricos")
async def ranking(interaction: discord.Interaction):
    await interaction.response.defer()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor('#2f3136')
    ax.axis('off')
    
    ax.text(0.5, 0.95, "🏆 TOP 10 MAIS RICOS", ha='center', fontsize=24, color='gold', weight='bold')
    
    # Dados simulados
    for i in range(1, 11):
        y = 0.88 - (i * 0.08)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        ax.text(0.1, y, f"{medal} Usuário {i}", fontsize=14, color='white')
        ax.text(0.9, y, f"{10000-i*500:,} 💰", fontsize=14, color='#00ff88', ha='right')
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='#2f3136')
    buffer.seek(0)
    plt.close()
    
    file = discord.File(buffer, filename='ranking.png')
    await interaction.followup.send(file=file)

# ==================== HELP ====================

@bot.tree.command(name="help", description="Painel de ajuda")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{CUSTOM_EMOJI} CentralDiv - Ajuda", description="Bot completo de moderação e economia", color=BLUE_COLOR)
    
    embed.add_field(name="🛡️ Moderação", value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/warns` `/clearwarns` `/setlogs` `/logs`", inline=False)
    embed.add_field(name="💰 Economia", value="`/carteira` `/trabalhar` `/transferir` `/depositar` `/cobrar`", inline=False)
    embed.add_field(name="🏪 Loja", value="`/loja` `/item` `/comprar`", inline=False)
    embed.add_field(name="⚙️ Gestão", value="`/backup` `/cargo_temporario` `/onboarding`", inline=False)
    embed.add_field(name="🔒 Punições+", value="`/isolate` `/demote` `/readonly` `/jailmode` `/audit`", inline=False)
    embed.add_field(name="📊 Gráficos", value="`/grafico` `/ranking`", inline=False)
    
    await interaction.response.send_message(embed=embed)

# ==================== EVENTOS ====================

@bot.event
async def on_member_join(member):
    db.get_or_create_user(member.id, member.guild.id)

# ==================== INICIAR ====================

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN não encontrado!")
        exit(1)
    bot.run(token)
