from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from services.auth_service import AuthService
from keyboards.menus import get_main_menu
from config.settings import config
import logging

logger = logging.getLogger(__name__)

async def start_command(message: types.Message, state: FSMContext):
    """Handle /start command"""
    user_data = await AuthService.get_user_data(message.from_user.id)
    
    if user_data:
        role = user_data['role']
        deposit_confirmed = user_data.get('insurance_deposit_confirmed', True) if role == "trader" else True
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu(role, deposit_confirmed))
        return
    
    welcome_text = """
🎉 Добро пожаловать в P2P Exchange Bot!

💱 Наш бот обеспечивает безопасный обмен USDT на RUB с системой ролей и подтверждением сделок.

🔐 Для доступа к системе введите ваш токен авторизации.

⚠️ Если у вас нет токена, обратитесь к администратору @evildains.
    """

    await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())
    await message.answer(
        "🔐 Для авторизации используйте команду: /token [ваш_токен]\n\nПример: /token AWbXXAxefGuqcY2h",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def token_command(message: types.Message, state: FSMContext):
    """Handle /token command for authorization"""
    try:
        # Получаем токен из аргументов команды
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Использование: /token [ваш_токен]")
            return
        
        token = args[1].strip()
        logger.info(f"🔥 КОМАНДА /token ВЫЗВАНА: {token}")
        logger.info(f"🔥 Пользователь: {message.from_user.id}, @{message.from_user.username}")
        
        # Проверяем длину токена
        if len(token) != 16 or not token.isalnum():
            await message.answer("❌ Неверный формат токена. Токен должен быть 16 символов.")
            return
        
        logger.info(f"🔍 Проверяем токен: {token} от пользователя {message.from_user.id}")
        
        # Проверяем подключение к БД
        from database.models import db
        logger.info(f"🔍 Статус пула БД: {db.pool is not None}")
        
        user = await AuthService.authenticate_user(
            token, 
            message.from_user.id, 
            message.from_user.username
        )
        
        logger.info(f"📋 Результат авторизации: {user}")
        
        if not user:
            logger.info("❌ Токен не найден в БД")
            await message.answer("❌ Неверный токен. Попробуйте еще раз:")
            return
        
        await state.clear()
        
        role = user['role']
        is_active = user.get('is_active', True)
        insurance_confirmed = user.get('insurance_deposit_confirmed', True)
        
        role_names = {
            "owner": "Владелец",
            "trader": "Трейдер",
            "operator": "Оператор"
        }
        
        welcome_message = f"""
✅ Авторизация успешна!
Роль: {role_names.get(role, role)}
    
Добро пожаловать в систему!
    """
        
        if role == "trader":
            if not insurance_confirmed:
                welcome_message += f"""
                
⚠️ ВНИМАНИЕ:
Для начала работы необходимо пополнить страховой депозит.
Сумма: {config.REQUIRED_INSURANCE_DEPOSIT} USDT
Адрес: {config.OWNER_WALLET_ADDRESS}
Сеть: USDT TRC-20

После перевода обратитесь к владельцу для подтверждения.

⚠️ Доступ к функционалу будет ограничен до подтверждения депозита.
Вы можете проверить статус в "Личном кабинете".
                """
            elif not is_active:
                welcome_message += f"""
                
⚠️ Ваш аккаунт деактивирован.
Обратитесь к владельцу для активации.
                """
        
        deposit_confirmed = insurance_confirmed if role == "trader" else True
        await message.answer(welcome_message, reply_markup=get_main_menu(role, deposit_confirmed))
        
    except Exception as e:
        logger.error(f"❌ Ошибка в token_command: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка сервера: {str(e)}")

async def logout_command(message: types.Message, state: FSMContext):
    """Logout user"""
    await AuthService.logout_user(message.from_user.id)
    await state.clear()
    await message.answer(
        "👋 Вы вышли из системы.\n"
        "Для входа используйте команду /start",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def back_to_main(message: types.Message, state: FSMContext):
    """Handle back button"""
    user_data = await AuthService.get_user_data(message.from_user.id)
    if user_data:
        role = user_data['role']
        deposit_confirmed = user_data.get('insurance_deposit_confirmed', True) if role == "trader" else True
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu(role, deposit_confirmed))
    else:
        await start_command(message, state)

def register_common_handlers(router: Router):
    router.message.register(start_command, F.text == "/start")
    router.message.register(token_command, F.text.startswith("/token"))
    router.message.register(logout_command, F.text == "/logout")
    router.message.register(logout_command, F.text == "🚪 Выйти")
    router.message.register(back_to_main, F.text == "🔙 Назад")