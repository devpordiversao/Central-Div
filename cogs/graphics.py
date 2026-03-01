import discord
from discord.ext import commands
from discord import app_commands
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import numpy as np
from datetime import datetime, timedelta

from database.db import db

class GraphicsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="grafico", description="Gera gráfico da economia do servidor")
    @app_commands.describe(periodo="Período (7d, 30d, 90d)")
    @app_commands.choices(periodo=[
        app_commands.Choice(name="7 dias", value="7"),
        app_commands.Choice(name="30 dias", value="30"),
        app_commands.Choice(name="90 dias", value="90")
    ])
    async def grafico(self, interaction: discord.Interaction, periodo: app_commands.Choice[str] = None):
        days = int(periodo.value) if periodo else 30
        
        # Gerar dados simulados (em produção, buscar do banco)
        dates = [datetime.now() - timedelta(days=i) for i in range(days)]
        dates.reverse()
        
        # Simular crescimento econômico
        base = 10000
        values = [base + (i * 500) + np.random.randint(-1000, 1000) for i in range(days)]
        
        # Criar gráfico
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.plot(dates, values, color='#00ff88', linewidth=2)
        ax.fill_between(dates, values, alpha=0.3, color='#00ff88')
        
        ax.set_title(f'💹 Economia do Servidor - Últimos {days} dias', fontsize=16, color='white')
        ax.set_xlabel('Data', color='white')
        ax.set_ylabel('Moedas em Circulação', color='white')
        
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Salvar em buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        
        # Enviar
        file = discord.File(buffer, filename='grafico_economia.png')
        
        embed = discord.Embed(
            title=f"{self.bot.CUSTOM_EMOJI} Gráfico Econômico",
            description=f"Período: {days} dias",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        plt.close()
        
        await interaction.response.send_message(embed=embed, file=file)
    
    @app_commands.command(name="ranking", description="Mostra ranking dos mais ricos")
    async def ranking(self, interaction: discord.Interaction):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, balance FROM users 
            WHERE guild_id = ?
            ORDER BY balance DESC
            LIMIT 10
        ''', (interaction.guild.id,))
        top = cursor.fetchall()
        conn.close()
        
        # Criar imagem do ranking
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.axis('off')
        
        # Fundo escuro
        fig.patch.set_facecolor('#2f3136')
        
        # Título
        ax.text(0.5, 0.95, "🏆 TOP 10 MAIS RICOS", 
                ha='center', va='top', fontsize=24, color='gold', weight='bold')
        
        # Lista
        for i, (user_id, balance) in enumerate(top, 1):
            user = interaction.guild.get_member(user_id)
            name = user.display_name if user else f"Usuário {user_id}"
            
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            color = {1: '#ffd700', 2: '#c0c0c0', 3: '#cd7f32'}.get(i, 'white')
            
            y_pos = 0.85 - (i * 0.08)
            ax.text(0.1, y_pos, f"{medal} {name}", 
                   ha='left', va='center', fontsize=14, color=color, weight='bold')
            ax.text(0.9, y_pos, f"{balance:,} 💰", 
                   ha='right', va='center', fontsize=14, color='#00ff88')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', 
                   facecolor='#2f3136', edgecolor='none')
        buffer.seek(0)
        
        file = discord.File(buffer, filename='ranking.png')
        plt.close()
        
        await interaction.response.send_message(file=file)

async def setup(bot):
    await bot.add_cog(GraphicsCog(bot))
