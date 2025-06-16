import os, re, time, logging
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ========== Logging ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("linkedin_scraper.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== Constants ==========
EXCEL_FILE = "Profiles.xlsx"

# ========== FastAPI App ==========
app = FastAPI()

class ScrapeRequest(BaseModel):
    username: str
    password: str
    search_url: str  # base URL (without page param if any)
    max_pages: int | None = None


@app.get("/")
def root():
    return {"message": "LinkedIn Scraper API is live."}


@app.post("/scrape-linkedin/")
def scrape_linkedin(request: ScrapeRequest):
    logger.info("Received scrape request.")
    driver = setup_driver()
    try:
        if not login_linkedin(driver, request.username, request.password):
            raise HTTPException(status_code=401, detail="LinkedIn login failed.")
        
        scrape_profiles(driver, request.search_url, request.max_pages)
        return {"message": "Scraping completed successfully."}
    finally:
        driver.quit()
        logger.info("Driver closed.")



def setup_driver():
    logger.info("Initializing Chrome WebDriver in headless mode...")
    options = Options()
    options.add_argument("--headless")  # <- THIS enables headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    driver=webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)  
    driver.set_script_timeout(30)
    return driver


def login_linkedin(driver, username, password):
    logger.info("Navigating to LinkedIn login page...")
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(3)

    if "feed" in driver.current_url:
        logger.info("Login successful.")
        return True
    else:
        logger.warning("Login failed.")
        return False

def load_existing_emails():
    if os.path.isfile(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        return df, set(df['Email'].dropna().str.lower())
    else:
        return pd.DataFrame(columns=['Name', 'Location', 'Profile URL', 'Company Name', 'About', 'Email']), set()

def append_df_to_excel(filename, df, sheet_name='Sheet1'):
    if not os.path.isfile(filename):
        df.to_excel(filename, index=False, sheet_name=sheet_name, encoding='utf-8')
    else:
        existing = pd.read_excel(filename, sheet_name=sheet_name)
        startrow = len(existing) + 1
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name=sheet_name, startrow=startrow, encoding='utf-8')

def scrape_profiles(driver, search_url, max_pages=None):
    existing_df, existing_emails = load_existing_emails()
    collected_profiles = []
    page_num = 1

    while True:
        paginated_url = f"{search_url}&page={page_num}"
        logger.info(f"Scraping page {page_num}: {paginated_url}")
        driver.get(paginated_url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'lxml')
        profiles = soup.find_all('div', class_=re.compile(r'^linked-area'))

        if not profiles:
            logger.info("No more profiles found, stopping.")
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
                collected_profiles.append({
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
                continue

        if collected_profiles:
            logger.info(f"Appending {len(collected_profiles)} profiles to Excel.")
            df_new = pd.DataFrame(collected_profiles)
            append_df_to_excel(EXCEL_FILE, df_new)
            existing_df = pd.concat([existing_df, df_new], ignore_index=True)
            collected_profiles = []

        page_num += 1
        if max_pages and page_num > max_pages:
            logger.info("Reached max_pages limit. Stopping.")
            break