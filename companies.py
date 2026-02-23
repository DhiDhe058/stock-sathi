import pandas as pd
import os

try:
    # ⚠️ THIS EXACT STRING MUST MATCH THE GITHUB FILE NAME PERFECTLY
    file_path = "ind_nifty500list" 
    
    df = pd.read_csv(file_path)
    NIFTY_COMPANIES = df['Company Name'].tolist()
except Exception:
    NIFTY_COMPANIES = ["Reliance Industries", "TCS", "HDFC Bank", "ICICI Bank", "Infosys"]