import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openpyxl import load_workbook
import os, time, re

load_dotenv()
USERNAME = os.getenv('UNAME')
PASSWORD = os.getenv('PASSWORD')
print(USERNAME)
print(PASSWORD)
excel_file = f'Profiles2.xlsx'  # Use a stable filename
if os.path.isfile(excel_file):
    existing_df = pd.read_excel(excel_file)
    existing_emails = set(existing_df['Email'].dropna().str.lower())
else:
    existing_df = pd.DataFrame(columns=['Name', 'Location', 'Profile URL', 'Company Name', 'About', 'Email'])
    existing_emails = set()


def append_df_to_excel(filename, df, sheet_name='Sheet1'):
    if not os.path.isfile(filename):
        df.to_excel(filename, index=False, sheet_name=sheet_name)
    else:
        existing = pd.read_excel(filename, sheet_name=sheet_name)
        startrow = len(existing) + 1  # next empty row

        with pd.ExcelWriter(filename, engine='openpyxl',mode='a', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False,
                        sheet_name=sheet_name, startrow=startrow)

# Setup WebDriver
options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

try:
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)
    driver.find_element(By.ID, "username").send_keys(USERNAME)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(5)
    if "feed" in driver.current_url:
        print("Login successful.")
    else:
        print("Login might have failed.")
        
    profile_info = []
    page_num = 1

    while True:
        search_url = (
            "https://www.linkedin.com/search/results/people/"
            "?keywords=hr%20recruiters%20of%20it%20companies&origin=CLUSTER_EXPANSION&sid=KwH"
            f"&page={page_num}"
        )
        driver.get(search_url)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        profiles=soup.find_all('div',class_=re.compile(r'^linked-area'))
        if not profiles:
            print("No more profiles found, ending.")
            break
        
        for profile in profiles:
            try:
                name_elem = profile.find('span', {'aria-hidden': 'true'})
                name= name_elem.text.strip() if name_elem else ''
                location_elem = profile.find('div', attrs={'class': lambda c: c and 't-14 t-normal' in c})
                location= location_elem.text.strip() if location_elem else ''
                profile_url_elem = profile.find('a', tabindex='0')
                profile_url=profile_url_elem['href'] if profile_url_elem else ''
                driver.get(profile_url)
                time.sleep(3)
                soup_profile = BeautifulSoup(driver.page_source, 'lxml')
                
                about_elem = soup_profile.find('div', class_='text-body-medium break-words')
                about = about_elem.text.strip() if about_elem else ''
                
                comp_elem = soup_profile.find('div', {'style': '-webkit-line-clamp:2;'})
                company_name = comp_elem.text.strip() if comp_elem else ''
                
                contact_link_elem = soup_profile.find('a', id='top-card-text-details-contact-info')
                email = ''
                if contact_link_elem:
                    driver.get('https://www.linkedin.com' + contact_link_elem['href'])
                    time.sleep(3)
                    soup_info = BeautifulSoup(driver.page_source, 'lxml')
                    mail_tag = soup_info.find('a', href=lambda h: h and h.startswith('mailto:'))
                    if mail_tag:
                        email = mail_tag['href'].replace('mailto:', '').lower()

                if not email:
                    print(f"No email for {name}, skipping.")
                    continue

                if email in existing_emails:
                    print(f"Duplicate email {email}, skipping.")
                    continue

                print(f"Adding {email}")
                profile_info.append({
                    'Name': name,
                    'Location': location,
                    'Profile URL': profile_url,
                    'Company Name': company_name,
                    'About': about,
                    'Email': email
                })
                existing_emails.add(email)
            
            except Exception as e:
                print(f"Error processing profile: {e}")
                continue
        # Save
        if profile_info:
            df_new = pd.DataFrame(profile_info)
            append_df_to_excel(excel_file, df_new)
            existing_df = pd.concat([existing_df, df_new], ignore_index=True)
            print(f'Appended {len(df_new)} new Profiles to {excel_file}.')
        else:
            print("No new profiles to append.")
        profile_info=[]
        page_num += 1
        # Optional: break after N pages
        if page_num >3:
            break
finally:
    driver.quit()