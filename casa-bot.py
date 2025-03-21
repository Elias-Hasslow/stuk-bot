import requests
import time
from datetime import datetime, timezone, timedelta
import telegram
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os

# Ladda in hemliga variabler från .env
load_dotenv()

# Konfigurerbara variabler
organization_id = "2698"
event_keyword = "casanova"
telegram_token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
card_number = os.getenv("CARD_NUMBER")
card_expiry = os.getenv("CARD_EXPIRY")
card_cvc = os.getenv("CARD_CVC")

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
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        plus_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "plus-button"))
        )

        for _ in range(ticket_count):
            plus_button.click()
            time.sleep(0.5)

        print("Två biljetter valda!")

        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next') and not(@disabled)]"))
        )
        next_button.click()
        print("Klickade på 'Next'!")

        # Logga in
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "pin"))
        )
        username_field.send_keys(username)

        password_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "password")))
        password_field.send_keys(password)

        sign_in_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign In') and not(@disabled)]"))
        )
        sign_in_button.click()
        print("Inloggad på Stuk!")

        time.sleep(6)

        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "nets-checkout-iframe"))
        )
        print("Iframe hittad!")

        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)
        print("Bytt till iframen!")

        button = driver.find_element(By.ID, "cardSelectButton")

        # Scroll the button into view
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        time.sleep(1)

        checkbox = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "consentOnMerchantTerms"))
        )

        # Click the checkbox
        checkbox.click()
        print("Checkbox klickad!")

        button.click()
        print("Klickade på knappen!")

        time.sleep(1)

        # Now switch to the inner iframe (`easy-checkout-iframe`)
        easy_checkout_iframe = driver.find_element(By.ID, "easy-checkout-iframe")
        driver.switch_to.frame(easy_checkout_iframe)
        print("Bytt till andra iframen (easy-checkout-iframe)!")

        # Hitta kortnummerfältet och använd JavaScript för att klicka på det
        card_number_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cardNumberInput"))
        )
        card_expiry_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cardExpiryInput"))
        )
        card_cvc_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cardCvcInput"))
        )

        #Fill in the card details
        card_number_field.send_keys(card_number)
        card_expiry_field.send_keys(card_expiry)
        card_cvc_field.send_keys(card_cvc)
        print("Kortnummer ifyllt!")

        # Now, switch back to the outer iframe (nets-checkout-iframe) before clicking the Pay button
        driver.switch_to.default_content()  # Switch back to the main document
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "nets-checkout-iframe"))
        )
        driver.switch_to.frame(iframe)  # Switch back to the outer iframe
        print("Bytt tillbaka till nets-checkout iframen!")

        # Find and click the Pay button
        pay_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btnPay"))
        )
        pay_button.click()
        print("Klickade på 'Pay' knappen!")


    except Exception as e:
        print(f"Kunde inte genomföra biljettval: {e}")

    finally:
        time.sleep(120)

while True:
    link = find_event()
    if link:
        print("Klar!")
        select_tickets(link, ticket_count=2)
    time.sleep(30)
