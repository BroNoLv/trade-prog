import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.exceptions import TelegramNetworkError as NetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

async def keep_alive_ping():
    """Keep-alive ping to prevent Render free tier from sleeping"""
    import aiohttp
    WEBHOOK_HOST = "https://trade-prog-2.onrender.com"
    while True:
        await asyncio.sleep(600)  # 10 minutes
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{WEBHOOK_HOST}/health") as resp:
                    logger.info(f"Keep-alive ping: {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

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
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавляем принудительный вывод в консоль
print("🚀 Бот запускается...")

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
        print("🔄 Начинаю инициализацию токенов...")
        async with db.pool.acquire() as conn:
            # Создаем таблицу tokens если не существует
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id SERIAL PRIMARY KEY,
                    token VARCHAR(16) UNIQUE NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Проверяем, есть ли уже токены
            existing = await conn.fetch("SELECT role, token FROM tokens WHERE is_active = TRUE")
            
            if existing:
                logger.info(f"⚠️ Найдено {len(existing)} существующих токенов, НЕ пересоздаем:")
                for token in existing:
                    logger.info(f"🔑 EXISTING TOKEN FOR {token['role'].upper()}: {token['token']}")
            else:
                # Создаем новые токены только если их нет
                logger.info("🔄 Токены не найдены, создаем новые...")
                tokens_data = []
                for role in ['owner', 'operator', 'trader']:
                    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                    await conn.execute(
                        "INSERT INTO tokens (token, role, is_active) VALUES ($1, $2, TRUE)",
                        token, role
                    )
                    tokens_data.append((role.upper(), token))
                
                logger.info("✅ Новые токены созданы:")
                for role, token in tokens_data:
                    logger.info(f"🔑 TOKEN FOR {role}: {token}")
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации токенов: {e}")

# HTTP Application (will be created in main)
app = None

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
    
    # Временно убираем middleware для тестирования токенов
    # router.message.middleware(AccessMiddleware())
    # router.callback_query.middleware(AccessMiddleware())
    
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
        logger.info("🔄 Начинаю инициализацию токенов...")
        await initialize_tokens()
        logger.info("✅ Инициализация токенов завершена")
        
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
    
    # Start bot with webhook (Render compatible)
    try:
        logger.info("🤖 Настраиваем webhook...")
        
        # Webhook URL на Render
        WEBHOOK_HOST = "https://trade-prog-2.onrender.com"
        WEBHOOK_PATH = "/webhook"
        WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        
        # Создаем aiohttp приложение
        global app
        app = web.Application()
        
        # Добавляем health check endpoint
        async def health_check(request):
            return web.Response(text="OK", status=200)
        app.router.add_get('/health', health_check)
        
        # Удаляем старый webhook и устанавливаем новый
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"✅ Webhook установлен: {WEBHOOK_URL}")
        
        # Настраиваем webhook handler
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        # Запускаем HTTP сервер
        port = int(os.getenv('PORT', 8080))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"🌐 Сервер запущен на порту {port}")
        logger.info("🤖 Бот работает через webhook")

        # Keep-alive to prevent Render free tier from sleeping
        asyncio.create_task(keep_alive_ping())
        logger.info("💓 Keep-alive ping запущен")

        # Держим сервер активным
        await asyncio.Event().wait()
        
    except NetworkError as e:
        logger.error(f"❌ Ошибка сети: {e}")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Удаляем PID файл при завершении
        cleanup_pid_file()

if __name__ == '__main__':
    asyncio.run(main())