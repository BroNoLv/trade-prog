import asyncio
import asyncpg

async def update_database_structure():
    """Обновление структуры базы данных"""
    
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'bot_db',
        'user': 'postgres',
        'password': '138616era',
        'port': 5432
    }
    
    try:
        print("🔄 Подключение к базе данных PostgreSQL...")
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ Подключение успешно!")
        
        print("📊 Обновление структуры базы данных...")
        
        # 1. Добавляем колонку is_deleted в таблицу deals
        try:
            await conn.execute('''
                ALTER TABLE deals 
                ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE
            ''')
            print("✅ Колонка is_deleted добавлена в deals")
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении is_deleted: {e}")
        
        # 2. Добавляем колонку is_active в таблицу users
        try:
            await conn.execute('''
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
            ''')
            print("✅ Колонка is_active добавлена в users")
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении is_active: {e}")
        
        # 3. Добавляем колонки detail_name и detail_type в payment_details
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
        
        # 4. Удаляем неактивные токены
        try:
            result = await conn.execute("DELETE FROM tokens WHERE is_active = FALSE")
            print(f"✅ Неактивные токены удалены: {result}")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении токенов: {e}")
        
        # 5. Создаем индексы для улучшения производительности
        try:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_deals_is_deleted 
                ON deals(is_deleted)
            ''')
            print("✅ Индекс idx_deals_is_deleted создан")
        except Exception as e:
            print(f"⚠️ Ошибка при создании индекса: {e}")
        
        try:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_is_active 
                ON users(is_active)
            ''')
            print("✅ Индекс idx_users_is_active создан")
        except Exception as e:
            print(f"⚠️ Ошибка при создании индекса: {e}")
        
        # 6. Проверяем и обновляем существующие данные
        try:
            # Устанавливаем is_active = TRUE для всех существующих пользователей
            await conn.execute('''
                UPDATE users SET is_active = TRUE WHERE is_active IS NULL
            ''')
            print("✅ Существующие пользователи активированы")
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении пользователей: {e}")
        
        try:
            # Устанавливаем is_deleted = FALSE для всех существующих сделок
            await conn.execute('''
                UPDATE deals SET is_deleted = FALSE WHERE is_deleted IS NULL
            ''')
            print("✅ Существующие сделки обновлены")
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении сделок: {e}")
        
        try:
            # Обновляем детали платежей
            await conn.execute('''
                UPDATE payment_details 
                SET detail_name = 'Без названия' 
                WHERE detail_name IS NULL
            ''')
            print("✅ Названия реквизитов обновлены")
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении реквизитов: {e}")
        
        try:
            await conn.execute('''
                UPDATE payment_details 
                SET detail_type = 'card' 
                WHERE detail_type IS NULL
            ''')
            print("✅ Типы реквизитов обновлены")
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении типов реквизитов: {e}")
        
        await conn.close()
        
        print("\n" + "="*60)
        print("✅ СТРУКТУРА БАЗЫ ДАННЫХ УСПЕШНО ОБНОВЛЕНА!")
        print("="*60)
        print("\n📋 Выполненные изменения:")
        print("1. Добавлена колонка is_deleted в таблицу deals")
        print("2. Добавлена колонка is_active в таблицу users")
        print("3. Добавлены колонки detail_name и detail_type в payment_details")
        print("4. Удалены неактивные токены")
        print("5. Созданы индексы для оптимизации")
        print("6. Обновлены существующие данные")
        
    except asyncpg.ConnectionDoesNotExistError:
        print("\n❌ ОШИБКА: Не удалось подключиться к PostgreSQL!")
        print("\n📝 Проверьте:")
        print("1. PostgreSQL запущен")
        print("2. Параметры подключения верны")
        print("3. Порт 5432 открыт")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(update_database_structure())