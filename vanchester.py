import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
import os

# --- КОНФИГУРАЦИЯ ---
# Читаем данные из переменных окружения Render
API_TOKEN = os.environ.get("API_TOKEN", "8085101197:AAEIGuw-ePwPePs1ljjwzSWm_6HD1CBUN90")
ADMIN_CHAT_ID_STR = os.environ.get("ADMIN_CHAT_ID", "6060013300")
ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR) if ADMIN_CHAT_ID_STR.isdigit() else 0

# Настройки для Render.com
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_PATH = "/webhook"
# !!! ЗАМЕНИТЕ ЭТОТ URL НА ВАШ АДРЕС НА RENDER (например, https://vanchester.onrender.com) !!!
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://vanchester.onrender.com") + WEBHOOK_PATH


# FSM States (состояния)
class BookingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_service = State()


# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()


# --- ОБРАБОТЧИКИ БОТА ---

@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    start_parameter = message.text.replace("/start", "").strip()
    service_name = None

    if start_parameter:
        # Определяем название услуги по коду
        if start_parameter == "apps":
            service_name = "Установка приложений"
        elif start_parameter == "cert":
            service_name = "Установка личного сертификата Apple"
        elif start_parameter == "iphone_restore":
            service_name = "Восстановление iPhone"
        elif start_parameter == "win_reinstall":
            service_name = "Переустановка Windows"
        elif start_parameter == "iphone_norecovery":
            service_name = "Восстановление iPhone без потери данных"

    if service_name:
        # Если услуга найдена, сохраняем её и запрашиваем имя
        await state.update_data(service=service_name)
        await message.answer(f"Здравствуйте! Вы выбрали услугу **'{service_name}'**. Как вас зовут?")
        await state.set_state(BookingStates.waiting_for_name)
    else:
        # Если пришли просто по /start или код неверный, просим выбрать услугу
        await message.answer("Здравствуйте! Я бот для записи на прием. Пожалуйста, выберите услугу из списка.")
        # Здесь можно добавить кнопки для выбора, если нужно


@dp.message(BookingStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(user_name=message.text)
    contact_button = KeyboardButton(text="Отправить мой номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer(
        "Спасибо, ваше имя сохранено. Теперь, пожалуйста, отправьте ваш номер телефона, нажав на кнопку ниже:",
        reply_markup=keyboard
    )
    await state.set_state(BookingStates.waiting_for_phone)


# ОБРАБОТЧИК КНОПКИ НОМЕРА ТЕЛЕФОНА (F.contact)
@dp.message(BookingStates.waiting_for_phone, F.contact)
async def process_phone_by_contact(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    data = await state.get_data()
    user_name = data.get("user_name")
    user_id = message.from_user.id
    username_tg = message.from_user.username if message.from_user.username else "нет"
    # Получаем название услуги, которую выбрали
    service_name = data.get("service", "Не указана")

    admin_message = (
        f"🎉 **НОВАЯ ЗАПИСЬ НА ПРИЕМ!** 🎉\n\n"
        f"💅 **Услуга:** {service_name}\n"
        f"👤 **Имя:** {user_name}\n"
        f"📞 **Телефон:** {phone_number}\n"
        f"🤖 **Tg Username:** @{username_tg}\n"
        f"🆔 **Tg ID:** `{user_id}`"
    )
    if ADMIN_CHAT_ID:
        await bot.send_message(ADMIN_CHAT_ID, admin_message)

    await message.answer(
        f"Отлично, {user_name}! Ваша заявка на '{service_name}' принята. Скоро с вами свяжутся!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()


# ОБРАБОТЧИК РУЧНОГО ВВОДА НОМЕРА ТЕЛЕФОНА (F.text)
@dp.message(BookingStates.waiting_for_phone, F.text)
async def process_phone_by_text_manual(message: types.Message):
    await message.answer(
        "Пожалуйста, воспользуйтесь **кнопкой 'Отправить мой номер телефона'** ниже. "
        "Или введите номер вручную в международном формате (+79991234567)."
    )


# --- ФУНКЦИИ ЗАПУСКА/ОСТАНОВКИ НА RENDER ---
async def on_startup(bot: Bot):
    print(f"Setting webhook to: {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL)
    if ADMIN_CHAT_ID:
        await bot.send_message(ADMIN_CHAT_ID, "✅ Бот запущен на сервере и готов принимать заявки!")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    if ADMIN_CHAT_ID:
        await bot.send_message(ADMIN_CHAT_ID, "❌ Бот остановлен/выключен.")


def main():
    logging.basicConfig(level=logging.INFO)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True,
    )
    webhook_requests_handler.register(app, WEBHOOK_PATH)
    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT,
    )


if __name__ == "__main__":
    main()