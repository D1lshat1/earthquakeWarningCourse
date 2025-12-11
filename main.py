import os
import threading
from datetime import date
import time
import random

import requests
import telebot
from telebot import types
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("TOKEN")
url = os.getenv("URL")
bot = telebot.TeleBot(token)

user_location = {}
user_min_mag = {}
user_alert_enabled = {}

SIMULATION = True

FAKE_QUAKES = [
    {
        "mag":"5",
        "place":"Алматы,20км юго-восток",
        "lat":"43.2389",
        "lon":"76.8897",
        "depth":"12",
        "time":int(time.time())
    },
    {
        "mag":"4.2",
        "place":"Талдыкорган",
        "lat":"45.015",
        "lon":"78.37",
        "depth":"8",
        "time":int(time.time())
    },
    {
        "mag":"3.2",
        "place":"Каскелен",
        "lat":"43.2",
        "lon":"76.6",
        "depth":"15",
        "time":int(time.time())
    }
]

def fake_alerts():
    while True:
        for chat_id, enabled in user_alert_enabled.items():
            if enabled:
                lat, lon = user_location.get(chat_id,(43.24,76.89))
                minmag = user_min_mag.get(chat_id,2)

                quakes = [q for q in FAKE_QUAKES if float(q["mag"]) >= minmag]

                for quake in quakes:
                    bot.send_message(chat_id,
                                     f"ВНИМАНИЕ! Симулированное землетрясение:\n"
                                     f"Магнитуда{quake['mag']} - {quake['place']}\n"
                                     f"Глубина: {quake['depth']} km\n"
                                     f"Координаты: {quake['lat']},{quake['lon']}\n"
                                     f"Посмотреть на карте: https://www.google.com/maps/search/?api=1&query={quake['lat']},{quake['lon']}")

        time.sleep(60)

def get_quakes(lat=43.24, lon=76.89, minmag=2):
    if SIMULATION:
        return [q for q in FAKE_QUAKES if float(q["mag"]) > minmag]

    today = date.today()
    url = (f"https://earthquake.usgs.gov/fdsnws/event/1/query?"
           f"format=geojson&latitude={lat}&longitude={lon}"
           f"&maxradiuskm=1000&starttime={today}&endtime={today}&minmagnitude={minmag}")

    data = requests.get(url).json()

    quakes = []
    for f in data["features"]:
        quakes.append({
            "mag":f["properties"]["mag"],
            "place":f["properties"]["place"],
            "lat":f["geometry"]["coordinates"][1],
            "lon":f["geometry"]["coordinates"][0],
            "depth":f["geometry"]["coordinates"][2],
            "time":f["properties"]["time"] // 1000
        })
    return quakes


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,'Привет,это бот который оповестит тебя о землетрясениях')

@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id,'Что умеет данный бот:\n\n'
                                     '/start - Запуск бота\n'
                                     '/earthquake_today - Сегодняшние землетрясения\n'
                                     '/my_location - Моя геолокация\n'
                                     '/alert_on - Включить уведомления\n'
                                     '/prepare - Советы как действовать при землетрясениях\n'
                                     '/map - Показать карту последних землетрясений\n'
                                     '/quake_risk - Риск землетрясений\n'
                                     '/stats - Статистика землетрясений'
                     )

@bot.message_handler(commands=['earthquake_today'])
def earthquake_today(message):
    minmag = user_min_mag.get(message.chat.id, 2)

    if message.chat.id in user_location:
        lat,lon = user_location[message.chat.id]
    else:
        lat,lon = 43.24,76.89
    quakes = get_quakes(lat, lon, minmag)

    if not quakes:
        bot.send_message(message.chat.id,"Землетрясений нет")
        return

    text = "Сегодняшние землетрясения: "
    for quake in quakes:
        text += f"Mагнитуда {quake['mag']} - {quake['place']}\n"

    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['my_location'])
def my_location(message):

    if message.chat.id in user_location:
        lat, lon = user_location[message.chat.id]
        bot.send_message(message.chat.id,f'Сохраненная локация: {lat},{lon}')
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = types.KeyboardButton('Отправить локацию', request_location=True)
    markup.add(button)
    bot.send_message(message.chat.id,'Отправьте свою локацию',reply_markup=markup)


@bot.message_handler(content_types=['location'])
def location(message):
    lat = message.location.latitude
    lon = message.location.longitude

    user_location[message.chat.id] = lat,lon
    user_min_mag[message.chat.id] = True

    bot.send_message(message.chat.id,f'Локация сохранена: {lat},{lon}',
                     reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['alert_on'])
def alert_on(message):
    user_alert_enabled[message.chat.id] = True

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Включить уведомления"),types.KeyboardButton("Выключить уведомления"))

    bot.send_message(message.chat.id,"Настройка уведомлений",reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in ["Включить уведомления","Выключить уведомления"])
def btn(message):
    if message.text == "Включить уведомления":
        user_alert_enabled[message.chat.id] = True
        bot.send_message(message.chat.id,"Уведомления включены",reply_markup=types.ReplyKeyboardRemove())
    elif message.text == "Выключить уведомления":
        user_alert_enabled[message.chat.id] = False
        bot.send_message(message.chat.id,"Уведомления выключены",reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=['prepare'])
def prepare(message):
    prepares = [
        "Сохраняйте спокойствие",
        "Найдите укрытие под прочным столом или кроватью",
        "Не подходите к явно поврежденным зданиям",
        "Возьмите с собой деньги,паспорт и предметы первой необходимости",
        "Отойдите на открытое место"
    ]

    text = random.choice(prepares)
    bot.send_message(message.chat.id,text)


@bot.message_handler(commands=['map'])
def map(message):
    minmag = user_min_mag.get(message.chat.id, 2)

    if message.chat.id in user_location:
        lat,lon = user_location[message.chat.id]
    else:
        lat,lon = 43.24,76.89

    quakes = get_quakes(lat, lon, minmag)

    if not quakes:
        bot.send_message(message.chat.id,"Землетрясений нет")
        return

    text = "Последние землетрясения:\n\n"
    for quake in quakes[:10]:
        text += f"Магнитуда {quake['mag']} - {quake['place']} (Глубина : {quake['depth']} km) \n"

    map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    text += f"Посмотреть на карте: {map_url}"

    bot.send_message(message.chat.id,text)


@bot.message_handler(commands=['quake_risk'])
def quake_risk(message):
    minmag = user_min_mag.get(message.chat.id, 2)

    if message.chat.id in user_location:
        lat, lon = user_location[message.chat.id]
    else:
        lat, lon = 43.24, 76.89

    quakes = get_quakes(lat, lon, minmag)
    if not quakes:
        bot.send_message(message.chat.id,"Землетрясений нет")
        return

    mags = [float(q['mag'])for q in quakes]
    max_mag = max(mags)
    avg_mag = sum(mags) / len(mags)
    count = len(quakes)

    avg_mag = round(avg_mag)
    if max_mag >= 5 or count >= 3:
        risk = "Высокий"
    elif max_mag >= 4 or count == 2:
        risk = "Средний"
    else:
        risk = "Низкий"


    text = (f"Оценка риска для вашего региона: \n\n"
            f"Количество землетрясений: {count}\n"
            f"Максимальная магнитуда: {max_mag}\n"
            f"Средняя магнитуда: {avg_mag}\n"
            f"Риск: {risk}")

    bot.send_message(message.chat.id,text)


@bot.message_handler(commands=['stats'])
def stats(message):
    minmag = user_min_mag.get(message.chat.id, 2)

    if message.chat.id in user_location:
        lat, lon = user_location[message.chat.id]
    else:
        lat, lon = 43.24, 76.89

    quakes = get_quakes(lat, lon, minmag)
    if not quakes:
        bot.send_message(message.chat.id, "Землетрясений нет")
        return

    mags = [float(q['mag']) for q in quakes]
    max_mag = max(mags)
    avg_mag = sum(mags) / len(mags)
    count = len(quakes)

    avg_mag = round(avg_mag)
    if max_mag >= 5 or count >= 3:
        risk = "Высокий"
    elif max_mag >= 4 or count == 2:
        risk = "Средний"
    else:
        risk = "Низкий"

    text = (f"Статистика землетрясений: \n\n"
            f"Количество землетрясений: {count}\n"
            f"Максимальная магнитуда: {max_mag}\n"
            f"Средняя магнитуда: {avg_mag}\n"
            f"Риск: {risk}\n"
            f"Соберите документы и предметы первой необходимости,на всякий случай,в вашем регионе уже {count} зарегистрированных случая")


    bot.send_message(message.chat.id,text)

threading.Thread(target=fake_alerts, daemon=True).start()


bot.polling(none_stop=True)

