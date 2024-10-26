import asyncio
import aiohttp
import pymysql
import schedule
import time
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
from flask import Flask, render_template

API_KEY = 'abe958810a040c4c7f5ed8a6c1e701ef'
cities = ['Delhi', 'Mumbai', 'Chennai', 'Bangalore', 'Kolkata', 'Hyderabad']

app = Flask(__name__)

def kelvin_to_celsius(kelvin):
    return kelvin - 273.15

def save_weather_data_batch(data):
    connection = None
    cursor = None
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='', 
            database='weather_data',
            autocommit=True,
            ssl={"ssl": False}
        )
        cursor = connection.cursor()

    
        sql = "INSERT INTO weather_reports (city, temp, feels_like, main, dt) VALUES (%s, %s, %s, %s, %s)"
        values = [(entry['city'], entry['temp'], entry['feels_like'], entry['main'], entry['dt']) for entry in data if entry]

        cursor.executemany(sql, values)
        connection.commit()
        print("Weather data saved successfully.")

    except pymysql.MySQLError as e:
        print(f"Error saving weather data: {e}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

async def fetch_weather_data(city, session):
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}'
    try:
        async with session.get(url) as response:
            print(f"Fetching data for {city}, status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"Data for {city}: {data}")
                return {
                    'city': city,
                    'temp': kelvin_to_celsius(data['main']['temp']),
                    'feels_like': kelvin_to_celsius(data['main']['feels_like']),
                    'main': data['weather'][0]['main'],
                    'dt': datetime.fromtimestamp(data['dt'])
                }
            else:
                print(f"Failed to fetch data for {city}, status: {response.status}")
                return None
    except Exception as e:
        print(f"Error fetching data for {city}: {e}")
        return None

async def get_all_weather_data():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_weather_data(city, session) for city in cities]
        results = await asyncio.gather(*tasks)
        return results

def fetch_and_store_weather_data():
    try:
        print("Fetching weather data...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        weather_data = loop.run_until_complete(get_all_weather_data())

        if not weather_data or all(data is None for data in weather_data):
            print("No data fetched from API.")
            return
        
        print("Weather data fetched successfully.")
        save_weather_data_batch(weather_data) 
        calculate_daily_summary()
        
    
        plot_temperature(get_daily_summary_data()) 
    except Exception as e:
        print(f"An error occurred during data fetch or storage: {e}")
    finally:
        loop.close()

def calculate_daily_summary():
    today = datetime.now().date()

    connection = None
    cursor = None
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='', 
            database='weather_data',
            autocommit=True,
            ssl={"ssl": False}
        )
        cursor = connection.cursor()

        query = "SELECT * FROM weather_reports WHERE DATE(dt) = %s"
        cursor.execute(query, (today,))
        results = cursor.fetchall()

        if not results:
            print(f"No weather data found for {today}")
            return

        total_temp = 0
        max_temp = float('-inf')
        min_temp = float('inf')
        count = 0
        conditions = defaultdict(int)

        for row in results:
            temp = row[2]
            condition = row[4]
            total_temp += temp
            max_temp = max(max_temp, temp)
            min_temp = min(min_temp, temp)
            count += 1
            conditions[condition] += 1

        if count > 0:
            avg_temp = total_temp / count
            dominant_condition = max(conditions, key=conditions.get)
            save_daily_summary(today, avg_temp, max_temp, min_temp, dominant_condition)

    except pymysql.MySQLError as e:
        print(f"Error calculating daily summary: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def save_daily_summary(date, avg_temp, max_temp, min_temp, dominant_condition):
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='', 
            database='weather_data',
            autocommit=True,
            ssl={"ssl": False}
        )
        cursor = connection.cursor()

        query = """
        INSERT INTO daily_weather_summaries (date, avg_temp, max_temp, min_temp, dominant_condition)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            avg_temp = VALUES(avg_temp),
            max_temp = VALUES(max_temp),
            min_temp = VALUES(min_temp),
            dominant_condition = VALUES(dominant_condition)
        """
        cursor.execute(query, (date, avg_temp, max_temp, min_temp, dominant_condition))
        connection.commit()
        print(f"Daily summary for {date} saved successfully.")
    except pymysql.MySQLError as e:
        print(f"Error saving daily summary: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_daily_summary_data():
    connection = None
    cursor = None
    data = []
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='', 
            database='weather_data',
            autocommit=True
        )
        cursor = connection.cursor()

        query = "SELECT date, avg_temp FROM daily_weather_summaries ORDER BY date ASC"
        cursor.execute(query)
        data = cursor.fetchall()

    except pymysql.MySQLError as e:
        print(f"Error fetching daily summary data: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return data

def plot_temperature(data):
    dates = [entry[0] for entry in data] 
    avg_temps = [entry[1] for entry in data]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, avg_temps, marker='o')
    plt.title('Daily Average Temperatures')
    plt.xlabel('Date')
    plt.ylabel('Average Temperature (°C)')
    plt.xticks(rotation=45)
    plt.grid()
    plt.tight_layout()
    plt.savefig('static/temperature_plot.png')
    plt.show()

from flask import Flask, render_template
import pymysql

app = Flask(__name__)

@app.route('/')
def index():
    connection = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='weather_data'
    )
    cursor = connection.cursor()
    cursor.execute("SELECT date, avg_temp FROM daily_weather_summaries ORDER BY date ASC")
    summaries = cursor.fetchall()
    connection.close()
    return render_template('index.html', summaries=summaries)

if __name__ == '__main__':
    app.run(debug=True)


