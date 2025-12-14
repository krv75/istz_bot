from dotenv import load_dotenv
import os
import logging
import asyncpg

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    print(f"⚠️ Файл .env не найден по пути: {ENV_PATH}")

# Проверка — выведем значение
print("🔹 DB_PORT =", os.getenv("DB_PORT"))

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),  # важно привести к int
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}


class Database:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(**DB_CONFIG)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def init_db(self):
        conn = await asyncpg.connect(**DB_CONFIG)

        await conn.execute('''
            CREATE TABLE IF NOT  EXISTS students (
            id BIGSERIAL PRIMARY KEY,
            tg_id BIGINT UNIQUE NOT NULL,
            name TEXT,
            phone TEXT
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
            id SERIAL PRIMARY KEY,
            day_of_week VARCHAR(50),
            num_subject VARCHAR(50),
            subject_name TEXT,
            room_number TEXT
            )
            ''')

        await conn.execute('''
        CREATE TABLE IF NOT EXISTS teacher (
        id SERIAL PRIMARY KEY,
        subject_name TEXT,
        teacher_name TEXT)
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS session_periods (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            start_date VARCHAR(50),
            end_date VARCHAR(50)
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS exams_schedule (
            id SERIAL PRIMARY KEY,
            certification TEXT,
            subject_name TEXT,
            exam_date VARCHAR(50),
            teacher_name TEXT
            )
            ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS deadlines (
            id SERIAL PRIMARY KEY,
            subject_name TEXT,
            deadline_date VARCHAR(50),
            description TEXT
            )
            ''')


    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

db = Database()