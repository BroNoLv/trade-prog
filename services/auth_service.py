from database.models import db
from config.settings import config
import logging

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    async def authenticate_user(token: str, telegram_id: int, username: str = None):
        """Authenticate user by token and return user data"""
        logger.info(f"🔍 AuthService: проверяем токен '{token}' для пользователя {telegram_id}")
        
        async with db.pool.acquire() as conn:
            # Проверяем, существует ли таблица tokens
            try:
                token_data = await conn.fetchrow(
                    "SELECT * FROM tokens WHERE token = $1 AND is_active = TRUE",
                    token
                )
                logger.info(f"📋 AuthService: результат поиска токена: {token_data}")
            except Exception as e:
                logger.error(f"❌ AuthService: ошибка при поиске токена: {e}")
                # Пробуем создать таблицу
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tokens (
                        id SERIAL PRIMARY KEY,
                        token VARCHAR(16) UNIQUE NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                return None
            
            if not token_data:
                logger.info(f"❌ AuthService: токен '{token}' не найден в БД")
                return None
            
            logger.info(f"✅ AuthService: токен найден, роль: {token_data['role']}")
            
            # Check if user exists
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id
            )
            
            if not user:
                # Create new user
                user = await conn.fetchrow(
                    '''
                    INSERT INTO users (telegram_id, username, role, token, is_active)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    ''',
                    telegram_id, 
                    username, 
                    token_data['role'], 
                    token,
                    # Для трейдеров по умолчанию неактивны, пока не подтвержден депозит
                    False if token_data['role'] == 'trader' else True
                )
            else:
                # Update user token and role
                user = await conn.fetchrow(
                    '''
                    UPDATE users 
                    SET token = $1, role = $2 
                    WHERE telegram_id = $3 
                    RETURNING *
                    ''',
                    token, token_data['role'], telegram_id
                )
            
            # Для трейдеров, если депозит не подтвержден - автоматически деактивируем
            if user['role'] == 'trader' and not user['insurance_deposit_confirmed']:
                await conn.execute(
                    "UPDATE users SET is_active = FALSE WHERE user_id = $1",
                    user['user_id']
                )
                # Обновляем статус в возвращаемом объекте
                user_dict = dict(user)
                user_dict['is_active'] = False
                return user_dict
            
            return dict(user)
    
    @staticmethod
    async def logout_user(telegram_id: int):
        """Logout user by clearing token"""
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET token = NULL WHERE telegram_id = $1",
                telegram_id
            )
    
    @staticmethod
    async def get_user_role(telegram_id: int):
        """Get user role"""
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT role FROM users WHERE telegram_id = $1 AND token IS NOT NULL",
                telegram_id
            )
            return user['role'] if user else None
    
    @staticmethod
    async def get_user_data(telegram_id: int):
        """Get full user data"""
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                '''
                SELECT u.* 
                FROM users u 
                WHERE telegram_id = $1 AND token IS NOT NULL
                ''',
                telegram_id
            )
            return dict(user) if user else None
    
    @staticmethod
    async def can_trader_access(telegram_id: int):
        """Check if trader can access features"""
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                '''
                SELECT insurance_deposit_confirmed, is_active 
                FROM users 
                WHERE telegram_id = $1 AND role = 'trader'
                ''',
                telegram_id
            )
            
            if not user:
                return False
            
            return user['insurance_deposit_confirmed'] and user['is_active']
    
    @staticmethod
    async def activate_trader(trader_id: int):
        """Activate trader after deposit confirmation"""
        async with db.pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE users 
                SET insurance_deposit_confirmed = TRUE,
                    is_active = TRUE,
                    insurance_deposit = $1
                WHERE user_id = $2
                ''',
                config.REQUIRED_INSURANCE_DEPOSIT,
                trader_id
            )