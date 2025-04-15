import os
import asyncio
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.types import Message, ChatMemberUpdated, ChatMemberAdministrator
from aiogram.filters import Command

from loguru import logger


from dotenv import load_dotenv

from database import prepare_db, get_strictness_level, set_strictness_level, add_chat, add_deleted

load_dotenv()

SECONDS_TO_DELETE = int(os.getenv('SECONDS_TO_DELETE'))
TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher()


SPAM_KEYWORDS = [
    'скидк', 'акци', 'подборк', 'тур', 'предложен',
    'переход', 'купи', 'заказ', 'выгод', 'лучш',
    'горящ', 'промо', 'распродаж', 'цена', 'рекомендуем',
    'канал', 'фулл', 'работа', 'подработка', 'зарпл',
    'оформ', 'арбитраж', 'подарок', 'отзывы', 'оплата',
    'прогнозы', 'ставки', '18+', 'блог',
]

EMOJI_PATTERNS = [r'↑', r'👆', r'🔥', r'💥', r'🤑', r'👇', r'❗', r'⚠']



def spam_bot_probability(nickname: str, bio: str, comment_text: str, time_diff_seconds: int):
    probability = 0.0

    bio = bio.lower()

    bio_keywords = sum(1 for word in SPAM_KEYWORDS if word in bio)
    probability += min(0.3, bio_keywords * 0.1)

    emoji_count = sum(1 for pattern in EMOJI_PATTERNS if re.search(pattern, bio))
    probability += min(0.2, emoji_count * 0.05)


    if len(bio) > 0:
        uppercase_ratio = sum(1 for c in bio if c.isupper()) / len(bio)
        if uppercase_ratio > 0.7:
            probability += 0.15

    if re.search(r'\d{3,}', nickname) or re.search(r'([a-zA-Z])\1{2,}', nickname):
        probability += 0.1

    comment = comment_text.lower()

    if re.search(r'(http|www|\.ru|\.com|t\.me)', comment):
        probability += 0.25

    comment_spam_words = sum(1 for word in SPAM_KEYWORDS if word in comment)
    probability += min(0.25, comment_spam_words * 0.05)

    word_count = len(comment_text.split())
    if time_diff_seconds > 0:
        speed = (word_count / time_diff_seconds) * 60
        if speed > 120:
            probability += 0.2
        elif speed > 80:
            probability += 0.1

    return min(probability, 1.0)


async def delete_after(*messages: Message, seconds: int = 10):
    await asyncio.sleep(seconds)
    for msg in messages:
        await msg.delete()


@dp.message(Command('start'))
async def start_command(message: Message):
    await message.answer('Привет!\nДобавь меня в чат своего канала и я буду удалять сообщения спам ботов.')


@dp.my_chat_member()
async def my_chat_member_handler(event: ChatMemberUpdated):
    if event.old_chat_member.status in ['left', 'kicked', 'restricted'] and event.new_chat_member.status in ['member', 'administrator']:
        await add_chat(event.chat.id)
        await event.answer('Спасибо, что добавили меня в чат. Теперь я буду помогать с удалением сообщений от спам ботов.\nВы можете изменить строгость бота с помощью /strictness.\nНе забудьте дать мне админку с правом на удаление сообщений, если ещё этого не сделали.')


@dp.message(Command('strictness'))
async def strictness_command(message: Message):
    if message.chat.type == 'private':
        tmsg = await message.reply('Строгость не может быть установлена в личном чате.')
        await delete_after(message, tmsg)
        return
    args = message.text.split(' ')
    if len(args) != 2:
        strictness_level = await get_strictness_level(message.chat.id)
        tmsg = await message.reply(f'Текущая строгость в чате: {strictness_level}.\nЧем ниже число, тем чувствительнее бот.\nСтрогость можно изменить командой: /strictness <10-100>.')
        await delete_after(message, tmsg)
        return
    try:
        strictness_level = int(args[1])
        if strictness_level < 10 or strictness_level > 100:
            raise ValueError
    except:
        tmsg = await message.reply('Правильное использование: /strictness <10-100>.')
        await delete_after(message, tmsg)
        return
    if message.sender_chat is not None and message.sender_chat.id != message.chat.id:
        tmsg = await message.reply('Это может настраивать только админ с правами на удаление сообщений.')
        await delete_after(message, tmsg)
        logger.info(f'Sender chat: {message.sender_chat.id}')
        return
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    logger.info(f'Admin: {member.status}')
    logger.info(f'Can delete messages: {member.can_delete_messages}')
    if member.status != ChatMemberStatus.CREATOR and (member.status not in ChatMemberStatus.ADMINISTRATOR or not member.can_delete_messages):
        tmsg = await message.reply('Это может настраивать только админ с правами на удаление сообщений.')
        await delete_after(message, tmsg)
        return
    await set_strictness_level(message.chat.id, strictness_level)
    tmsg = await message.reply(f'Строгость в чате установлена на {strictness_level}.')
    await delete_after(message, tmsg)


@dp.message(F.text)
async def text_message_handler(message: Message):
    if message.chat.type == 'private':
        return
    await add_chat(message.chat.id)
    strictness_level = await get_strictness_level(message.chat.id)
    if message.from_user.is_bot:
        return
    if message.reply_to_message is None:
        return
    if not message.reply_to_message.is_automatic_forward:
        return
    orig_time = message.reply_to_message.date
    ans_time = message.date
    diff = ans_time - orig_time
    if diff.total_seconds() > SECONDS_TO_DELETE:
        return
    if message.sender_chat is None:
        bio = (await bot.get_chat(message.from_user.id)).bio
        name = message.from_user.full_name
    else:
        bio = message.sender_chat.bio
        name = message.sender_chat.title
    spam_probability = spam_bot_probability(
        name,
        bio or '',
        message.text,
        round(diff.total_seconds())
    )
    logger.info(f'Probability: {round(spam_probability * 100)}')
    if round(spam_probability * 100) >= strictness_level:
        await message.delete()
        await add_deleted(message.chat.id)


async def main():
    me = await bot.get_me()
    logger.info(f'Bot started as @{me.username}')
    await prepare_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())