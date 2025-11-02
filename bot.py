import logging
import json
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8362080499:AAGZJ_LH5Xr9tb7Tm7tcXFbmGOe6-4mzVaI"

# Состояния разговора
MAIN_MENU, SELECTING_TEST, WAITING_ANSWERS = range(3)

# Время теста в секундах (1 час + 5 минут = 65 минут)
TEST_TIME_SECONDS = 65 * 60  # 3900 секунд

class TestManager:
    def __init__(self):
        # Папки для хранения
        self.tests_dir = 'data/tests'
        self.pdfs_dir = 'data/pdfs'
        self.stats_dir = 'data/stats'
        
        # Создаем папки если их нет
        os.makedirs(self.tests_dir, exist_ok=True)
        os.makedirs(self.pdfs_dir, exist_ok=True)
        os.makedirs(self.stats_dir, exist_ok=True)
        
        # Загружаем тесты
        self.tests = self.load_tests()
    
    def load_tests(self):
        """Загружает тесты из JSON файлов"""
        tests = {}
        if os.path.exists(self.tests_dir):
            for filename in os.listdir(self.tests_dir):
                if filename.endswith('.json'):
                    test_id = filename[:-5]  # убираем .json
                    try:
                        with open(os.path.join(self.tests_dir, filename), 'r', encoding='utf-8') as f:
                            tests[test_id] = json.load(f)
                        print(f"✅ Загружен тест: {test_id}")
                    except Exception as e:
                        print(f"❌ Ошибка загрузки теста {test_id}: {e}")
        else:
            print("❌ Папка tests не существует")
        
        print(f"📁 Всего загружено тестов: {len(tests)}")
        return tests
    
    def get_test(self, test_id):
        return self.tests.get(test_id)
    
    def get_all_tests(self):
        return self.tests
    
    def get_pdf_path(self, pdf_filename):
        """Возвращает полный путь к PDF файлу"""
        return os.path.join(self.pdfs_dir, pdf_filename)
    
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
    
    keyboard = [
        [InlineKeyboardButton("📝 Выбор теста", callback_data='select_test')],
        [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')]
    ]
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
    elif choice == 'help':
        return await show_help(update, context)

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
            "Пока нет доступных тестов.\n\n"
            "Чтобы добавить тест:\n"
            "1. Создайте JSON файл в data/tests/\n"
            "2. Положите PDF в data/pdfs/",
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

async def select_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора теста - отправляет PDF и запускает таймер"""
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
    context.user_data['current_test'] = test_id
    context.user_data['test_completed'] = False
    context.user_data['time_expired'] = False
    
    # Пытаемся отправить PDF
    pdf_filename = test.get('pdf_filename')
    if pdf_filename:
        pdf_path = test_manager.get_pdf_path(pdf_filename)
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, 'rb') as pdf_file:
                    await query.message.reply_document(
                        document=pdf_file,
                        filename=f"{test['name']}.pdf",
                        caption=f"📄 {test['name']}\n\n"
                               f"📊 Вопросов: {test['questions_count']}\n"
                               f"⏰ Время: 1 час 5 минут\n\n"
                               f"➡️ После решения пришлите {test['questions_count']} ответов в формате:\n"
                               f"A,B,C,D,A,B,..."
                    )
            except Exception as e:
                print(f"❌ Ошибка отправки PDF: {e}")
                await query.message.reply_text(
                    f"❌ Ошибка отправки PDF файла\n\n"
                    f"📋 {test['name']}\n"
                    f"📊 Вопросов: {test['questions_count']}\n"
                    f"⏰ Время: 1 час 5 минут\n\n"
                    f"➡️ Пришлите {test['questions_count']} ответов: A,B,C,D,..."
                )
        else:
            await query.message.reply_text(
                f"❌ PDF файл не найден: {pdf_filename}\n\n"
                f"📋 {test['name']}\n"
                f"📊 Вопросов: {test['questions_count']}\n"
                f"⏰ Время: 1 час 5 минут\n\n"
                f"➡️ Пришлите {test['questions_count']} ответов: A,B,C,D,..."
            )
    else:
        await query.message.reply_text(
            f"📋 {test['name']}\n"
            f"📊 Вопросов: {test['questions_count']}\n"
            f"⏰ Время: 1 час 5 минут\n\n"
            f"➡️ Пришлите {test['questions_count']} ответов в формате:\n"
            f"A,B,C,D,A,B,..."
        )
    
    # Запускаем таймер
    context.user_data['timer_task'] = asyncio.create_task(
        timer_task(context, query.message.chat_id, test['name'])
    )
    
    # Отправляем напоминание о времени
    await query.message.reply_text(
        f"⏰ ТАЙМЕР ЗАПУЩЕН!\n\n"
        f"У вас 1 час 5 минут на решение теста '{test['name']}'.\n"
        f"Когда закончите, пришлите ответы в формате: A,B,C,D,...\n\n"
        f"⏱️ Если не успеете вовремя, тест будет автоматически завершен."
    )
    
    return WAITING_ANSWERS

async def process_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов пользователя"""
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
        "3. Бот отправит PDF с вопросами\n"
        "4. ⏰ У вас 1 час 5 минут на решение\n"
        "5. Пришлите ответы в формате: A,B,C,D,A,B,...\n"
        "6. Получите результат\n\n"
        "⏰ ВАЖНО: Если не успеете отправить ответы за 1 час 5 минут,\n"
        "тест будет автоматически завершен!",
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

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    return await start_from_query(update, context)

async def start_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск главного меню из callback"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📝 Выбор теста", callback_data='select_test')],
        [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📚 Проверка тестов\n\nГлавное меню:",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    await update.message.reply_text("Используйте /start для открытия главного меню")

def main():
    """Запуск бота"""
    print("🤖 Запуск бота для проверки тестов с исправленным таймером...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Настройка обработчиков
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_handler, pattern='^(select_test|show_stats|help)$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
                CallbackQueryHandler(show_details, pattern='^show_details$')
            ],
            SELECTING_TEST: [
                CallbackQueryHandler(select_test, pattern='^test_'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ],
            WAITING_ANSWERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_answers)
            ],
        },
        fallbacks=[CommandHandler('cancel', back_to_menu)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    
    print("✅ Бот запущен! Напишите /start в Telegram")
    print("⏰ Таймер теста: 1 час 5 минут")
    print("🔔 Бот будет писать 'ВРЕМЯ ВЫШЛО!' если не успеете")
    application.run_polling()

if __name__ == '__main__':
    main()
