import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import random
import matplotlib.pyplot as plt
import io
import os

from database.db import db

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_investments.start()
        self.pay_salaries.start()
        self.daily_reset.start()
    
    def cog_unload(self):
        self.check_investments.cancel()
        self.pay_salaries.cancel()
        self.daily_reset.cancel()
    
    # ===== BANCO =====
    
    @app_commands.command(name="banco", description="Inicializa ou mostra o sistema econômico")
    @app_commands.describe(
        moeda="Nome da moeda",
        simbolo="Símbolo da moeda",
        inicial="Saldo inicial para novos membros"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def banco(self, interaction: discord.Interaction, moeda: str = None, simbolo: str = None, inicial: int = None):
        guild_id = interaction.guild.id
        
        if moeda and simbolo:
            # Configurar novo banco
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO guild_config (guild_id, currency_name, currency_symbol, start_balance)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, moeda, simbolo, inicial or 1000))
            
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Banco Central Criado",
                description=f"Moeda: {simbolo} {moeda}\nSaldo inicial: {inicial or 1000}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            # Mostrar configuração atual
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM guild_config WHERE guild_id = ?', (guild_id,))
            config = cursor.fetchone()
            conn.close()
            
            if not config:
                return await interaction.response.send_message("❌ Banco não configurado! Use `/banco criar`", ephemeral=True)
            
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} {config[1]}",
                description=f"Símbolo: {config[2]}\nInicial: {config[3]}",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="carteira", description="Mostra seu painel financeiro")
    @app_commands.describe(usuario="Usuário para verificar (opcional)")
    async def carteira(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        guild_id = interaction.guild.id
        
        user_data = db.get_or_create_user(target.id, guild_id)
        balance = user_data[2]
        total_earned = user_data[4]
        total_spent = user_data[5]
        
        # Pegar config da moeda
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT currency_symbol, currency_name FROM guild_config WHERE guild_id = ?', (guild_id,))
        config = cursor.fetchone()
        symbol = config[0] if config else "💰"
        name = config[1] if config else "Moedas"
        conn.close()
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Carteira de {target.display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name=f"{symbol} Saldo Atual", value=f"**{balance:,}** {name}", inline=False)
        embed.add_field(name="📈 Total Ganho", value=f"{total_earned:,}", inline=True)
        embed.add_field(name="📉 Total Gasto", value=f"{total_spent:,}", inline=True)
        
        # Ranking no servidor
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, balance FROM users WHERE guild_id = ?
            ORDER BY balance DESC
        ''', (guild_id,))
        ranking = cursor.fetchall()
        conn.close()
        
        rank = next((i+1 for i, (uid, _) in enumerate(ranking) if uid == target.id), "?")
        total = len(ranking)
        
        embed.add_field(name="🏆 Ranking", value=f"#{rank} de {total}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="depositar", description="Adiciona moeda a um usuário (Admin)")
    @app_commands.describe(usuario="Usuário", valor="Quantidade", motivo="Motivo")
    @app_commands.checks.has_permissions(administrator=True)
    async def depositar(self, interaction: discord.Interaction, usuario: discord.Member, valor: int, motivo: str = "Não especificado"):
        db.add_money(usuario.id, interaction.guild.id, valor, f"Depósito admin: {motivo}")
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Depósito Realizado",
            description=f"{valor:,} moedas adicionadas à carteira de {usuario.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Motivo", value=motivo, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # Log
        logs_cog = self.bot.get_cog('LogsCog')
        if logs_cog:
            await logs_cog.send_log(interaction.guild, embed)
    
    @app_commands.command(name="cobrar", description="Remove moeda de um usuário (Admin)")
    @app_commands.describe(usuario="Usuário", valor="Quantidade", motivo="Motivo")
    @app_commands.checks.has_permissions(administrator=True)
    async def cobrar(self, interaction: discord.Interaction, usuario: discord.Member, valor: int, motivo: str = "Não especificado"):
        if db.remove_money(usuario.id, interaction.guild.id, valor, f"Cobrança admin: {motivo}"):
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Cobrança Realizada",
                description=f"{valor:,} moedas removidas de {usuario.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Motivo", value=motivo, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Usuário não tem saldo suficiente!", ephemeral=True)
    
    @app_commands.command(name="transferir", description="Transfere moedas para outro usuário")
    @app_commands.describe(usuario="Destinatário", valor="Quantidade")
    async def transferir(self, interaction: discord.Interaction, usuario: discord.Member, valor: int):
        if usuario == interaction.user:
            return await interaction.response.send_message("❌ Não pode transferir para si mesmo!", ephemeral=True)
        
        # Taxa de 5%
        tax = 0.05
        final_amount = db.transfer_money(interaction.user.id, usuario.id, interaction.guild.id, valor, tax)
        
        if final_amount:
            tax_amount = int(valor * tax)
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Transferência Realizada",
                description=f"{interaction.user.mention} → {usuario.mention}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Valor Enviado", value=f"{valor:,}", inline=True)
            embed.add_field(name="Taxa (5%)", value=f"{tax_amount:,}", inline=True)
            embed.add_field(name="Recebido", value=f"{final_amount:,}", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
    
    @app_commands.command(name="extrato", description="Mostra histórico de transações")
    @app_commands.describe(usuario="Usuário", quantidade="Número de transações")
    async def extrato(self, interaction: discord.Interaction, usuario: discord.Member = None, quantidade: int = 10):
        target = usuario or interaction.user
        transactions = db.get_transactions(target.id, interaction.guild.id, quantidade)
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Extrato de {target.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not transactions:
            embed.description = "Nenhuma transação encontrada."
        else:
            for trans in transactions:
                tipo = "🟢" if trans[3] == 'income' else "🔴"
                data = datetime.fromisoformat(trans[5]).strftime("%d/%m %H:%M")
                embed.add_field(
                    name=f"{tipo} {data}",
                    value=f"{trans[4]:,} - {trans[5][:50]}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ===== TRABALHO & RENDA =====
    
    @app_commands.command(name="trabalhar", description="Trabalhe para ganhar moedas")
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def trabalhar(self, interaction: discord.Interaction):
        # Ganho aleatório entre 100 e 500
        base = random.randint(100, 500)
        
        # Chance de evento especial (10%)
        bonus = 0
        event = ""
        if random.random() < 0.1:
            bonus = base
            event = "\n🎉 **EVENTO ESPECIAL!** Ganho dobrado!"
        
        total = base + bonus
        db.add_money(interaction.user.id, interaction.guild.id, total, "Trabalho")
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Trabalho Realizado",
            description=f"Você trabalhou e ganhou **{total:,}** moedas!{event}",
            color=discord.Color.green()
        )
        if bonus:
            embed.add_field(name="Base", value=f"{base:,}", inline=True)
            embed.add_field(name="Bônus", value=f"{bonus:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="missao", description="Missão diária")
    async def missao(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # Verificar se já tem missão ativa
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM daily_missions 
            WHERE user_id = ? AND guild_id = ? AND date(expires_at) = date('now')
        ''', (user_id, guild_id))
        mission = cursor.fetchone()
        conn.close()
        
        if not mission:
            # Gerar nova missão
            mission_data = db.generate_daily_mission(user_id, guild_id)
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Nova Missão Diária!",
                description=f"**Objetivo:** {mission_data[1]}\n**Recompensa:** {mission_data[3]} moedas",
                color=discord.Color.purple()
            )
            embed.set_footer(text="Válida até 23:59")
        else:
            status = "✅ Completa!" if mission[7] else f"Progresso: {mission[6]}/{mission[4]}"
            embed = discord.Embed(
                title=f"{self.bot.CUSTOM_EMOJI} Missão de Hoje",
                description=f"**{mission[2]}**\nProgresso: {mission[6]}/{mission[4]}\nRecompensa: {mission[5]} moedas",
                color=discord.Color.gold() if not mission[7] else discord.Color.green()
            )
            embed.add_field(name="Status", value=status, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="investir", description="Invista seu dinheiro")
    @app_commands.describe(valor="Quantidade", risco="Nível de risco (baixo/medio/alto)")
    @app_commands.choices(risco=[
        app_commands.Choice(name="Baixo (5-15% retorno)", value="baixo"),
        app_commands.Choice(name="Médio (15-40% retorno)", value="medio"),
        app_commands.Choice(name="Alto (40-100% retorno)", value="alto")
    ])
    async def investir(self, interaction: discord.Interaction, valor: int, risco: app_commands.Choice[str]):
        if not db.remove_money(interaction.user.id, interaction.guild.id, valor, f"Investimento {risco.value}"):
            return await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
        
        # Duração baseada no risco
        durations = {'baixo': 24, 'medio': 48, 'alto': 72}
        duration = durations[risco.value]
        
        # Taxa de retorno aleatória
        rates = {
            'baixo': (0.05, 0.15),
            'medio': (0.15, 0.40),
            'alto': (0.40, 1.00)
        }
        rate = random.uniform(*rates[risco.value])
        
        end_date = datetime.now() + timedelta(hours=duration)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO investments (user_id, guild_id, amount, risk_level, end_date, return_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (interaction.user.id, interaction.guild.id, valor, risco.value, end_date, rate))
        conn.commit()
        conn.close()
        
        retorno = int(valor * (1 + rate))
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Investimento Realizado",
            description=f"Risco: **{risco.value.upper()}**\nValor: {valor:,} moedas",
            color=discord.Color.blue()
        )
        embed.add_field(name="Retorno Estimado", value=f"{retorno:,} moedas", inline=True)
        embed.add_field(name="Resgate em", value=f"<t:{int(end_date.timestamp())}:R>", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="investimentos", description="Ver seus investimentos ativos")
    async def investimentos(self, interaction: discord.Interaction):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM investments 
            WHERE user_id = ? AND guild_id = ? AND status = 'active'
        ''', (interaction.user.id, interaction.guild.id))
        investments = cursor.fetchall()
        conn.close()
        
        if not investments:
            return await interaction.response.send_message("Você não tem investimentos ativos.", ephemeral=True)
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Seus Investimentos",
            color=discord.Color.gold()
        )
        
        for inv in investments:
            end = datetime.fromisoformat(inv[6])
            retorno = int(inv[4] * (1 + inv[7]))
            status = "✅ Pronto!" if datetime.now() > end else f"⏰ <t:{int(end.timestamp())}:R>"
            
            embed.add_field(
                name=f"{inv[5].upper()} - {inv[4]:,}",
                value=f"Retorno: {retorno:,}\n{status}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    # ===== SALÁRIOS =====
    
    @app_commands.command(name="salario", description="Configura salários automáticos")
    @app_commands.describe(cargo="Cargo", valor="Valor", intervalo="Intervalo em horas")
    @app_commands.checks.has_permissions(administrator=True)
    async def salario(self, interaction: discord.Interaction, cargo: discord.Role, valor: int, intervalo: int):
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO salaries (guild_id, role_id, amount, interval_hours, last_paid)
            VALUES (?, ?, ?, ?, ?)
        ''', (interaction.guild.id, cargo.id, valor, intervalo, datetime.now()))
        
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Salário Configurado",
            description=f"Cargo: {cargo.mention}\nValor: {valor:,} a cada {intervalo}h",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    # ===== TASKS =====
    
    @tasks.loop(minutes=5)
    async def check_investments(self):
        """Verifica investimentos prontos para resgate"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM investments 
            WHERE status = 'active' AND end_date <= ?
        ''', (datetime.now(),))
        
        ready = cursor.fetchall()
        
        for inv in ready:
            user_id, guild_id, amount, rate = inv[1], inv[2], inv[4], inv[7]
            retorno = int(amount * (1 + rate))
            
            db.add_money(user_id, guild_id, retorno, "Retorno de investimento")
            
            cursor.execute('UPDATE investments SET status = ? WHERE investment_id = ?', 
                         ('completed', inv[0]))
        
        conn.commit()
        conn.close()
    
    @tasks.loop(hours=1)
    async def pay_salaries(self):
        """Paga salários automáticos"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM salaries')
        salaries = cursor.fetchall()
        
        for sal in salaries:
            guild_id, role_id, amount, interval, last_paid = sal[0], sal[1], sal[2], sal[3], sal[4]
            
            if datetime.fromisoformat(last_paid) + timedelta(hours=interval) <= datetime.now():
                guild = self.bot.get_guild(guild_id)
                if guild:
                    role = guild.get_role(role_id)
                    if role:
                        for member in role.members:
                            db.add_money(member.id, guild_id, amount, f"Salário: {role.name}")
                
                cursor.execute('UPDATE salaries SET last_paid = ? WHERE guild_id = ? AND role_id = ?',
                             (datetime.now(), guild_id, role_id))
        
        conn.commit()
        conn.close()
    
    @tasks.loop(hours=24)
    async def daily_reset(self):
        """Reseta missões diárias"""
        # Automático pelo SQLite date()
        pass

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
