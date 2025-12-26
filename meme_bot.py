import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart


BOT_TOKEN = "токен_моего_бота"

# В каких подреддитах ищем
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

REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}

def transliterate_ru_to_en(text: str) -> str:
    # Если бот не нашел слово на русском, то он будет переводить русские буквы в английские
    trans_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    return ''.join(trans_dict.get(c.lower(), c) for c in text)

# Проверка, содержит ли текст русские буквы
def is_russian(text: str) -> bool:
    return any('а' <= c.lower() <= 'я' for c in text)

# Ищем мемы через Reddit Search API
def search_reddit_memes(keyword: str, limit: int = 5):
    if not keyword.strip():
        return []

    results = []
    seen_urls = set()  # Избегаем дубликаты

    for subreddit in MEME_SUBREDDITS:
        if len(results) >= limit:
            break

        # Используем search API
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": keyword,
            "restrict_sr": "true",  # Искать только в этом подреддите
            "sort": "relevance",
            "limit": 25,
            "t": "all"  # Ищем за все время
        }

        try:
            resp = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()

            for post in data["data"]["children"]:
                post_data = post["data"]
                img_url = post_data.get("url", "")

                # Проверяем формат изображения
                if not img_url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                    continue

                # Пропускаем NSFW
                if post_data.get("over_18"):
                    continue

                # Избегаем дубликатов
                if img_url in seen_urls:
                    continue

                seen_urls.add(img_url)
                results.append({
                    "title": post_data["title"],
                    "image_url": img_url,
                    "subreddit": subreddit
                })

                if len(results) >= limit:
                    break

        except Exception as e:
            logging.error(f"Ошибка при запросе к r/{subreddit}: {e}")
            continue

    return results


# Для структурирования
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет!\n\n"
        "Отправь мне слово на русском или на английском.\n"
        "Например, <code>кот</code> или <code>cat</code>, и я найду для тебя мемы на эту тему!",
        parse_mode = "html",
    )

@router.message(Command("help"))
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


@router.message(F.text)
async def handle_text(message: Message):
    keyword = message.text.strip()

# Игнорируем слова, введенные как команды
    if keyword.startswith('/'):
        await message.answer("Неправильно введено слово. Попробуй ещё раз!")
        return

    if not keyword:
        await message.answer("Пожалуйста, введи слово для поиска.")
        return

    await message.answer(f"Ищу мемы по слову «{keyword}»...")

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
            caption = f"<b>{meme['title']}</b>\n\n r/{meme['subreddit']}"
            if len(caption) > 1024:
                caption = caption[:1021] + "..."
            await message.answer_photo(
                photo=meme["image_url"],
                caption=caption,
                parse_mode="HTML"
            )
            # Небольшая задержка между отправками
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.error(f"Не удалось отправить мем: {e}")
            continue


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
