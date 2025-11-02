import os
import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'your_bot_token_here')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния разговора
MAIN_MENU, SELECTING_TEST, WAITING_ANSWERS, WAITING_ANSWERS_BUTTONS, ADMIN_PANEL = range(5)

# Время теста в секундах (1 час + 5 минут = 65 минут)
TEST_TIME_SECONDS = 65 * 60  # 3900 секунд

# Список администраторов (замените на ваши ID)
ADMIN_IDS = [921454401]  # Ваш Telegram ID

def is_admin(user_id):
    return user_id in ADMIN_IDS

print("=" * 50)
print("🤖 Бот запускается на Render...")
print("=" * 50)

class AchievementSystem:
    def __init__(self):
        self.achievements = {
            'first_test': {
                'name': 'Первый шаг 🎯',
                'description': 'Пройдите первый тест',
                'icon': '🎯'
            },
            'excellent': {
                'name': 'Отличник 📚', 
                'description': 'Наберите 90%+ в тесте',
                'icon': '📚'
            },
            'speedster': {
                'name': 'Спринтер ⚡',
                'description': 'Завершите тест досрочно',
                'icon': '⚡'
            },
            'persistent': {
                'name': 'Настойчивый 💪',
                'description': 'Пройдите 5 тестов',
                'icon': '💪'
            },
            'perfectionist': {
                'name': 'Перфекционист 🌟',
                'description': 'Наберите 100% в тесте',
                'icon': '🌟'
            }
        }
    
    def check_achievements(self, user_id, test_result, test_manager):
        """Проверяет и выдает достижения"""
        user_stats = test_manager.get_user_statistics(user_id)
        new_achievements = []
        
        if not user_stats:
            return new_achievements
            
        tests_count = len(user_stats.get('tests', []))
        
        # Проверяем достижения
        if tests_count == 1:
            new_achievements.append('first_test')
        
        if test_result['percentage'] >= 90:
            new_achievements.append('excellent')
            
        if test_result['percentage'] == 100:
            new_achievements.append('perfectionist')
            
        if tests_count >= 5:
            new_achievements.append('persistent')
        
        return new_achievements
    
    def get_achievement_message(self, achievement_ids):
        """Создает сообщение о полученных достижениях"""
        if not achievement_ids:
            return ""
            
        message = "🎉 Новые достижения!\n\n"
        for achievement_id in achievement_ids:
            achievement = self.achievements[achievement_id]
            message += f"{achievement['icon']} {achievement['name']}\n"
            message += f"   {achievement['description']}\n\n"
        
        return message

class TestManager:
    def __init__(self):
        # Папки для хранения
        self.tests_dir = 'data/tests'
        self.stats_dir = 'data/stats'
        
        # Создаем папки если их нет
        os.makedirs(self.tests_dir, exist_ok=True)
        os.makedirs(self.stats_dir, exist_ok=True)
        
        # Система достижений
        self.achievement_system = AchievementSystem()
        
        # Загружаем тесты
        self.tests = self.load_tests()
    
    def load_tests(self):
        """Загружает тесты (встроенные в код)"""
        tests = {
            'test1': {
                'name': 'Тест #1 - Математика',
                'questions_count': 5,
                'questions': [
                    {
                        'question': 'Сколько будет 2 + 2?',
                        'options': ['3', '4', '5', '6'],
                        'correct_answer': '4'
                    },
                    {
                        'question': 'Чему равно 3 × 5?',
                        'options': ['10', '15', '20', '25'],
                        'correct_answer': '15'
                    },
                    {
                        'question': 'Какое число простое?',
                        'options': ['4', '6', '7', '8'],
                        'correct_answer': '7'
                    },
                    {
                        'question': 'Площадь квадрата со стороной 5?',
                        'options': ['20', '25', '30', '35'],
                        'correct_answer': '25'
                    },
                    {
                        'question': 'Чему равен √16?',
                        'options': ['2', '3', '4', '5'],
                        'correct_answer': '4'
                    }
                ],
                'correct_answers': ['4', '15', '7', '25', '4']
            }
        }
        print(f"📁 Загружено тестов: {len(tests)}")
        return tests
    
    def get_test(self, test_id):
        return self.tests.get(test_id)
    
    def get_all_tests(self):
        return self.tests
    
    def check_answers(self, test_id, user_answers, user_id):
        """Проверяет ответы пользователя"""
        test = self.get_test(test_id)
        if not test:
            return {'error': 'Тест не найден'}
            
        correct_answers = test.get('correct_answers', [])
        questions_count = test.get('questions_count', 0)
        
        # Проверяем количество ответов
        if len(user_answers) != questions_count:
            return {
                'error': f'Ожидается {questions_count} ответов, получено {len(user_answers)}'
            }
        
        correct_count = 0
        detailed_results = []
        
        for i, (user_answer, correct) in enumerate(zip(user_answers, correct_answers)):
            user_norm = str(user_answer).strip().upper()
            correct_norm = str(correct).strip().upper()
            
            is_correct = user_norm == correct_norm
            if is_correct:
                correct_count += 1
                
            detailed_results.append({
                'question_number': i + 1,
                'user_answer': user_answer,
                'correct_answer': correct,
                'is_correct': is_correct
            })
        
        percentage = (correct_count / questions_count) * 100
        
        result = {
            'correct_count': correct_count,
            'total_questions': questions_count,
            'percentage': round(percentage, 2),
            'detailed_results': detailed_results
        }
        
        # Сохраняем статистику
        self.save_statistics(user_id, test_id, result)
        
        return result
    
    def save_statistics(self, user_id, test_id, result):
        """Сохраняет статистику пользователя"""
        user_file = os.path.join(self.stats_dir, f'{user_id}.json')
        
        user_data = {}
        if os.path.exists(user_file):
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        
        test_entry = {
            'test_id': test_id,
            'test_name': self.tests[test_id]['name'],
            'result': result
        }
        
        if 'tests' not in user_data:
            user_data['tests'] = []
        
        user_data['tests'].append(test_entry)
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    def get_user_statistics(self, user_id):
        """Получает статистику пользователя"""
        user_file = os.path.join(self.stats_dir, f'{user_id}.json')
        
        if not os.path.exists(user_file):
            return None
        
        with open(user_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_all_users_stats(self):
        """Получает статистику всех пользователей"""
        all_stats = []
        if os.path.exists(self.stats_dir):
            for filename in os.listdir(self.stats_dir):
                if filename.endswith('.json'):
                    user_id = filename[:-5]
                    try:
                        with open(os.path.join(self.stats_dir, filename), 'r', encoding='utf-8') as f:
                            user_data = json.load(f)
                            all_stats.append({
                                'user_id': user_id,
                                'stats': user_data
                            })
                    except:
                        continue
        return all_stats

async def timer_task(context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_name: str):
    """Задача таймера - ждет и отправляет сообщение о завершении времени"""
    try:
        print(f"⏰ Таймер запущен для теста '{test_name}'")
        await asyncio.sleep(TEST_TIME_SECONDS)
        
        # Проверяем, не отправлены ли уже ответы
        if not context.user_data.get('test_completed', False):
            print(f"⏰ Время вышло для теста '{test_name}'")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ ВРЕМЯ ВЫШЛО!\n\n"
                     f"Тест '{test_name}' завершен.\n"
                     f"Вы не успели отправить ответы вовремя.\n\n"
                     f"➡️ Используйте /start чтобы начать новый тест."
            )
            context.user_data['time_expired'] = True
            context.user_data['test_completed'] = True
        else:
            print(f"⏰ Таймер отменен - тест '{test_name}' уже завершен")
    except asyncio.CancelledError:
        print("⏰ Таймер отменен")
    except Exception as e:
        print(f"❌ Ошибка в таймере: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    # Очищаем данные предыдущего теста
    context.user_data.clear()
    
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📝 Выбор теста", callback_data='select_test')],
        [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')],
        [InlineKeyboardButton("🏆 Достижения", callback_data='show_achievements')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')]
    ]
    
    # Добавляем админ-панель для администраторов
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 Проверка тестов\n\n"
        "Бот проверяет ваши ответы на тесты.\n"
        "⏰ Время на тест: 1 час 5 минут\n"
        "Формат ответов: A,B,C,D,A,B,...\n\n"
        "Выберите раздел:",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик главного меню"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == 'select_test':
        return await show_test_selection(update, context)
    elif choice == 'show_stats':
        return await show_statistics(update, context)
    elif choice == 'show_achievements':
        return await show_achievements(update, context)
    elif choice == 'help':
        return await show_help(update, context)
    elif choice == 'admin_panel':
        return await admin_panel(update, context)

async def show_test_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список тестов"""
    query = update.callback_query
    test_manager = TestManager()
    tests = test_manager.get_all_tests()
    
    if not tests:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 Доступные тесты\n\n"
            "Пока нет доступных тестов.",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    keyboard = []
    for test_id, test_info in tests.items():
        keyboard.append([InlineKeyboardButton(
            f"{test_info['name']} ({test_info['questions_count']} вопросов)", 
            callback_data=f'test_{test_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📝 Выберите тест для проверки:",
        reply_markup=reply_markup
    )
    
    return SELECTING_TEST

async def start_test_with_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск теста с интерактивными кнопками"""
    query = update.callback_query
    await query.answer()
    
    test_id = query.data.replace('test_', '')
    test_manager = TestManager()
    test = test_manager.get_test(test_id)
    
    if not test:
        await query.edit_message_text("❌ Тест не найден")
        return MAIN_MENU
    
    # Очищаем предыдущие данные теста
    context.user_data.clear()
    
    # Сохраняем данные теста
    context.user_data.update({
        'current_test': test_id,
        'test_completed': False,
        'time_expired': False,
        'current_question': 0,
        'user_answers': [],
        'questions': test.get('questions', [])
    })
    
    # Запускаем таймер
    context.user_data['timer_task'] = asyncio.create_task(
        timer_task(context, query.message.chat_id, test['name'])
    )
    
    # Показываем первый вопрос с кнопками
    await show_question_with_buttons(update, context, 0)
    
    return WAITING_ANSWERS_BUTTONS

async def show_question_with_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, question_index):
    """Показывает вопрос с кнопками ответов"""
    questions = context.user_data['questions']
    question = questions[question_index]
    
    # Создаем кнопки с вариантами ответов
    keyboard = []
    row = []
    for i, option in enumerate(question['options']):
        row.append(InlineKeyboardButton(option, callback_data=f'answer_{question_index}_{i}'))
        if len(row) == 2:  # 2 кнопки в строке
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Кнопки навигации
    nav_buttons = []
    if question_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'prev_{question_index}'))
    if question_index < len(questions) - 1:
        nav_buttons.append(InlineKeyboardButton("Далее ➡️", callback_data=f'next_{question_index}'))
    else:
        nav_buttons.append(InlineKeyboardButton("✅ Завершить", callback_data='finish_test'))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    question_text = f"❓ Вопрос {question_index + 1}/{len(questions)}\n\n{question['question']}"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(question_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question_text, reply_markup=reply_markup)

async def handle_button_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ через кнопку"""
    query = update.callback_query
    await query.answer()
    
    # Разбираем callback_data: answer_questionIndex_optionIndex
    parts = query.data.split('_')
    question_index = int(parts[1])
    option_index = int(parts[2])
    
    questions = context.user_data['questions']
    question = questions[question_index]
    selected_answer = question['options'][option_index]
    
    # Сохраняем ответ
    user_answers = context.user_data['user_answers']
    if len(user_answers) <= question_index:
        user_answers.extend([None] * (question_index - len(user_answers) + 1))
    user_answers[question_index] = selected_answer
    
    # Показываем следующий вопрос или завершаем
    if question_index < len(questions) - 1:
        await show_question_with_buttons(update, context, question_index + 1)
    else:
        # Все вопросы отвечены, завершаем тест
        await finish_button_test(update, context)

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает навигацию по вопросам"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('prev_'):
        question_index = int(query.data.split('_')[1]) - 1
        await show_question_with_buttons(update, context, question_index)
    elif query.data.startswith('next_'):
        question_index = int(query.data.split('_')[1]) + 1
        await show_question_with_buttons(update, context, question_index)
    elif query.data == 'finish_test':
        await finish_button_test(update, context)

async def finish_button_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает тест с кнопочным вводом"""
    user_answers = context.user_data['user_answers']
    test_id = context.user_data['current_test']
    user_id = update.effective_user.id
    
    # Проверяем, все ли вопросы отвечены
    if None in user_answers:
        await update.callback_query.message.reply_text(
            "❌ Не все вопросы отвечены! Завершить тест нельзя."
        )
        return
    
    # Отменяем таймер
    timer_task_obj = context.user_data.get('timer_task')
    if timer_task_obj and not timer_task_obj.done():
        timer_task_obj.cancel()
    
    # Проверяем ответы
    test_manager = TestManager()
    result = test_manager.check_answers(test_id, user_answers, user_id)
    
    # Помечаем тест как завершенный
    context.user_data['test_completed'] = True
    
    # Форматируем результаты
    text = f"📊 РЕЗУЛЬТАТЫ: {test_manager.get_test(test_id)['name']}\n\n"
    text += f"✅ Правильных: {result['correct_count']}/{result['total_questions']}\n"
    text += f"📈 Процент: {result['percentage']}%\n\n"
    
    # Оценка
    if result['percentage'] >= 90:
        text += "🎉 Отлично! Превосходный результат!\n"
    elif result['percentage'] >= 70:
        text += "👍 Хорошо! Solid knowledge!\n"
    elif result['percentage'] >= 50:
        text += "⚠️ Удовлетворительно. Есть над чем поработать.\n"
    else:
        text += "📚 Нужно повторить материал.\n"
    
    # Проверяем достижения
    achievements = test_manager.achievement_system.check_achievements(user_id, result, test_manager)
    if achievements:
        achievement_msg = test_manager.achievement_system.get_achievement_message(achievements)
        text += f"\n{achievement_msg}"
    
    # Кнопки для деталей
    keyboard = [
        [InlineKeyboardButton("📋 Детали результатов", callback_data='show_details')],
        [InlineKeyboardButton("📊 В статистику", callback_data='show_stats')],
        [InlineKeyboardButton("📝 Новый тест", callback_data='select_test')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['last_result'] = result
    
    await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    
    return MAIN_MENU

async def process_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых ответов пользователя (для обратной совместимости)"""
    user_message = update.message.text.strip()
    test_id = context.user_data.get('current_test')
    user_id = update.effective_user.id
    
    # Проверяем, не завершен ли уже тест по времени
    if context.user_data.get('time_expired'):
        await update.message.reply_text(
            "❌ Время на этот тест истекло!\n\n"
            "➡️ Используйте /start чтобы начать новый тест."
        )
        return MAIN_MENU
    
    # Проверяем, не завершен ли уже тест
    if context.user_data.get('test_completed'):
        await update.message.reply_text(
            "❌ Этот тест уже завершен.\n\n"
            "➡️ Используйте /start чтобы начать новый тест."
        )
        return MAIN_MENU
    
    if not test_id:
        await update.message.reply_text("❌ Ошибка: тест не выбран")
        return await start(update, context)
    
    test_manager = TestManager()
    test = test_manager.get_test(test_id)
    
    if not test:
        await update.message.reply_text("❌ Тест не найден")
        return await start(update, context)
    
    # Парсим ответы
    answers = [ans.strip().upper() for ans in user_message.split(',')]
    
    # Проверяем ответы
    result = test_manager.check_answers(test_id, answers, user_id)
    
    if 'error' in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return WAITING_ANSWERS
    
    # Отменяем таймер если он еще работает
    timer_task_obj = context.user_data.get('timer_task')
    if timer_task_obj and not timer_task_obj.done():
        timer_task_obj.cancel()
        print("⏰ Таймер отменен - ответы получены")
    
    # Помечаем тест как завершенный
    context.user_data['test_completed'] = True
    
    # Форматируем результаты
    text = f"📊 РЕЗУЛЬТАТЫ: {test['name']}\n\n"
    text += f"✅ Правильных: {result['correct_count']}/{result['total_questions']}\n"
    text += f"📈 Процент: {result['percentage']}%\n\n"
    
    # Оценка
    if result['percentage'] >= 90:
        text += "🎉 Отлично! Превосходный результат!\n"
    elif result['percentage'] >= 70:
        text += "👍 Хорошо! Solid knowledge!\n"
    elif result['percentage'] >= 50:
        text += "⚠️ Удовлетворительно. Есть над чем поработать.\n"
    else:
        text += "📚 Нужно повторить материал.\n"
    
    # Проверяем достижения
    achievements = test_manager.achievement_system.check_achievements(user_id, result, test_manager)
    if achievements:
        achievement_msg = test_manager.achievement_system.get_achievement_message(achievements)
        text += f"\n{achievement_msg}"
    
    # Кнопки для деталей
    keyboard = [
        [InlineKeyboardButton("📋 Детали результатов", callback_data='show_details')],
        [InlineKeyboardButton("📊 В статистику", callback_data='show_stats')],
        [InlineKeyboardButton("📝 Новый тест", callback_data='select_test')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['last_result'] = result
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return MAIN_MENU

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    
    test_manager = TestManager()
    stats = test_manager.get_user_statistics(user_id)
    
    if not stats or 'tests' not in stats or not stats['tests']:
        keyboard = [
            [InlineKeyboardButton("📝 Пройти тест", callback_data='select_test')],
            [InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📊 Статистика\n\n"
            "У вас пока нет пройденных тестов.",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    # Формируем статистику
    tests = stats['tests']
    total_tests = len(tests)
    avg_percentage = sum(test['result']['percentage'] for test in tests) / total_tests
    
    text = f"📊 Ваша статистика\n\n"
    text += f"📈 Всего тестов: {total_tests}\n"
    text += f"🏆 Средний результат: {avg_percentage:.1f}%\n\n"
    
    text += "📋 Последние тесты:\n"
    for test in tests[-5:]:
        text += f"• {test['test_name']}: {test['result']['percentage']}%\n"
    
    keyboard = [
        [InlineKeyboardButton("📝 Пройти тест", callback_data='select_test')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return MAIN_MENU

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает достижения пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    
    test_manager = TestManager()
    user_stats = test_manager.get_user_statistics(user_id)
    
    if not user_stats:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏆 Достижения\n\n"
            "У вас пока нет достижений. Пройдите первый тест!",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    # Получаем все возможные достижения
    all_achievements = test_manager.achievement_system.achievements
    tests_count = len(user_stats.get('tests', []))
    
    text = "🏆 Ваши достижения:\n\n"
    
    # Проверяем каждое достижение
    for achievement_id, achievement in all_achievements.items():
        has_achievement = False
        
        if achievement_id == 'first_test' and tests_count >= 1:
            has_achievement = True
        elif achievement_id == 'persistent' and tests_count >= 5:
            has_achievement = True
        # Для остальных достижений нужна более сложная логика
        
        icon = "✅" if has_achievement else "❌"
        text += f"{icon} {achievement['icon']} {achievement['name']}\n"
        text += f"   {achievement['description']}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return MAIN_MENU

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку"""
    query = update.callback_query
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "ℹ️ Помощь\n\n"
        "📚 Бот для проверки тестов\n\n"
        "Как пользоваться:\n"
        "1. Выберите 'Выбор теста'\n"
        "2. Выберите нужный тест\n"
        "3. ⏰ У вас 1 час 5 минут на решение\n"
        "4. Отвечайте на вопросы с помощью кнопок\n"
        "5. Получите результат и достижения\n\n"
        "🏆 Система достижений:\n"
        "• Пройдите тесты чтобы получить достижения\n"
        "• Следите за своим прогрессом",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def show_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали результатов"""
    query = update.callback_query
    await query.answer()
    
    result = context.user_data.get('last_result')
    
    if not result:
        await query.edit_message_text("❌ Результаты не найдены")
        return MAIN_MENU
    
    text = "📋 Детали результатов:\n\n"
    for detail in result['detailed_results']:
        status = "✅" if detail['is_correct'] else "❌"
        text += f"{status} {detail['question_number']:2d}: "
        text += f"Ваш: {detail['user_answer']} | "
        text += f"Прав: {detail['correct_answer']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return MAIN_MENU

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("❌ Доступ запрещен")
        else:
            await update.message.reply_text("❌ Доступ запрещен")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика всех", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "⚙️ Панель администратора:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚙️ Панель администратора:",
            reply_markup=reply_markup
        )
    
    return ADMIN_PANEL

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает действия администратора"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == 'admin_stats':
        await show_admin_stats(update, context)
    elif action == 'admin_users':
        await show_admin_users(update, context)
    
    return ADMIN_PANEL

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику всех пользователей"""
    query = update.callback_query
    
    test_manager = TestManager()
    all_stats = test_manager.get_all_users_stats()
    
    if not all_stats:
        await query.edit_message_text("📊 Нет данных о пользователях")
        return
    
    total_users = len(all_stats)
    total_tests = sum(len(user['stats'].get('tests', [])) for user in all_stats)
    avg_percentage = sum(
        test['result']['percentage'] 
        for user in all_stats 
        for test in user['stats'].get('tests', [])
    ) / total_tests if total_tests > 0 else 0
    
    text = f"📊 Общая статистика\n\n"
    text += f"👥 Всего пользователей: {total_users}\n"
    text += f"📈 Всего тестов пройдено: {total_tests}\n"
    text += f"🏆 Средний результат: {avg_percentage:.1f}%\n\n"
    
    text += "Топ пользователей:\n"
    user_scores = []
    for user in all_stats:
        user_tests = user['stats'].get('tests', [])
        if user_tests:
            avg_score = sum(test['result']['percentage'] for test in user_tests) / len(user_tests)
            user_scores.append((user['user_id'], avg_score, len(user_tests)))
    
    user_scores.sort(key=lambda x: x[1], reverse=True)
    
    for i, (user_id, score, tests_count) in enumerate(user_scores[:5], 1):
        text += f"{i}. ID: {user_id[:8]}... - {score:.1f}% ({tests_count} тестов)\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список пользователей"""
    query = update.callback_query
    
    test_manager = TestManager()
    all_stats = test_manager.get_all_users_stats()
    
    text = f"👥 Список пользователей: {len(all_stats)}\n\n"
    
    for i, user in enumerate(all_stats[:10], 1):  # Показываем первых 10
        user_tests = user['stats'].get('tests', [])
        tests_count = len(user_tests)
        text += f"{i}. ID: {user['user_id']} - {tests_count} тестов\n"
    
    if len(all_stats) > 10:
        text += f"\n... и еще {len(all_stats) - 10} пользователей"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    return await start_from_query(update, context)

async def start_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск главного меню из callback"""
    query = update.callback_query
    
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("📝 Выбор теста", callback_data='select_test')],
        [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')],
        [InlineKeyboardButton("🏆 Достижения", callback_data='show_achievements')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')]
    ]
    
    # Добавляем админ-панель для администраторов
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📚 Проверка тестов\n\nГлавное меню:",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    await update.message.reply_text("Используйте /start для открытия главного меню")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда админ-панели"""
    return await admin_panel(update, context)

def main():
    """Запуск бота"""
    print("🚀 Запуск бота на Render...")
    
    # Создаем application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Настройка обработчиков
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start), 
            CommandHandler('admin', admin_command)
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_handler, pattern='^(select_test|show_stats|show_achievements|help|admin_panel)$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
                CallbackQueryHandler(show_details, pattern='^show_details$')
            ],
            SELECTING_TEST: [
                CallbackQueryHandler(start_test_with_buttons, pattern='^test_'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ],
            WAITING_ANSWERS_BUTTONS: [
                CallbackQueryHandler(handle_button_answer, pattern='^answer_'),
                CallbackQueryHandler(handle_navigation, pattern='^(prev_|next_|finish_test)')
            ],
            WAITING_ANSWERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_answers)
            ],
            ADMIN_PANEL: [
                CallbackQueryHandler(handle_admin_actions, pattern='^admin_'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ]
        },
        fallbacks=[CommandHandler('cancel', back_to_menu)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    
    print("✅ Бот запущен и готов к работе!")
    print("📱 Ожидание сообщений...")
    
    # Запуск бота с обработкой ошибок
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
