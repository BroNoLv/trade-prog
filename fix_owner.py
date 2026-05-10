import re

with open('handlers/owner.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'show_owner_stats_menu': '📈 Общая статистика',
    'show_stats_by_period': '📈 Общая статистика',
    'manage_tokens_start': '🔑 Управление токенами',
    'create_token_start': '🔐 Создать токен',
    'list_tokens': '📋 Список токенов',
    'deactivate_token_start': '❌ Деактивировать токен',
    'manage_exchange_rate': '💱 Курс USDT',
    'set_rate_manual_start': '✏️ Установить вручную',
    'auto_update_rate': '🔄 Автообновление курса',
    'manage_users': '👥 Управление пользователями',
    'delete_specific_deal_start': '🗑️ Удалить сделку',
    'handle_back_from_tokens': '🔙 Назад',
}

for func_name, button_text in replacements.items():
    pattern = f'router.message.register\\({func_name}, F.text == \"\"\\)'
    replacement = f'router.message.register({func_name}, F.text == \"{button_text}\")'
    content = re.sub(pattern, replacement, content)

with open('handlers/owner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
