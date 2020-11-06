from dataclasses import dataclass
import re
from typing import List

import httpx
from loguru import logger
import html2text
from bs4 import BeautifulSoup, SoupStrainer

import telegram.ext
from telegram.ext import Updater, CommandHandler


@dataclass
class VKGroup:
    url_path: str           # окончание url группы
    description: str = ''   # человеческое описание группы/название
    last_wall_id: str = ''


PARSER = "lxml"
TOKEN = ''                  # токен ТГ бота
CHAT_ID = ''                # ИД чата, куда бот будет слать сообщения
JOB_INTERVAL = 120          # секунды
VK_BASE_URL = "https://m.vk.com/"


vk_groups = {
    'group_uniq_key': VKGroup(url_path='url_path', description='Tratatata')
}

# html2text config
h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True


def parse_groups() -> List[str]:
    new_posts = []
    for group_key, group in vk_groups.items():
        r = httpx.get(f"{VK_BASE_URL}{group.url_path}")
        if r.is_error:
            logger.error(f"Не смогли получить страницу группы {group_key}.")
            continue

        wall_items = BeautifulSoup(     # получаем последние 5 обявлений
            r.text,
            PARSER,
            parse_only=SoupStrainer('div', attrs={'data-stat-container': 'group_wall'})
        ).find_all('div', attrs={'class': 'wall_item'})

        post_ids = [        # генерим ID (url) для полученных обявлений
            f"wall{item.find('a', attrs={'data-post-id': re.compile('.*')})['data-post-id']}"
            for item in wall_items
        ]
        if not group.last_wall_id:    # при старте мы должны установить точку отсчета для каждой группы
            vk_groups[group_key].last_wall_id = max(post_ids)
            continue

        new_post_ids = [i for i in post_ids if i > group.last_wall_id]
        if new_post_ids:
            vk_groups[group_key].last_wall_id = max(new_post_ids)

        new_posts.extend(new_post_ids)
    return new_posts


def get_data_from_posts(new_posts: List[str]) -> List[str]:
    messages_for_tg = []
    for post in new_posts:
        r = httpx.get(f"{VK_BASE_URL}{post}")
        if r.is_error:
            logger.error(f"Не смогли получить страницу объявления {post}.")
            continue

        pi_text = BeautifulSoup(    # текст обьявления
            r.text,
            PARSER,
            parse_only=SoupStrainer('div', attrs={'class': 'pi_text'})
        )
        pi_signed = BeautifulSoup(  # автор обьявления
            r.text,
            PARSER,
            parse_only=SoupStrainer('div', attrs={'class': 'pi_signed'})
        ).find('a', attrs={'class': 'user'})

        div = str(pi_text).replace("<!DOCTYPE html>\n", '')
        message = f"{h.handle(div)}"
        if pi_signed:
            message = f"{message}\nАвтор:\n{VK_BASE_URL}{pi_signed.get('href')[1:]}"
        messages_for_tg.append(message)
    return messages_for_tg


def callback_minute(context: telegram.ext.CallbackContext):

    messages = get_data_from_posts(parse_groups())

    if not messages:
        logger.info(f"Новые обьявления отсутствуют.")
    for m in messages:
        context.bot.send_message(chat_id=CHAT_ID, text=m)
        logger.info(f"Send_message: {m}")


# tg bot config
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher
jq = updater.job_queue

job_minute = jq.run_repeating(callback_minute, interval=JOB_INTERVAL, first=0)

# Запускаем бота
updater.start_polling(clean=True)









