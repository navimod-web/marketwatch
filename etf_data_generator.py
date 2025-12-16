"""
ETF Data Generator v3.0
=======================
Yahoo Finance'den veri çeker ve JSON dosyası üretir.
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
    min_required = max(3, period_days // 2)  # En az period'un yarısı veya 3 gün
    
    if len(prices) < min_required:
        return None
    
    # Mevcut veriyi kullan (period_days veya daha az)
    actual_days = min(period_days, len(prices))
    p = prices.tail(actual_days).dropna()
    
    if len(p) < 3:  # En az 3 gün veri olsun
        return None
    
    # Return
    ret = (p.iloc[-1] / p.iloc[0] - 1) * 100
    
    # Trend (annualized)
    x = np.arange(len(p))
    slope, _, r, _, _ = stats.linregress(x, np.log(p.values + 0.0001))
    trend = (np.exp(slope * 252) - 1) * 100
    quality = r ** 2
    
    # Acceleration
    mid = len(p) // 2
    slope1, _, _, _, _ = stats.linregress(np.arange(mid), np.log(p.iloc[:mid].values + 0.0001))
    slope2, _, _, _, _ = stats.linregress(np.arange(len(p)-mid), np.log(p.iloc[mid:].values + 0.0001))
    accel = (slope2 - slope1) * 252 * 100
    
    # Risk metrics
    rets = p.pct_change().dropna()
    if len(rets) < 5:
        return None
    
    ann_ret = rets.mean() * 252
    ann_vol = rets.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    
    neg_rets = rets[rets < 0]
    down_vol = neg_rets.std() * np.sqrt(252) if len(neg_rets) > 0 else ann_vol
    sortino = ann_ret / down_vol if down_vol > 0 else 0
    
    # Max drawdown
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    stability = ann_ret / abs(dd) if dd < 0 else ann_ret * 10
    
    return {
        'RETURN': round(ret, 2),
        'TREND': round(trend, 2),
        'ACCELERATION': round(accel, 2),
        'QUALITY': round(quality, 4),
        'SHARPE': round(sharpe, 2),
        'SORTINO': round(sortino, 2),
        'STABILITY': round(stability, 2)
    }

def calc_regime(ratios):
    """Risk ve Cycle skorları hesapla"""
    risk_score = 0
    cycle_score = 0
    signals = {}
    
    # VXX Level
    vxx = ratios.get('VXX_LEVEL', {}).get('1M', 0)
    if vxx > 25: 
        signals['VXX'] = {'value': 'PANIC', 'score': -2}
        risk_score -= 2
    elif vxx > 20: 
        signals['VXX'] = {'value': 'ELEVATED', 'score': -1}
        risk_score -= 1
    elif vxx < 15: 
        signals['VXX'] = {'value': 'COMPLACENT', 'score': 1}
        risk_score += 1
    else:
        signals['VXX'] = {'value': 'NEUTRAL', 'score': 0}
    
    # SPY/TLT
    spy_tlt_chg = ratios.get('SPY_TLT', {}).get('1M_chg', 0)
    if spy_tlt_chg > 3:
        signals['SPY_TLT'] = {'value': 'RISK-ON', 'score': 1}
        risk_score += 1
    elif spy_tlt_chg < -3:
        signals['SPY_TLT'] = {'value': 'RISK-OFF', 'score': -1}
        risk_score -= 1
    else:
        signals['SPY_TLT'] = {'value': 'NEUTRAL', 'score': 0}
    
    # HYG/LQD
    hyg_lqd = ratios.get('HYG_LQD', {}).get('1M', 0)
    if hyg_lqd < 0.85:
        signals['HYG_LQD'] = {'value': 'CREDIT STRESS', 'score': -2}
        risk_score -= 2
    elif hyg_lqd > 0.90:
        signals['HYG_LQD'] = {'value': 'CREDIT OK', 'score': 1}
        risk_score += 1
    else:
        signals['HYG_LQD'] = {'value': 'NEUTRAL', 'score': 0}
    
    # XLY/XLP
    xly_xlp_chg = ratios.get('XLY_XLP', {}).get('1M_chg', 0)
    if xly_xlp_chg > 2:
        signals['XLY_XLP'] = {'value': 'EXPANSION', 'score': 1}
        cycle_score += 1
    elif xly_xlp_chg < -2:
        signals['XLY_XLP'] = {'value': 'CONTRACTION', 'score': -1}
        cycle_score -= 1
    else:
        signals['XLY_XLP'] = {'value': 'NEUTRAL', 'score': 0}
    
    # CPER/GLD
    cper_gld_chg = ratios.get('CPER_GLD', {}).get('1M_chg', 0)
    if cper_gld_chg > 3:
        signals['CPER_GLD'] = {'value': 'REFLATION', 'score': 1}
        cycle_score += 1
    elif cper_gld_chg < -3:
        signals['CPER_GLD'] = {'value': 'DEFLATION', 'score': -1}
        cycle_score -= 1
    else:
        signals['CPER_GLD'] = {'value': 'NEUTRAL', 'score': 0}
    
    # Overall
    total = risk_score + cycle_score
    if total >= 2:
        overall = 'RISK-ON'
    elif total <= -2:
        overall = 'RISK-OFF'
    else:
        overall = 'NEUTRAL'
    
    return {
        'overall': overall,
        'riskScore': risk_score,
        'cycleScore': cycle_score,
        'totalScore': total,
        'signals': signals
    }

def generate_data():
    """Ana veri üretim fonksiyonu"""
    
    # Fiyatları çek
    symbols = list(ETF_UNIVERSE.keys())
    prices = fetch_prices(symbols)
    
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
    
    # Regime hesapla
    regime = calc_regime(ratio_dict)
    print(f"✅ Regime: {regime['overall']} (Risk: {regime['riskScore']}, Cycle: {regime['cycleScore']})")
    
    return {
        'generated_at': datetime.now().isoformat(),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'etf_count': len(etfs),
        'ratio_count': len(ratios),
        'regime': regime,
        'ratios': ratios,
        'etfs': etfs
    }

def main():
    print("=" * 60)
    print("📊 ETF Data Generator v3.0")
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
        print(f"   {data['etf_count']} ETFs, {data['ratio_count']} Ratios")
        print(f"   Regime: {data['regime']['overall']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
