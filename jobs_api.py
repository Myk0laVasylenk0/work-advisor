import aiohttp
import asyncpg
from configuration import DATABASE_URL, API_KEY

# Cloud Database Config


class DatabaseManager:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await asyncpg.connect(DATABASE_URL)

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def execute(self, query, *params):
        await self.conn.execute(query, *params)

    async def fetch(self, query, *params):
        return await self.conn.fetch(query, *params)

class JobFetcher:
    @staticmethod
    async def fetch_jobs(params):
        url = "https://jobs-api14.p.rapidapi.com/list"
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "jobs-api14.p.rapidapi.com"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response_dict = await response.json()
        return response_dict

class JobSaver:
    @staticmethod
    async def save_job_to_db(db_manager, job):
        query = '''
            INSERT INTO saved_jobs (title, company, employmenttype, dateposted, url)
            VALUES ($1, $2, $3, $4, $5)
        '''
        await db_manager.execute(query, job['title'], job['company'], job['employmentType'], job['datePosted'], job['jobProviders'][0]['url'])

class JobDeleter:
    @staticmethod
    async def delete_job_from_db(db_manager, job_id):
        query = 'DELETE FROM saved_jobs WHERE id = $1'
        await db_manager.execute(query, job_id)

class JobRetriever:
    @staticmethod
    async def fetch_saved_jobs(db_manager):
        query = 'SELECT id, title, company, employmenttype, dateposted, url FROM saved_jobs'
        return await db_manager.fetch(query)

async def init_db():
    db_manager = DatabaseManager()
    await db_manager.connect()
    await db_manager.execute('''
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id SERIAL PRIMARY KEY,
            title TEXT,
            company TEXT,
            employmenttype TEXT,
            dateposted TEXT,
            url TEXT
        )
    ''')
    await db_manager.close()

# Functions to be used in main.py
async def fetch_jobs(params):
    return await JobFetcher.fetch_jobs(params)

async def save_job_to_db(job):
    db_manager = DatabaseManager()
    await db_manager.connect()
    await JobSaver.save_job_to_db(db_manager, job)
    await db_manager.close()

async def delete_job_from_db(job_id):
    db_manager = DatabaseManager()
    await db_manager.connect()
    await JobDeleter.delete_job_from_db(db_manager, job_id)
    await db_manager.close()

async def fetch_saved_jobs():
    db_manager = DatabaseManager()
    await db_manager.connect()
    jobs = await JobRetriever.fetch_saved_jobs(db_manager)
    await db_manager.close()
    return jobs
