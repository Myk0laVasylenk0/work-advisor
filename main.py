import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, html, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from jobs_api import init_db, fetch_jobs, save_job_to_db, delete_job_from_db, fetch_saved_jobs
from configuration import TOKEN

# Bot token can be obtained via https://t.me/BotFather


# All handlers should be attached to the Router (or Dispatcher)
# Bot and Dispatcher setup

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}!\nI will help you in job hunting!\nChoose command /search from menu "
        f"and I will try to find suitable positions for you.\nOr choose /review to take a look at your saved vacancies. ")

class SearchJob(StatesGroup):
    waiting_for_keywords = State()
    waiting_for_location = State()
    showing_results = State()

# Start search command handler
@dp.message(Command("search"))
async def start_search(message: types.Message, state: FSMContext):
    await message.answer("Please enter the keywords of the position:")
    await state.set_state(SearchJob.waiting_for_keywords)

# Handle the keywords input
@dp.message(SearchJob.waiting_for_keywords)
async def process_keywords(message: types.Message, state: FSMContext):
    await state.update_data(keywords=message.text)
    await message.answer("Please enter the location:")
    await state.set_state(SearchJob.waiting_for_location)

# Handle the location input and perform the job search
@dp.message(SearchJob.waiting_for_location)
async def process_location(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    keywords = user_data['keywords']
    location = message.text

    # Prepare the initial request parameters
    params = {
        "query": keywords,
        "location": location,
        "distance": "1.0",
        "language": "en_GB",
        "remoteOnly": "false",
        "datePosted": "month",
        "employmentTypes": "fulltime;parttime;intern;contractor",
        "index": "0"
    }
    response_dict = await fetch_jobs(params)
    if 'jobs' in response_dict and response_dict['jobs']:
        await state.update_data(jobs=response_dict['jobs'], job_index=0, params=params)
        await state.set_state(SearchJob.showing_results)
        await show_next_job(message, state)
    else:
        await message.answer('No jobs found.')

async def show_next_job(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    jobs = user_data['jobs']
    job_index = user_data['job_index']

    if job_index < len(jobs):
        job = jobs[job_index]
        # employment_type = job.get('employmenttype', 'N/A')
        # date_posted = job.get('dateposted', 'N/A')
        message_text = f"Title: {html.bold(job['title'])}\nCompany: {job['company']}\nEmployment type: {job['employmentType']}\nJob was posted: {job['datePosted']}\nLink: {job['jobProviders'][0]['url']}"
        next_button = InlineKeyboardButton(text="Next position", callback_data="next_job")
        save_button = InlineKeyboardButton(text="Save this position", callback_data=f"save_job_{job_index}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[next_button, save_button]])
        await message.answer(message_text, reply_markup=keyboard)
        await state.update_data(job_index=job_index + 1)
    else:
        params = user_data['params']
        params['index'] = str(int(params['index']) + 1)

        response_dict = await fetch_jobs(params)

        if 'jobs' in response_dict and response_dict['jobs']:
            await state.update_data(jobs=response_dict['jobs'], job_index=0, params=params)
            await show_next_job(message, state)
        else:
            await message.answer("No more jobs available.")
            await state.clear()

@dp.callback_query(lambda c: c.data.startswith("save_job_"))
async def save_job(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    job_index = int(callback_query.data.split("_")[-1])
    job = user_data['jobs'][job_index]

    await save_job_to_db(job)
    await callback_query.answer("Job saved!")

@dp.callback_query(lambda c: c.data == "next_job")
async def process_next_job(callback_query: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == SearchJob.showing_results.state:
        await show_next_job(callback_query.message, state)
    await callback_query.answer()

class ReviewJobs(StatesGroup):
    reviewing_jobs = State()

@dp.message(Command("review"))
async def review_saved_jobs(message: types.Message, state: FSMContext):
    jobs = await fetch_saved_jobs()

    if jobs:
        await state.set_state(ReviewJobs.reviewing_jobs)
        await state.update_data(review_jobs=jobs, job_index=0)
        await show_saved_job(message, state)
    else:
        await message.answer("No saved jobs found.")

async def show_saved_job(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    jobs = user_data['review_jobs']
    job_index = user_data['job_index']

    if job_index < len(jobs):
        job = jobs[job_index]
        employment_type = job.get('employmenttype', 'N/A')
        date_posted = job.get('dateposted', 'N/A')
        message_text = f"Title: {html.bold(job['title'])}\nCompany: {job['company']}\nEmployment type: {employment_type}\nJob was posted: {date_posted}\nLink: {job['url']}"
        next_button = InlineKeyboardButton(text="Next saved job", callback_data="next_saved_job")
        remove_button = InlineKeyboardButton(text="Remove this job", callback_data=f"remove_job_{job['id']}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[next_button, remove_button]])
        await message.answer(message_text, reply_markup=keyboard)
        await state.update_data(job_index=job_index + 1)
    else:
        await message.answer("No more saved jobs.")
        await state.clear()

@dp.callback_query(lambda c: c.data == "next_saved_job")
async def process_next_saved_job(callback_query: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == ReviewJobs.reviewing_jobs.state:
        await show_saved_job(callback_query.message, state)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("remove_job_"))
async def remove_saved_job(callback_query: types.CallbackQuery, state: FSMContext):
    job_id = int(callback_query.data.split("_")[-1])

    await delete_job_from_db(job_id)
    await callback_query.answer("Job removed!")

async def main() -> None:
    await init_db()  # Initialize the database

    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
