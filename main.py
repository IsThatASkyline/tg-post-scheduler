from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3


from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChat, PeerChannel
from telethon.tl.types import InputPeerEmpty
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import InputChannel
from telethon.tl.types import ChannelParticipantsSearch
import telethon.sync
from telethon.tl.functions.channels import JoinChannelRequest



TOKEN = '5871237130:AAFtGRwICWcrBVQ1S1hqZDf8W6kW7me_SLU'

storage = MemoryStorage()
conn = sqlite3.connect('planirovshik.db', check_same_thread=False)
cursor = conn.cursor()
bot = Bot(TOKEN)
dp = Dispatcher(bot, storage=storage)
scheduler = AsyncIOScheduler()


# Тут вставляй свои данные с https://my.telegram.org/apps
api_id = 29736540
api_hash = 'c1f2cd45b512de78286d3dbcb9775417'

client = TelegramClient('anon', api_id, api_hash)
client.start()


def add_post_to_db(text, chats, time):
    cursor.execute('INSERT INTO posts (text) VALUES (?)', (text,))
    conn.commit()
    post_id = cursor.lastrowid
    for chat in chats:
        cursor.execute('INSERT INTO posts_chats (post_id, chat_id, time) VALUES (?, ?, ?)', (post_id, f'-100{chat}', time,))
        conn.commit()
    return post_id


def add_schedule_job_to_db(job_id, post_id):
    cursor.execute('INSERT INTO jobs_posts (job_id, post_id) VALUES (?, ?)', (job_id, post_id))
    conn.commit()
    return


def edit_post_to_db(post_id, field, value):
    if field == 'text':
        cursor.execute('UPDATE posts set(text) = (?) WHERE id = ?', (value, post_id))
        conn.commit()
    elif field == 'time':
        cursor.execute('UPDATE posts_chats set(time) = (?) WHERE post_id = ?', (value, post_id))
        conn.commit()
    return


def edit_post_in_scheduler(post_id, value):
    scheduler.print_jobs()
    date, time = value.split()
    day, month, year = date.split('-')
    hour, minutes = time.split(':')
    jobs_ids = cursor.execute('SELECT job_id FROM jobs_posts WHERE post_id = ?', (post_id,)).fetchall()
    jobs_ids = [x[0] for x in jobs_ids]
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.id in jobs_ids:
            try:
                job.reschedule('cron', year=year, month=month, day=day, hour=hour, minute=minutes)
                cursor.execute('UPDATE posts_chats set(time) = (?) WHERE post_id = ?', (value, post_id))
                conn.commit()
            except Exception as ex:
                print(ex)
                continue
    return


def get_menu1():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton(text='Посмотреть посты', callback_data=f'view_posts'))
    kb.add(InlineKeyboardButton(text='Добавить пост', callback_data=f'add_post'))
    return kb


def get_menu_posts(post_id):
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(InlineKeyboardButton(text='Изменить текст поста', callback_data=f'change_text_{post_id}'))
    kb.add(InlineKeyboardButton(text='Изменить получателей', callback_data=f'change_chats_{post_id}'))
    kb.add(InlineKeyboardButton(text='Изменить время', callback_data=f'change_time_{post_id}'))
    kb.add(InlineKeyboardButton(text='Удалить пост', callback_data=f'remove_post_{post_id}'))
    return kb


class ClientStatesGroup(StatesGroup):
    in_menu = State()
    view_post = State()
    add_post = State()
    add_post_text = State()
    add_post_chats = State()
    add_post_time = State()
    change_text = State()
    change_time = State()
    change_post_info = State()


@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await bot.send_message(chat_id=message.chat.id, text=f"Что вы хотите сделать?", reply_markup=get_menu1())
    await ClientStatesGroup.in_menu.set()

@dp.callback_query_handler(lambda call: call.data.startswith('view_posts'), state=ClientStatesGroup.in_menu)
async def view_posts(call):
    await call.message.delete()
    posts = cursor.execute('SELECT * FROM posts').fetchall()
    for post in posts:
        post_id = post[0]
        await bot.send_message(chat_id=call.from_user.id, text=f"ПОСТ №{post_id} \n{post[1]}", reply_markup=get_menu_posts(post_id))
    await ClientStatesGroup.view_post.set()

@dp.callback_query_handler(lambda call: call.data.startswith('change_text'), state=ClientStatesGroup.view_post)
async def change_text(call, state: FSMContext):
    await call.message.delete()
    post_id = call.data.strip('change_text_')
    async with state.proxy() as data:
        data['post_id'] = post_id
        data['change_field'] = 'text'
    await bot.send_message(chat_id=call.from_user.id, text="Введите новый текст поста")
    await ClientStatesGroup.change_post_info.set()

@dp.callback_query_handler(lambda call: call.data.startswith('change_time'), state=ClientStatesGroup.view_post)
async def change_time(call, state: FSMContext):
    post_id = call.data.strip('change_time_')
    async with state.proxy() as data:
        data['post_id'] = post_id
        data['change_field'] = 'time'
    await call.message.delete()
    await bot.send_message(chat_id=call.from_user.id, text="Введите новое время поста")
    await ClientStatesGroup.change_post_info.set()

@dp.message_handler(state=ClientStatesGroup.change_post_info)
async def change_post_on_db(message: types.Message, state: FSMContext):
    await message.delete()
    async with state.proxy() as data:
        post_id = data['post_id']
        field = data['change_field']
    try:
        edit_post_to_db(post_id, field, message.text)
        if field == 'time':
            edit_post_in_scheduler(post_id, message.text)
        await bot.send_message(chat_id=message.from_user.id, text=f"Поле {field} изменено", reply_markup=get_menu1())
    except Exception as ex:
        print(ex)
        await bot.send_message(chat_id=message.from_user.id, text=f"Ошибка при изменении")
    await ClientStatesGroup.in_menu.set()

@dp.callback_query_handler(lambda call: call.data.startswith('remove_post'), state=ClientStatesGroup.view_post)
async def remove_post(call):
    await call.message.delete()
    post_id = call.data.strip('remove_post_')
    cursor.execute('DELETE FROM posts WHERE id = ?', (post_id, ))
    conn.commit()
    cursor.execute('DELETE FROM posts_chats WHERE post_id = ?', (post_id, ))
    conn.commit()
    await bot.send_message(chat_id=call.from_user.id, text=f"Пост удален", reply_markup=get_menu1())
    await ClientStatesGroup.in_menu.set()

@dp.callback_query_handler(lambda call: call.data.startswith('add_post'), state=ClientStatesGroup.in_menu)
async def add_post(call):
    await call.message.delete()
    await bot.send_message(chat_id=call.from_user.id, text="Введите текст поста")
    await ClientStatesGroup.add_post_text.set()

@dp.message_handler(state=ClientStatesGroup.add_post_text)
async def add_post_text(message: types.Message, state: FSMContext):
    await message.delete()
    async with state.proxy() as data:
        data['post_text'] = message.text
    await bot.send_message(chat_id=message.chat.id, text="Введите @username нужных чатов через пробел")
    await ClientStatesGroup.add_post_chats.set()

@dp.message_handler(state=ClientStatesGroup.add_post_chats)
async def add_post_chats(message: types.Message, state: FSMContext):
    await message.delete()
    chats_ids = []
    try:
        chats = message.text.split()
        if type(chats) is list:
            for chat in chats:
                chat_entity = await client.get_input_entity(chat)
                chats_ids.append(chat_entity.channel_id)
        else:
            chat = message.text
            chat_entity = await client.get_input_entity(chat)
            chats_ids.append(chat_entity.channel_id)
    except Exception as ex:
        print(ex)
    async with state.proxy() as data:
        data['post_chats'] = chats_ids
    await bot.send_message(chat_id=message.chat.id, text="Введите время, в которое должны выходить посты")
    await ClientStatesGroup.add_post_time.set()

@dp.message_handler(state=ClientStatesGroup.add_post_time)
async def add_post_time(message: types.Message, state: FSMContext):
    await message.delete()
    time = message.text
    async with state.proxy() as data:
        data['post_time'] = time
    try:

        async with state.proxy() as data:
            text = data['post_text']
            chats = data['post_chats']
            time = data['post_time']
        post_id = add_post_to_db(text, chats, time)
        chats = cursor.execute('SELECT * FROM posts_chats WHERE post_id = ?', (post_id, )).fetchall()
        for chat in chats:
            add_schedule_job(chat)
        await bot.send_message(chat_id=message.chat.id, text="Пост успешно добавлен", reply_markup=get_menu1())
    except:
        await bot.send_message(chat_id=message.chat.id, text="Ошибка при добавлении в бд", reply_markup=get_menu1())
    await ClientStatesGroup.in_menu.set()



async def spam(post_id, chat_id):
    post = cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id, )).fetchone()
    cursor.execute('DELETE FROM jobs_posts WHERE post_id = ?', (post_id,))
    cursor.execute('DELETE FROM posts_chats WHERE (post_id, chat_id) = (?, ?)', (post_id, chat_id,))
    conn.commit()
    try:
        count = len(cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchall())
        if count > 1:
            await bot.send_message(chat_id=chat_id, text=post[1])
        else:
            await bot.send_message(chat_id=chat_id, text=post[1])
            cursor.execute('DELETE FROM posts WHERE id = (?)', (post_id,))
            conn.commit()
    except Exception as ex:
        print(ex)



def schedule_jobs():
    chats = cursor.execute('SELECT * FROM posts_chats').fetchall()
    for chat in chats:
        add_schedule_job(chat)

def add_schedule_job(chat):
    post_id = chat[1]
    chat_id = chat[2]
    date, time = chat[3].split()
    day, month, year = date.split('-')
    hour, minutes = time.split(':')
    job = scheduler.add_job(spam, 'cron', year=year, month=month, day=day, hour=hour, minute=minutes, args=(post_id, chat_id))
    add_schedule_job_to_db(job.id, post_id)


async def on_startup(dp):
    schedule_jobs()


if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    client.run_until_disconnected()

