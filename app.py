import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.exceptions import TelegramNetworkError as NetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

from config.settings import config
from database.models import db
from handlers.common import register_common_handlers
from handlers.trader import register_trader_handlers
from handlers.operator import register_operator_handlers
from handlers.owner import register_owner_handlers
from services.deal_service import DealService
from services.exchange_service import ExchangeService
from middlewares.access_middleware import AccessMiddleware
import random
import string
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use /tmp for PID file in cloud environments
PID_FILE = "/tmp/bot.pid" if os.path.exists("/tmp") else "bot.pid"

def check_single_instance():
    """Проверяет, запущен ли уже другой экземпляр бота"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Проверяем, существует ли процесс с этим PID
            try:
                os.kill(pid, 0)  # Сигнал 0 проверяет существование процесса
                logger.error(f"❌ Бот уже запущен с PID {pid}. Остановите его перед запуском нового экземпляра.")
                logger.error("   Для остановки используйте: taskkill /F /PID {pid}")
                sys.exit(1)
            except OSError:
                # Процесс не существует, удаляем старый PID файл
                os.remove(PID_FILE)
        except (ValueError, IOError):
            # PID файл поврежден, удаляем его
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    
    # Создаем новый PID файл
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup_pid_file():
    """Удаляет PID файл при корректном завершении"""
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except:
            pass

async def initialize_tokens():
    """Инициализация токенов при запуске бота"""
    try:
        async with db.pool.acquire() as conn:
            # Проверяем, есть ли активные токены
            existing_tokens = await conn.fetch("SELECT COUNT(*) as count FROM tokens WHERE is_active = TRUE")
            
            if existing_tokens[0]['count'] == 0:
                logger.info("🔑 Создаем начальные токены...")
                
                # Создаем новые токены
                tokens_data = []
                for role in ['owner', 'operator', 'trader']:
                    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                    await conn.execute(
                        "INSERT INTO tokens (token, role, is_active) VALUES ($1, $2, TRUE)",
                        token, role
                    )
                    tokens_data.append((role.upper(), token))
                
                logger.info("✅ Токены созданы:")
                for role, token in tokens_data:
                    logger.info(f"🔑 TOKEN FOR {role}: {token}")
            else:
                logger.info(f"📋 Найдено {existing_tokens[0]['count']} активных токенов")
                tokens = await conn.fetch("SELECT role, token FROM tokens WHERE is_active = TRUE")
                for token in tokens:
                    logger.info(f"🔑 EXISTING TOKEN FOR {token['role'].upper()}: {token['token']}")
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации токенов: {e}")

# HTTP Server for health checks (wake-on-webhook)
app = web.Application()
bot_instance = None

async def health_check(request):
    """Health check endpoint for Render wake-on-webhook"""
    return web.Response(text="OK", status=200)

async def webhook_handler(request):
    """Webhook handler for Telegram bot"""
    if bot_instance:
        update = await request.json()
        # Process update through dispatcher
        # This is a simplified version - full webhook setup requires more configuration
        return web.Response(text="OK", status=200)
    return web.Response(text="Bot not ready", status=503)

app.router.add_get('/health', health_check)
app.router.add_post('/webhook', webhook_handler)

async def start_http_server():
    """Start HTTP server for health checks"""
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 HTTP сервер запущен на порту {port}")

async def scheduled_tasks():
    """Background tasks"""
    try:
        # Check expired deals
        expired = await DealService.check_expired_deals()
        if expired:
            logger.info(f"✅ Проверка истекших сделок: найдено {len(expired)}")
        
        # Auto-update exchange rate every hour
        rate = await ExchangeService.update_rate_automatically()
        if rate:
            logger.info(f"✅ Курс обновлен: {rate} RUB/USDT")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в scheduled_tasks: {e}")

async def main():
    # Проверяем, что только один экземпляр бота запущен
    check_single_instance()
    
    # Initialize bot and dispatcher
    # Поддержка прокси через переменную окружения PROXY_URL
    proxy_url = getattr(config, 'PROXY_URL', None)
    if proxy_url:
        bot = Bot(token=config.BOT_TOKEN, proxy=proxy_url)
        logger.info(f"🔧 Используется прокси: {proxy_url}")
    else:
        bot = Bot(token=config.BOT_TOKEN)
    
    global bot_instance
    bot_instance = bot
    
    dp = Dispatcher()
    
    # Create router for handlers
    router = Router()
    
    # Add middleware
    router.message.middleware(AccessMiddleware())
    router.callback_query.middleware(AccessMiddleware())
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_tasks, 'interval', minutes=60)  # Каждый час
    scheduler.add_job(DealService.check_expired_deals, 'interval', minutes=5)  # Каждые 5 минут
    scheduler.start()
    
    # Connect to database
    try:
        await db.connect()
        logger.info("✅ База данных подключена успешно")
        
        # Initialize tokens if needed
        await initialize_tokens()
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return
    
    # Register handlers
    register_common_handlers(router)
    register_trader_handlers(router)
    register_operator_handlers(router)
    register_owner_handlers(router)
    
    # Include router in dispatcher
    dp.include_router(router)
    
    # Start HTTP server for health checks (Render wake-on-webhook)
    await start_http_server()
    
    # Start bot
    try:
        logger.info("🤖 Бот запущен успешно!")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except NetworkError as e:
        logger.error(f"❌ Ошибка сети: {e}")
        logger.error("Проверьте подключение к интернету и настройки прокси")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
    finally:
        # Правильное закрытие сессии для aiogram 3.x
        try:
            session = await bot.get_session()
            await session.close()
            logger.info("👋 Бот остановлен корректно")
        except Exception as e:
            logger.error(f"⚠️ Ошибка при остановке бота: {e}")
        finally:
            # Удаляем PID файл при завершении
            cleanup_pid_file()

if __name__ == '__main__':
    asyncio.run(main())