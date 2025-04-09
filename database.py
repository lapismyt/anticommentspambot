import os
import aiosqlite
from loguru import logger

from dotenv import load_dotenv
load_dotenv()

DB_FILE = os.getenv('DB_FILE')
DEFAULT_STRICTNESS_LEVEL = int(os.getenv('DEFAULT_STRICTNESS_LEVEL'))


async def prepare_db():
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id	   INTEGER PRIMARY KEY,
                    strictness_level    INTEGER DEFAULT 40,
                    deleted    INTEGER DEFAULT 0
                );
                '''
            )
            await db.commit()

        except Exception as e:
            logger.error(f"Ошибка при создании таблицы chats: {e}")


async def add_chat(chat_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            await db.execute('INSERT OR IGNORE INTO chats (chat_id, strictness_level) VALUES (?, ?);', (chat_id, DEFAULT_STRICTNESS_LEVEL))
            await db.commit()

        except Exception as e:
            logger.error(f"Ошибка при добавлении чата в chats: {e}")


async def add_deleted(chat_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            await db.execute('UPDATE chats SET deleted = deleted + 1 WHERE chat_id = ?;', (chat_id,))
            await db.commit()

        except Exception as e:
            logger.error(f"Ошибка при добавлении чата в chats: {e}")


async def get_strictness_level(chat_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            cursor = await db.execute('SELECT strictness_level FROM chats WHERE chat_id = ?;', (chat_id,))

            data = await cursor.fetchone()
            return data[0]

        except Exception as e:
            logger.error(f"Ошибка при получении strictness_level из chats: {e}")
            return 40


async def set_strictness_level(chat_id: int, strictness_level: int):
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            await db.execute('UPDATE chats SET strictness_level = ? WHERE chat_id = ?;', (strictness_level, chat_id))
            await db.commit()

        except Exception as e:
            logger.error(f"Ошибка при установке strictness_level в chats: {e}")


async def get_deleted_single(chat_id: int):
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            cursor = await db.execute('SELECT deleted FROM chats WHERE chat_id = ?;', (chat_id,))

            data = await cursor.fetchone()
            return data[0]

        except Exception as e:
            logger.error(f"Ошибка при получении deleted из chats: {e}")
            return 0


async def get_deleted_sum():
    async with aiosqlite.connect(DB_FILE, timeout=20) as db:
        try:
            cursor = await db.execute('SELECT SUM(deleted) FROM chats;')

            data = await cursor.fetchone()
            return data[0]

        except Exception as e:
            logger.error(f"Ошибка при получении суммы deleted из chats: {e}")
            return 0