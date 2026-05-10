import re

with open('handlers/operator.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'create_deal_start': '➕ Создать заявку',
    'show_operator_stats': '📊 Статистика',
    'search_transactions_start': '🔍 Поиск транзакций',
    'show_active_deals_operator': '📋 Активные заявки',
}

for func_name, button_text in replacements.items():
    pattern = f'router.message.register\\({func_name}, F.text == \"\"\\)'
    replacement = f'router.message.register({func_name}, F.text == \"{button_text}\")'
    content = re.sub(pattern, replacement, content)

with open('handlers/operator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
