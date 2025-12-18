"""
Market Data Generator v4.0
==========================
Yahoo Finance'den ETF ve Stock verisi çeker ve JSON dosyası üretir.
HTML dashboard bu JSON'u yükler.

Kullanım:
    python etf_data_generator.py

Çıktı:
    etf_data.json - Dashboard'un yükleyeceği veri dosyası
"""

import pandas as pd
import numpy as np
import yfinance as yf
from scipy import stats
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# ETF UNIVERSE (66 ETF)
# =============================================================================
ETF_UNIVERSE = {
    "UUP": ("Macro", "Currency", "US Dollar Index"),
    "VXX": ("Macro", "Volatility", "Short-Term VIX Futures"),
    "BIL": ("Bonds", "Cash", "1-3 Month T-Bill"),
    "SHY": ("Bonds", "Treasury", "1-3 Year Treasury"),
    "IEF": ("Bonds", "Treasury", "7-10 Year Treasury"),
    "TLT": ("Bonds", "Treasury", "20+ Year Treasury"),
    "TIP": ("Bonds", "Inflation", "TIPS"),
    "GOVT": ("Bonds", "Treasury", "US Treasury All Maturities"),
    "AGG": ("Bonds", "Aggregate", "Core US Aggregate Bond"),
    "BND": ("Bonds", "Aggregate", "Total Bond Market"),
    "HYG": ("Bonds", "Credit", "High Yield Bond"),
    "LQD": ("Bonds", "Credit", "Inv. Grade Corp Bond"),
    "SPY": ("Equity", "Core", "S&P 500"),
    "QQQ": ("Equity", "Core", "Nasdaq-100"),
    "IWM": ("Equity", "Core", "Russell 2000"),
    "OEF": ("Equity", "Core", "S&P 100"),
    "FEZ": ("Equity", "Global", "Euro Stoxx 50"),
    "VGK": ("Equity", "Global", "FTSE Europe"),
    "EWJ": ("Equity", "Global", "MSCI Japan"),
    "VXUS": ("Equity", "Global", "Total Intl ex-US"),
    "EEM": ("Equity", "Global", "Emerging Markets"),
    "VWO": ("Equity", "Global", "EM Low Cost"),
    "FXI": ("Equity", "Global", "FTSE China 50"),
    "KWEB": ("Equity", "Global", "China Internet"),
    "INDA": ("Equity", "Global", "MSCI India"),
    "VTV": ("Equity", "Factor", "Value"),
    "MTUM": ("Equity", "Factor", "Momentum"),
    "LCTU": ("Equity", "Factor", "Quality Low Vol"),
    "XLF": ("Sector", "Cyclical", "Financials"),
    "XLK": ("Sector", "Growth", "Technology"),
    "XLE": ("Sector", "Cyclical", "Energy"),
    "XLY": ("Sector", "Cyclical", "Consumer Discretionary"),
    "XLP": ("Sector", "Defensive", "Consumer Staples"),
    "XLI": ("Sector", "Cyclical", "Industrials"),
    "XLB": ("Sector", "Cyclical", "Materials"),
    "XLV": ("Sector", "Defensive", "Healthcare"),
    "XLC": ("Sector", "Cyclical", "Communication Services"),
    "XLU": ("Sector", "Defensive", "Utilities"),
    "XLRE": ("Sector", "Interest", "Real Estate"),
    "SOXX": ("Industry", "Tech", "Semiconductors"),
    "IGV": ("Industry", "Tech", "Software/SaaS"),
    "CIBR": ("Industry", "Tech", "Cybersecurity"),
    "SKYY": ("Industry", "Tech", "Cloud Computing"),
    "ITA": ("Industry", "Defense", "Aerospace & Defense"),
    "XAR": ("Industry", "Defense", "Aerospace Alt"),
    "XRT": ("Industry", "Consumer", "Retail"),
    "XBI": ("Industry", "Biotech", "Biotech"),
    "MOO": ("Industry", "Agri", "Agribusiness"),
    "TAN": ("Industry", "Energy", "Solar"),
    "ARKK": ("Thematic", "Innovation", "Disruptive Innovation"),
    "DRIV": ("Thematic", "Auto", "Autonomous & EV"),
    "BOTZ": ("Thematic", "Tech", "Robotics & AI"),
    "GLD": ("Comm.", "Precious", "Gold"),
    "SLV": ("Comm.", "Precious", "Silver"),
    "BNO": ("Comm.", "Energy", "Brent Oil"),
    "CPER": ("Comm.", "Industrial", "Copper"),
    "UGA": ("Comm.", "Energy", "Gasoline"),
    "URA": ("Comm.", "Energy", "Uranium"),
    "USO": ("Comm.", "Energy", "WTI Oil"),
    "UNG": ("Comm.", "Energy", "Natural Gas"),
    "DBA": ("Comm.", "Agri", "Agriculture Fund"),
    "WEAT": ("Comm.", "Agri", "Wheat"),
    "CORN": ("Comm.", "Agri", "Corn"),
    "SOYB": ("Comm.", "Agri", "Soybean"),
    "IBIT": ("Crypto", "Bitcoin", "Spot Bitcoin ETF"),
    "ETHA": ("Crypto", "Ethereum", "Spot Ethereum ETF"),
}

# =============================================================================
# SP100 STOCKS (125 Stocks)
# =============================================================================
STOCK_UNIVERSE = {
    # Technology
    'AAPL': ('Technology', 'Hardware', 'Apple Inc.'),
    'MSFT': ('Technology', 'Software', 'Microsoft Corp.'),
    'GOOGL': ('Technology', 'Internet', 'Alphabet Inc.'),
    'META': ('Technology', 'Social Media', 'Meta Platforms'),
    'NVDA': ('Technology', 'Semiconductors', 'NVIDIA Corp.'),
    'AVGO': ('Technology', 'Semiconductors', 'Broadcom Inc.'),
    'CSCO': ('Technology', 'Networking', 'Cisco Systems'),
    'ADBE': ('Technology', 'Software', 'Adobe Inc.'),
    'CRM': ('Technology', 'Software', 'Salesforce Inc.'),
    'ORCL': ('Technology', 'Software', 'Oracle Corp.'),
    'ACN': ('Technology', 'Consulting', 'Accenture plc'),
    'IBM': ('Technology', 'IT Services', 'IBM Corp.'),
    'INTC': ('Technology', 'Semiconductors', 'Intel Corp.'),
    'AMD': ('Technology', 'Semiconductors', 'AMD Inc.'),
    'QCOM': ('Technology', 'Semiconductors', 'Qualcomm Inc.'),
    'TXN': ('Technology', 'Semiconductors', 'Texas Instruments'),
    'AMAT': ('Technology', 'Equipment', 'Applied Materials'),
    'NOW': ('Technology', 'Software', 'ServiceNow Inc.'),
    'INTU': ('Technology', 'Software', 'Intuit Inc.'),
    
    # Healthcare
    'JNJ': ('Healthcare', 'Pharma', 'Johnson & Johnson'),
    'UNH': ('Healthcare', 'Insurance', 'UnitedHealth Group'),
    'PFE': ('Healthcare', 'Pharma', 'Pfizer Inc.'),
    'ABBV': ('Healthcare', 'Pharma', 'AbbVie Inc.'),
    'MRK': ('Healthcare', 'Pharma', 'Merck & Co.'),
    'LLY': ('Healthcare', 'Pharma', 'Eli Lilly & Co.'),
    'TMO': ('Healthcare', 'Equipment', 'Thermo Fisher'),
    'ABT': ('Healthcare', 'Devices', 'Abbott Labs'),
    'DHR': ('Healthcare', 'Equipment', 'Danaher Corp.'),
    'BMY': ('Healthcare', 'Pharma', 'Bristol-Myers Squibb'),
    'AMGN': ('Healthcare', 'Biotech', 'Amgen Inc.'),
    'GILD': ('Healthcare', 'Biotech', 'Gilead Sciences'),
    'MDT': ('Healthcare', 'Devices', 'Medtronic plc'),
    'CVS': ('Healthcare', 'Retail', 'CVS Health'),
    'ISRG': ('Healthcare', 'Devices', 'Intuitive Surgical'),
    
    # Financials
    'JPM': ('Financials', 'Banks', 'JPMorgan Chase'),
    'BAC': ('Financials', 'Banks', 'Bank of America'),
    'WFC': ('Financials', 'Banks', 'Wells Fargo'),
    'GS': ('Financials', 'Investment Banks', 'Goldman Sachs'),
    'MS': ('Financials', 'Investment Banks', 'Morgan Stanley'),
    'BLK': ('Financials', 'Asset Mgmt', 'BlackRock Inc.'),
    'SCHW': ('Financials', 'Brokers', 'Charles Schwab'),
    'AXP': ('Financials', 'Credit Cards', 'American Express'),
    'C': ('Financials', 'Banks', 'Citigroup Inc.'),
    'USB': ('Financials', 'Banks', 'U.S. Bancorp'),
    'PNC': ('Financials', 'Banks', 'PNC Financial'),
    'TFC': ('Financials', 'Banks', 'Truist Financial'),
    'COF': ('Financials', 'Credit Cards', 'Capital One'),
    'BK': ('Financials', 'Custody', 'Bank of NY Mellon'),
    'CME': ('Financials', 'Exchanges', 'CME Group'),
    'MA': ('Financials', 'Payments', 'Mastercard Inc.'),
    'V': ('Financials', 'Payments', 'Visa Inc.'),
    'PYPL': ('Financials', 'Payments', 'PayPal Holdings'),
    'MET': ('Financials', 'Insurance', 'MetLife Inc.'),
    'AIG': ('Financials', 'Insurance', 'AIG Inc.'),
    
    # Consumer Discretionary
    'AMZN': ('Consumer Disc.', 'E-Commerce', 'Amazon.com'),
    'TSLA': ('Consumer Disc.', 'Auto', 'Tesla Inc.'),
    'HD': ('Consumer Disc.', 'Retail', 'Home Depot'),
    'MCD': ('Consumer Disc.', 'Restaurants', 'McDonald\'s Corp.'),
    'NKE': ('Consumer Disc.', 'Apparel', 'Nike Inc.'),
    'SBUX': ('Consumer Disc.', 'Restaurants', 'Starbucks Corp.'),
    'LOW': ('Consumer Disc.', 'Retail', 'Lowe\'s Cos.'),
    'TJX': ('Consumer Disc.', 'Retail', 'TJX Companies'),
    'TGT': ('Consumer Disc.', 'Retail', 'Target Corp.'),
    'F': ('Consumer Disc.', 'Auto', 'Ford Motor'),
    'GM': ('Consumer Disc.', 'Auto', 'General Motors'),
    'BKNG': ('Consumer Disc.', 'Travel', 'Booking Holdings'),
    
    # Consumer Staples
    'PG': ('Consumer Stpl.', 'Household', 'Procter & Gamble'),
    'KO': ('Consumer Stpl.', 'Beverages', 'Coca-Cola Co.'),
    'PEP': ('Consumer Stpl.', 'Beverages', 'PepsiCo Inc.'),
    'COST': ('Consumer Stpl.', 'Retail', 'Costco Wholesale'),
    'WMT': ('Consumer Stpl.', 'Retail', 'Walmart Inc.'),
    'PM': ('Consumer Stpl.', 'Tobacco', 'Philip Morris'),
    'MO': ('Consumer Stpl.', 'Tobacco', 'Altria Group'),
    'CL': ('Consumer Stpl.', 'Household', 'Colgate-Palmolive'),
    'KHC': ('Consumer Stpl.', 'Food', 'Kraft Heinz'),
    'MDLZ': ('Consumer Stpl.', 'Food', 'Mondelez Intl'),
    'EL': ('Consumer Stpl.', 'Personal', 'Estee Lauder'),
    
    # Energy
    'XOM': ('Energy', 'Integrated', 'Exxon Mobil'),
    'CVX': ('Energy', 'Integrated', 'Chevron Corp.'),
    'COP': ('Energy', 'E&P', 'ConocoPhillips'),
    'SLB': ('Energy', 'Services', 'Schlumberger'),
    'EOG': ('Energy', 'E&P', 'EOG Resources'),
    'OXY': ('Energy', 'E&P', 'Occidental Petro'),
    'PSX': ('Energy', 'Refining', 'Phillips 66'),
    'VLO': ('Energy', 'Refining', 'Valero Energy'),
    
    # Industrials
    'HON': ('Industrials', 'Conglomerate', 'Honeywell Intl'),
    'UNP': ('Industrials', 'Railroads', 'Union Pacific'),
    'UPS': ('Industrials', 'Logistics', 'United Parcel'),
    'RTX': ('Industrials', 'Aerospace', 'RTX Corp.'),
    'CAT': ('Industrials', 'Machinery', 'Caterpillar Inc.'),
    'DE': ('Industrials', 'Machinery', 'Deere & Co.'),
    'BA': ('Industrials', 'Aerospace', 'Boeing Co.'),
    'GE': ('Industrials', 'Conglomerate', 'GE Aerospace'),
    'LMT': ('Industrials', 'Defense', 'Lockheed Martin'),
    'MMM': ('Industrials', 'Conglomerate', '3M Company'),
    'FDX': ('Industrials', 'Logistics', 'FedEx Corp.'),
    'EMR': ('Industrials', 'Electrical', 'Emerson Electric'),
    'GD': ('Industrials', 'Defense', 'General Dynamics'),
    
    # Communication Services
    'DIS': ('Communication', 'Entertainment', 'Walt Disney'),
    'NFLX': ('Communication', 'Streaming', 'Netflix Inc.'),
    'CMCSA': ('Communication', 'Cable', 'Comcast Corp.'),
    'T': ('Communication', 'Telecom', 'AT&T Inc.'),
    'VZ': ('Communication', 'Telecom', 'Verizon Comm.'),
    'TMUS': ('Communication', 'Telecom', 'T-Mobile US'),
    'CHTR': ('Communication', 'Cable', 'Charter Comm.'),
    
    # Utilities
    'NEE': ('Utilities', 'Electric', 'NextEra Energy'),
    'DUK': ('Utilities', 'Electric', 'Duke Energy'),
    'SO': ('Utilities', 'Electric', 'Southern Co.'),
    'D': ('Utilities', 'Electric', 'Dominion Energy'),
    'AEP': ('Utilities', 'Electric', 'American Electric'),
    'EXC': ('Utilities', 'Electric', 'Exelon Corp.'),
    
    # Materials
    'LIN': ('Materials', 'Chemicals', 'Linde plc'),
    'APD': ('Materials', 'Chemicals', 'Air Products'),
    'ECL': ('Materials', 'Chemicals', 'Ecolab Inc.'),
    'DD': ('Materials', 'Chemicals', 'DuPont de Nemours'),
    'NEM': ('Materials', 'Mining', 'Newmont Corp.'),
    'FCX': ('Materials', 'Mining', 'Freeport-McMoRan'),
    'DOW': ('Materials', 'Chemicals', 'Dow Inc.'),
    
    # Real Estate
    'AMT': ('Real Estate', 'REITs', 'American Tower'),
    'PLD': ('Real Estate', 'REITs', 'Prologis Inc.'),
    'CCI': ('Real Estate', 'REITs', 'Crown Castle'),
    'EQIX': ('Real Estate', 'REITs', 'Equinix Inc.'),
    'PSA': ('Real Estate', 'REITs', 'Public Storage'),
    'SPG': ('Real Estate', 'REITs', 'Simon Property'),
}

MARKET_RATIOS = {
    "VXX_LEVEL": {"num": "VXX", "denom": None, "cat": "Risk-On/Off", "name": "Fear Index (VIX)"},
    "SPY_TLT": {"num": "SPY", "denom": "TLT", "cat": "Risk-On/Off", "name": "Stocks vs Bonds"},
    "HYG_LQD": {"num": "HYG", "denom": "LQD", "cat": "Risk-On/Off", "name": "Credit Spread"},
    "GLD_SPY": {"num": "GLD", "denom": "SPY", "cat": "Risk-On/Off", "name": "Gold vs Stocks"},
    "IWM_SPY": {"num": "IWM", "denom": "SPY", "cat": "Risk-On/Off", "name": "Small vs Large Cap"},
    "ARKK_SPY": {"num": "ARKK", "denom": "SPY", "cat": "Risk-On/Off", "name": "Speculation Index"},
    "XLY_XLP": {"num": "XLY", "denom": "XLP", "cat": "Economic Cycle", "name": "Consumer Cycle"},
    "CPER_GLD": {"num": "CPER", "denom": "GLD", "cat": "Economic Cycle", "name": "Copper/Gold Ratio"},
    "XLI_SPY": {"num": "XLI", "denom": "SPY", "cat": "Economic Cycle", "name": "Industrial Strength"},
    "XRT_SPY": {"num": "XRT", "denom": "SPY", "cat": "Economic Cycle", "name": "Retail Strength"},
    "SOXX_SPY": {"num": "SOXX", "denom": "SPY", "cat": "Economic Cycle", "name": "Semis Leadership"},
    "XLE_SPY": {"num": "XLE", "denom": "SPY", "cat": "Inflation", "name": "Energy vs Market"},
    "TIP_IEF": {"num": "TIP", "denom": "IEF", "cat": "Inflation", "name": "Breakeven Inflation"},
    "DBA_SPY": {"num": "DBA", "denom": "SPY", "cat": "Inflation", "name": "Agri vs Market"},
    "TLT_SHY": {"num": "TLT", "denom": "SHY", "cat": "Fed/Rates", "name": "Yield Curve"},
    "TLT_IEF": {"num": "TLT", "denom": "IEF", "cat": "Fed/Rates", "name": "Duration Preference"},
    "UUP_LEVEL": {"num": "UUP", "denom": None, "cat": "Fed/Rates", "name": "Dollar Strength"},
    "EEM_SPY": {"num": "EEM", "denom": "SPY", "cat": "Global", "name": "EM vs US"},
    "FXI_SPY": {"num": "FXI", "denom": "SPY", "cat": "Global", "name": "China vs US"},
    "KWEB_QQQ": {"num": "KWEB", "denom": "QQQ", "cat": "Global", "name": "China Tech vs US Tech"},
    "INDA_EEM": {"num": "INDA", "denom": "EEM", "cat": "Global", "name": "India vs EM"},
    "VGK_SPY": {"num": "VGK", "denom": "SPY", "cat": "Global", "name": "Europe vs US"},
    "EWJ_SPY": {"num": "EWJ", "denom": "SPY", "cat": "Global", "name": "Japan vs US"},
    "XLK_XLF": {"num": "XLK", "denom": "XLF", "cat": "Sector Rotation", "name": "Tech vs Financials"},
    "XLY_XLV": {"num": "XLY", "denom": "XLV", "cat": "Sector Rotation", "name": "Cyclical vs Defensive"},
    "XLB_XLP": {"num": "XLB", "denom": "XLP", "cat": "Sector Rotation", "name": "Materials vs Staples"},
}

PERIODS = {
    '1W': 5, '2W': 10, '1M': 21, '3M': 63, '6M': 126, '12M': 252
}

# =============================================================================
# CALCULATIONS
# =============================================================================
def fetch_prices(symbols, days=400):
    """Yahoo Finance'den fiyat çek - retry mekanizması ile"""
    import time
    
    print(f"📡 Fetching {len(symbols)} ETFs from Yahoo Finance...")
    end = datetime.now()
    start = end - timedelta(days=days)
    
    all_prices = pd.DataFrame()
    symbols_list = list(symbols)
    
    # Daha küçük gruplar halinde çek
    batch_size = 10
    max_retries = 5
    
    for i in range(0, len(symbols_list), batch_size):
        batch = symbols_list[i:i+batch_size]
        print(f"   Batch {i//batch_size + 1}/{(len(symbols_list)-1)//batch_size + 1}: {', '.join(batch[:3])}...")
        
        for attempt in range(max_retries):
            try:
                data = yf.download(
                    batch, 
                    start=start, 
                    end=end, 
                    progress=False, 
                    auto_adjust=True,
                    threads=False
                )
                
                if len(batch) == 1:
                    prices = data['Close'] if 'Close' in data.columns else data
                    if isinstance(prices, pd.Series):
                        prices = prices.to_frame(batch[0])
                else:
                    prices = data['Close'] if 'Close' in data.columns else data
                
                if prices is not None and len(prices) > 0:
                    all_prices = pd.concat([all_prices, prices], axis=1)
                break
                
            except Exception as e:
                print(f"   ⚠️ Attempt {attempt+1}/{max_retries}: {str(e)[:40]}...")
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 3  # 3, 6, 9, 12 saniye
                    print(f"   ⏳ Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Skipping: {', '.join(batch)}")
        
        time.sleep(1)  # Rate limit için bekleme
    
    # Duplicate kolonları temizle
    all_prices = all_prices.loc[:, ~all_prices.columns.duplicated()]
    
    print(f"✅ Fetched {len(all_prices)} days, {len(all_prices.columns)} symbols")
    return all_prices

def calc_metrics(prices, period_days):
    """Bir periyot için metrikler hesapla"""
    
    # DÜZELTME: Önce o hisse için boş olan günleri at (Sadece işlem günleri kalsın)
    clean_prices = prices.dropna()
    
    # Yeterli veri var mı kontrol et
    min_required = max(3, period_days // 2)
    if len(clean_prices) < min_required:
        return None
        
    # Temiz veri üzerinden son X günü al
    actual_days = min(period_days, len(clean_prices))
    p = clean_prices.tail(actual_days)
    
    if len(p) < 3:  # En az 3 gün veri olsun
        return None
    
    # Return
    ret = (p.iloc[-1] / p.iloc[0] - 1) * 100
    
    # Trend (annualized)
    x = np.arange(len(p))
    try:
        slope, _, r, _, _ = stats.linregress(x, np.log(p.values + 0.0001))
    except Exception:
        return None
    trend = (np.exp(slope * 252) - 1) * 100
    quality = r ** 2
    
    # Acceleration - minimum 4 gün gerekli (2+2)
    mid = len(p) // 2
    if mid < 2:
        accel = 0  # Yetersiz veri için 0
    else:
        try:
            slope1, _, _, _, _ = stats.linregress(np.arange(mid), np.log(p.iloc[:mid].values + 0.0001))
            slope2, _, _, _, _ = stats.linregress(np.arange(len(p)-mid), np.log(p.iloc[mid:].values + 0.0001))
            accel = (slope2 - slope1) * 252 * 100
        except Exception:
            accel = 0
    
    # Risk metrics
    rets = p.pct_change().dropna()
    if len(rets) < 2:  # En az 2 return olsun
        return None
    
    ann_ret = rets.mean() * 252
    ann_vol = rets.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    
    neg_rets = rets[rets < 0]
    down_vol = neg_rets.std() * np.sqrt(252) if len(neg_rets) > 0 else ann_vol
    sortino = ann_ret / down_vol if down_vol > 0 else 0
    sortino = max(-10, min(10, sortino))  # -10 ile +10 arası sınırla
    
    # Max drawdown
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    # Calmar: minimum %0.5 drawdown varsay, max 10 ile sınırla
    min_dd = min(dd, -0.005)  # En az %0.5 drawdown
    stability = ann_ret / abs(min_dd)
    stability = max(-10, min(10, stability))  # -10 ile +10 arası sınırla
    
    return {
        'RETURN': round(ret, 2),
        'TREND': round(trend, 2),
        'ACCELERATION': round(accel, 2),
        'QUALITY': round(quality, 4),
        'SHARPE': round(sharpe, 2),
        'SORTINO': round(sortino, 2),
        'STABILITY': round(stability, 2)
    }

def calc_regime(ratios, etfs=None):
    """Risk ve Cycle skorları hesapla - Akıllı Rejim Algoritması"""
    risk_score = 0
    cycle_score = 0
    signals = {}
    
    # === SECTOR BREADTH (Yeni) ===
    sector_etfs = ['XLF', 'XLK', 'XLY', 'XLP', 'XLU', 'XLI', 'XLE', 'XLB', 'XLV', 'XLRE', 'XLC']
    breadth_positive = 0
    breadth_total = 0
    
    if etfs:
        for etf in etfs:
            if etf.get('Symbol') in sector_etfs:
                breadth_total += 1
                w1_ret = etf.get('1W', {}).get('RETURN', 0)
                if w1_ret and w1_ret > 0:
                    breadth_positive += 1
    
    breadth_ratio = breadth_positive / breadth_total if breadth_total > 0 else 0.5
    signals['BREADTH'] = {
        'value': f'{breadth_positive}/{breadth_total} POSITIVE',
        'score': breadth_positive - (breadth_total - breadth_positive),  # net positive count
        'positive': breadth_positive,
        'total': breadth_total
    }
    
    # === VXX Level + Direction ===
    vxx_level = ratios.get('VXX_LEVEL', {}).get('1M', 0)
    vxx_1w_chg = ratios.get('VXX_LEVEL', {}).get('1W_chg', 0)
    
    if vxx_level > 25:
        if vxx_1w_chg > 0:  # Rising panic = worse
            signals['VXX'] = {'value': 'PANIC ↑', 'score': -2}
            risk_score -= 2
        else:  # Falling panic = easing
            signals['VXX'] = {'value': 'PANIC ↓', 'score': -1}
            risk_score -= 1
    elif vxx_level > 20:
        if vxx_1w_chg > 0:
            signals['VXX'] = {'value': 'ELEVATED ↑', 'score': -1}
            risk_score -= 1
        else:
            signals['VXX'] = {'value': 'ELEVATED ↓', 'score': 0}
    elif vxx_level < 15:
        signals['VXX'] = {'value': 'COMPLACENT', 'score': 1}
        risk_score += 1
    else:
        signals['VXX'] = {'value': 'NEUTRAL', 'score': 0}
    
    # === SPY/TLT ===
    spy_tlt_chg = ratios.get('SPY_TLT', {}).get('1M_chg', 0)
    if spy_tlt_chg > 3:
        signals['SPY_TLT'] = {'value': 'RISK-ON', 'score': 1}
        risk_score += 1
    elif spy_tlt_chg < -3:
        signals['SPY_TLT'] = {'value': 'RISK-OFF', 'score': -1}
        risk_score -= 1
    else:
        signals['SPY_TLT'] = {'value': 'NEUTRAL', 'score': 0}
    
    # === HYG/LQD - Level + Direction (Düzeltildi) ===
    hyg_lqd_level = ratios.get('HYG_LQD', {}).get('1M', 0)
    hyg_lqd_1w_chg = ratios.get('HYG_LQD', {}).get('1W_chg', 0)
    
    if hyg_lqd_level < 0.85:
        if hyg_lqd_1w_chg < 0:  # Stress zone AND worsening
            signals['HYG_LQD'] = {'value': 'CREDIT STRESS ↓', 'score': -2}
            risk_score -= 2
        else:  # Stress zone BUT improving
            signals['HYG_LQD'] = {'value': 'CREDIT STRESS ↑', 'score': -1}
            risk_score -= 1
    elif hyg_lqd_level > 0.90:
        signals['HYG_LQD'] = {'value': 'CREDIT OK', 'score': 1}
        risk_score += 1
    else:
        if hyg_lqd_1w_chg > 0:
            signals['HYG_LQD'] = {'value': 'NEUTRAL ↑', 'score': 0}
        elif hyg_lqd_1w_chg < 0:
            signals['HYG_LQD'] = {'value': 'NEUTRAL ↓', 'score': 0}
        else:
            signals['HYG_LQD'] = {'value': 'NEUTRAL', 'score': 0}
    
    # === XLY/XLP (Cycle) ===
    xly_xlp_chg = ratios.get('XLY_XLP', {}).get('1M_chg', 0)
    if xly_xlp_chg > 2:
        signals['XLY_XLP'] = {'value': 'EXPANSION', 'score': 1}
        cycle_score += 1
    elif xly_xlp_chg < -2:
        signals['XLY_XLP'] = {'value': 'CONTRACTION', 'score': -1}
        cycle_score -= 1
    else:
        signals['XLY_XLP'] = {'value': 'NEUTRAL', 'score': 0}
    
    # === CPER/GLD (Cycle) ===
    cper_gld_chg = ratios.get('CPER_GLD', {}).get('1M_chg', 0)
    if cper_gld_chg > 3:
        signals['CPER_GLD'] = {'value': 'REFLATION', 'score': 1}
        cycle_score += 1
    elif cper_gld_chg < -3:
        signals['CPER_GLD'] = {'value': 'DEFLATION', 'score': -1}
        cycle_score -= 1
    else:
        signals['CPER_GLD'] = {'value': 'NEUTRAL', 'score': 0}
    
    # === SMART REGIME ALGORITHM ===
    total = risk_score + cycle_score
    
    # Conflict Check: Risk negatif ama Cycle pozitif = Mixed/Rotation
    has_risk_stress = risk_score <= -2
    has_cycle_expansion = cycle_score >= 1
    has_good_breadth = breadth_positive >= 7
    has_weak_breadth = breadth_positive <= 4
    
    # Determine regime with conflict awareness
    if has_risk_stress and has_cycle_expansion:
        # Conflict: Risk signals bad but cycle good
        overall = 'ROTATION'
        regime_note = 'Risk stress with expansion signals - sector rotation likely'
    elif has_risk_stress and has_good_breadth:
        # Conflict: Risk signals bad but breadth healthy
        overall = 'CAUTION'
        regime_note = 'Risk indicators negative but breadth healthy - selective caution'
    elif total >= 3 and has_good_breadth:
        overall = 'RISK-ON'
        regime_note = 'Broad risk appetite confirmed'
    elif total >= 2:
        overall = 'RISK-ON'
        regime_note = 'Risk appetite positive'
    elif total <= -3 and has_weak_breadth:
        overall = 'RISK-OFF'
        regime_note = 'Confirmed defensive mode - weak breadth'
    elif total <= -2:
        if has_weak_breadth:
            overall = 'RISK-OFF'
            regime_note = 'Defensive mode'
        else:
            overall = 'CAUTION'
            regime_note = 'Risk signals negative but breadth mixed'
    else:
        overall = 'NEUTRAL'
        regime_note = 'Mixed signals - no clear direction'
    
    return {
        'overall': overall,
        'riskScore': risk_score,
        'cycleScore': cycle_score,
        'totalScore': total,
        'signals': signals,
        'breadth': {'positive': breadth_positive, 'total': breadth_total},
        'note': regime_note
    }

def normalize_metric(value, min_val, max_val):
    """Metriği 0-100 arasına normalize et"""
    if value is None:
        return 50  # Default orta değer
    if max_val == min_val:
        return 50
    normalized = (value - min_val) / (max_val - min_val) * 100
    return max(0, min(100, normalized))

def calc_overbought_penalty(prices, lookback=14):
    """
    14 günlük Bollinger Band bazlı overbought cezası hesapla
    
    Fiyat > 2σ → -5 puan (Overbought)
    Fiyat > 3σ → -10 puan (Aşırı Overbought)
    """
    if prices is None or len(prices) < lookback:
        return 0
    
    recent = prices.tail(lookback)
    if len(recent) < lookback:
        return 0
    
    current_price = recent.iloc[-1]
    mean = recent.mean()
    std = recent.std()
    
    if std == 0 or std is None:
        return 0
    
    # Z-score hesapla
    z_score = (current_price - mean) / std
    
    # Ceza uygula
    if z_score > 3:
        return 10  # Aşırı overbought
    elif z_score > 2:
        return 5   # Overbought
    else:
        return 0

def calc_max_drawdown_penalty(prices, period_days):
    """
    Belirli periyot için max drawdown cezası hesapla
    
    1M (22 gün) dd > %10 → -10 puan
    3M (66 gün) dd > %15 → -10 puan
    6M (126 gün) dd > %20 → -10 puan
    """
    if prices is None or len(prices) < period_days:
        return 0
    
    recent = prices.tail(period_days).dropna()
    if len(recent) < 5:
        return 0
    
    # Max drawdown hesapla
    cum_max = recent.cummax()
    drawdown = (recent - cum_max) / cum_max
    max_dd = drawdown.min()  # Negatif değer
    
    return abs(max_dd) * 100  # Yüzde olarak döndür

def calc_quant_score(item, sector_1m_return=None, sector_2w_return=None, is_stock=False, overbought_penalty=0, spy_6m_return=None, dd_1m=0, dd_3m=0, dd_6m=0):
    """
    Quant Score hesapla
    
    Period Weights: 6M=20%, 3M=20%, 1M=20%, 2W=20%, 1W=20% (eşit)
    Metric Weights: Return=35%, Acceleration=25%, Sortino=20%, Calmar=10%, Trend=10%
    Penalties:
      - Her negatif return periyodu için -10 puan
      - Overbought: 2σ üstü -5, 3σ üstü -10 puan (14 gün)
      - Düşük return: 1M < %2 → -10, 3M < %5 → -10
      - SPY altı: 6M return < SPY 6M return → -10 puan
      - Max Drawdown: 1M > %10 → -10, 3M > %15 → -10, 6M > %20 → -10
    Filters:
      - 1M Return < %1 → Listeye girmesin (None döndür)
    Stock Bonus: Sektör 1M ve 2W return pozitifse +5 puan
    """
    
    # === MINIMUM RETURN FİLTRESİ ===
    ret_1m = item.get('1M', {}).get('RETURN', 0) or 0
    if ret_1m < 1:  # 1M return < %1 → diskalifiye
        return None
    
    PERIODS = ['1W', '2W', '1M', '3M', '6M']
    PERIOD_WEIGHT = 0.20  # Her biri %20
    
    METRIC_WEIGHTS = {
        'RETURN': 0.40,
        'SORTINO': 0.20,
        'STABILITY': 0.20,      # Calmar
        'TREND': 0.10,
        'ACCELERATION': 0.10
    }
    
    # Normalize bounds (tipik değer aralıkları)
    BOUNDS = {
        'RETURN': (-30, 30),
        'ACCELERATION': (-50, 50),
        'SORTINO': (-3, 3),
        'STABILITY': (-3, 3),
        'TREND': (-100, 100)
    }
    
    period_scores = {}
    negative_count = 0  # Negatif return sayacı
    
    for period in PERIODS:
        if period not in item:
            continue
            
        metrics = item[period]
        metric_score = 0
        
        # Return negatif mi kontrol et
        period_return = metrics.get('RETURN', 0)
        if period_return is not None and period_return < 0:
            negative_count += 1
        
        for metric, metric_weight in METRIC_WEIGHTS.items():
            value = metrics.get(metric)
            min_val, max_val = BOUNDS[metric]
            # Değeri sınırlar içine al
            if value is not None:
                value = max(min_val, min(max_val, value))
            normalized = normalize_metric(value, min_val, max_val)
            metric_score += normalized * metric_weight
        
        period_scores[period] = metric_score
    
    # Ağırlıklı ortalama
    if not period_scores:
        return None
    
    total_weight = 0
    weighted_sum = 0
    
    for period, score in period_scores.items():
        weighted_sum += score * PERIOD_WEIGHT
        total_weight += PERIOD_WEIGHT
    
    base_score = weighted_sum / total_weight if total_weight > 0 else 0
    
    # Negatif cezası: Her negatif periyot için -10 puan
    penalty = negative_count * 10
    final_score = base_score - penalty
    
    # Overbought cezası
    final_score -= overbought_penalty
    
    # === DÜŞÜK RETURN CEZASI ===
    ret_3m = item.get('3M', {}).get('RETURN', 0) or 0
    ret_6m = item.get('6M', {}).get('RETURN', 0) or 0
    if ret_1m < 2:  # 1M return < %2 → -10 puan
        final_score -= 10
    if ret_3m < 5:  # 3M return < %5 → -10 puan
        final_score -= 10
    
    # === SPY BENCHMARK FİLTRESİ ===
    if spy_6m_return is not None and ret_6m < spy_6m_return:
        return None  # SPY'ın altındaysa direkt diskalifiye
    
    # === MAX DRAWDOWN CEZASI ===
    if dd_1m > 5:  # 1M drawdown > %5 → -10 puan
        final_score -= 10
    if dd_3m > 10:  # 3M drawdown > %10 → -10 puan
        final_score -= 10
    if dd_6m > 15:  # 6M drawdown > %15 → -10 puan
        final_score -= 10
    
    # === R² (QUALITY) CEZASI - Choppy hareket filtresi ===
    r2_1m = item.get('1M', {}).get('QUALITY', 1) or 1
    r2_3m = item.get('3M', {}).get('QUALITY', 1) or 1
    r2_6m = item.get('6M', {}).get('QUALITY', 1) or 1
    if r2_1m < 0.2:  # 1M R² < 0.2 → -20 puan (çok choppy)
        final_score -= 20
    if r2_3m < 0.3:  # 3M R² < 0.3 → -20 puan (trend güvenilmez)
        final_score -= 20
    if r2_6m < 0.4:  # 6M R² < 0.4 → -20 puan (uzun vadeli trend zayıf)
        final_score -= 20
    
    # Stock bonus: Sektör 1M ve 2W return pozitifse +5 puan
    if is_stock and sector_1m_return is not None and sector_2w_return is not None:
        if sector_1m_return > 0 and sector_2w_return > 0:
            final_score += 5
    
    # 0-100 arası sınırla
    final_score = max(0, min(100, final_score))
    
    return round(final_score, 1)

def calc_sector_returns(stocks):
    """Her sektörün 1M ve 2W ortalama return'ünü hesapla"""
    sector_returns = {}
    
    for stock in stocks:
        category = stock.get('Category', 'Other')
        
        if category not in sector_returns:
            sector_returns[category] = {'1M': [], '2W': []}
        
        # 1M return
        if '1M' in stock and stock['1M'].get('RETURN') is not None:
            sector_returns[category]['1M'].append(stock['1M']['RETURN'])
        
        # 2W return
        if '2W' in stock and stock['2W'].get('RETURN') is not None:
            sector_returns[category]['2W'].append(stock['2W']['RETURN'])
    
    # Ortalamaları hesapla
    sector_avg = {}
    for category, data in sector_returns.items():
        avg_1m = sum(data['1M']) / len(data['1M']) if data['1M'] else 0
        avg_2w = sum(data['2W']) / len(data['2W']) if data['2W'] else 0
        sector_avg[category] = {'1M': avg_1m, '2W': avg_2w}
    
    return sector_avg

def generate_data():
    """Ana veri üretim fonksiyonu"""
    
    # Tüm sembolleri birleştir
    etf_symbols = list(ETF_UNIVERSE.keys())
    stock_symbols = list(STOCK_UNIVERSE.keys())
    all_symbols = etf_symbols + stock_symbols
    
    print(f"📡 Total symbols: {len(etf_symbols)} ETFs + {len(stock_symbols)} Stocks = {len(all_symbols)}")
    
    # Fiyatları çek
    prices = fetch_prices(all_symbols)
    
    # ETF Metrikleri
    print("📊 Calculating ETF metrics...")
    etfs = []
    for symbol, (cat, subcat, name) in ETF_UNIVERSE.items():
        if symbol not in prices.columns:
            continue
        
        etf = {
            'Symbol': symbol,
            'Name': name,
            'Category': cat,
            'SubCategory': subcat
        }
        
        for period, days in PERIODS.items():
            metrics = calc_metrics(prices[symbol], days)
            if metrics:
                etf[period] = metrics
        
        etfs.append(etf)
    
    print(f"✅ Calculated metrics for {len(etfs)} ETFs")
    
    # Stock Metrikleri
    print("📊 Calculating Stock metrics...")
    stocks = []
    for symbol, (cat, subcat, name) in STOCK_UNIVERSE.items():
        if symbol not in prices.columns:
            continue
        
        stock = {
            'Symbol': symbol,
            'Name': name,
            'Category': cat,
            'SubCategory': subcat
        }
        
        for period, days in PERIODS.items():
            metrics = calc_metrics(prices[symbol], days)
            if metrics:
                stock[period] = metrics
        
        stocks.append(stock)
    
    print(f"✅ Calculated metrics for {len(stocks)} Stocks")
    
    # Ratio Hesapla
    print("📈 Calculating market ratios...")
    ratios = []
    ratio_dict = {}
    
    for ratio_id, config in MARKET_RATIOS.items():
        num = config['num']
        denom = config['denom']
        
        if num not in prices.columns:
            continue
        if denom and denom not in prices.columns:
            continue
        
        ratio_data = {
            'id': ratio_id,
            'name': config['name'],
            'category': config['cat'],
            'values': {},
            'changes': {}
        }
        
        for period, days in PERIODS.items():
            if denom:
                ratio_prices = prices[num] / prices[denom]
            else:
                ratio_prices = prices[num]
            
            if len(ratio_prices) >= days:
                current = ratio_prices.iloc[-1]
                past = ratio_prices.iloc[-days]
                change = ((current / past) - 1) * 100
                
                ratio_data['values'][period] = round(float(current), 4)
                ratio_data['changes'][period] = round(float(change), 2)
        
        ratios.append(ratio_data)
        
        # Regime için dict
        if ratio_data['values']:
            ratio_dict[ratio_id] = {
                '1M': ratio_data['values'].get('1M', 0),
                '1M_chg': ratio_data['changes'].get('1M', 0)
            }
    
    print(f"✅ Calculated {len(ratios)} ratios")
    
    # Regime hesapla (breadth için etfs gerekli)
    regime = calc_regime(ratio_dict, etfs)
    print(f"✅ Regime: {regime['overall']} (Risk: {regime['riskScore']}, Cycle: {regime['cycleScore']}, Breadth: {regime['breadth']['positive']}/{regime['breadth']['total']})")
    print(f"   Note: {regime.get('note', '')}")
    
    # === QUANT RANKINGS ===
    print("🏆 Calculating Quant Rankings...")
    
    # SPY 6M return'ü al (benchmark)
    spy_6m_return = None
    spy_etf = next((e for e in etfs if e['Symbol'] == 'SPY'), None)
    if spy_etf and '6M' in spy_etf:
        spy_6m_return = spy_etf['6M'].get('RETURN', 0)
        print(f"📊 SPY 6M Return (benchmark): {spy_6m_return:.2f}%")
    
    # ETF Quant Scores (overbought penalty + SPY benchmark + drawdown ile)
    for etf in etfs:
        symbol = etf['Symbol']
        ob_penalty = 0
        dd_1m, dd_3m, dd_6m = 0, 0, 0
        if symbol in prices.columns:
            ob_penalty = calc_overbought_penalty(prices[symbol])
            dd_1m = calc_max_drawdown_penalty(prices[symbol], 22)   # 1M
            dd_3m = calc_max_drawdown_penalty(prices[symbol], 66)   # 3M
            dd_6m = calc_max_drawdown_penalty(prices[symbol], 126)  # 6M
        etf['QuantScore'] = calc_quant_score(
            etf, 
            is_stock=False, 
            overbought_penalty=ob_penalty, 
            spy_6m_return=spy_6m_return,
            dd_1m=dd_1m,
            dd_3m=dd_3m,
            dd_6m=dd_6m
        )
    
    # Stock Quant Scores (sektör bonusu, overbought penalty + SPY benchmark + drawdown ile)
    sector_avg = calc_sector_returns(stocks)
    for stock in stocks:
        symbol = stock['Symbol']
        category = stock.get('Category', 'Other')
        sect_data = sector_avg.get(category, {'1M': 0, '2W': 0})
        ob_penalty = 0
        dd_1m, dd_3m, dd_6m = 0, 0, 0
        if symbol in prices.columns:
            ob_penalty = calc_overbought_penalty(prices[symbol])
            dd_1m = calc_max_drawdown_penalty(prices[symbol], 22)   # 1M
            dd_3m = calc_max_drawdown_penalty(prices[symbol], 66)   # 3M
            dd_6m = calc_max_drawdown_penalty(prices[symbol], 126)  # 6M
        stock['QuantScore'] = calc_quant_score(
            stock, 
            sector_1m_return=sect_data['1M'],
            sector_2w_return=sect_data['2W'],
            is_stock=True,
            overbought_penalty=ob_penalty,
            spy_6m_return=spy_6m_return,
            dd_1m=dd_1m,
            dd_3m=dd_3m,
            dd_6m=dd_6m
        )
    
    # Top 10 ETFs ve Stocks
    etfs_with_score = [e for e in etfs if e.get('QuantScore') is not None]
    stocks_with_score = [s for s in stocks if s.get('QuantScore') is not None]
    
    top10_etfs = sorted(etfs_with_score, key=lambda x: x['QuantScore'], reverse=True)[:10]
    top10_stocks = sorted(stocks_with_score, key=lambda x: x['QuantScore'], reverse=True)[:10]
    
    quant_rankings = {
        'top10_etfs': [{'Symbol': e['Symbol'], 'Name': e['Name'], 'Category': e['Category'], 'QuantScore': e['QuantScore']} for e in top10_etfs],
        'top10_stocks': [{'Symbol': s['Symbol'], 'Name': s['Name'], 'Category': s['Category'], 'QuantScore': s['QuantScore']} for s in top10_stocks]
    }
    
    print(f"✅ Top 10 ETFs: {[e['Symbol'] for e in top10_etfs]}")
    print(f"✅ Top 10 Stocks: {[s['Symbol'] for s in top10_stocks]}")
    
    return {
        'generated_at': datetime.now().isoformat(),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'etf_count': len(etfs),
        'stock_count': len(stocks),
        'ratio_count': len(ratios),
        'regime': regime,
        'ratios': ratios,
        'etfs': etfs,
        'stocks': stocks,
        'quant_rankings': quant_rankings
    }

def main():
    print("=" * 60)
    print("📊 Market Data Generator v4.0")
    print("=" * 60)
    
    try:
        data = generate_data()
        
        # NaN değerlerini null'a çevir (JSON'da NaN geçersiz)
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
                return None
            else:
                return obj
        
        data = clean_nan(data)
        
        # JSON kaydet
        with open('etf_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Data saved to: etf_data.json")
        print(f"   {data['etf_count']} ETFs, {data['stock_count']} Stocks, {data['ratio_count']} Ratios")
        print(f"   Regime: {data['regime']['overall']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
