from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, MediaGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3, re


from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChat, PeerChannel
# from telethon.tl.types import InputPeerEmpty
# from telethon.tl.functions.messages import GetDialogsRequest
# from telethon.tl.functions.channels import GetParticipantsRequest
# from telethon.tl.types import InputChannel
# from telethon.tl.types import ChannelParticipantsSearch
# import telethon.sync
# from telethon.tl.functions.channels import JoinChannelRequest

import warnings

# Ignore dateparser warnings regarding pytz
warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)



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


async def add_post_to_db(text, chats, time, photos):
    cursor.execute('INSERT INTO posts (text) VALUES (?)', (text,))
    conn.commit()
    post_id = cursor.lastrowid
    not_found = []
    for chat in chats:
        try:
            try:
                chat_entity = await client.get_input_entity(chat)
                print(chat_entity)
                chat_id = f'-100{chat_entity.channel_id}'
            except Exception:
                chat_entity = await client.get_entity(PeerChannel(int(chat.split('-100')[1])))
                chat_id = f'-100{chat_entity.id}'
                chat = chat_entity.title
                print(chat_entity)
            cursor.execute('INSERT INTO posts_chats (post_id, chat_id, chat_name, time) VALUES (?, ?, ?, ?)', (post_id, chat_id, chat, time,))
            conn.commit()
        except Exception as ex:
            not_found.append(chat)
            print(ex)
    for photo in photos:
        try:
            cursor.execute('INSERT INTO photos(post_id, photo_id) VALUES (?, ?)', (post_id, photo,))
            conn.commit()
        except Exception as ex:
            print(ex)
    return post_id, not_found


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
async def start(message: types.Message):
    await bot.send_message(chat_id=message.chat.id, text=f"Что вы хотите сделать?", reply_markup=get_menu1())
    await ClientStatesGroup.in_menu.set()

@dp.callback_query_handler(lambda call: call.data.startswith('view_posts'), state=ClientStatesGroup.in_menu)
async def view_posts(call):
    await call.message.delete()
    posts = cursor.execute('SELECT * FROM posts').fetchall()
    if posts:
        for post in posts:
            post_id = post[0]
            photos = cursor.execute('SELECT photo_id FROM photos WHERE post_id = ?', (post_id, )).fetchall()
            photos = [photo[0] for photo in photos]
            chats = cursor.execute('SELECT chat_name FROM posts_chats WHERE post_id = ?',(post_id, )).fetchall()
            time = cursor.execute('SELECT time FROM posts_chats WHERE post_id = ?', (post_id, )).fetchone()[0]
            await bot.send_photo(chat_id=call.from_user.id, photo=photos[0], caption=f"{'+' + str(len(photos)-1) + ' фото' if len(photos) > 1 else '' } \nПОСТ №{post_id} \n{'-' * 10} \n{post[1]} \n{'-' * 10} \nКаналы: {', '.join([chat[0] for chat in chats])} \nДата публикации: {time}", reply_markup=get_menu_posts(post_id))
            # media_group = []
            # for i, photo in enumerate(photos):
            #     media_group.append(InputMediaPhoto((photo), caption=f"ПОСТ №{post_id} \n{'-' * 10} \n{post[1]} \n{'-' * 10} \nКаналы: {', '.join([chat[0] for chat in chats])} \nДата публикации: {time}" if i == 0 else ''))
            # await bot.send_media_group(chat_id=call.from_user.id, media=media_group)

        await ClientStatesGroup.view_post.set()
    else:
        await bot.send_message(chat_id=call.from_user.id, text="Нет постов", reply_markup=get_menu1())


@dp.callback_query_handler(lambda call: call.data.startswith('change_text'), state=ClientStatesGroup.view_post)
async def change_text(call, state: FSMContext):
    try:
        try:
            await call.message.delete()
        except Exception:
            pass
        post_id = call.data.strip('change_text_')
        msg = await bot.send_message(chat_id=call.from_user.id, text="Введите новый текст поста")
        async with state.proxy() as data:
            data['post_id'] = post_id
            data['change_field'] = 'text'
            data['last_msg'] = msg
        await ClientStatesGroup.change_post_info.set()
    except Exception as ex:
        print(ex)
        await bot.send_message(chat_id=call.from_user.id, text="Возникла непредвиденная ошибка")

@dp.callback_query_handler(lambda call: call.data.startswith('change_time'), state=ClientStatesGroup.view_post)
async def change_time(call, state: FSMContext):
    try:
        try:
            await call.message.delete()
        except Exception:
            pass
        post_id = call.data.strip('change_time_')
        msg = await bot.send_message(chat_id=call.from_user.id, text="Введите новое время поста")
        async with state.proxy() as data:
            data['post_id'] = post_id
            data['change_field'] = 'time'
            data['last_msg'] = msg
        await ClientStatesGroup.change_post_info.set()
    except Exception as ex:
        print(ex)
        await bot.send_message(chat_id=call.from_user.id, text="Возникла непредвиденная ошибка")

@dp.message_handler(state=ClientStatesGroup.change_post_info)
async def change_post_on_db(message: types.Message, state: FSMContext):
    try:
        try:
            await message.delete()
        except Exception:
            pass
        async with state.proxy() as data:
            post_id = data['post_id']
            field = data['change_field']
            last_msg = data['last_msg']
        await last_msg.delete()
        try:
            edit_post_to_db(post_id, field, message.text)
            if field == 'time':
                if re.fullmatch("\d{2}-\d{2}-\d{4} \d{2}:\d{2}", message.text):
                    edit_post_in_scheduler(post_id, message.text)
                    await bot.send_message(chat_id=message.from_user.id, text=f"Поле {field} изменено", reply_markup=get_menu1())
                    await ClientStatesGroup.in_menu.set()
                else:
                    await bot.send_message(chat_id=message.chat.id, text="Пожалуйста введите дату в правильном формате (ДД-ММ-ГГ Ч:М)")
        except Exception as ex:
            await bot.send_message(chat_id=message.from_user.id, text=f"Такого поста не существует")
    except Exception as ex:
        print(ex)
        await bot.send_message(chat_id=message.from_user.id, text="Возникла непредвиденная ошибка")

@dp.callback_query_handler(lambda call: call.data.startswith('remove_post'), state=ClientStatesGroup.view_post)
async def remove_post(call):
    try:
        # Вынести логику отдельно
        await call.message.delete()
        post_id = call.data.strip('remove_post_')
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id, ))
        cursor.execute('DELETE FROM posts_chats WHERE post_id = ?', (post_id, ))
        cursor.execute('DELETE FROM jobs_posts WHERE post_id = ?', (post_id,))
        cursor.execute('DELETE FROM photos WHERE post_id = ?', (post_id,))
        conn.commit()
        await bot.send_message(chat_id=call.from_user.id, text=f"Пост удален", reply_markup=get_menu1())
        await ClientStatesGroup.in_menu.set()
    except Exception:
        await bot.send_message(chat_id=call.from_user.id, text=f"Такого поста не существует", reply_markup=get_menu1())
        await ClientStatesGroup.in_menu.set()

@dp.callback_query_handler(lambda call: call.data.startswith('add_post'), state=ClientStatesGroup.in_menu)
async def add_post(call, state: FSMContext):
    await call.message.delete()
    msg = await bot.send_message(chat_id=call.from_user.id, text="Отправьте фотографии, а затем введите текст поста")
    async with state.proxy() as data:
        data['last_msg'] = msg.message_id
        data['photos_ids'] = []
    await ClientStatesGroup.add_post_text.set()

@dp.message_handler(content_types=['photo'], state=ClientStatesGroup.add_post_text)
async def load_photo(message, state: FSMContext):
    await message.delete()
    async with state.proxy() as data:
        photos_ids = data['photos_ids']
    file_id = message.photo[-1].file_id
    photos_ids.append(file_id)
    async with state.proxy() as data:
        data['photos_ids'] = photos_ids

@dp.message_handler(state=ClientStatesGroup.add_post_text)
async def add_post_text(message: types.Message, state: FSMContext):
    await message.delete()
    async with state.proxy() as data:
        data['post_text'] = message.text
        last_msg = data['last_msg']
    await bot.edit_message_text(chat_id=message.chat.id, message_id=last_msg, text="Введите @username нужных чатов через пробел")
    await ClientStatesGroup.add_post_chats.set()

@dp.message_handler(state=ClientStatesGroup.add_post_chats)
async def add_post_chats(message: types.Message, state: FSMContext):
    await message.delete()
    chats_names = []
    try:
        chats = message.text.split()
        for chat in chats:
            chats_names.append(chat)
        async with state.proxy() as data:
            data['post_chats'] = chats_names
            last_msg = data['last_msg']
        await bot.edit_message_text(chat_id=message.chat.id, message_id=last_msg, text="Введите время, в которое должны выходить посты \nНапример 28-02-2023 12:15")
    except Exception as ex:
        print(ex)
        await bot.edit_message_text(chat_id=message.chat.id, message_id=last_msg, text="Некоторые username не были найдены, добавлены только найденные")
    await ClientStatesGroup.add_post_time.set()

@dp.message_handler(state=ClientStatesGroup.add_post_time)
async def add_post_time(message: types.Message, state: FSMContext):
    await message.delete()
    time = message.text
    async with state.proxy() as data:
        last_msg = data['last_msg']
    if re.fullmatch("\d{2}-\d{2}-\d{4} \d{2}:\d{2}", message.text):
        async with state.proxy() as data:
            data['post_time'] = time
        try:
            async with state.proxy() as data:
                text = data['post_text']
                chats = data['post_chats']
                time = data['post_time']
                photos_ids = data['photos_ids']
            post_id, not_found = await add_post_to_db(text, chats, time, photos_ids)
            chats = cursor.execute('SELECT * FROM posts_chats WHERE post_id = ?', (post_id, )).fetchall()
            for chat in chats:
                add_schedule_job(chat)
            await bot.delete_message(chat_id=message.chat.id, message_id=last_msg)
            if not_found:
                await bot.send_message(chat_id=message.chat.id, text=f"Не были найдены чаты: {', '.join([x for x in not_found])} \nПост будет опубликован только в найденных каналах", reply_markup=get_menu1())
            else:
                await bot.send_message(chat_id=message.chat.id, text="Пост успешно добавлен", reply_markup=get_menu1())
            await ClientStatesGroup.in_menu.set()
        except Exception as ex:
            print(ex)
            await bot.edit_message_text(chat_id=message.chat.id, message_id=last_msg, text="Пожалуйста введите дату в правильном формате (ДД-ММ-ГГ Ч:М)")
    else:
        await bot.edit_message_text(chat_id=message.chat.id, message_id=last_msg, text="Пожалуйста введите дату в правильном формате (ДД-ММ-ГГ Ч:М)")


async def spam(post_id, chat_id):
    post = cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id, )).fetchone()
    photos = cursor.execute('SELECT photo_id FROM photos WHERE post_id = ?', (post_id,)).fetchall()
    photos = [photo[0] for photo in photos]
    cursor.execute('DELETE FROM posts_chats WHERE (post_id, chat_id) = (?, ?)', (post_id, chat_id,))
    conn.commit()
    try:
        count = len(cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchall())
        media = types.MediaGroup()
        for i, photo in enumerate(photos):
            media.attach_photo(InputMediaPhoto((photo), caption=f"{post[1]}" if i == 0 else ''))
        await bot.send_media_group(chat_id=chat_id, media=media)
        # await bot.send_message(chat_id=chat_id, text=post[1])
        if count == 1:
            # Вынести логику отдельно
            cursor.execute('DELETE FROM posts WHERE id = (?)', (post_id,))
            cursor.execute('DELETE FROM jobs_posts WHERE post_id = ?', (post_id,))
            cursor.execute('DELETE FROM photos WHERE post_id = ?', (post_id,))
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
    date, time = chat[4].split()
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

