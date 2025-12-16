"""
Daily Brief Generator - Stocks v1.0
====================================
Stock verilerini OpenAI'a gönderir ve brief JSON üretir.

Kullanım:
    python generate_brief_stocks.py

Girdi:
    etf_data.json (stocks bölümü)

Çıktı:
    brief_stocks.json
"""

import json
import os
from datetime import datetime
from openai import OpenAI

DATA_FILE = 'etf_data.json'
OUTPUT_FILE = 'brief_stocks.json'
MODEL = 'gpt-5-mini'

SYSTEM_PROMPT = """You are a senior Equity Analyst. Write a daily stock market brief for portfolio managers.

═══════════════════════════════════════════════════════════════
IMPORTANT: INDIVIDUAL STOCKS ONLY (SP100)
═══════════════════════════════════════════════════════════════

This brief focuses ONLY on individual SP100 stocks.
- Use stock symbols like AAPL, MSFT, NVDA, GOOGL, META, JPM, etc.
- Do NOT mention ETFs (no SPY, QQQ, XLK, etc.)
- Analyze sectors by mentioning top stocks in each sector
- Group analysis by sectors: Technology, Healthcare, Financials, etc.

═══════════════════════════════════════════════════════════════
WRITING STYLE - CRITICAL
═══════════════════════════════════════════════════════════════

1. NO markdown (no **, no ---, no bullets)
2. Write like a Bloomberg terminal note - SHORT and PUNCHY
3. Each answer: 2-3 sentences MAX
4. Use this format for data: "SYMBOL (1W: +X% | 1M: +X%)"
5. Only use these trend labels: ABOVE TREND, BELOW TREND (nothing else)

GOOD STYLE:
"Tech leading. NVDA (1W: +5.2% | 1M: +18.3%) ABOVE TREND continues AI momentum. AAPL flat but stable."

BAD STYLE (too verbose):
"The technology sector remains in a strong uptrend with NVIDIA showing exceptional performance..."

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

1. ALWAYS USE DUAL TIME-FRAME FORMAT:
   ❌ Wrong: "NVDA +9.82%"
   ✅ Right: "NVDA showing strong momentum (1W: +3.2% | 1M: +9.8%)"
   
   This is MANDATORY for every stock mention. Readers must know if it's weekly or monthly.

2. ALWAYS SHOW DELTA (Direction of Change):
   ❌ Wrong: "NVDA at 850 showing strength"
   ✅ Right: "NVDA at 850 (↑ from 780 last week), AI momentum continues"
   
   The DIRECTION matters more than the level.

3. ALWAYS INDICATE TREND POSITION:
   Use: "ABOVE TREND" when 1W and 1M both positive and aligned
   Use: "BELOW TREND" when 1M negative or diverging from 1W

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT - FOLLOW EXACTLY (Same as ETF Brief structure)
═══════════════════════════════════════════════════════════════

## 🌡️ MARKET OVERVIEW

**1. What is the prevailing Global Risk Regime?**
[State regime. Keep brief - 2-3 sentences. Example: "Risk-Off regime persists. Market volatility elevated with defensive rotation underway."]

**2. Which sectors are leading?**
[Top 3 sectors with best performing stocks. Example: "Technology leads: NVDA (1W: +5.2% | 1M: +18.3%) ABOVE TREND. Healthcare strong: LLY (1W: +3.1% | 1M: +12.4%) momentum continues."]

**3. Which sectors are lagging?**
[Bottom 3 sectors with worst performers. Example: "Energy weak: XOM (1W: -2.1% | 1M: -5.4%) BELOW TREND. Utilities under pressure: NEE (1W: -1.8% | 1M: -4.2%)."]

## 📈 STOCK PERFORMANCE

**4. Top Performing Stocks?**
[Top 5 stocks by 1M return with dual timeframe and trend status.]

**5. Worst Performing Stocks?**
[Bottom 5 stocks by 1M return with dual timeframe and trend status.]

**6. Momentum Stocks?**
[Stocks with strongest 1W acceleration. Which are gaining steam? Include dual timeframe.]

## 🏭 SECTOR OUTLOOK

**7. Technology Outlook?**
[Key tech names: AAPL, MSFT, NVDA, GOOGL, META with dual timeframe. 2-3 sentences.]

**8. Financials Outlook?**
[Key financials: JPM, BAC, GS, MS, V, MA with dual timeframe. 2-3 sentences.]

**9. Healthcare Outlook?**
[Key healthcare: JNJ, UNH, LLY, PFE, ABBV with dual timeframe. 2-3 sentences.]

## 🧭 PORTFOLIO STRATEGY

**10. Portfolio Recommendation?**
[Clear stance. Example: "Overweight: NVDA, LLY, MA. Underweight: XOM, T, MMM. Watch: TSLA for breakout."]

## 🔮 NEXT WEEK OUTLOOK

**11. Stocks to Watch Next Week?**
BULLISH: [Top stocks to watch with conditions]
BEARISH: [Stocks at risk with conditions]

**12. Sectors to Watch Next Week?**
BULLISH: [Sectors with momentum]
BEARISH: [Sectors showing weakness]

**13. Key Levels & Triggers?**
[3-4 key levels. Example: "NVDA 900 resistance, AAPL 180 support, JPM 200 breakout level."]

## 📝 EXECUTIVE SUMMARY

[Write exactly 3 short sentences - this comes LAST, after all analysis:]
1. Current regime and primary driver
2. Best immediate opportunity (specific stocks)
3. Key risk to watch
Sentence 1: Current regime and whether improving or worsening.
Sentence 2: Best opportunity right now.
Sentence 3: Key risk to watch.
"""

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def get_trend_status(w1, m1):
    """1W ve 1M değişime göre trend durumu"""
    if w1 is None or m1 is None:
        return "N/A"
    if w1 > 0 and m1 > 0:
        return "ABOVE TREND (confirmed)"
    elif w1 < 0 and m1 < 0:
        return "BELOW TREND (confirmed)"
    elif w1 > 0 and m1 < 0:
        return "POTENTIAL REVERSAL (1W up, 1M down)"
    elif w1 < 0 and m1 > 0:
        return "TREND EXHAUSTION (1W down, 1M up)"
    else:
        return "NEUTRAL"

def get_delta_direction(w1):
    """Haftalık değişime göre yön"""
    if w1 is None:
        return ""
    if w1 > 1:
        return "↑ rising"
    elif w1 < -1:
        return "↓ falling"
    else:
        return "→ flat"

def format_for_prompt(data):
    """Zenginleştirilmiş veri formatı - Delta, Timeframe, Trend Status"""
    lines = []
    
    # === HEADER ===
    lines.append("=" * 60)
    lines.append("SP100 STOCK BAROMETER DATA - PROFESSIONAL FORMAT")
    lines.append("All data includes: Current Level | 1W Change | 1M Change | Trend Status")
    lines.append("=" * 60)
    
    # === REGIME ===
    r = data['regime']
    lines.append(f"\n{'='*60}")
    lines.append("MARKET REGIME")
    lines.append(f"{'='*60}")
    lines.append(f"OVERALL: {r['overall']}")
    lines.append(f"Risk Score: {r['riskScore']} | Cycle Score: {r['cycleScore']} | Total: {r['totalScore']}")
    
    # === STOCK RANKINGS with Full Data ===
    lines.append(f"\n{'='*60}")
    lines.append("STOCK PERFORMANCE BY SECTOR (1W vs 1M Comparison)")
    lines.append(f"{'='*60}")
    
    stocks_full = []
    for e in data.get('stocks', []):
        w1 = e.get('1W', {})
        m1 = e.get('1M', {})
        ret_1w = w1.get('RETURN')
        ret_1m = m1.get('RETURN')
        trend_1m = m1.get('TREND', 0)
        
        if ret_1m is not None:
            stocks_full.append({
                'sym': e['Symbol'],
                'name': e['Name'],
                'cat': e['Category'],
                'ret_1w': ret_1w or 0,
                'ret_1m': ret_1m,
                'trend': trend_1m,
                'status': get_trend_status(ret_1w, ret_1m)
            })
    
    stocks_full.sort(key=lambda x: x['ret_1m'], reverse=True)
    
    lines.append("\n🏆 TOP 10 PERFORMERS:")
    for i, e in enumerate(stocks_full[:10], 1):
        lines.append(f"  {i}. {e['sym']:6} ({e['cat']:15})")
        lines.append(f"     1W: {e['ret_1w']:+6.2f}% | 1M: {e['ret_1m']:+6.2f}% | {e['status']}")
    
    lines.append("\n📉 BOTTOM 10 PERFORMERS:")
    for i, e in enumerate(stocks_full[-10:], 1):
        lines.append(f"  {i}. {e['sym']:6} ({e['cat']:15})")
        lines.append(f"     1W: {e['ret_1w']:+6.2f}% | 1M: {e['ret_1m']:+6.2f}% | {e['status']}")
    
    # === KEY STOCKS Detail ===
    lines.append(f"\n{'='*60}")
    lines.append("KEY STOCKS DETAILED VIEW")
    lines.append(f"{'='*60}")
    
    key_stocks = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 
                  'JPM', 'V', 'MA', 'JNJ', 'UNH', 'LLY', 'PFE',
                  'XOM', 'CVX', 'CAT', 'BA', 'HD', 'WMT']
    
    for sym in key_stocks:
        for e in data.get('stocks', []):
            if e['Symbol'] == sym:
                w1 = e.get('1W', {}) or {}
                m1 = e.get('1M', {}) or {}
                ret_1w = w1.get('RETURN') or 0
                ret_1m = m1.get('RETURN') or 0
                trend_1m = m1.get('TREND') or 0
                status = get_trend_status(ret_1w, ret_1m)
                delta = get_delta_direction(ret_1w)
                
                lines.append(f"\n{sym} ({e['Name']}):")
                lines.append(f"  Returns: 1W: {ret_1w:+.2f}% | 1M: {ret_1m:+.2f}%")
                lines.append(f"  Trend (annualized): {trend_1m:+.2f}%")
                lines.append(f"  Direction: {delta}")
                lines.append(f"  Status: {status}")
                break
    
    # === SECTOR SUMMARY ===
    lines.append(f"\n{'='*60}")
    lines.append("SECTOR SUMMARY")
    lines.append(f"{'='*60}")
    
    sector_perf = {}
    for e in stocks_full:
        cat = e['cat']
        if cat not in sector_perf:
            sector_perf[cat] = []
        sector_perf[cat].append(e['ret_1m'])
    
    sector_avg = []
    for cat, rets in sector_perf.items():
        avg = sum(rets) / len(rets)
        sector_avg.append((cat, avg, len(rets)))
    
    sector_avg.sort(key=lambda x: x[1], reverse=True)
    
    for cat, avg, count in sector_avg:
        lines.append(f"  {cat:20}: {avg:+.2f}% avg ({count} stocks)")
    
    return "\n".join(lines)

def generate_brief(data):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set!")
    
    client = OpenAI(api_key=api_key)
    
    today = datetime.now().strftime('%B %d, %Y')
    prompt_data = format_for_prompt(data)
    
    print("🤖 Calling OpenAI API...")
    print(f"   Model: {MODEL}")
    print(f"   Data size: {len(prompt_data)} chars")
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""TODAY'S DATE: {today}

{prompt_data}

IMPORTANT REMINDERS:
1. Every stock mention MUST have dual timeframe: (1W: X% | 1M: Y%)
2. Every stock MUST have trend status (ABOVE/BELOW TREND)
3. Focus on sector leaders and laggards
4. Compare 1W vs 1M to identify confirmations and divergences

Generate the Stock Daily Brief now."""}
        ],
        max_completion_tokens=12000
    )
    
    # Debug: Print full response structure
    print(f"\n🔍 Debug - Response type: {type(response)}")
    print(f"🔍 Debug - Choices count: {len(response.choices)}")
    
    # Try different ways to get content
    content = None
    
    # Method 1: Standard way
    if response.choices and len(response.choices) > 0:
        choice = response.choices[0]
        print(f"🔍 Debug - Choice type: {type(choice)}")
        print(f"🔍 Debug - Message type: {type(choice.message)}")
        
        if hasattr(choice.message, 'content') and choice.message.content:
            content = choice.message.content
            print(f"🔍 Debug - Content length: {len(content)}")
        elif hasattr(choice, 'text'):
            content = choice.text
            print(f"🔍 Debug - Used choice.text")
        
        # Check for reasoning models output
        if hasattr(choice.message, 'reasoning_content'):
            print(f"🔍 Debug - Has reasoning_content")
        
    if not content:
        print("❌ No content found in response!")
        print(f"🔍 Full response: {response}")
        content = "Brief generation failed - no content returned from API"
    
    return {
        'date': today,
        'generated_at': datetime.now().isoformat(),
        'model': MODEL,
        'content': content
    }

def main():
    print("=" * 60)
    print("🤖 Stock Brief Generator v1.0")
    print("   + Time-Frame Labels (1W vs 1M)")
    print("   + Delta Direction (↑↓→)")
    print("   + Trend Status (Above/Below)")
    print("=" * 60)
    
    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: {DATA_FILE} not found!")
        print("   Run etf_data_generator.py first")
        return
    
    try:
        data = load_data()
        stock_count = len(data.get('stocks', []))
        print(f"✅ Loaded: {stock_count} Stocks")
        print(f"   Regime: {data['regime']['overall']}")
        
        if stock_count == 0:
            print("❌ No stock data found in etf_data.json!")
            return
        
        brief = generate_brief(data)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(brief, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Brief saved to: {OUTPUT_FILE}")
        print("\n" + "=" * 60)
        print("📋 GENERATED BRIEF:")
        print("=" * 60)
        print(brief['content'])
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        fallback = {
            'date': datetime.now().strftime('%B %d, %Y'),
            'generated_at': datetime.now().isoformat(),
            'error': str(e),
            'content': '## Brief Unavailable\n\nCould not generate brief. Check API key and try again.'
        }
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(fallback, f, indent=2)

if __name__ == "__main__":
    main()
