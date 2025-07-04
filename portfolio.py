import streamlit as st
import pandas_ta as ta
from openai import OpenAI
import time
import requests
import gspread
from alpha_vantage.timeseries import TimeSeries
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import tempfile
import json
from pydantic import BaseModel
import os 
import re
import anthropic
#from dotenv import load_dotenv
#from curl_cffi import requests as curl_requests
from datetime import datetime, timedelta,date
import pandas as pd
from serpapi import GoogleSearch
from dateutil.relativedelta import relativedelta
import markdown2
from bs4 import BeautifulSoup


api_key = st.secrets["OPENAI_API_KEY"]
alpha_vantage_key = st.secrets["ALPHA_VANTAGE_API_KEY"]
serpapi_key = st.secrets["SERPAPI_KEY"]
diffbot_token = st.secrets["DIFFBOT_API"]

client = OpenAI(api_key= api_key)

tickers_info = {
    "ACAD": {"name": "ACADIA Pharmaceuticals, Inc.", "website": "acadia.com"},
    "ALXO": {"name": "ALX Oncology Holdings, Inc.", "website": "alxoncology.com"},
    "AXSM": {"name": "Axsome Therapeutics, Inc.", "website": "axsome.com"},
    "GLPG": {"name": "Galapagos N.V.", "website": "glpg.com"},
    "GMAB": {"name": "Genmab A/S", "website": "genmab.com"},
    "ITCI": {"name": "Intra‑Cellular Therapies, Inc.", "website": "intracellulartherapies.com"},
    "ALM": {"name": "Almirall", "website": "almirall.com"},
    "MRK": {"name": "Merck & Co., Inc.", "website": "merck.com"},
    "ROIV": {"name": "Roivant Sciences Ltd.", "website": "roivant.com"},
    "UCB": {"name": "Union Chimique Belge.", "website": "ucb.com"},
    "ZLAB": {"name": "Zai Lab Limited", "website": "zailaboratory.com"},
    "FDMT": {"name": "4D Molecular Therapeutics", "website": "fdmt.com"},
    "ARWR": {"name": "Arrowhead Pharmaceuticals, Inc.", "website": "arrowheadpharma.com"},
    "AUTL": {"name": "Autolus Therapeutics plc", "website": "autolus.com"},
    "RNA": {"name": "Avidity Biosciences, Inc.", "website": "aviditybiosciences.com"},
    "CRSP": {"name": "CRISPR Therapeutics AG", "website": "crisprtx.com"},
    "DYN": {"name": "Dyne Therapeutics, Inc.", "website": "dynetherapeutics.com"},
    "EVT": {"name": "Evotec", "website": "evotec.com"},
    "FATE": {"name": "Fate Therapeutics", "website": "fatetherapeutics.com"},
    "NTLA": {"name": "Intellia Therapeutics", "website": "intelliatx.com"},
    "IONS": {"name": "Ionis Pharmaceuticals", "website": "ionispharma.com"},
    "KRYS": {"name": "Krystal", "website": "krystalbio.com"},
    "LXEO": {"name": "Lexeo Therapeutics", "website": "lxeotx.com"},
    "MGTX": {"name": "MeiraGTx Holdings plc", "website": "meiragtx.com"},
    "MRNA": {"name": "Moderna, Inc.", "website": "modernatx.com"},
    "PSTX": {"name": "Poseida Therapeutics, Inc.", "website": "poseida.com"},
    "PRQR": {"name": "ProQR Therapeutics N.V.", "website": "proqr.com"},
    "RXRX": {"name": "Recursion Pharmaceuticals, Inc.", "website": "recursion.com"},
    "RCKT": {"name": "Rocket Pharmaceuticals, Inc.", "website": "rocketpharma.com"},
    "TSHA": {"name": "Taysha Gene Therapies, Inc.", "website": "tayshagtx.com"},
    "RARE": {"name": "Ultragenyx Pharmaceutical Inc.", "website": "ultragenyx.com"},
    "QURE": {"name": "UniQure", "website": "uniqure.com"},
    "WVE": {"name": "Wave Life Sciences Ltd.", "website": "wavelifesciences.com"}
}



@st.cache_data(ttl=3600)
def fetch_alpha_vantage_data(ticker, period):
    """Fetch data from Alpha Vantage and filter by period, including price growth calculation"""
    ts = TimeSeries(key=alpha_vantage_key, output_format='pandas')
    
    try:
        # Get full daily data (we'll filter it later)
        data, meta_data = ts.get_daily(symbol=ticker, outputsize='full')
        data.index = pd.to_datetime(data.index)
        
        # Filter based on selected period
        today = pd.Timestamp.today()
        period_map = {
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365
        }
        cutoff_days = period_map.get(period, 365)
        cutoff_date = today - pd.Timedelta(days=cutoff_days)

        filtered_data = data[data.index >= cutoff_date]
        
        # Rename columns to match yfinance format
        filtered_data = filtered_data.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume'
        })
        
        filtered_data = filtered_data.sort_index()  # ascending by date

        # --- Calculate price growth ---
        if not filtered_data.empty:
            first_close = filtered_data['Close'].iloc[0]
            last_close = filtered_data['Close'].iloc[-1]
            price_growth_pct = ((last_close - first_close) / first_close) * 100
        else:
            price_growth_pct = None

        return filtered_data, price_growth_pct

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None


def df_dict_to_dict_of_records(d):
    # d: {key: DataFrame}
    return {k: v.to_dict(orient="records") for k, v in d.items()}
    
def calculate_technical_indicators(data, ticker, weight_choice=None):
    """
    Calculate various technical indicators, prepare them for AI analysis,
    and compute a weighted technical score.

    Args:
        data (pd.DataFrame): The input financial data.
        ticker (str): The stock ticker.
        weights (dict): Optional dict of weights for each indicator.

    Returns:
        Tuple: (results dict, recent_data, availability, scores, weighted_score)
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
            "bbands": 0.0  # Set to 0 if not using
        }

# Choose the right weights
    if weight_choice == "Short Term":
        weights = short_term_weights
    if weight_choice == "Long Term":
        weights = long_term_weights
    if weight_choice == "Default":
        weights = weights

    # --- Default Weights if not provided ---

    # Initialize availability flags
    sma_available = False
    rsi_available = False
    macd_available = False
    obv_available = False
    adx_available = False
    bbands_available = False

    # --- Calculate SMA ---
    if 'Close' in data.columns:
        data['SMA_20'] = ta.sma(data['Close'], length=20)
        data['SMA_50'] = ta.sma(data['Close'], length=50)
        data['SMA_200'] = ta.sma(data['Close'], length=200)
        sma_available = data[['SMA_20', 'SMA_50', 'SMA_200']].notna().any().any()

    # --- Calculate RSI ---
    if 'Close' in data.columns:
        data['RSI'] = ta.rsi(data['Close'], length=14)
        rsi_available = 'RSI' in data.columns and data['RSI'].notna().any()

    # --- Calculate MACD ---
    macd = ta.macd(data['Close'])
    if macd is not None and all(col in macd.columns for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
        data['MACD'] = macd['MACD_12_26_9']
        data['MACD_signal'] = macd['MACDs_12_26_9']
        data['MACD_hist'] = macd['MACDh_12_26_9']
        macd_available = True

    # --- Calculate OBV ---
    if 'Close' in data.columns and 'Volume' in data.columns:
        data['OBV'] = ta.obv(data['Close'], data['Volume'])
        obv_available = 'OBV' in data.columns and data['OBV'].notna().any()

    # --- Calculate ADX ---
    adx = ta.adx(data['High'], data['Low'], data['Close'])
    if adx is not None and 'ADX_14' in adx.columns:
        data['ADX'] = adx['ADX_14']
        adx_available = True

    # --- Calculate Bollinger Bands ---
    bbands = ta.bbands(data['Close'], length=20, std=2)
    if bbands is not None and all(col in bbands.columns for col in ['BBU_20_2.0', 'BBM_20_2.0', 'BBL_20_2.0']):
        data['upper_band'] = bbands['BBU_20_2.0']
        data['middle_band'] = bbands['BBM_20_2.0']
        data['lower_band'] = bbands['BBL_20_2.0']
        bbands_available = True

    # --- Resample data weekly ---
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

    # --- Prepare data for analysis ---
    recent_data = data

    # --- Run your original analysis functions (these return text) ---
    results = {
        "bd_result": recent_data[["Open", "High", "Low", "Close", "Volume", "upper_band", "middle_band", "lower_band"]],
        "sma_result": recent_data[["Open", "High", "Low", "Close", "SMA_20", "SMA_50", "SMA_200"]],
        "rsi_result": recent_data[["Open", "High", "Low", "Close", "RSI"]],
        "macd_result": recent_data[["Open", "High", "Low", "Close", "MACD", "MACD_signal", "MACD_hist"]],
        "obv_result": recent_data[["Open", "High", "Low", "Close", "Volume", "OBV"]],
        "adx_result": recent_data[["Open", "High", "Low", "Close", "ADX"]]
    }

    availability = {
        "sma_available": sma_available,
        "rsi_available": rsi_available,
        "macd_available": macd_available,
        "obv_available": obv_available,
        "adx_available": adx_available,
        "bbands_available": bbands_available
    }

    # --- SCORING SECTION (replace these with your real logic!) ---
    last = recent_data.iloc[-1]  # Last row (most recent week)
    scores = {}

    # Simple scoring logic (customize as needed)
    # Bullish (+1), Bearish (-1), Neutral (0)
    scores['sma'] = 1 if sma_available and last['Close'] > last['SMA_20'] else -1 if sma_available else 0
    scores['rsi'] = 1 if rsi_available and last['RSI'] > 55 else -1 if rsi_available and last['RSI'] < 45 else 0
    scores['macd'] = 1 if macd_available and last['MACD'] > last['MACD_signal'] else -1 if macd_available else 0
    scores['obv'] = 1 if obv_available and last['OBV'] > 0 else -1 if obv_available and last['OBV'] < 0 else 0
    scores['adx'] = 1 if adx_available and last['ADX'] > 20 else -1 if adx_available and last['ADX'] < 20 else 0
    scores['bbands'] = 1 if bbands_available and last['Close'] > last['middle_band'] else -1 if bbands_available else 0

    # --- Weighted score ---
    total_weight = sum([weights.get(k, 0) for k in scores if availability.get(f"{k}_available", False)])
    weighted_score = sum(
        scores[k] * weights.get(k, 0)
        for k in scores if availability.get(f"{k}_available", False)
    ) / total_weight if total_weight > 0 else 0

    # --- RETURN everything ---
    return results, recent_data, availability, scores, weighted_score

def generate_company_news_message(ticker, time_period):
    # Define the messages for different time periods 
    info = tickers_info.get(ticker)

    if not info:
        return f"No info found for {ticker}."
    
    company_name = info["name"]
    website = info["website"]


    query = f""" "{company_name}" """

    
    params = {
        "engine": "google_news",
        "q": query,
        "api_key": serpapi_key
    }

    print(f"\n🔍 Searching SerpAPI with query: {query}")
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        print(results)
        print("✅ SerpAPI search completed")
    except Exception as e:
        print(f"❌ SerpAPI error: {e}")
        return
    
    news = []
    for item in results.get("news_results", [])[:20]:
        title = item.get("title", "")
        date = item.get("date", "")
        link = item.get("link", "")
        print(f"\n📄 Scraping: {title}")
        content = extract_diffbot_data(link)

        news.append({
            "title": title,
            "date": date,
            "link": link,
            "content": content
        })

        time.sleep(4)

    #Webhook payload
    payload = {
        "news": news,
        "company": company_name,
        "time_frame": time_period
    }

    return payload


def extract_diffbot_data(link):
    url = f"https://api.diffbot.com/v3/analyze?url={link}&token={diffbot_token}"
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        article = data.get("objects", [])[0]  # Take the first object

        title = article.get("title", "N/A")
        date = article.get("date", "N/A")
        link = article.get("pageUrl", "N/A")
        content = article.get("text", "N/A")

        return content


    except Exception as e:
        print(f"❌ Failed to extract Diffbot data: {e}")
        print(link)

def analyse_results(gathered_data,timeframe):

    today = date.today()
    formatted = today.strftime('%Y-%m-%d')

    if timeframe == "3 Months":
        delta = relativedelta(months=3)
    elif timeframe == "6 Months":
        delta = relativedelta(months=6)
    elif timeframe == "1 Year":
        delta = relativedelta(years=1)
    else:
        delta = relativedelta(months=0)  # default, in case

    date_ago = today - delta
    formatted_date_ago = date_ago.strftime('%Y-%m-%d')

    system_prompt = f"""
    You are a world-class investment analyst specializing in synthesizing technical, news, and event-driven data for stock prediction.

    You will receive a JSON dataset for several tickers, each containing:
    - technical analysis (scores, indicators, trends)
    - news/events (summaries, dates, catalysts)
    - user-selected weightings and a precomputed weighted_score for each ticker
    - the actual company_growth_pct (historical price change for the selected timeframe)

    **IMPORTANT INSTRUCTIONS:**
    - Only analyze and reference data (technical indicators, news/events, growth_pct) from {formatted_date_ago} onward. Ignore any information from before this date.
    - Provide a concise rationale referencing only the dataset provided.
    - DO NOT use any external data, prior trends, or information from before {formatted_date_ago}.

    **Your main objectives:**
    - Rank the top 5 companies most likely to achieve the highest percentage price growth over the next {timeframe}, using only data since {formatted_date_ago}.
    - Emphasize your top pick and explain your reasoning for its selection.
    - For each of the top 5 companies, generate a comprehensive HTML report using the template provided below.

    **CRITICAL INSTRUCTION FOR NEWS/EVENTS ANALYSIS:**
    - In your analysis and ranking, **assign significantly higher weight to companies that have upcoming scheduled catalysts within the timeframe (such as data releases, product launches, FDA decisions, or major events) as these are historically strong triggers for short-term stock price movement.**
    - Clearly identify and call out these scheduled events in your news/events section, explaining why they are likely to move the stock more than general positive news or recent past news alone.
    - Positive recent news may support a steady growth thesis, but upcoming scheduled catalysts should be considered stronger predictors of significant movement and ranked accordingly.

    **For each of the 5 tickers, your HTML report must include:**
    - Executive summary focused on predicted future growth and justification for ranking
    - Concise rationale for the potential growth, citing the most relevant technical/news evidence
    - Technical outlook and relevant indicators (SMA, RSI, MACD, OBV, ADX, Bollinger Bands) since {formatted_date_ago}
    - News/events analysis, noting any catalysts, risks, or trends that could impact price since {formatted_date_ago}
        - Explicitly highlight any scheduled catalysts (data releases, product launches, regulatory decisions, earnings, etc.) expected within the timeframe and explain their likely impact
    - The actual historical company_growth_pct (for the selected timeframe, starting {formatted_date_ago})
    - Explanation of why the top company is expected to outperform the others in the selected timeframe
    - Display of key weights, weighted_score, and any confidence ratings
    - Investment recommendation (Buy/Hold/Sell) and any suggested entry/exit or risk strategies
    - Brief sector or cross-ticker summary if any trends emerge

    **Additional rules:**
    - If a data field cannot be filled, use “Not available” or leave the field empty, but always keep the template structure.
    - Only output a valid HTML file: for each selected ticker, fill a .container report section and combine all 5 in the HTML <body>.
    - Your output must be fully ready to display in a browser or HTML viewer.
    - In your final ranking and commentary, clarify if a company’s high predicted growth is due to an upcoming event/catalyst and why it is likely to have a greater effect than other news.

    So, if a company has good recent historical news, that is a positive indicator for steady growth, but if they have a big event, data release, or scheduled catalyst soon, that should be weighted as a bigger trigger and may significantly affect the stock price. Take this into consideration in your rankings and explanations.

    **HTML Template:**  
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprehensive Investment Analysis</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 0px;
                background-color: transparent;
            }}
            .container {{
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                padding: 30px;
                margin-bottom: 30px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            h2 {{
                color: #2c3e50;
                border-left: 5px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }}
            h3 {{
                color: #2c3e50;
                margin-top: 20px;
                border-bottom: 1px dashed #ddd;
                padding-bottom: 5px;
            }}
            .section {{
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .prediction-number {{
                font-size: 2em;
                font-weight: bold;
                color: #1d8348;
                margin-bottom: 10px;
                text-align: right;
            }}
            .recommendation {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                text-align: center;
            }}
            .buy {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .hold {{
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }}
            .sell {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .indicator {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
            }}
            .indicator h4 {{
                margin-top: 0;
                color: #2980b9;
            }}
            .summary-box {{
                background-color: #e8f4fd;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }}
            .timeframe {{
                font-weight: bold;
                color: #2c3e50;
                background-color: #e8f4fd;
                padding: 5px 10px;
                border-radius: 3px;
                display: inline-block;
                margin-bottom: 15px;
            }}
            .weights-section {{
                background-color: #f0f4f9;
                border-left: 4px solid #2980b9;
                margin-bottom: 30px;
                padding: 15px;
                border-radius: 0 5px 5px 0;
            }}
            .footnote {{
                font-size: 0.9em;
                font-style: italic;
                color: #6c757d;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #dee2e6;
            }}
            .highlight {{
                background-color: #ffeaa7;
                padding: 2px 4px;
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        [INSERT_ALL_ANALYSIS_HTML_HERE]
        <div class="footnote">
            <p>This investment analysis was generated on {formatted} and incorporates available data as of this date. All investment decisions should be made in conjunction with personal financial advice and risk tolerance assessments.</p>
        </div>
    </body>
    </html>
    """


    user_message = f"The data to analyse: {gathered_data})"
    
    # Call Claude API to generate the HTML with progress indicator
    with st.spinner("Generating investment analysis..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",  # Use the appropriate Claude model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
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

# def fix_html_with_embedded_markdown(text):
#     """
#     Detects markdown sections embedded within mostly-HTML output,
#     converts them to HTML, and replaces them in the text.
#     """
#     if not text:
#         return text

#     # Don't touch it if it's a fully valid HTML document
#     if bool(re.search(r'<html', text, re.IGNORECASE)):
#         return text

def fix_html_with_embedded_markdown_all(html, tags=None):
    soup = BeautifulSoup(html, 'html.parser')
    if tags is None:
        tags = ['div', 'section', 'td', 'span', 'p']

    for tag in soup.find_all(tags):
        raw = tag.string
        if raw and not re.search(r'<[a-z][\s\S]*?>', raw):
            # If markdown is detected
            if re.search(r'(\*\*|__|#|\* |\d+\.)', raw):
                html_converted = markdown2.markdown(raw)
                html_converted = re.sub(r'^<p>|</p>$', '', html_converted.strip())
                tag.clear()
                tag.append(BeautifulSoup(html_converted, 'html.parser'))
    return str(soup)



def stock_page():
    if "run_analysis_complete" not in st.session_state:
        st.session_state["run_analysis_complete"] = False

    st.title("Portfolio Analysis")

    with st.sidebar:
        st.subheader("Select Timeframe for Analysis")
        timeframe = st.radio(
            "Choose timeframe:",
            ("3 Months", "6 Months", "1 Year"),
            index=2,
            help="Select the period of historical data for the stock analysis"
        )

        # --- Analysis Options ---
        st.subheader("Analysis Options")
        technical_analysis = st.checkbox("Technical Analysis", help="Select to run technical analysis indicators")
        news_and_events = st.checkbox("News and Events", help="Get recent news and event analysis for the company")

        selected_types = [
            technical_analysis,
            news_and_events
        ]
        selected_count = sum(selected_types)

        weight_choice = "Default"
        if technical_analysis:
            weight_choice = st.radio(
                "Weighting Style",
                ("Short Term", "Long Term", "Default"),
                index=1,
                help="Choose analysis style for technical indicators"
            )

        if selected_count > 1:
            st.subheader("Analysis Weightings")
            default_weights = {
                "Technical": 0.5,
                "News": 0.5
            }
            tech_weight = st.slider("Technical Analysis Weight", 0.0, 1.0, default_weights["Technical"])
            news_weight = st.slider("News Analysis Weight", 0.0, 1.0, default_weights["News"])
            # Normalize to sum to 1
            total = tech_weight + news_weight
            if total > 0:
                tech_weight /= total
                news_weight /= total
            else:
                tech_weight = news_weight = 0.5
        else:
            tech_weight = 1.0 if technical_analysis else 0.0
            news_weight = 1.0 if news_and_events else 0.0

        st.header("Input Options")
        input_method = st.radio(
            "How would you like to input the data?",
            ("Upload CSVs", "Enter Manually","Full Portfolio")
        )

        # --- Gather tickers ---
        portfolio_df = None
        if input_method == "Upload CSV":
            portfolio_file = st.file_uploader("Upload Portfolio Tickers CSV", type="csv")
            if portfolio_file:
                portfolio_df = pd.read_csv(portfolio_file)
                if 'Ticker' not in portfolio_df.columns:
                    st.error("CSV must contain a 'Ticker' column.")
                    st.stop()
        elif input_method == "Enter Manually":
            portfolio_tickers = st.text_area(
                "Enter Portfolio Tickers (comma-separated)",
                help="Example: ACAD,ALXO,AXSM"
            )
            tickers = [t.strip().upper() for t in portfolio_tickers.split(",") if t.strip()]
            if tickers:
                portfolio_df = pd.DataFrame({"Ticker": tickers})
        elif input_method == "Full Portfolio":
            tickers = list(tickers_info.keys())
            portfolio_df = pd.DataFrame({"Ticker": tickers})

    # Portfolio DataFrame and tickers will be available outside the sidebar for further use.
    # If you want to display the tickers in the main area:
        run_button = st.button("Run Analysis")
        st.markdown("---")
        st.info("Click 'Run Analysis' after selecting options to start.")

        # Button to start analysis
    if run_button:
        all_results = {}
        with st.expander("Loading..."):
            for idx, row in portfolio_df.iterrows():
                ticker = row['Ticker']
                st.write(f"Analyzing {ticker}...")
                
                data,company_growth = fetch_alpha_vantage_data(ticker, timeframe)
                if data is None or data.empty:
                    st.warning(f"No data found for {ticker}.")
                    continue

                result_data = {}
                # --- Technical Analysis ---
                if technical_analysis:
                    try:
                        results, recent_data, availability, scores, weighted_score = calculate_technical_indicators(
                            data, ticker, weight_choice
                        )
                        result_data["technical"] = {
                            "indicator_results": df_dict_to_dict_of_records(results),
                            #"recent_data": recent_data.to_dict(orient="records"),
                            "availability": availability,
                            "scores": scores,
                            "weighted_score": weighted_score,
                            "company_growth_pct": company_growth,
                            "tech_weight": tech_weight
                        }
                        #st.success(f"{ticker} technical analysis complete! Weighted Score: {weighted_score:.2f}")
                    except Exception as e:
                        st.error(f"Technical analysis error for {ticker}: {e}")

                # --- News and Events Analysis (Placeholder - replace with your logic) ---
                if news_and_events:
                    try:
                        news_payload = generate_company_news_message(ticker, timeframe)
                        result_data["news"] = {
                            "results": news_payload,  # or a summary string from payload, adjust as needed
                            "news_weight": news_weight
                        }
                        #st.info(f"{ticker} news/events analysis complete! Used query: site:{tickers_info.get(ticker,{}).get('website','')} ...")
                    except Exception as e:
                        st.error(f"News/events analysis error for {ticker}: {e}")

            # Store all analysis for this ticker
                all_results[ticker] = result_data

        st.session_state["all_ticker_results"] = all_results

        html_text = analyse_results(all_results,timeframe)
        html_output_no_fix = clean_html_response(html_text)
        html_output = fix_html_with_embedded_markdown(html_output_no_fix)

        st.components.v1.html(html_output, height=700, scrolling=True)


        st.download_button(
            label="Download as HTML",
            data=html_output,
            file_name="stock_analysis_summary.html",
            mime="text/html"
        )


        # --- Display results ---
        # st.write("## Portfolio Summary:")
        # for ticker, results in all_results.items():
        #     st.write(f"### {ticker}")
        #     if "technical" in results:
        #         st.write("**Technical Analysis Weighted Score:**", results['technical']['weighted_score'])
        #         st.write("**Recent Data:**")
        #         st.dataframe(results["technical"]["recent_data"])
        #         st.write("**Indicator Summaries:**")
        #         st.json(results["technical"]["indicator_results"])
        #     if "news" in results:
        #         st.write("**News & Events Summary:**", results["news"]["summary"])
        #     st.write("---")

    # if "all_ticker_results" in st.session_state and st.session_state["all_ticker_results"]:
    #     st.download_button(
    #         "Download Results (JSON)",
    #         data=json.dumps(st.session_state["all_ticker_results"], default=str, indent=2),
    #         file_name="portfolio_analysis.json",
    #         mime="application/json"
    #     )

    

if __name__ == "__main__":
    stock_page()






