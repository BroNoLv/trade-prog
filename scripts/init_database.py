import asyncio
import asyncpg
import random
import string

async def initialize_database():
    """Инициализация базы данных и создание начальных токенов"""
    
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
        
        # Удаляем неактивные токены
        await conn.execute("DELETE FROM tokens WHERE is_active = FALSE")
        
        # Проверяем, есть ли уже активные токены
        existing_tokens = await conn.fetch("SELECT COUNT(*) as count FROM tokens WHERE is_active = TRUE")
        if existing_tokens[0]['count'] > 0:
            print("⚠️ Активные токены уже существуют. Создать новые?")
            response = input("Введите 'yes' для создания новых токенов: ")
            if response.lower() != 'yes':
                print("Создание новых токенов отменено.")
                await conn.close()
                return
        
        # Удаляем все старые токены
        await conn.execute("DELETE FROM tokens")
        
        # Создаем новые токены
        print("🔑 Генерируем токены...")
        
        tokens_data = []
        for role in ['owner', 'operator', 'trader']:
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            await conn.execute(
                "INSERT INTO tokens (token, role, is_active) VALUES ($1, $2, TRUE)",
                token, role
            )
            tokens_data.append((role.upper(), token))
        
        print("✅ База данных успешно инициализирована!")
        
        await conn.close()
        
        print("\n" + "="*60)
        print("✅ НОВЫЕ ТОКЕНЫ СОЗДАНЫ!")
        print("="*60)
        print("\n📋 СОХРАНИТЕ ЭТИ ТОКЕНЫ:")
        print("="*60)
        for role, token in tokens_data:
            print(f"\n{role}:")
            print(f"  {token}")
        print("\n" + "="*60)
        print("\n⚠️ ВАЖНО: Сохраните токены в безопасном месте!")
        print("Они больше не будут показаны.")
        
    except asyncpg.InvalidCatalogNameError:
        print("\n❌ ОШИБКА: База данных 'bot_db' не существует!")
        print("\n📝 Создайте базу данных в PostgreSQL:")
        print("1. Откройте pgAdmin или psql")
        print("2. Выполните команду: CREATE DATABASE bot_db;")
        print("3. Запустите скрипт снова")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")

if __name__ == '__main__':
    asyncio.run(initialize_database())