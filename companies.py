import pandas as pd
import os

try:
    # ⚠️ THE GPS TRACKER: This forces Python to look in the exact folder where this code lives
    current_folder = os.path.dirname(__file__)
    file_path = os.path.join(current_folder, "ind_nifty500list.csv")
    
    df = pd.read_csv(file_path)
    
    # Find the company column automatically
    company_column = [col for col in df.columns if 'Company' in col][0]
    NIFTY_COMPANIES = df[company_column].dropna().tolist()

except Exception as e:
    # If this fails, it will explicitly tell us why in the dropdown!
    NIFTY_COMPANIES = ["Reliance Industries", f"⚠️ CLOUD BUG: {str(e)}", "TCS", "HDFC Bank", "ICICI Bank"]