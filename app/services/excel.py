import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)
EXCEL_FILE = "data/Profiles.xlsx"

def load_existing_emails():
    if os.path.isfile(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        return df, set(df['Email'].dropna().str.lower())
    else:
        cols = ['Name','Location','Profile URL','Company Name','About','Email']
        return pd.DataFrame(columns=cols), set()

def append_df_to_excel(filename, df, sheet_name='Sheet1'):
    if not os.path.isfile(filename):
        df.to_excel(filename, index=False, sheet_name=sheet_name)
    else:
        import openpyxl
        existing = pd.read_excel(filename, sheet_name=sheet_name)
        startrow = len(existing) + 1
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name=sheet_name, startrow=startrow)
    logger.info(f"Appended {len(df)} rows to {filename}.")