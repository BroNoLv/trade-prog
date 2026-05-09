import asyncio
import random
import string
import sys
import os

# Добавляем корневую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def create_initial_tokens():
    # Импортируем здесь, чтобы избежать циклических импортов
    from database.models import db
    
    await db.connect()
    
    async with db.pool.acquire() as conn:
        # Проверяем, есть ли уже токены
        existing_tokens = await conn.fetch("SELECT COUNT(*) as count FROM tokens")
        if existing_tokens[0]['count'] > 0:
            print("⚠️ Токены уже созданы. Хотите создать новые?")
            response = input("Введите 'yes' для создания новых токенов: ")
            if response.lower() != 'yes':
                print("Создание новых токенов отменено.")
                return
        
        # Очищаем старые токены
        await conn.execute("DELETE FROM tokens")
        
        # Create owner token
        owner_token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        await conn.execute(
            "INSERT INTO tokens (token, role) VALUES ($1, 'owner')",
            owner_token
        )
        
        # Create operator token
        operator_token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        await conn.execute(
            "INSERT INTO tokens (token, role) VALUES ($1, 'operator')",
            operator_token
        )
        
        # Create trader token
        trader_token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        await conn.execute(
            "INSERT INTO tokens (token, role) VALUES ($1, 'trader')",
            trader_token
        )
        
        print("\n" + "="*50)
        print("✅ Initial tokens created:")
        print("="*50)
        print(f"👑 Owner token: {owner_token}")
        print(f"👨‍💼 Operator token: {operator_token}")
        print(f"💰 Trader token: {trader_token}")
        print("="*50)
        print("\n⚠️ Save these tokens! They won't be shown again.")
        print("⚠️ Copy and paste them to a secure location.")

if __name__ == '__main__':
    asyncio.run(create_initial_tokens())