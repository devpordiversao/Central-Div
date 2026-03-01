import sqlite3
import json
from datetime import datetime, timedelta
import os

class Database:
    def __init__(self):
        self.db_path = "centraldiv.db"
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela de economia - usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 0,
                bank_balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                last_work TIMESTAMP,
                last_daily TIMESTAMP,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # Tabela de transações
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
        
        # Tabela de lojas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shops (
                shop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_id INTEGER,
                name TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_official INTEGER DEFAULT 0
            )
        ''')
        
        # Tabela de itens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                name TEXT,
                description TEXT,
                price INTEGER,
                stock INTEGER DEFAULT -1,
                effect_type TEXT,
                effect_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de inventário
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                guild_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id, item_id)
            )
        ''')
        
        # Tabela de leilões
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auctions (
                auction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                seller_id INTEGER,
                item_id INTEGER,
                start_price INTEGER,
                current_bid INTEGER,
                highest_bidder INTEGER,
                ends_at TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Tabela de investimentos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                investment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                amount INTEGER,
                risk_level TEXT,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                return_rate REAL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Tabela de negócios (renda passiva)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS businesses (
                business_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                guild_id INTEGER,
                name TEXT,
                type TEXT,
                investment INTEGER,
                daily_income INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de salários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS salaries (
                guild_id INTEGER,
                role_id INTEGER,
                amount INTEGER,
                interval_hours INTEGER,
                last_paid TIMESTAMP,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        
        # Tabela de configuração do servidor
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                currency_name TEXT DEFAULT 'CentralCoins',
                currency_symbol TEXT DEFAULT '💰',
                start_balance INTEGER DEFAULT 1000,
                tax_rate REAL DEFAULT 0.05,
                work_cooldown INTEGER DEFAULT 3600,
                daily_reward INTEGER DEFAULT 500
            )
        ''')
        
        # Tabela de missões diárias
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
                claimed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, date(expires_at))
            )
        ''')
        
        # Tabela de backups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de punições criativas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creative_punishments (
                punishment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                type TEXT,
                data TEXT,
                applied_at TIMESTAMP,
                expires_at TIMESTAMP,
                applied_by INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ===== MÉTODOS DE ECONOMIA =====
    
    def get_or_create_user(self, user_id, guild_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM users WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        
        user = cursor.fetchone()
        if not user:
            cursor.execute('''
                INSERT INTO users (user_id, guild_id, balance)
                VALUES (?, ?, (SELECT start_balance FROM guild_config WHERE guild_id = ?))
            ''', (user_id, guild_id, guild_id))
            conn.commit()
            
            cursor.execute('''
                SELECT * FROM users WHERE user_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
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
        
        cursor.execute('''
            UPDATE users SET balance = balance + ?, total_earned = total_earned + ?
            WHERE user_id = ? AND guild_id = ?
        ''', (amount, amount, user_id, guild_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, guild_id, type, amount, description)
            VALUES (?, ?, 'income', ?, ?)
        ''', (user_id, guild_id, amount, description))
        
        conn.commit()
        conn.close()
        return True
    
    def remove_money(self, user_id, guild_id, amount, description=""):
        balance = self.get_balance(user_id, guild_id)
        if balance < amount:
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET balance = balance - ?, total_spent = total_spent + ?
            WHERE user_id = ? AND guild_id = ?
        ''', (amount, amount, user_id, guild_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, guild_id, type, amount, description)
            VALUES (?, ?, 'expense', ?, ?)
        ''', (user_id, guild_id, amount, description))
        
        conn.commit()
        conn.close()
        return True
    
    def transfer_money(self, from_id, to_id, guild_id, amount, tax=0):
        if not self.remove_money(from_id, guild_id, amount, f"Transferência para {to_id}"):
            return False
        
        tax_amount = int(amount * tax)
        final_amount = amount - tax_amount
        
        self.add_money(to_id, guild_id, final_amount, f"Transferência de {from_id}")
        return final_amount
    
    def get_transactions(self, user_id, guild_id, limit=10):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE user_id = ? AND guild_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, guild_id, limit))
        
        transactions = cursor.fetchall()
        conn.close()
        return transactions
    
    # ===== LOJA =====
    
    def create_shop(self, guild_id, owner_id, name, description="", is_official=False):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO shops (guild_id, owner_id, name, description, is_official)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, owner_id, name, description, 1 if is_official else 0))
        
        shop_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return shop_id
    
    def create_item(self, shop_id, name, price, description="", stock=-1, effect_type=None, effect_data=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO items (shop_id, name, description, price, stock, effect_type, effect_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (shop_id, name, description, price, stock, effect_type, json.dumps(effect_data) if effect_data else None))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id
    
    def get_shop_items(self, shop_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM items WHERE shop_id = ?', (shop_id,))
        items = cursor.fetchall()
        conn.close()
        return items
    
    def buy_item(self, user_id, guild_id, item_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Pegar info do item
        cursor.execute('SELECT * FROM items WHERE item_id = ?', (item_id,))
        item = cursor.fetchone()
        
        if not item:
            conn.close()
            return None, "Item não encontrado"
        
        price = item[4]
        stock = item[5]
        
        if stock == 0:
            conn.close()
            return None, "Item fora de estoque"
        
        # Verificar saldo
        if not self.remove_money(user_id, guild_id, price, f"Compra: {item[2]}"):
            conn.close()
            return None, "Saldo insuficiente"
        
        # Atualizar estoque
        if stock > 0:
            cursor.execute('UPDATE items SET stock = stock - 1 WHERE item_id = ?', (item_id,))
        
        # Adicionar ao inventário
        cursor.execute('''
            INSERT INTO inventory (user_id, guild_id, item_id, quantity)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, guild_id, item_id) 
            DO UPDATE SET quantity = quantity + 1
        ''', (user_id, guild_id, item_id))
        
        conn.commit()
        conn.close()
        return item, "Compra realizada"
    
    def get_inventory(self, user_id, guild_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.*, inv.quantity FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.user_id = ? AND inv.guild_id = ?
        ''', (user_id, guild_id))
        
        items = cursor.fetchall()
        conn.close()
        return items
    
    # ===== LEILÃO =====
    
    def create_auction(self, guild_id, seller_id, item_id, start_price, duration_hours):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        ends_at = datetime.now() + timedelta(hours=duration_hours)
        
        cursor.execute('''
            INSERT INTO auctions (guild_id, seller_id, item_id, start_price, current_bid, ends_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, seller_id, item_id, start_price, start_price, ends_at))
        
        auction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return auction_id
    
    def place_bid(self, auction_id, bidder_id, amount):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM auctions WHERE auction_id = ?', (auction_id,))
        auction = cursor.fetchone()
        
        if not auction or auction[7] != 'active':
            conn.close()
            return False, "Leilão não encontrado ou finalizado"
        
        if datetime.now() > datetime.fromisoformat(auction[6]):
            conn.close()
            return False, "Leilão já encerrado"
        
        if amount <= auction[4]:
            conn.close()
            return False, "Lance deve ser maior que o atual"
        
        # Devolver dinheiro do último licitante
        if auction[5]:
            self.add_money(auction[5], auction[1], auction[4], "Devolução de lance")
        
        # Cobrar novo lance
        if not self.remove_money(bidder_id, auction[1], amount, f"Lance leilão #{auction_id}"):
            conn.close()
            return False, "Saldo insuficiente"
        
        cursor.execute('''
            UPDATE auctions SET current_bid = ?, highest_bidder = ?
            WHERE auction_id = ?
        ''', (amount, bidder_id, auction_id))
        
        conn.commit()
        conn.close()
        return True, "Lance realizado"
    
    # ===== MISSÕES =====
    
    def generate_daily_mission(self, user_id, guild_id):
        import random
        
        mission_types = [
            ('messages', 'Envie 50 mensagens', 50, 200),
            ('voice', 'Fique 1 hora em call', 60, 300),
            ('reactions', 'Reaja a 20 mensagens', 20, 150),
            ('commands', 'Use 10 comandos', 10, 250)
        ]
        
        mission = random.choice(mission_types)
        expires_at = datetime.now() + timedelta(days=1)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO daily_missions (user_id, guild_id, mission_type, target, reward, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, guild_id, mission[0], mission[2], mission[3], expires_at))
            conn.commit()
        except:
            pass  # Missão já existe para hoje
        
        conn.close()
        return mission
    
    # ===== BACKUP =====
    
    def create_backup(self, guild_id, name, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backups (guild_id, name, data)
            VALUES (?, ?, ?)
        ''', (guild_id, name, json.dumps(data)))
        
        backup_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return backup_id
    
    def get_backup(self, backup_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM backups WHERE backup_id = ?', (backup_id,))
        backup = cursor.fetchone()
        conn.close()
        
        if backup:
            return json.loads(backup[3])
        return None

# Instância global
db = Database()
