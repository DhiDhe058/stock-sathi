import pandas as pd
import os

# We use a "try-except" block so the app doesn't crash if the file is missing
try:
    # Look for the CSV file in your folder
    file_path = "ind_nifty500list.csv"
    
    # Let Pandas read the spreadsheet
    df = pd.read_csv(file_path)
    
    # Extract the 'Company Name' column and turn it into a Python list
    NIFTY_COMPANIES = df['Company Name'].tolist()

except Exception:
    # If it can't find the file, use a backup list so the app still works!
    NIFTY_COMPANIES = ["Reliance Industries", "TCS", "HDFC Bank", "ICICI Bank", "Infosys"]