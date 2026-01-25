import asyncio
import logging
import requests # для http-запросов к Reddit API
from aiogram import Bot, Dispatcher, Router, F
# Bot — интерфейс для взаимодействия с Telegram Bot API.
# Dispatcher — маршрутизатор входящих сообщений.
# Router — подмодуль диспетчера для группировки обработчиков.
# F — специальный объект для фильтрации сообщений по содержимому
from aiogram.types import Message
from aiogram.filters import Command, CommandStart


BOT_TOKEN = "токен_моего_бота"

# Список названий подреддитов, в которых ищем мемы
MEME_SUBREDDITS = [
    # Русскоязычные
    "Pikabu", "ru", "Russia", "AskARussian", "russian_memes_only",
    "TheRussianMemeSub", "russian", "SovietMemes", "RusNotAsk",

    # Основные мемы
    "memes", "dankmemes", "funny", "me_irl", "wholesomememes",
    "EuropeanMemes",

    # Тематические
    "ProgrammerHumor", "historymemes", "mathmemes", "sciencememes","lanadelrey",
    "comedyheaven", "teenagers", "Catmemes", "MemeTemplates", "DeepFriedMemes", "bonehurtingjuice"

]
# Заголовок User-Agent в HTTP-запросе для корректного обращения к API Reddit и предотвращения блокировки запроса
REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}

def transliterate_ru_to_en(text):
    # Если бот не нашел слово на русском, то он будет переводить русские буквы в английские
    trans_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    return ''.join(trans_dict.get(c.lower(), c) for c in text) # проходим по каждому символу в строке, если символ есть в словаре, то заменяем, если нет оставляем как есть

# Проверка, содержит ли текст русские буквы
def is_russian(text):
    return any('а' <= c.lower() <= 'я' for c in text)

# Ищем мемы через Reddit Search API
def search_reddit_memes(keyword: str, limit: int = 5):
    if not keyword.strip():  # Если ключевое слово пустое или состоит только из пробелов, то возвращаем пустой список
        return []

    results = []
    seen_urls = set()  # Избегаем дубликаты
                       # создаем множество с уже просмотренными реддитами

    for subreddit in MEME_SUBREDDITS:
        if len(results) >= limit:
            break

        # Используем search API
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": keyword, # поисковый запрос
            "restrict_sr": "true",  # ищем только в этом подреддите
            "sort": "relevance", # сортируем по релевантности
            "limit": 25,  # запрашиваем до 25 постов за раз
            "t": "all"  # посты за все время
        }

        try:
            resp = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=12)
            resp.raise_for_status() # вызываем исключение при ошибках
            data = resp.json() # ответ преобразуем в json

            for post in data["data"]["children"]: # т.к. ответе Reddit API список постов находится в data → children.
                                                  # children - список постов в структуре json
                                                  # data - сами данные поста(url, автор и тд)
                post_data = post["data"]
                img_url = post_data.get("url", "")  # извлекаем url изображения из поля "url"

                # Проверяем формат изображения
                if not img_url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                    continue           # пропускаем, если не изображение

                # пропускаем повторения
                if img_url in seen_urls:
                    continue

                seen_urls.add(img_url)       # добавляем url в уже увиденное
                results.append({
                    "title": post_data["title"],  # сохраняем заголовок, url, подреддит
                    "image_url": img_url,
                    "subreddit": subreddit
                })

                if len(results) >= limit:
                    break

        except Exception as e:
            logging.error(f"Ошибка при запросе к r/{subreddit}: {e}")
            continue         # записываем в логи любые ошибки

    return results


# Для структурирования, обработки апдейтов создаем router
router = Router()

@router.message(CommandStart())  # обработчик команды /start
async def cmd_start(message: Message):
    await message.answer(  # await - ключевое слово для приостановки выполнения асинхронной функции
        "Привет!\n\n"
        "Отправь мне слово на русском или на английском.\n"
        "Например, <code>кот</code> или <code>cat</code>, и я найду для тебя мемы на эту тему!",
        parse_mode = "html",
    )

@router.message(Command("help"))  # обработчик команды /help
async def cmd_help(message: Message):
    await message.answer(
        "Просто отправь любое слово — и получишь мемы!\n\n"
        "Примеры:\n"
        "• <code>cat</code> или <code>кот</code>\n"
        "• <code>школа</code> или <code>school</code>\n"
        "• <code>programming</code> или <code>программирование</code>\n\n"
        "Бот попробует найти мемы на русском и английском!",
        parse_mode="html"
    )


@router.message(F.text)   # обработчик любого текстового сообщения, которое не является командой
async def handle_text(message: Message):
    keyword = message.text.strip() # убираем лишние пробелы по краям

# Игнорируем слова, введенные как команды
    if keyword.startswith('/'):
        await message.answer("Неправильно введено слово. Попробуй ещё раз!")
        return

# если поле пустое
    if not keyword:
        await message.answer("Пожалуйста, введи слово для поиска.")
        return

    await message.answer(f"Ищу мемы по слову «{keyword}»...")

# вызываем синхронную функцию search_reddit_memes в отдельном потоке,
# чтобы не блокировать асинхронный event loop, так как requests — блокирующая операция.
    loop = asyncio.get_event_loop()

    # Ищем по оригинальному слову
    memes = await loop.run_in_executor(None, search_reddit_memes, keyword, 5)

    # Если не нашли русское слово, то пробуем транслитерацию
    if not memes and is_russian(keyword):
        transliterated = transliterate_ru_to_en(keyword)
        await message.answer(f"Попробую поискать как «{transliterated}»...")
        memes = await loop.run_in_executor(None, search_reddit_memes, transliterated, 5)

    if not memes:
        await message.answer(
            "Мемы не найдены.\n\n"
            "Попробуй:\n"
            "• Другое слово\n"
            "• Более общую тему (например, <code>животные</code> вместо <code>капибары</code>)\n"
            "• Английский вариант слова",
            parse_mode = "html"
        )
        return

    await message.answer(f"Найдено мемов: {len(memes)}")

    for meme in memes:
        try:
            caption = f"<b>{meme['title']}</b>\n\n r/{meme['subreddit']}"  # делаем заголовок мема жирным (оборачиваем его в <b>...</b> в parse_mode='HTML')
            if len(caption) > 1024:                  # возможно, на Reddit длина подписи к посту будет длиннее,
                caption = caption[:1021] + "..."     # чем разрешено в телеграмме к сообщению(<=1024), поэтому сокращаем длину и добавляем в конце "..."
            await message.answer_photo(
                photo=meme["image_url"],
                caption=caption,
                parse_mode="HTML"
            )
            # Небольшая задержка между отправками
            await asyncio.sleep(0.5)    # задержка между отправками, чтобы не превысить лимиты Telegram API
        except Exception as e:
            logging.error(f"Не удалось отправить мем: {e}")
            continue

async def main(): # Настраиваем формат и уровень логирования
    logging.basicConfig(
        level=logging.INFO, # уровень логирования
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # формат лога: дата и время, имя логгера, уровень, само сообщение
    )
    # инициализируем бот
    bot = Bot(token=BOT_TOKEN)
    # инициализируем диспетчер для принятия входящих обновлений и направления их обработчикам
    dp = Dispatcher()
    # подключаем router к диспетчеру для структурирования и организации кода обработки событий
    dp.include_router(router)

    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
