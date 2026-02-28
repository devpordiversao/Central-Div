from discord.ext import commands, tasks
import discord
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Configurações Anti-Spam
        self.message_cache = defaultdict(list)  # {user_id: [timestamps]}
        self.spam_threshold = 5  # mensagens
        self.spam_interval = 5   # segundos
        
        # Configurações Anti-Raid
        self.join_cache = []  # [timestamps]
        self.raid_threshold = 10  # joins
        self.raid_interval = 10   # segundos
        self.raid_mode = False
        
        # Lista de palavrões (expanda conforme necessário)
        self.bad_words = [
            "porra", "caralho", "merda", "bosta", "puta", "viado", "gay", "lesbica",
            "fdp", "filho da puta", "cuzão", "buceta", "pica", "rola", "cu", "viada",
            "crl", "pqp", "krl", "vsf", "se foder", "foder", "fudido", "fudida",
            "arrombado", "arrombada", "corno", "corna", "otario", "otaria", "babaca",
            "idiota", "estupido", "retardado", "down", "mongol", "lixo", "nojento"
        ]
        
        # Regex para links suspeitos
        self.suspicious_links = re.compile(r'(discord\.gg|discord\.com\/invite|bit\.ly|tinyurl|t\.co|short\.link)', re.IGNORECASE)
        
        # Cooldown para warns automáticos
        self.warn_cooldown = defaultdict(lambda: datetime.min)
        
        # Iniciar task de limpeza
        self.clean_cache.start()

    def cog_unload(self):
        self.clean_cache.cancel()

    @tasks.loop(seconds=30)
    async def clean_cache(self):
        """Limpa caches antigos"""
        now = datetime.now()
        
        # Limpar message cache
        for user_id in list(self.message_cache.keys()):
            self.message_cache[user_id] = [
                ts for ts in self.message_cache[user_id] 
                if (now - ts).seconds < 60
            ]
            if not self.message_cache[user_id]:
                del self.message_cache[user_id]
        
        # Limpar join cache
        self.join_cache = [
            ts for ts in self.join_cache 
            if (now - ts).seconds < 60
        ]

    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitora todas as mensagens"""
        if message.author.bot or not message.guild:
            return
        
        # Ignorar admins
        if message.author.guild_permissions.administrator:
            return
        
        await self.check_spam(message)
        await self.check_bad_words(message)
        await self.check_links(message)
        await self.check_mentions(message)

    async def check_spam(self, message):
        """Verifica spam de mensagens"""
        user_id = message.author.id
        now = datetime.now()
        
        self.message_cache[user_id].append(now)
        
        # Verificar se excedeu limite
        recent = [ts for ts in self.message_cache[user_id] if (now - ts).seconds <= self.spam_interval]
        
        if len(recent) >= self.spam_threshold:
            # Spam detectado
            try:
                await message.author.timeout(timedelta(minutes=5), reason="Spam detectado")
                await message.channel.send(
                    f"🚫 {message.author.mention} foi silenciado por 5 minutos por spam!",
                    delete_after=10
                )
                
                # Limpar mensagens recentes
                async for msg in message.channel.history(limit=50):
                    if msg.author.id == user_id and (now - msg.created_at).seconds < 30:
                        try:
                            await msg.delete()
                        except:
                            pass
                
                self.message_cache[user_id] = []
                
                # Log
                embed = discord.Embed(
                    title=f"{self.bot.CUSTOM_EMOJI} AutoMod - Spam Detectado",
                    color=discord.Color.red(),
                    timestamp=now
                )
                embed.add_field(name="Usuário", value=message.author.mention, inline=True)
                embed.add_field(name="Canal", value=message.channel.mention, inline=True)
                embed.add_field(name="Ação", value="Mute de 5 minutos", inline=False)
                
                logs_cog = self.bot.get_cog('LogsCog')
                if logs_cog:
                    await logs_cog.send_log(message.guild, embed)
                    
            except discord.Forbidden:
                pass

    async def check_bad_words(self, message):
        """Verifica palavrões"""
        content_lower = message.content.lower()
        
        for word in self.bad_words:
            if word in content_lower:
                # Verificar cooldown (evitar spam de warns)
                now = datetime.now()
                if (now - self.warn_cooldown[message.author.id]).seconds < 30:
                    return
                
                self.warn_cooldown[message.author.id] = now
                
                try:
                    await message.delete()
                    
                    # Warn silencioso (só usuário vê)
                    try:
                        warn_embed = discord.Embed(
                            title="⚠️ Aviso de Moderação",
                            description=f"Sua mensagem foi removida por conter linguagem inadequada.\n**Palavra detectada:** ||{word}||",
                            color=discord.Color.gold()
                        )
                        await message.author.send(embed=warn_embed)
                    except:
                        pass
                    
                    # Log
                    log_embed = discord.Embed(
                        title=f"{self.bot.CUSTOM_EMOJI} AutoMod - Linguagem Inadequada",
                        color=discord.Color.orange(),
                        timestamp=now
                    )
                    log_embed.add_field(name="Usuário", value=message.author.mention, inline=True)
                    log_embed.add_field(name="Canal", value=message.channel.mention, inline=True)
                    log_embed.add_field(name="Conteúdo", value=f"||{message.content[:100]}||", inline=False)
                    
                    logs_cog = self.bot.get_cog('LogsCog')
                    if logs_cog:
                        await logs_cog.send_log(message.guild, log_embed)
                    
                    return  # Só processa primeiro palavrão encontrado
                    
                except discord.Forbidden:
                    pass

    async def check_links(self, message):
        """Verifica links suspeitos (exceto em canais específicos)"""
        # Ignorar canais de divulgação (você pode ajustar isso)
        divulgacao_keywords = ['divulgação', 'divulgacao', 'pub', 'anuncio', 'promo']
        channel_name = message.channel.name.lower()
        
        if any(keyword in channel_name for keyword in divulgacao_keywords):
            return  # Permite links em canais de divulgação
        
        # Verificar links suspeitos
        if self.suspicious_links.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"🔗 {message.author.mention}, links encurtados ou suspeitos não são permitidos aqui!",
                    delete_after=10
                )
            except:
                pass

    async def check_mentions(self, message):
        """Verifica mention spam"""
        if len(message.mentions) > 5 or len(message.role_mentions) > 3:
            try:
                await message.delete()
                await message.author.timeout(timedelta(minutes=10), reason="Mention spam")
                await message.channel.send(
                    f"🚫 {message.author.mention} foi silenciado por mention spam!",
                    delete_after=10
                )
            except:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Anti-Raid: Monitora entradas de membros"""
        now = datetime.now()
        self.join_cache.append(now)
        
        # Limpar entradas antigas
        self.join_cache = [ts for ts in self.join_cache if (now - ts).seconds <= self.raid_interval]
        
        # Verificar raid
        if len(self.join_cache) >= self.raid_threshold and not self.raid_mode:
            self.raid_mode = True
            
            # Ativar modo raid (bloquear novas entradas temporariamente)
            embed = discord.Embed(
                title="🚨 MODO RAID ATIVADO",
                description=f"Detectamos {len(self.join_cache)} entradas em {self.raid_interval} segundos!\nAtivando proteções...",
                color=discord.Color.red()
            )
            
            # Enviar alerta para mods
            for channel in member.guild.text_channels:
                if "mod" in channel.name or "admin" in channel.name or "logs" in channel.name:
                    try:
                        await channel.send("@here", embed=embed)
                        break
                    except:
                        continue
            
            # Aguardar e desativar modo raid após 2 minutos
            await asyncio.sleep(120)
            self.raid_mode = False
            
            # Notificar fim do modo raid
            end_embed = discord.Embed(
                title="✅ Modo Raid Desativado",
                description="As proteções anti-raid foram desativadas.",
                color=discord.Color.green()
            )
            
            for channel in member.guild.text_channels:
                if "mod" in channel.name or "admin" in channel.name or "logs" in channel.name:
                    try:
                        await channel.send(embed=end_embed)
                        break
                    except:
                        continue

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Detecta edição de mensagens para palavrões"""
        if before.content != after.content:
            await self.check_bad_words(after)

async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
