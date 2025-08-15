from unittest import result
import streamlit as st
import pandas as pd
import pandas_ta as ta  # Ensure ta is imported
import numpy as np
from openai import OpenAI
from alpha_vantage.timeseries import TimeSeries
from msal import ConfidentialClientApplication
import requests
import json
import re
import markdown2 
import os 
from bs4 import BeautifulSoup


alpha_vantage_key = st.secrets["ALPHA_VANTAGE_API_KEY"]
api_key = st.secrets["OPENAI_API_KEY"]
API_KEY = st.secrets["MARKETSTACK_API_KEY"]
client = OpenAI(api_key= api_key)

# Initialize MSAL client for Azure AD authentication

client_id = st.secrets["CLIENT_ID"]
client_secret = st.secrets["CLIENT_SECRET"]
tenant_id = st.secrets["TENANT_ID"]
domain = st.secrets["SHAREPOINT_DOMAIN"]

# Microsoft Graph auth setup
authority = f"https://login.microsoftonline.com/{tenant_id}"
scope = ["https://graph.microsoft.com/.default"]

MARKETSTACK_TICKER_MAP = {
    "ETR:EVT": "EVT.XETRA",
    "EPA:GLPG": "GLPG.XAMS",
    "CPH:GMAB": "GMAB.XCSE",
    "BME:ALM": "ALM.BMEX",
    "EPA:PHARM": "PHARM.XAMS",
    "LON:PRTC": "PRTC.XLON",
    "EPA:SAN": "SAN.XPAR",
    "CPH:ZEAL": "ZEAL.XCSE"
}

@st.cache_data(ttl=3600)
def get_access_token():
    app = ConfidentialClientApplication(
        client_id=client_id,
        authority=authority,
        client_credential=client_secret
    )
    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        print("Access token retrieved")
        return result["access_token"]
    else:
        raise Exception("Authentication failed: " + str(result.get("error_description")))

@st.cache_data(ttl=3600)
def fetch_marketstack_data(ticker, period):
    """Fetch daily EOD data from Marketstack, filter by period, and resample to weekly."""

    ticker = MARKETSTACK_TICKER_MAP.get(ticker, ticker)  # Map ticker if needed

    # Define how many days of data to fetch based on selected period
    period_map = {
        "3 Months": 65,
        "6 Months": 130,
        "1 Year": 260
    }
    limit = period_map.get(period, 260)

    # Construct URL with full path and query string
    url = f"http://api.marketstack.com/v2/tickers/{ticker}/eod?access_key={API_KEY}&limit={limit}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        json_response = response.json()

        # Extract EOD data
        eod_data = json_response.get("data", {}).get("eod", [])
        if not eod_data:
            return None

        # Convert to DataFrame
        df = pd.DataFrame(eod_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")

        # Select and format columns
        df = df[["open", "high", "low", "close", "volume", "symbol", "exchange"]]
        df.columns = [col.capitalize() for col in df.columns]
        #st.write(f"Fetched {len(df)} rows of data for {ticker} from Marketstack.")

        # Resample to weekly frequency
        # df_weekly = df.resample("W").agg({
        #     "Open": "first",
        #     "High": "max",
        #     "Low": "min",
        #     "Close": "last",
        #     "Volume": "sum",
        #     "Symbol": "last",
        #     "Exchange": "last"
        # })

        return df

    except Exception as e:
        st.error(f"Marketstack API Error: {e}")
        return None

def get_excel_from_sharepoint():
    access_token = get_access_token()
    
    # Step 1: Get Site ID
    site_url = "https://graph.microsoft.com/v1.0/sites/aescapventure.sharepoint.com:/sites/2:"
    site_response = requests.get(site_url, headers={"Authorization": f"Bearer {access_token}"})
    if site_response.status_code != 200:
        st.error(f"Failed retrieve site information: {site_response.text}")
        raise Exception("Failed to retrieve site information")
    site_response.raise_for_status()
    print("success")
    site_id = site_response.json()["id"]
    print(f"Site ID: {site_id}")

    headers = {
         "Authorization": f"Bearer {access_token}"
    }

    # Step 2: Get Excel File
    file_url = f"https://graph.microsoft.com/v1.0/drives/b!A0JnyH_77Eiuk7lDhz6P8EkKu4plSodEq_r0yGard3Ap3bFfX_sNQ4EYOzkehZn5/items/01VQKIKT5GA6KRYDT5TRG3T52IW7KDIPGE/children?$filter=name eq 'Portfolios.xlsx'"
    file_response = requests.get(file_url, headers=headers).json()
    download_url = file_response["value"][0]["@microsoft.graph.downloadUrl"]
    
    response = requests.get(download_url)

    if response.status_code == 200:
        with open("Portfolios.xlsx", "wb") as f:
            f.write(response.content)
        print("✅ File downloaded and saved as Portfolios.xlsx")

    else:
        print(f"❌ Failed to download file. Status code: {response.status_code}")
    #print(f"Download URL: {download_url}")

    return "done"



    # # Step 2: Get Excel File
    # file_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/Shared Documents/{file_path}:/content"
    # file_response = requests.get(file_url, headers=headers)
    # file_response.raise_for_status()

    # # Save temporarily and read
    # with open("portfolio.xlsx", "wb") as f:
    #     f.write(file_response.content)
    
    # df = pd.read_excel("portfolio.xlsx")
    # return df


# === 4. Cache and display the data ===
@st.cache_data(ttl=600)
def load_firm_portfolio():
    # Example path: "Portfolios/firm-portfolio.xlsx"
    return get_excel_from_sharepoint("09e44ed5-835c-4149-9131-8652c1187dda", "Internal use of AI/Lincoln/Portfolios.xlsx")


 # Fix duplicate or missing headers
def make_unique_headers(headers):
    seen = {}
    fixed_headers = []
    for h in headers:
        if pd.isna(h):
            h = "Unnamed"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        fixed_headers.append(str(h))
    return fixed_headers

def calculate_technical_indicators(data, ticker, weight_choice=None, portfolio_weight=1.0):
    """
    Calculate various technical indicators, prepare them for AI analysis,
    and compute a portfolio-weighted technical score.

    Args:
        data (pd.DataFrame): The input financial data.
        ticker (str): The stock ticker.
        weight_choice (str): One of "Short Term", "Long Term", or "Default".
        portfolio_weight (float): Portfolio allocation weight (0.0 to 1.0)

    Returns:
        Tuple: (
            results (dict),
            recent_data (pd.DataFrame),
            availability (dict),
            weighted_score (float),
            final_weighted_score (float)
        )
    """
    short_term_weights = {
        "sma": 0.1,
        "rsi": 0.3,
        "macd": 0.3,
        "obv": 0.1,
        "adx": 0.1,
        "bbands": 0.1
    }
    long_term_weights = {
        "sma": 0.4,
        "rsi": 0.1,
        "macd": 0.15,
        "obv": 0.15,
        "adx": 0.2,
        "bbands": 0.0
    }
    weights = {
        "sma": 0.2,
        "rsi": 0.2,
        "macd": 0.2,
        "obv": 0.2,
        "adx": 0.2,
        "bbands": 0.0
    }

    if weight_choice == "Short Term":
        weights = short_term_weights
    elif weight_choice == "Long Term":
        weights = long_term_weights

    # Initialize availability flags
    sma_available = rsi_available = macd_available = False
    obv_available = adx_available = bbands_available = False

    # Calculate indicators
    if 'Close' in data.columns:
        data['SMA_20'] = ta.sma(data['Close'], length=20)
        data['SMA_50'] = ta.sma(data['Close'], length=50)
        data['SMA_200'] = ta.sma(data['Close'], length=200)
        sma_available = data[['SMA_20', 'SMA_50', 'SMA_200']].notna().any().any()

        data['RSI'] = ta.rsi(data['Close'], length=14)
        rsi_available = data['RSI'].notna().any()

    macd = ta.macd(data['Close'])
    if macd is not None and all(col in macd.columns for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
        data['MACD'] = macd['MACD_12_26_9']
        data['MACD_signal'] = macd['MACDs_12_26_9']
        data['MACD_hist'] = macd['MACDh_12_26_9']
        macd_available = True

    if 'Volume' in data.columns and 'Close' in data.columns:
        data['OBV'] = ta.obv(data['Close'], data['Volume'])
        obv_available = data['OBV'].notna().any()

    adx = ta.adx(data['High'], data['Low'], data['Close'])
    if adx is not None and 'ADX_14' in adx.columns:
        data['ADX'] = adx['ADX_14']
        adx_available = True

    bbands = ta.bbands(data['Close'], length=20, std=2)
    if bbands is not None and all(col in bbands.columns for col in ['BBU_20_2.0', 'BBM_20_2.0', 'BBL_20_2.0']):
        data['upper_band'] = bbands['BBU_20_2.0']
        data['middle_band'] = bbands['BBM_20_2.0']
        data['lower_band'] = bbands['BBL_20_2.0']
        bbands_available = True

    data = data.resample('W').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
        'SMA_20': 'last',
        'SMA_50': 'last',
        'SMA_200': 'last',
        'RSI': 'last',
        'MACD': 'last',
        'MACD_signal': 'last',
        'MACD_hist': 'last',
        'OBV': 'last',
        'ADX': 'last',
        'upper_band': 'last',
        'middle_band': 'last',
        'lower_band': 'last'
    })

    recent_data = data.tail(8).reset_index().rename(columns={"date": "Date"})
    recent_data["Date"] = recent_data["Date"].dt.strftime("%Y-%m-%d")


    availability = {
        "sma_available": sma_available,
        "rsi_available": rsi_available,
        "macd_available": macd_available,
        "obv_available": obv_available,
        "adx_available": adx_available,
        "bbands_available": bbands_available
    }

    # --- Score each indicator weekly ---
    indicator_scores = {k: [] for k in weights}

    for _, week in data.iterrows():
        if availability['sma_available'] and pd.notna(week['Close']) and pd.notna(week['SMA_20']):
            score = 1 if week['Close'] > week['SMA_20'] else -1
            indicator_scores['sma'].append(score)
        if availability['rsi_available'] and pd.notna(week['RSI']):
            if week['RSI'] > 55:
                score = 1
            elif week['RSI'] < 45:
                score = -1
            else:
                score = 0
            indicator_scores['rsi'].append(score)
        if availability['macd_available'] and pd.notna(week['MACD']) and pd.notna(week['MACD_signal']):
            score = 1 if week['MACD'] > week['MACD_signal'] else -1
            indicator_scores['macd'].append(score)
        if availability['obv_available'] and pd.notna(week['OBV']):
            if week['OBV'] > 0:
                score = 1
            elif week['OBV'] < 0:
                score = -1
            else:
                score = 0
            indicator_scores['obv'].append(score)
        if availability['adx_available'] and pd.notna(week['ADX']):
            score = 1 if week['ADX'] > 20 else -1
            indicator_scores['adx'].append(score)
        if availability['bbands_available'] and pd.notna(week['Close']) and pd.notna(week['middle_band']):
            score = 1 if week['Close'] > week['middle_band'] else -1
            indicator_scores['bbands'].append(score)

    # --- Calculate final scores ---
    final_scores = {}
    for k in indicator_scores:
        final_scores[k] = np.mean(indicator_scores[k]) if indicator_scores[k] else 0

    total_weight = sum(weights[k] for k in final_scores if availability.get(f"{k}_available", False))
    weighted_score = (
        sum(final_scores[k] * weights[k] for k in final_scores if availability.get(f"{k}_available", False)) / total_weight
        if total_weight > 0 else 0
    )

    final_weighted_score =  round(weighted_score * portfolio_weight, 4)

    print("Final Indicator Averages:", final_scores)
    print("Weighted Score:", weighted_score)
    print("Final Weighted Score:", final_weighted_score)

    return recent_data, availability, round(weighted_score,2), final_weighted_score


# === 5. Streamlit UI ===
# st.title("📊 Firm Portfolio Analyzer")

# try:
#     df = load_firm_portfolio()
#     st.success("Successfully loaded data from SharePoint.")
#     st.write(df)
# except Exception as e:
#     st.error(f"Failed to load file: {e}")

# uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

# if uploaded_file is not None:
#     try:
#         # Load the Excel file without headers
#         xls = pd.read_excel(uploaded_file, sheet_name=None, header=None)
#         sheet_names = list(xls.keys())
#         st.write("📄 Available sheets:", sheet_names)

#         # Choose which sheet to process
#         if "Benchmark LS" in sheet_names:
#             sheet_name = "Benchmark LS"
#         elif "Portfolio LS" in sheet_names:
#             sheet_name = "Portfolio LS"
#         else:
#             st.error("Neither 'Benchmark LS' nor 'Portfolio LS' found in the uploaded file.")
#             st.stop()

   
#         # Drop the first column (column index 0)
#         raw_df = xls[sheet_name]
#         if sheet_name == "Benchmark LS":
               
#             st.write("Benchmark LS detected. Skipping data cleaning.")

#                 # Load the sheet with no header
#             raw_df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)

#             # Set the first row as the header (i.e., ["Ticker", "Weights", ...])
#             header_row = raw_df.iloc[0].tolist()
#             raw_df = raw_df.iloc[1:].reset_index(drop=True)
#             raw_df.columns = header_row

#             # Keep only Ticker and Weights columns
#             if "Ticker" in raw_df.columns and "Weights" in raw_df.columns:
#                 mapped_df = raw_df[["Ticker", "Weights"]].dropna()
#                 mapped_df["Weights"] = mapped_df["Weights"].astype(float) / 100
#             else:
#                 st.error("Could not find 'Ticker' and 'Weights' columns in Benchmark LS sheet.")
#                 mapped_df = pd.DataFrame()
#         else:
#             st.write("Processing Portfolio LS...")
#             raw_df = raw_df.drop(columns=0)

#             # Use the 4th row (index 4) as headers
#             raw_headers = raw_df.iloc[4].tolist()


#             cleaned_headers = make_unique_headers(raw_headers)

#             # Apply headers and remove the first 5 rows
#             cleaned_df = raw_df.iloc[5:].reset_index(drop=True)
#             cleaned_df.columns = cleaned_headers

#             if "Ticker" in cleaned_df.columns and "Percentage Without cash" in cleaned_df.columns:
#                 # Drop rows with missing tickers or weights
#                 filtered_df = cleaned_df[["Ticker", "Percentage Without cash"]].dropna()

#                 # Exclude the unwanted ticker
#                 filtered_df = filtered_df[filtered_df["Ticker"] != "Aescap Genetics"]

#                 # Rename for clarity
#                 mapped_df = filtered_df.rename(columns={
#                     "Ticker": "Ticker",
#                     "Percentage Without cash": "Weights"
#                 }).reset_index(drop=True)

#                 st.subheader("Mapped Ticker Weights:")
#                 st.dataframe(mapped_df)

#         if not mapped_df.empty:
#             st.subheader("Running analysis for 3 tickers...")

#             # Select first 3 tickers (or random 3 if you want)
#             top3_df = mapped_df

#             total_scores = []

#             for _, row in top3_df.iterrows():
#                 ticker = row["Ticker"]
#                 weight = float(row["Weights"])  # Convert % to decimal

#                 st.markdown(f"### 🔍 {ticker} (Weight: {weight:.2%})")

#                 # Fetch Marketstack data
#                 data = fetch_marketstack_data(ticker, "3 Months")
#                 if data is not None and not data.empty:
#                     recent_data, availability, weighted_score, final_score = calculate_technical_indicators(
#                         data,
#                         ticker,
#                         weight_choice="Long Term",  # or "Short Term", "Default"
#                         portfolio_weight=weight
#                     )

#                     total_scores.append(final_score)

#                     # st.write(f"**Weighted Score:** {weighted_score:.3f}")
#                     # st.write(f"**Final Weighted Score (with portfolio allocation):** {final_score:.3f}")
#                     # st.line_chart(recent_data["Close"])
#                     # st.write("### Technical Indicators:")
#                     # st.write(recent_data)
#                     # st.write(weighted_score)
                    
#                 else:
#                     st.warning(f"No data found for {ticker}.")
                
#             total_portfolio_score = sum(total_scores)
#             st.subheader(f"📊 Total Portfolio Technical Score: {total_portfolio_score:.3f}")

#         else:
#             st.warning("Required columns 'Ticker' and/or 'Percentage Without cash' not found.")
        
        

#     except Exception as e:
#         st.error(f"Error reading or processing the Excel file: {e}")

def html_analysis2(analysis_results):
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Investment Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }
            .container {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                width: 100%;
                max-width: 100%;
                margin-bottom: 30px;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }
            h2 {
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }
            h3 {
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            ul, ol {
                padding-left: 25px;
            }
            ul li, ol li {
                margin-bottom: 8px;
            }
            .metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin: 20px 0;
            }
            .metric-card {
                background-color: #f0f7ff;
                border-radius: 5px;
                padding: 15px;
                flex: 1;
                min-width: 200px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            .metric-title {
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 5px;
            }
            .metric-value {
                font-size: 1.2em;
                font-weight: bold;
            }
            .indicator {
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }
            .indicator h4 {
                margin-top: 0;
                color: #2980b9;
            }
            .timeframe {
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            .footnote {
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Comprehensive Investment Analysis: [PORTFOLIO_NAME]</h1>
            <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>

            <h2>1. Executive Summary</h2>
            <div class="section">
                <p>Summary analyzing the momentum scores and current weight allocations in the portfolio. This section highlights whether the current weight distribution is aligned with momentum trends and identifies opportunities for improved allocation to enhance performance.</p>
            </div>

            <h2>2. Total Momentum Overview</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-title">Portfolio Total Momentum Score</div>
                    <div class="metric-value">[PORTFOLIO_TOTAL_SCORE]</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Momentum Alignment Score (1–10)</div>
                    <div class="metric-value">[ALIGNMENT_SCORE]</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Top Momentum Contributors</div>
                    <div class="metric-value">[TOP_CONTRIBUTORS]</div>
                </div>
            </div>
            <div class="section">
                <p>[Interpretation: Is momentum distributed efficiently? Which tickers are misaligned in terms of weight vs score?]</p>
            </div>

            <h2>3. Top 5 Momentum Performers</h2>
            <div class="section">
                <!-- Repeat this block for each top ticker -->
                <div class="indicator">
                    <h4>[TICKER_SYMBOL]</h4>
                    <ul>
                        <li><strong>Current Weight:</strong> [CURRENT_WEIGHT]</li>
                        <li><strong>Weighted Momentum Score:</strong> [WEIGHTED_SCORE]</li>
                        <li><strong>Final Score:</strong> [FINAL_SCORE]</li>
                        <li><strong>RSI:</strong> [RSI_DETAILS]</li>
                        <li><strong>MACD:</strong> [MACD_DETAILS]</li>
                        <li><strong>SMA:</strong> [SMA_CROSSOVER]</li>
                        <li><strong>ADX:</strong> [ADX_VALUE]</li>
                        <li><strong>Bollinger Bands:</strong> [BB_STATE]</li>
                        <li><strong>Trend Summary:</strong> [TREND_DESCRIPTION]</li>
                    </ul>
                </div>
            </div>

            <h2>4. Weight vs Momentum Insights</h2>
            <div class="section">
                <ul>
                    <li>Tickers currently underweighted relative to momentum: [UNDERWEIGHTED_TICKERS]</li>
                    <li>Tickers overweighted despite weak momentum: [OVERWEIGHTED_TICKERS]</li>
                    <li>Top gainers to concentrate exposure: [GAINER_TICKERS]</li>
                    <li>Portfolio efficiency based on alignment: [EFFICIENCY_COMMENT]</li>
                </ul>
            </div>

            <h2>5. Strategic Implications</h2>
            <div class="section">
                <ul>
                    <li>Proposed revised weight distribution: [REVISED_WEIGHT_TABLE]</li>
                    <li>Top momentum performers to overweight: [SUGGESTED_OVERWEIGHTS]</li>
                    <li>Low momentum laggards to underweight or remove: [SUGGESTED_UNDERWEIGHTS]</li>
                    <li>Suggested risk posture: [DEFENSIVE_OR_AGGRESSIVE]</li>
                </ul>
            </div>

            <h2>6. Ticker Snapshot Overview</h2>
            <div class="section">
                <table>
                    <tr>
                        <th>Ticker</th>
                        <th>Current Weight</th>
                        <th>Suggested Weight</th>
                        <th>Final Score</th>
                        <th>RSI</th>
                        <th>MACD</th>
                        <th>SMA</th>
                    </tr>
                    <!-- Repeat for all tickers -->
                    <tr>
                        <td>[TICKER]</td>
                        <td>[CURRENT_WEIGHT]</td>
                        <td>[SUGGESTED_WEIGHT]</td>
                        <td>[FINAL_SCORE]</td>
                        <td>[RSI]</td>
                        <td>[MACD]</td>
                        <td>[SMA]</td>
                    </tr>
                </table>
            </div>

            <div class="footnote">
                Report generated by AI based on technical momentum indicators and current portfolio allocation. Interpret with discretion. Rebalancing decisions should be aligned with overall investment objectives and risk tolerance.
            </div>
        </div>
    </body>
    </html> 
    """

    system_prompt = """
    You are a professional financial analyst and investment strategist. You are given a dictionary containing momentum analysis results for a portfolio of tickers. Each entry includes:
    - ticker: stock ticker symbol
    - recent_data: weekly resampled price data
    - current_weight: current weight of the ticker in the portfolio
    - weighted_score: technical score based on momentum indicators (e.g. RSI, OBV, MACD, etc.)
    - final_score: score adjusted by weight

    Your task is to:

    1. Analyze momentum patterns across all tickers in the portfolio.
    2. Identify the top 5 tickers by **momentum (weighted_score)**.
    3. Assess whether current weights align with momentum performance.
    4. Propose a **revised weight distribution** aimed at maximizing overall portfolio momentum.
    5. Provide strategic commentary on which tickers to overweight, underweight, or drop.

    Output structured HTML-ready content that can be directly inserted into the template sections.

    **Formatting Requirements:**
    - DO NOT USE MARKDOWN OR PLAIN TEXT HEADINGS UNDER ANY CIRCUMSTANCES.
    - DO NOT use Markdown syntax such as #, ##, or bullet points.
    - DO NOT use Markdown lists.
    - DO NOT output any content outside of the provided HTML template.
    - RESPOND ONLY IN VALID HTML using the provided template, filling all placeholders with the relevant data.
    - KEEP THE TITLE OF THE REPORT AS "Comprehensive Investment Analysis". 
    - FOR CURRENT WEIGHT, GET THE DATA FROM "Weights" don't get it mixed up with "weighted_score".
    """

    user_message = f"The data to analyse: {json.dumps(analysis_results)}"
    
    # Call Claude API to generate the HTML with progress indicator
    with st.spinner("Generating analysis..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",  
                messages=[
                    {"role": "system", "content": f"{system_prompt} HTML template: {html_template}"},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            # Extract the response content
            html_content = response.choices[0].message.content
            return html_content
            
        except Exception as e:
            st.error(f"Error generating analysis: {e}")
            return None
        





def html_analysis(analysis_results):
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Investment Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }
            .container {
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                width: 100%;
                max-width: 100%;
                margin-bottom: 30px;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }
            h2 {
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }
            h3 {
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            ul, ol {
                padding-left: 25px;
            }
            ul li, ol li {
                margin-bottom: 8px;
            }
            .recommendation {
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }
            .buy {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .hold {
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }
            .sell {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin: 20px 0;
            }
            .metric-card {
                background-color: #f0f7ff;
                border-radius: 5px;
                padding: 15px;
                flex: 1;
                min-width: 200px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
            .metric-title {
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 5px;
            }
            .metric-value {
                font-size: 1.2em;
                font-weight: bold;
            }
            .chart-container {
                margin: 20px 0;
                text-align: center;
            }
            .footnote {
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }
            strong {
                color: #2980b9;
            }
            .highlight {
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            .summary-box {
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }
            .indicator {
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }
            .indicator h4 {
                margin-top: 0;
                color: #2980b9;
            }
            .timeframe {
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }
            .weights-section {
                background-color: #f0f4f9;
                border-left: 4px solid #2980b9;
                margin-bottom: 30px;
                padding: 15px;
                border-radius: 0 5px 5px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Comprehensive Investment Analysis: [TICKER_PLACEHOLDER] - [COMPANY_PLACEHOLDER]</h1>
            <div class="timeframe">Analysis Timeframe: [TIMEFRAME_PLACEHOLDER]</div>

            <h2>1. Executive Summary</h2>
            <div class="section">
                <p>[Summary comparing Portfolio and Benchmark momentum — which is stronger, general direction]</p>
            </div>

            <h2>2. Total Momentum Overview</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-title">Portfolio Total Score</div>
                    <div class="metric-value">[PORTFOLIO_TOTAL_SCORE]</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Benchmark Total Score</div>
                    <div class="metric-value">[BENCHMARK_TOTAL_SCORE]</div>
                </div>
            </div>
            <div class="section">
                <p>[Interpretation: Is this bullish, neutral, bearish? What does the margin suggest?]</p>
            </div>

            <h2>3. Top 5 Momentum Performers in Each Group</h2>

            <h3>Portfolio – Top 5 Tickers</h3>
            <div class="section">
                <!-- Repeat this block -->
                <div class="indicator">
                    <h4>[TICKER_SYMBOL]</h4>
                    <ul>
                        <li><strong>Weighted Score:</strong> [WEIGHTED_SCORE]</li>
                        <li><strong>Final Score:</strong> [FINAL_SCORE]</li>
                        <li><strong>RSI:</strong> [RSI_DETAILS]</li>
                        <li><strong>MACD:</strong> [MACD_DETAILS]</li>
                        <li><strong>SMA:</strong> [SMA_CROSSOVER]</li>
                        <li><strong>ADX:</strong> [ADX_VALUE]</li>
                        <li><strong>Bollinger Bands:</strong> [BB_STATE]</li>
                        <li><strong>Trend Summary:</strong> [TREND_DESCRIPTION]</li>
                    </ul>
                </div>
            </div>

            <h3>Benchmark – Top 5 Tickers</h3>
            <div class="section">
                <!-- Repeat this block -->
                <div class="indicator">
                    <h4>[TICKER_SYMBOL]</h4>
                    <ul>
                        <li><strong>Weighted Score:</strong> [WEIGHTED_SCORE]</li>
                        <li><strong>Final Score:</strong> [FINAL_SCORE]</li>
                        <li><strong>RSI:</strong> [RSI_DETAILS]</li>
                        <li><strong>MACD:</strong> [MACD_DETAILS]</li>
                        <li><strong>SMA:</strong> [SMA_CROSSOVER]</li>
                        <li><strong>ADX:</strong> [ADX_VALUE]</li>
                        <li><strong>Bollinger Bands:</strong> [BB_STATE]</li>
                        <li><strong>Trend Summary:</strong> [TREND_DESCRIPTION]</li>
                    </ul>
                </div>
            </div>

            <h2>4. Comparative Insights</h2>
            <div class="section">
                <ul>
                    <li>Portfolio vs Benchmark: [Comparison statement]</li>
                    <li>Outperformance by Portfolio tickers: [Highlights]</li>
                    <li>Momentum concentration: [Broad vs few contributors]</li>
                    <li>Potential Benchmark tickers to add: [Suggestions]</li>
                </ul>
            </div>

            <h2>5. Strategic Implications</h2>
            <div class="section">
                <ul>
                    <li>Rebalancing Opportunities: [Suggested moves]</li>
                    <li>Underperformers to reduce: [Tickers]</li>
                    <li>Top performers to overweight: [Tickers]</li>
                    <li>Momentum signals: [Breakouts/reversals]</li>
                    <li>Risk posture: [Defensive or aggressive?]</li>
                </ul>
            </div>

            <h2>6. Appendix</h2>
            <div class="section">
                <p>[Compare shared tickers across both groups if applicable]</p>
                <table>
                    <tr>
                        <th>Ticker</th>
                        <th>Group</th>
                        <th>Final Score</th>
                        <th>RSI</th>
                        <th>MACD Trend</th>
                        <th>SMA Position</th>
                    </tr>
                    <!-- Add one <tr> per ticker -->
                    <tr>
                        <td>EVT</td>
                        <td>Portfolio</td>
                        <td>0.738</td>
                        <td>Overbought, Falling</td>
                        <td>Bearish Crossover</td>
                        <td>Below 50 SMA</td>
                        <td>Bearish Momentum</td>
                    </tr>
                </table>
            </div>

            <div class="footnote">
                Report generated by AI based on technical momentum indicators. Interpret with discretion.
            </div>
        </div>
    </body>
    </html>
"""

    system_prompt = f"""
    You are a professional financial analyst and investment strategist. You are given a dictionary containing momentum analysis results for two categories: "Portfolio" and "Benchmark". Each contains the following:

    ticker: stock ticker
    recent_data: weekly resampled price data
    weighted_score: technical score based on indicators like RSI, OBV, etc.
    final_score: score adjusted by portfolio weight

    Your task is to:

    1) Analyze momentum patterns across the top 5 tickers (by highest weighted_score) for BOTH Portfolio and Benchmark.
    2) Highlight significant insights, divergences, or alignments between the two groups.
    3) Compare sector or regional trends if any.
    4) Identify which side is stronger from a technical perspective.

    IMPORTANT: Strategic implementations MUST focus ONLY on the Portfolio.
    - The Benchmark is for context/comparison only.
    - Do NOT recommend actions on, or new positions in, Benchmark tickers.
    - In all rebalancing/overweight/underweight/suggested-weight outputs, reference Portfolio tickers only.

    For the Top 5 sections:
    - Select the top five tickers by highest weighted_score within each group (Portfolio and Benchmark) and provide detailed analysis for each.

    Output structured HTML-ready content that can be directly inserted into the template sections.

    **Formatting Requirements:**
    - DO NOT USE MARKDOWN OR PLAIN TEXT HEADINGS UNDER ANY CIRCUMSTANCES.
    - DO NOT use Markdown syntax such as #, ##, or bullet points.
    - DO NOT use Markdown lists.
    - DO NOT output any content outside of the provided HTML template.
    - RESPOND ONLY IN VALID HTML using the provided template, filling all placeholders with the relevant data.
    - KEEP THE TITLE OF THE REPORT AS "Comprehensive Investment Analysis".

    Use the user-input analysis results.

    Embed the report into this HTML structure and return full HTML. Be analytical, structured, and domain-specific.

    When producing the "Strategic Implications" section:
    - Propose a revised weight distribution for the Portfolio only.
    - Identify Portfolio tickers to overweight/underweight/remove based on momentum alignment.
    - DO NOT include any Benchmark tickers in recommendations or allocations.
    """
    user_message = f"The data to analyse: {json.dumps(analysis_results)}"
    
    # Call Claude API to generate the HTML with progress indicator
    with st.spinner("Generating analysis..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",  
                messages=[
                    {"role": "system", "content": f"{system_prompt} HTML template: {html_template}"},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            # Extract the response content
            html_content = response.choices[0].message.content
            return html_content
            
        except Exception as e:
            st.error(f"Error generating analysis: {e}")
            return None
        
    
    

def clean_html_response(response):
    # Remove markdown formatting from response
    if response.startswith("```html"):
        response = response.lstrip("```html").strip()
    if response.endswith("```"):
        response = response.rstrip("```").strip()
    return response

def fix_html_with_embedded_markdown(text):
    """
    Detects markdown sections embedded within mostly-HTML output,
    converts them to HTML, and replaces them in the text.
    """
    if not text:
        return text

    # Don't touch it if it's a fully valid HTML document
    if bool(re.search(r'<html', text, re.IGNORECASE)):
        return text

    # Pattern to detect markdown-style headings, lists, bold, etc.
    markdown_blocks = list(re.finditer(
        r'(?:(^|\n)(\s*)(#{1,6} .+|[-*+] .+|\d+\..+|>\s.+|\*\*.+\*\*|__.+__)([\s\S]+?))(?=\n{2,}|\Z)', 
        text,
        flags=re.MULTILINE
    ))

    # Convert and replace each markdown block
    for match in reversed(markdown_blocks):  # reversed to not break indices when replacing
        md_block = match.group(0).strip()
        # Only convert if not inside an HTML tag already
        if not re.match(r'<[a-z][^>]*>', md_block):
            html_block = markdown2.markdown(md_block)
            # Optionally strip <p> if markdown2 wraps the entire block
            if html_block.startswith('<p>') and html_block.endswith('</p>\n'):
                html_block = html_block[3:-5]
            # Replace markdown block with HTML
            start, end = match.span(0)
            text = text[:start] + html_block + text[end:]

    return text
  
def main():
    get_excel_from_sharepoint()
    
    st.set_page_config(
        page_title="Firm Portfolio Analyzer",
        layout="wide"
    )
    try:
        st.sidebar.header("Analysis Settings")

        portfolio_choice = st.sidebar.radio(
            "Select Portfolio:",
            ["Life Science Portfolio", "Genetics Portfolio"]
        )

        selected_period = st.sidebar.selectbox(
            "Select Time Period:",
            ["3 Months", "6 Months", "1 Year"]
        )

        weight_choice = st.sidebar.radio(
            "Technical Indicator Weighting:",
            ["Default", "Short Term", "Long Term"]
        )

        run_analysis = st.sidebar.button("Run Analysis")

        if run_analysis:
            with st.spinner("🔄 Processing portfolio and benchmark data..."):
                with st.expander("Processing", expanded=True):
                    sheet_name = "Portfolio LS" if portfolio_choice == "Life Science Portfolio" else "Portfolio G"
                    raw_portfolio_df = pd.read_excel("Portfolios.xlsx", sheet_name=sheet_name, header=None)
                    st.write(f"✅ Loaded {portfolio_choice} from {sheet_name} sheet.")

                    raw_portfolio_df = raw_portfolio_df.drop(columns=0)

                    if portfolio_choice == "Life Science Portfolio":
                        raw_headers = raw_portfolio_df.iloc[4].tolist()
                        cleaned_df = raw_portfolio_df.iloc[5:].reset_index(drop=True)
                        percentage_col = "Percentage Without cash"
                    else:
                        raw_headers = raw_portfolio_df.iloc[3].tolist()
                        cleaned_df = raw_portfolio_df.iloc[4:].reset_index(drop=True)
                        percentage_col = "Percentage (excluding cash)"

                    cleaned_headers = make_unique_headers(raw_headers)
                    cleaned_df.columns = cleaned_headers

                    if "Ticker" in cleaned_df.columns and percentage_col in cleaned_df.columns:
                        filtered_df = cleaned_df[["Ticker", percentage_col]].dropna()

                        if portfolio_choice == "Life Science Portfolio":
                            filtered_df = filtered_df[filtered_df["Ticker"] != "Aescap Genetics"]

                        mapped_df = filtered_df.rename(columns={
                            "Ticker": "Ticker",
                            percentage_col: "Weights"
                        }).reset_index(drop=True)

                        mapped_df["Weights"] = mapped_df["Weights"].astype(float)

                        st.subheader("🎯 Portfolio Holdings")
                        st.dataframe(mapped_df)
                    else:
                        st.error("Portfolio sheet is missing required columns.")
                        st.stop()

                    benchmark_df = pd.DataFrame()
                    if portfolio_choice != "Genetics Portfolio":
                        raw_benchmark_df = pd.read_excel("IBB Benchmark.xlsx", sheet_name="Benchmark LS", header=None)
                        st.write("✅ Loaded Benchmark LS from IBB Benchmark.xlsx")

                        header_row = raw_benchmark_df.iloc[0].tolist()
                        raw_benchmark_df = raw_benchmark_df.iloc[1:].reset_index(drop=True)
                        raw_benchmark_df.columns = header_row

                        if "Ticker" in raw_benchmark_df.columns and "Weights" in raw_benchmark_df.columns:
                            benchmark_df = raw_benchmark_df[["Ticker", "Weights"]].dropna()
                            benchmark_df["Weights"] = benchmark_df["Weights"].astype(float) / 100
                        else:
                            st.error("Benchmark sheet is missing required columns.")
                            benchmark_df = pd.DataFrame()

                    combined_data = [("Portfolio", mapped_df)]
                    if portfolio_choice != "Genetics Portfolio":
                        combined_data.append(("Benchmark", benchmark_df))

                    analysis_results = {}
                    for label, df in combined_data:
                        if df.empty:
                            st.warning(f"{label} data is empty, skipping.")
                            continue

                        total_scores = []
                        ticker_data = {}

                        for _, row in df.iterrows():
                            ticker = row["Ticker"]
                            weight = float(row["Weights"])

                            data = fetch_marketstack_data(ticker, selected_period)
                            if data is not None and not data.empty:
                                recent_data, availability, weighted_score, final_score = calculate_technical_indicators(
                                    data,
                                    ticker,
                                    weight_choice=weight_choice,
                                    portfolio_weight=weight
                                )
                                total_scores.append(final_score)

                                ticker_data[ticker] = {
                                    "recent_data": recent_data.to_dict(orient='records'),
                                    "weighted_score": weighted_score,
                                    "final_score": final_score,
                                    "Portfolio Weight": weight
                                }
                            else:
                                st.warning(f"No data found for {ticker}.")

                        total_score = sum(total_scores)
                        analysis_results[label] = {
                            "tickers": ticker_data,
                            "total_score": total_score
                        }

                    # ✅ Use html_analysis2 if Genetics Portfolio
                    analysis_func = html_analysis2 if portfolio_choice == "Genetics Portfolio" else html_analysis
                    results = analysis_func(analysis_results)
                    print(analysis_results)

                    html_output_no_fix = clean_html_response(results)
                    html_output = fix_html_with_embedded_markdown(html_output_no_fix)

            st.components.v1.html(html_output, height=700, scrolling=True)

            soup = BeautifulSoup(html_output, "html.parser")
            plain_text = soup.get_text(separator='\n')
            if "html_output" not in st.session_state:
                st.session_state["html_output"] = html_output
            if "plain_text" not in st.session_state:
                st.session_state["plain_text"] = plain_text
            st.download_button("Download as HTML", st.session_state["html_output"], "stock_analysis_summary.html", "text/html")
            st.download_button("Download as Plain Text", st.session_state["plain_text"], "stock_analysis_summary.txt", "text/plain")
            if st.button("Run Another Analysis"):
                st.experimental_rerun()

            if os.path.exists("Portfolios.xlsx"):
                os.remove("Portfolios.xlsx")
                st.success("Processing Complete.")
            else:
                st.warning("⚠️ Portfolios.xlsx file not found for deletion.")

        else:
            st.info("👈 Adjust settings and click **Run Analysis** to start.")

    except Exception as e:
        st.error(f"❌ Error loading files: {e}")


if __name__ == "__main__":
    main()
