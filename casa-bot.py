import requests
import time
from datetime import datetime, timezone, timedelta
import telegram
import asyncio
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

# Hämta värden från .env
telegram_token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

# Konfigurerbara variabler
organization_id = "2711"
event_keyword = "sunset"

# URL till API:et
api_url = f"https://api.studentkortet.se/organization/{organization_id}/organization-events"

# Funktion för att skicka telegram-notis
def send_telegram_message(message):
    bot = telegram.Bot(token=telegram_token)
    asyncio.run(bot.send_message(chat_id=chat_id, text=message))

# Funktion för att hämta event-id, occur-id och biljettsstatus
def find_event():
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        latest_event = None

        # Gå igenom eventen från början till slut och spara det senaste eventet som matchar nyckelordet
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict) and 'data' in data:
            events = data['data']
        else:
            print("Oväntat format på API-svaret.")
            return None

        swedish_timezone = timezone(timedelta(hours=1))
        now = datetime.now(swedish_timezone)
        max_date = now + timedelta(days=5)

        for event in events:
            if 'title' in event and event_keyword.lower() in event['title'].lower():
                occurrences = event.get('organization_event_occurrences', [])
                for occurrence in occurrences:
                    start_date = occurrence.get('start_date', None)
                    if start_date:
                        event_datetime = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                        if now < event_datetime <= max_date:
                            latest_event = event
                            occur_id = occurrence['id']
                            sold_out = any(ticket.get('sold_out', False) for ticket in occurrence.get('tickets', []))
                            break

        if latest_event:
            event_id = latest_event['id']
            print(f"Hittade senaste {event_keyword}-eventet! Event ID: {event_id}, Occurrence ID: {occur_id}")
            event_link = f"https://ob.addreax.com/{organization_id}/events/{event_id}/occur/{occur_id}"
            print(f"Länk till eventet: {event_link}")
            print(f"Biljetter slutsålda: {'Ja' if sold_out else 'Nej'}")

            # Skicka Telegram-notis endast om biljetterna inte är slutsålda
            if not sold_out:
                send_telegram_message(f"🎟️ {event_keyword.capitalize()}-eventet hittades! Biljetter är tillgängliga. Länk: {event_link}")

            return event_link if not sold_out else None

        print(f"{event_keyword.capitalize()}-eventet hittades inte.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"Fel vid hämtning av event: {e}")
        return None

# Funktion för att välja antal biljetter med Selenium
def select_tickets(link, ticket_count=2):
    options = webdriver.ChromeOptions()
    options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    options.add_argument("--enable-javascript")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    driver.get(link)

    try:
        # Vänta tills sidan laddats klart
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Scrolla ner för att se till att knappen syns
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Välj biljetter
        plus_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "plus-button"))
        )

        for _ in range(ticket_count):
            plus_button.click()
            time.sleep(0.5)

        print("Två biljetter valda!")

        # Klicka på 'Next'-knappen
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next') and not(@disabled)]"))
        )
        next_button.click()
        print("Klickade på 'Next'!")

    except Exception as e:
        print(f"Kunde inte välja biljetter: {e}")
        with open("error_page.html", "w", encoding="utf-8") as file:
            file.write(driver.page_source)
        print("Sidans HTML sparad som 'error_page.html'.")

    finally:
        time.sleep(10)
        driver.quit()

# Loop som kollar varje 30:e sekund
while True:
    link = find_event()
    if link:
        print("Klar!")
        select_tickets(link, ticket_count=2)
        break
    time.sleep(30)
