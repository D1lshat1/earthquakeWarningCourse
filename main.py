import os
import threading
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import date
import time
import random
from io import BytesIO
from PIL import Image
import requests
import telebot
from telebot import types
from dotenv import load_dotenv
from staticmap import StaticMap, CircleMarker
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



def generate_quake_map(quakes, center=(43.24, 76.89), zoom=6, size=(800, 600)):
    m = StaticMap(size[0], size[1], url_template='http://a.tile.openstreetmap.org/{z}/{x}/{y}.png')

    for quake in quakes:
        lat = float(quake['lat'])
        lon = float(quake['lon'])
        mag = float(quake['mag'])
        color = 'red' if mag >= 5 else 'orange' if mag >= 4 else 'yellow'
        radius = 6 + int(mag * 2)
        marker = CircleMarker((lon, lat), color, radius)
        m.add_marker(marker)


    image = m.render(zoom=zoom, center=(float(center[1]), float(center[0])))
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

    map_data = m._to_png(5)
    img = Image.open(BytesIO(map_data))
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def generate_user_location_map(lat, lon, zoom=10, size=(800, 600)):
    m = StaticMap(
        size[0],
        size[1],
        url_template='http://a.tile.openstreetmap.org/{z}/{x}/{y}.png'
    )

    marker = CircleMarker((lon, lat), 'blue', 12)
    m.add_marker(marker)

    image = m.render(zoom=zoom, center=(lon, lat))
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes



def fake_alerts():
    while True:
        for chat_id, enabled in user_alert_enabled.items():
            if not enabled:
                continue

            lat, lon = user_location.get(chat_id, (43.24, 76.89))
            lat, lon = float(lat), float(lon)
            minmag = user_min_mag.get(chat_id, 2)

            quakes = [q for q in FAKE_QUAKES if float(q["mag"]) >= minmag]

            if not quakes:
                continue

            text = "Симулированное землетрясение\n\n"
            for quake in quakes[:5]:
                text += (
                    f"{quake['mag']} | {quake['place']}\n"
                    f"{quake['depth']} км\n\n"
                )

            map_image = generate_quake_map(quakes, center=(lat, lon))

            bot.send_photo(
                chat_id,
                map_image,
                caption=text
            )

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
                                     '/stats - Статистика землетрясений'
                     )

@bot.message_handler(commands=['earthquake_today'])
def earthquake_today(message):
    minmag = user_min_mag.get(message.chat.id, 2)


    lat, lon = user_location.get(message.chat.id, (43.24, 76.89))
    lat, lon = float(lat), float(lon)

    quakes = get_quakes(lat, lon, minmag)

    if not quakes:
        bot.send_message(message.chat.id, "Сегодня землетрясений не зафиксировано")
        return


    text = "Сегодняшние землетрясения:\n\n"
    for quake in quakes:
        text += (
            f"Магнитуда: {quake['mag']}\n"
            f"{quake['place']}\n"
            f"Глубина: {quake['depth']} км\n\n"
        )


    map_image = generate_quake_map(quakes, center=(lat, lon))


    bot.send_photo(
        message.chat.id,
        map_image,
        caption=text
    )


@bot.message_handler(commands=['my_location'])
def my_location(message):
    chat_id = message.chat.id

    if message.chat.id in user_location:
        lat, lon = user_location[message.chat.id]
        caption = (f'Сохраненная локация: {lat},{lon}')
        map_image = generate_user_location_map(lat, lon)
        bot.send_photo(chat_id, map_image, caption=caption)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = types.KeyboardButton('Отправить локацию', request_location=True)
    markup.add(button)
    bot.send_message(message.chat.id,'Отправьте свою локацию',reply_markup=markup)


@bot.message_handler(content_types=['location'])
def location(message):
    lat = float(message.location.latitude)
    lon = float(message.location.longitude)

    user_location[message.chat.id] = (lat, lon)
    user_min_mag[message.chat.id] = 2

    map_image = generate_user_location_map(lat, lon)

    caption = (
        "Ваша локация сохранена\n\n"
        f"Координаты:\n"
        f"Широта: {lat}\n"
        f"Долгота: {lon}"
    )

    bot.send_photo(
        message.chat.id,
        map_image,
        caption=caption,
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(commands=['alert_on'])
def alert_on(message):
    # Показываем кнопки управления уведомлениями
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("Включить уведомления"),
        types.KeyboardButton("Выключить уведомления")
    )

    bot.send_message(
        message.chat.id,
        "Настройка уведомлений. Выберите действие:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: message.text in ["Включить уведомления", "Выключить уведомления"])
def handle_alert_buttons(message):
    chat_id = message.chat.id

    if message.text == "Включить уведомления":
        user_alert_enabled[chat_id] = True

        lat, lon = user_location.get(chat_id, (43.24, 76.89))
        lat, lon = float(lat), float(lon)
        minmag = user_min_mag.get(chat_id, 2)

        quakes = get_quakes(lat, lon, minmag)

        if not quakes:
            bot.send_message(
                chat_id,
                "Уведомления включены.\nНа данный момент землетрясений в вашем регионе нет.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return

        text = "Уведомления включены\n\nПоследние землетрясения:\n\n"
        for quake in quakes[:5]:
            text += (
                f"Магнитуда: {quake['mag']}\n"
                f"{quake['place']}\n"
                f"Глубина: {quake['depth']} км\n\n"
            )

        map_image = generate_quake_map(quakes, center=(lat, lon))

        bot.send_photo(
            chat_id,
            map_image,
            caption=text,
            reply_markup=types.ReplyKeyboardRemove()
        )

    elif message.text == "Выключить уведомления":
        user_alert_enabled[chat_id] = False
        bot.send_message(
            chat_id,
            "Уведомления выключены",
            reply_markup=types.ReplyKeyboardRemove()
        )


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
def show_map(message):
    lat, lon = user_location.get(message.chat.id, (43.24, 76.89))
    lat, lon = float(lat), float(lon)
    minmag = user_min_mag.get(message.chat.id, 2)
    quakes = get_quakes(lat, lon, minmag)

    if not quakes:
        bot.send_message(message.chat.id, "Землетрясений нет")
        return

    map_image = generate_quake_map(quakes, center=(lat, lon))
    bot.send_photo(message.chat.id, map_image, caption="Последние землетрясения (цвет маркера зависит от магнитуды)")


@bot.message_handler(commands=['stats'])
def quake_stats(message):
    chat_id = message.chat.id
    minmag = user_min_mag.get(chat_id, 2)
    lat, lon = user_location.get(chat_id, (43.24, 76.89))
    lat, lon = float(lat), float(lon)

    quakes = get_quakes(lat, lon, minmag)
    if not quakes:
        bot.send_message(chat_id, "Землетрясений нет")
        return

    lats = [float(q['lat']) for q in quakes]
    lons = [float(q['lon']) for q in quakes]
    mags = [float(q['mag']) for q in quakes]
    places = [q['place'] for q in quakes]

    plt.figure(figsize=(8,6))
    plt.scatter(lons, lats, c=mags, s=[m*20 for m in mags],
                cmap='hot', alpha=0.6, edgecolors='k')
    plt.colorbar(label='Магнитуда')
    plt.title('Статистика землетрясений')
    plt.xlabel('Долгота')
    plt.ylabel('Широта')
    plt.xlim(min(lons)-0.1, max(lons)+0.1)
    plt.ylim(min(lats)-0.1, max(lats)+0.1)
    plt.grid(True, alpha=0.3)

    for i, place in enumerate(places):
        plt.text(lons[i], lats[i], place, fontsize=8, ha='left', va='bottom', alpha=0.7)

    buf = BytesIO()
    plt.savefig(buf, format='PNG', bbox_inches='tight')
    buf.seek(0)
    plt.close()

    bot.send_photo(chat_id, buf, caption="Статистика землетрясений в вашем регионе")


threading.Thread(target=fake_alerts, daemon=True).start()


bot.polling(none_stop=True)

