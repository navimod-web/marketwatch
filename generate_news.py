# -*- coding: utf-8 -*-
"""
Company News Generator v3.0
===========================
Full SP100+ universe + Sentiment filtering

Kullanım:
    python generate_news.py

Filtre: Sadece sentiment != 0 olan haberler dahil edilir
"""

import json
import warnings
import os
from datetime import datetime, timezone
import yfinance as yf
import time
from openai import OpenAI

warnings.filterwarnings("ignore")

OUTPUT_FILE = "news_data.json"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# ============================================================
# FULL STOCK UNIVERSE (~125 stocks)
# ============================================================
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
    'MCD': ('Consumer Disc.', 'Restaurants', "McDonald's Corp."),
    'NKE': ('Consumer Disc.', 'Apparel', 'Nike Inc.'),
    'SBUX': ('Consumer Disc.', 'Restaurants', 'Starbucks Corp.'),
    'LOW': ('Consumer Disc.', 'Retail', "Lowe's Cos."),
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

# ============================================================
# SENTIMENT PROMPT (Optimized for Algo Trading)
# ============================================================
SENTIMENT_SYSTEM_PROMPT = """ROLE: You are a senior financial sentiment analyst specialized in algorithmic trading. Your job is to quantify the short-term impact of news headlines on stock prices.

TASK: Analyze the provided headlines and return a sentiment score (-100 to +100) based on potential market reaction.

SCORING SCALE:
+70 to +100 : VERY BULLISH
  - M&A Target (company being bought)
  - Earnings beat + Raised guidance
  - Major regulatory win (e.g., FDA approval)
  - Massive stock buyback announcement

+30 to +69 : BULLISH
  - Analyst upgrade / Price target raise
  - Strong earnings (meeting or beating expectations)
  - New product launch or significant contract win
  - Strategic partnership

-9 to +9 : NEUTRAL
  - Routine corporate updates / No material impact
  - Macro/Sector news with no specific company mention
  - "Trending" news without substance
  - Mixed signals (e.g., Revenue beat but EPS miss)

-30 to -69 : BEARISH
  - Earnings miss / Lowered guidance
  - Analyst downgrade / Price target cut
  - Product delays / Minor legal setbacks
  - M&A Acquirer (often drops short-term due to cost/debt)

-70 to -100 : VERY BEARISH
  - Accounting fraud / SEC investigation
  - Bankruptcy risk / Going concern warning
  - CEO resignation for cause
  - Major lawsuit loss / Product recall

CRITICAL RULES:
1. CONTEXT > KEYWORDS: A headline saying "Record Revenue" is BEARISH (-score) if the text implies a miss on expectations or lowered future guidance. Forward-looking guidance is the primary driver.

2. ANALYST ACTIONS: Standard upgrades/downgrades should typically fall in the ±40 to ±60 range. Do not score them as extreme (+/- 80) unless accompanied by a massive fundamental shift.

3. M&A DYNAMICS: For merger/acquisition news, score the TARGET company (being bought) as Very Bullish (+70 to +100). Score the ACQUIRER cautiously (often Neutral or Slightly Bearish due to cash outlay/dilution), unless the deal is clearly accretive immediately.

4. NOISE FILTERING: If the ticker/company is missing, unclear, or if the news is general macro (e.g., "Fed raises rates"), score as 0.

5. CATALYST REQUIRED: Do not overweight "Shares moving" headlines (e.g., "Stock up 5%") unless the headline explains the *reason*. Focus on the catalyst, not the movement.

OUTPUT FORMAT:
Return ONLY valid JSON, no markdown:
{"scores":[{"id":"ID","symbol":"TICKER","score":INTEGER},...]}
"""


def get_time_ago(pub_date_str):
    if not pub_date_str:
        return "Recently"
    try:
        now = datetime.now(timezone.utc)
        if isinstance(pub_date_str, str):
            pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
        else:
            return "Recently"
        diff = now - pub_dt
        hours = int(diff.total_seconds() / 3600)
        if hours < 1:
            mins = int(diff.total_seconds() / 60)
            return "Just now" if mins < 1 else f"{mins}m ago"
        elif hours < 24:
            return f"{hours}h ago"
        else:
            return f"{hours // 24}d ago"
    except:
        return "Recently"


def extract_news_item(item, symbol):
    try:
        content = item.get("content") or {}
        title = content.get("title", "") or ""
        
        # Provider - nested dict kontrolü
        provider = content.get("provider") or {}
        publisher = provider.get("displayName", "Unknown") if isinstance(provider, dict) else "Unknown"
        
        # Click through URL - nested dict kontrolü
        click_through = content.get("clickThroughUrl") or {}
        link = click_through.get("url", "") if isinstance(click_through, dict) else ""
        
        pub_date = content.get("pubDate", None)

        thumbnail = None
        thumb_data = content.get("thumbnail") or {}
        if thumb_data and isinstance(thumb_data, dict):
            resolutions = thumb_data.get("resolutions") or []
            if resolutions and len(resolutions) > 0:
                if len(resolutions) > 1:
                    thumbnail = resolutions[1].get("url") if isinstance(resolutions[1], dict) else None
                else:
                    thumbnail = resolutions[0].get("url") if isinstance(resolutions[0], dict) else None

        # Stock info from universe
        stock_info = STOCK_UNIVERSE.get(symbol, ("Other", "Other", symbol))
        
        return {
            "symbol": symbol,
            "name": stock_info[2],
            "sector": stock_info[0],
            "industry": stock_info[1],
            "title": title,
            "publisher": publisher,
            "link": link,
            "publish_time": pub_date,
            "time_ago": get_time_ago(pub_date),
            "thumbnail": thumbnail,
            "type": content.get("contentType", "STORY") or "STORY",
            "sentiment": 0
        }
    except Exception as e:
        # Herhangi bir hata durumunda boş döndür
        return None


def fetch_news_for_stock(symbol, retries=2):
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            news_items = ticker.news
            if not news_items:
                return []
            processed = []
            # Her hisseden max 5 haber
            for item in news_items[:5]:
                # None veya geçersiz item kontrolü
                if item is None:
                    continue
                if not isinstance(item, dict):
                    continue
                # content kontrolü - None olabilir
                content = item.get("content")
                if content is None:
                    continue
                news_item = extract_news_item(item, symbol)
                if news_item and news_item.get("title"):
                    processed.append(news_item)
            return processed
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)  # Retry öncesi bekle
                continue
            print(f"⚠️ {symbol} fetch error: {e}")
            return []
    return []


def analyze_sentiment_batch(news_items, client: OpenAI, retries=3):
    """Batch sentiment analysis with retry"""
    if not news_items:
        return news_items

    payload = []
    for idx, n in enumerate(news_items):
        payload.append({
            "id": f"{n.get('symbol','UNK')}_{idx}",
            "symbol": n.get("symbol", "UNK"),
            "headline": n.get("title", "")
        })

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ],
                max_completion_tokens=1500
            )

            content = response.choices[0].message.content

            if not content:
                if attempt < retries - 1:
                    time.sleep(3)
                    continue
                return news_items

            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            obj = json.loads(content)
            scores = obj.get("scores", [])

            score_map = {s.get("id"): s.get("score", 0) for s in scores if s.get("id")}

            for idx, n in enumerate(news_items):
                _id = f"{n.get('symbol','UNK')}_{idx}"
                s = score_map.get(_id, 0)
                try:
                    n["sentiment"] = max(-100, min(100, int(s)))
                except:
                    n["sentiment"] = 0
            
            return news_items

        except json.JSONDecodeError:
            break
        except Exception:
            if attempt < retries - 1:
                time.sleep(3)
                continue

    return news_items


def main():
    print("=" * 60)
    print("📰 Company News Generator v3.0 (Full Universe)")
    print(f"   {len(STOCK_UNIVERSE)} stocks | Model: {MODEL}")
    print(f"   yfinance: {yf.__version__}")
    print("=" * 60)

    api_key = os.getenv("OPENAI_API_KEY")
    client = None
    if api_key:
        client = OpenAI(api_key=api_key)
        print("   ✅ OpenAI API connected")
    else:
        print("   ⚠️ No OPENAI_API_KEY")

    print("=" * 60)

    # Fetch all news
    all_news = []
    symbols = list(STOCK_UNIVERSE.keys())
    
    print(f"\n📡 Fetching news from {len(symbols)} stocks...")
    for i, symbol in enumerate(symbols, 1):
        if i % 20 == 0 or i == len(symbols):
            print(f"   Progress: {i}/{len(symbols)} ({i*100//len(symbols)}%)")
        
        news = fetch_news_for_stock(symbol)
        all_news.extend(news)
        
        # Rate limiting - her istek arasında küçük bekleme
        time.sleep(0.15)
        
        # Her 20 hissede ekstra bekleme
        if i % 20 == 0:
            time.sleep(1.0)

    all_news = [n for n in all_news if n.get("title")]
    print(f"\n📊 Raw news collected: {len(all_news)}")

    # ============================================================
    # FILTER 1: Only last 5 days
    # ============================================================
    from datetime import timedelta
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=5)
    
    recent_news = []
    for n in all_news:
        pub_time = n.get("publish_time")
        if pub_time:
            try:
                pub_dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                if pub_dt >= cutoff_date:
                    recent_news.append(n)
            except:
                recent_news.append(n)  # Keep if can't parse
        else:
            recent_news.append(n)  # Keep if no date
    
    print(f"   📅 Last 5 days filter: {len(all_news)} → {len(recent_news)} news")
    all_news = recent_news

    # Sentiment analysis
    if client and all_news:
        print(f"\n🧠 Analyzing sentiment with {MODEL}...")

        batch_size = 10
        total_batches = (len(all_news) - 1) // batch_size + 1
        
        for i in range(0, len(all_news), batch_size):
            batch = all_news[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"   Batch {batch_num}/{total_batches}...", end=" ")
            
            analyze_sentiment_batch(batch, client)
            print("✅")
            
            if batch_num < total_batches:
                time.sleep(2.5)

    # ============================================================
    # NO FILTER - Keep all news (UI will filter)
    # ============================================================
    # Sort by time (newest first)
    all_news.sort(key=lambda x: x.get("publish_time") or "", reverse=True)

    # Stats
    bullish = len([n for n in all_news if n["sentiment"] > 0])
    bearish = len([n for n in all_news if n["sentiment"] < 0])
    neutral = len([n for n in all_news if n["sentiment"] == 0])
    
    print(f"\n📊 SENTIMENT BREAKDOWN:")
    print(f"   🟢 Bullish: {bullish}")
    print(f"   🔴 Bearish: {bearish}")
    print(f"   ⚪ Neutral: {neutral}")
    
    # Sector breakdown
    sector_stats = {}
    for n in all_news:
        sec = n.get("sector", "Other")
        if sec not in sector_stats:
            sector_stats[sec] = {"count": 0, "bull": 0, "bear": 0, "neutral": 0}
        sector_stats[sec]["count"] += 1
        if n["sentiment"] > 0:
            sector_stats[sec]["bull"] += 1
        elif n["sentiment"] < 0:
            sector_stats[sec]["bear"] += 1
        else:
            sector_stats[sec]["neutral"] += 1

    output = {
        "generated_at": datetime.now().isoformat(),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stock_count": len(STOCK_UNIVERSE),
        "news_count": len(all_news),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "has_sentiment": client is not None,
        "filter": "last 5 days",
        "sector_stats": sector_stats,
        "news": all_news
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✅ Saved {len(all_news)} news to: {OUTPUT_FILE}")
    print(f"   🟢 Bullish: {bullish}  |  🔴 Bearish: {bearish}  |  ⚪ Neutral: {neutral}")
    print("=" * 60)

    # Top movers
    if all_news:
        print("\n📈 TOP BULLISH:")
        top_bull = sorted([n for n in all_news if n["sentiment"] > 0], 
                         key=lambda x: -x["sentiment"])[:5]
        for item in top_bull:
            title = item["title"][:45] + "..." if len(item["title"]) > 45 else item["title"]
            print(f"  🟢 [{item['symbol']:5}] +{item['sentiment']:3d} | {title}")

        print("\n📉 TOP BEARISH:")
        top_bear = sorted([n for n in all_news if n["sentiment"] < 0], 
                         key=lambda x: x["sentiment"])[:5]
        for item in top_bear:
            title = item["title"][:45] + "..." if len(item["title"]) > 45 else item["title"]
            print(f"  🔴 [{item['symbol']:5}] {item['sentiment']:4d} | {title}")


if __name__ == "__main__":
    main()
