from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.auth_service import AuthService
from keyboards.menus import get_main_menu
from config.settings import config

class AuthStates(StatesGroup):
    waiting_for_token = State()

async def start_command(message: types.Message, state: FSMContext):
    """Start command - ask for token"""
    await state.set_state(AuthStates.waiting_for_token)

    welcome_text = """
🎉 Добро пожаловать в P2P Exchange Bot!

💱 Наш бот обеспечивает безопасный обмен USDT на RUB с системой ролей и подтверждением сделок.

🔐 Для доступа к системе введите ваш токен авторизации.

⚠️ Если у вас нет токена, обратитесь к администратору @evildains.
    """

    await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())
    await message.answer(
        "🔐 Введите ваш токен для доступа к системе:",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def process_token(message: types.Message, state: FSMContext):
    """Process entered token"""
    token = message.text.strip()
    print(f"🔍 Проверяем токен: {token} от пользователя {message.from_user.id}")
    logger.info(f"🔍 Проверяем токен: {token} от пользователя {message.from_user.id}")
    
    user = await AuthService.authenticate_user(
        token, 
        message.from_user.id, 
        message.from_user.username
    )
    
    print(f"📋 Результат авторизации: {user}")
    logger.info(f"📋 Результат авторизации: {user}")
    
    if not user:
        print("❌ Токен не найден в БД")
        logger.info("❌ Токен не найден в БД")
        await message.answer("❌ Неверный токен. Попробуйте еще раз:")
        return
    
    await state.clear()
    
    role = user['role']
    is_active = user.get('is_active', True)
    insurance_confirmed = user.get('insurance_deposit_confirmed', True)
    
    logger.info(f"👤 Данные пользователя: role={role}, is_active={is_active}, insurance_confirmed={insurance_confirmed}")
    
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
            logger.info("❌ Трейдер без подтвержденного депозита - доступ запрещен")
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
            logger.info("❌ Трейдер деактивирован - доступ запрещен")
            welcome_message += f"""
            
⚠️ Ваш аккаунт деактивирован.
Обратитесь к владельцу для активации.
            """
    
    deposit_confirmed = insurance_confirmed if role == "trader" else True
    await message.answer(welcome_message, reply_markup=get_main_menu(role, deposit_confirmed))

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
    router.message.register(logout_command, F.text == "/logout")
    router.message.register(logout_command, F.text == "🚪 Выйти")
    router.message.register(back_to_main, F.text == "🔙 Назад")
    router.message.register(process_token, AuthStates.waiting_for_token)