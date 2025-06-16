import os
import re
import time
import logging
import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from app.utils.driver import setup_driver
from app.services.excel import load_existing_emails, append_df_to_excel, EXCEL_FILE

logger = logging.getLogger(__name__)

def login_linkedin(driver, username, password) -> bool:
    logger.info("Logging into LinkedIn...")
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(3)

    if "feed" in driver.current_url:
        logger.info("Login successful.")
        return True
    logger.warning("Login failed.")
    return False

def scrape_profiles(driver, search_url, max_pages=None):
    existing_df, existing_emails = load_existing_emails()
    collected = []
    page = 1

    while True:
        url = f"{search_url}&page={page}"
        logger.info(f"Scraping page {page}: {url}")
        driver.get(url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'lxml')
        profiles = soup.find_all('div', class_=re.compile(r'^linked-area'))
        if not profiles:
            logger.info("No more profiles found.")
            break

        for profile in profiles:
            try:
                name_elem = profile.find('span', {'aria-hidden': 'true'})
                name = name_elem.text.strip() if name_elem else ''
                location_elem = profile.find('div', attrs={'class': lambda c: c and 't-14 t-normal' in c})
                location = location_elem.text.strip() if location_elem else ''
                profile_url_elem = profile.find('a', tabindex='0')
                profile_url = profile_url_elem['href'] if profile_url_elem else ''

                logger.info(f"Processing profile: {name} | {location} | {profile_url}")
                driver.get(profile_url)
                time.sleep(2)
                soup_profile = BeautifulSoup(driver.page_source, 'lxml')

                about_elem = soup_profile.find('div', class_='text-body-medium break-words')
                about = about_elem.text.strip() if about_elem else ''

                comp_elem = soup_profile.find('div', {'style': '-webkit-line-clamp:2;'})
                company_name = comp_elem.text.strip() if comp_elem else ''

                contact_link_elem = soup_profile.find('a', id='top-card-text-details-contact-info')
                email = ''
                if contact_link_elem:
                    logger.info("Visiting contact info page.")
                    driver.get('https://www.linkedin.com' + contact_link_elem['href'])
                    time.sleep(2)
                    soup_info = BeautifulSoup(driver.page_source, 'lxml')
                    mail_tag = soup_info.find('a', href=lambda h: h and h.startswith('mailto:'))
                    if mail_tag:
                        email = mail_tag['href'].replace('mailto:', '').lower()

                if not email:
                    logger.info(f"No email found for {name}, skipping.")
                    continue
                if email in existing_emails:
                    logger.info(f"Duplicate email {email}, skipping.")
                    continue

                logger.info(f"Adding new profile with email: {email}")
                collected.append({
                    'Name': name,
                    'Location': location,
                    'Profile URL': profile_url,
                    'Company Name': company_name,
                    'About': about,
                    'Email': email
                })
                existing_emails.add(email)
            except Exception as e:
                logger.exception(f"Error processing profile: {e}")

        if collected:
            df_new = pd.DataFrame(collected)
            append_df_to_excel(EXCEL_FILE, df_new)
            collected.clear()

        page += 1
        if max_pages and page > max_pages:
            logger.info("Reached page limit.")
            break