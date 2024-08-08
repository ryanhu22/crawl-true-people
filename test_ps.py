import pytest
from playwright.sync_api import sync_playwright
import time
import pandas as pd
import random


def random_small_time():
    return random.randint(250, 400)


def random_big_time():
    return random.randint(800, 1200)


def search_address_from_home(page, address1, address2):
    # Search for an address
    page.click("text=Address Search")
    page.wait_for_timeout(random_big_time())

    # Slow type the street address
    address_input = page.locator("input[aria-label='Street Address']").first
    address_input.click()  # Ensure the input is focused

    for char in address1:
        address_input.type(char, delay=10)  # 100ms delay between keystrokes
        time.sleep(0.1)  # Additional 100ms delay after each character

    address_input.press("Tab")

    for char in address2:
        page.keyboard.type(char, delay=10)  # 100ms delay between keystrokes
        time.sleep(0.1)  # Additional 100ms delay after each character

    # Press Enter key
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")

    # Wait for the search results to load
    page.wait_for_timeout(random_big_time())  # Increase the timeout if necessary


def extract_phone_email(page):
    # Set a default timeout of 3000 milliseconds (3 seconds) for all operations on this page
    page.set_default_timeout(3000)
    page.wait_for_timeout(3000)  # Wait for the person details to load
    telephones = []
    try:
        telephone_list = page.locator("span[itemprop='telephone']").element_handles()
        for telephone in telephone_list:
            telephones.append(telephone.inner_text())
    except Exception as e:
        telephone = None
        print(f"Error extracting telephone: {e}")

    try:
        email_container = page.locator(
            "div.col-12:has(div.h5:has-text('Email Addresses'))"
        ).first
        emails = email_container.all_inner_texts()[0].split("\n")[1:]
    except Exception as e:
        emails = []
        print(f"Error extracting emails: {e}")
    print(telephones)
    print(emails)
    return telephones, emails


def print_card(card):
    detail_link = card.get_attribute("data-detail-link")
    name = card.locator("div.h4").inner_text()
    age = card.locator("span.content-value").nth(0).inner_text()
    location = card.locator("span.content-value").nth(1).inner_text()
    related_to = card.locator("span.content-value").nth(2).inner_text()
    print(f"Name: {name}")
    print(f"Age: {age}")
    print(f"Location: {location}")
    print(f"Related to: {related_to}")
    print(f"Detail link: {detail_link}")
    print("-" * 50)


def extract_person_details(page, names):
    # Check if any person cards are found
    person_cards = page.locator("div[data-detail-link^='/find/person']")
    card_count = person_cards.count()
    print(f"Found {card_count} person cards")
    telephone_data = dict()
    email_data = dict()

    if card_count == 0:
        print("No person cards found.")
    else:
        for i in range(card_count):
            card = person_cards.nth(i)
            name = card.locator("div.h4").inner_text()
            print(name)
            name_parts = name.split()
            if any(part.lower() in names for part in name_parts):
                # Click card and extract details
                page.wait_for_timeout(random_small_time())
                card.click()
                page.wait_for_timeout(random_small_time())
                telephones, emails = extract_phone_email(page)
                telephones.append(page.url)
                telephone_data[name] = telephones
                email_data[name] = emails

                # Navigate back to the main page
                page.go_back(wait_until="domcontentloaded")

    return telephone_data, email_data


def run_search(page, address1, address2, names):
    page.goto("https://www.truepeoplesearch.com/")

    # Search for an address
    search_address_from_home(page, address1, address2)

    # Extract person details
    telephone_data, email_data = extract_person_details(page, names)
    return telephone_data, email_data

    # page.goto("https://www.truepeoplesearch.com/")


@pytest.mark.only_browser("chromium")  # Specify the browser to use
def test_extract_person_details(playwright):
    browser = playwright.chromium.launch(headless=False)  # Run in headed mode
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}  # Adjust this resolution as needed
    )
    page = context.new_page()
    page.set_default_timeout(
        20000
    )  # Increase the default timeout for all actions in this page

    # CSV Magic
    df = pd.read_csv("fha_loans_mini.csv")

    # Ensure the "Phone numbers" column exists
    if "Phone numbers-Ryan" not in df.columns:
        df["Phone numbers-Ryan"] = None

    if "Emails-Ryan" not in df.columns:
        df["Emails-Ryan"] = None

    for index, row in df.iterrows():
        if pd.notna(row["Phone numbers-Ryan"]):
            continue
        if pd.notna(row["Emails-Ryan"]):
            continue
        address1 = row["Property Address"]
        address2 = str(row["Mailing City"]) + ", " + str(row["Mailing State"])
        names = [name.lower() for name in row["Owner Names"].split(" ")]

        # Cleanups
        if address2 == "S San Fran, CA":
            address2 = "South San Francisco, CA"
        print(address1)
        print(address2)
        print(names)
        telephone_data, email_data = run_search(page, address1, address2, names)

        df.at[index, "Phone numbers-Ryan"] = telephone_data
        df.at[index, "Emails-Ryan"] = email_data

        # Save the modified DataFrame to a new CSV file
        df.to_csv("fha_loans_mini.csv", index=False)

    page.wait_for_timeout(5000)  # Wait for the test to complete
    browser.close()
