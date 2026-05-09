import asyncpg
from datetime import datetime, timedelta
from config.settings import config

class Database:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        # Support for DATABASE_URL (Neon) or individual parameters
        if config.DATABASE_URL:
            self.pool = await asyncpg.create_pool(config.DATABASE_URL)
        else:
            self.pool = await asyncpg.create_pool(
                host=config.DB_HOST,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                port=int(config.DB_PORT)
            )
        await self.create_tables()
        await self.update_tables_structure()  # Добавляем автоматическое обновление
    
    async def create_tables(self):
        """Создание таблиц (без новых колонок для совместимости)"""
        async with self.pool.acquire() as conn:
            # Users table (старая версия)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(100),
                    role VARCHAR(20) NOT NULL,
                    token VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW(),
                    insurance_deposit DECIMAL(15,2) DEFAULT 0,
                    working_deposit DECIMAL(15,2) DEFAULT 0,
                    insurance_deposit_confirmed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Access tokens table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    token_id SERIAL PRIMARY KEY,
                    token VARCHAR(50) UNIQUE NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
                )
            ''')
            
            # Payment details (старая версия)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS payment_details (
                    detail_id SERIAL PRIMARY KEY,
                    trader_id BIGINT NOT NULL,
                    bank_name VARCHAR(100) NOT NULL,
                    full_name VARCHAR(200) NOT NULL,
                    card_number VARCHAR(20),
                    phone_number VARCHAR(20),
                    min_amount DECIMAL(15,2) DEFAULT 0,
                    max_amount DECIMAL(15,2) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    FOREIGN KEY (trader_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            
            # Deals (старая версия)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id SERIAL PRIMARY KEY,
                    deal_number VARCHAR(20) UNIQUE NOT NULL,
                    operator_id BIGINT NOT NULL,
                    trader_id BIGINT NOT NULL,
                    payment_detail_id INT,
                    amount_rub DECIMAL(15,2) NOT NULL,
                    amount_usdt DECIMAL(15,2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    confirmed_at TIMESTAMP,
                    dispute_opened BOOLEAN DEFAULT FALSE,
                    dispute_resolved BOOLEAN DEFAULT FALSE,
                    resolution VARCHAR(20),
                    FOREIGN KEY (operator_id) REFERENCES users(user_id),
                    FOREIGN KEY (trader_id) REFERENCES users(user_id),
                    FOREIGN KEY (payment_detail_id) REFERENCES payment_details(detail_id)
                )
            ''')
            
            # Exchange rates
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS exchange_rates (
                    rate_id SERIAL PRIMARY KEY,
                    usdt_to_rub DECIMAL(10,2) NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    updated_by BIGINT,
                    is_auto_updated BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Disputes
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS disputes (
                    dispute_id SERIAL PRIMARY KEY,
                    deal_id INT NOT NULL,
                    opened_by BIGINT NOT NULL,
                    opened_at TIMESTAMP DEFAULT NOW(),
                    resolved_by BIGINT,
                    resolved_at TIMESTAMP,
                    resolution VARCHAR(20),
                    reason TEXT,
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id) ON DELETE CASCADE,
                    FOREIGN KEY (opened_by) REFERENCES users(user_id),
                    FOREIGN KEY (resolved_by) REFERENCES users(user_id)
                )
            ''')
            
            # Insert initial exchange rate
            await conn.execute('''
                INSERT INTO exchange_rates (usdt_to_rub, updated_at)
                VALUES (90.0, NOW())
                ON CONFLICT DO NOTHING
            ''')
            
            print("✅ Основные таблицы созданы")
    
    async def update_tables_structure(self):
        """Добавление новых колонок к существующим таблицам"""
        async with self.pool.acquire() as conn:
            print("🔄 Проверка и обновление структуры таблиц...")
            
            # Добавляем новые колонки, если их нет
            try:
                await conn.execute('''
                    ALTER TABLE deals 
                    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE
                ''')
                print("✅ Колонка is_deleted добавлена в deals")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении is_deleted: {e}")
            
            try:
                await conn.execute('''
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
                ''')
                print("✅ Колонка is_active добавлена в users")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении is_active: {e}")
            
            try:
                await conn.execute('''
                    ALTER TABLE payment_details 
                    ADD COLUMN IF NOT EXISTS detail_name VARCHAR(100) DEFAULT 'Без названия'
                ''')
                print("✅ Колонка detail_name добавлена в payment_details")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении detail_name: {e}")
            
            try:
                await conn.execute('''
                    ALTER TABLE payment_details 
                    ADD COLUMN IF NOT EXISTS detail_type VARCHAR(10) DEFAULT 'card'
                ''')
                print("✅ Колонка detail_type добавлена в payment_details")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении detail_type: {e}")
            
            try:
                await conn.execute('''
                    ALTER TABLE deals 
                    ADD COLUMN IF NOT EXISTS resolution VARCHAR(20)
                ''')
                print("✅ Колонка resolution добавлена в deals")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении resolution: {e}")
            
            # Обновляем существующие данные
            try:
                await conn.execute('''
                    UPDATE deals SET is_deleted = FALSE WHERE is_deleted IS NULL
                ''')
                print("✅ Существующие сделки обновлены")
            except Exception as e:
                print(f"⚠️ Ошибка при обновлении deals: {e}")
            
            try:
                await conn.execute('''
                    UPDATE users SET is_active = TRUE WHERE is_active IS NULL
                ''')
                print("✅ Существующие пользователи обновлены")
            except Exception as e:
                print(f"⚠️ Ошибка при обновлении users: {e}")
            
            try:
                await conn.execute('''
                    UPDATE payment_details 
                    SET detail_name = 'Без названия', detail_type = 'card'
                    WHERE detail_name IS NULL OR detail_type IS NULL
                ''')
                print("✅ Существующие реквизиты обновлены")
            except Exception as e:
                print(f"⚠️ Ошибка при обновлении payment_details: {e}")
            
            print("✅ Структура базы данных обновлена")

db = Database()