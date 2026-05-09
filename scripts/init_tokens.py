#!/usr/bin/env python3
"""
Скрипт для создания начальных токенов на Render
Использует DATABASE_URL из переменных окружения
"""

import asyncio
import asyncpg
import random
import string
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def create_initial_tokens():
    """Создание начальных токенов в базе данных"""
    
    # Получаем DATABASE_URL из переменных окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не найдена в переменных окружения")
        return
    
    try:
        print("🔄 Подключение к базе данных...")
        
        conn = await asyncpg.connect(database_url)
        print("✅ Подключение успешно!")
        
        # Проверяем, есть ли уже активные токены
        existing_tokens = await conn.fetch("SELECT COUNT(*) as count FROM tokens WHERE is_active = TRUE")
        if existing_tokens[0]['count'] > 0:
            print(f"⚠️ Найдено {existing_tokens[0]['count']} активных токенов")
            print("📋 Существующие токены:")
            tokens = await conn.fetch("SELECT role, token FROM tokens WHERE is_active = TRUE")
            for token in tokens:
                print(f"   {token['role'].upper()}: {token['token']}")
                print(f"🔑 EXISTING TOKEN FOR {token['role'].upper()}: {token['token']}")  # Для видимости в логах Render
        else:
            print("🔑 Активных токенов не найдено, создаем новые...")
            
            # Создаем новые токены
            tokens_data = []
            for role in ['owner', 'operator', 'trader']:
                token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                await conn.execute(
                    "INSERT INTO tokens (token, role, is_active) VALUES ($1, $2, TRUE)",
                    token, role
                )
                tokens_data.append((role.upper(), token))
            
            print("✅ Токены созданы:")
            for role, token in tokens_data:
                print(f"   {role}: {token}")
                print(f"🔑 TOKEN FOR {role}: {token}")  # Для видимости в логах Render
        
        await conn.close()
        print("👋 Работа завершена")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(create_initial_tokens())
