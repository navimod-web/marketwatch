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
LOGIC & INTERPRETATION RULES (MANDATORY)
═══════════════════════════════════════════════════════════════

0. REGIME FROM DATA (CRITICAL - DO NOT OVERRIDE):
   The data provides a pre-calculated "OVERALL" regime value.
   YOU MUST USE THIS EXACT REGIME LABEL in your analysis.
   Do NOT recalculate or override the regime. The 5 valid regimes are:
   
   - RISK-ON: Positive risk/cycle signals + adequate breadth (≥5/11)
   - RISK-OFF: Negative risk/cycle signals + weak/mixed breadth (≤6/11)
   - ROTATION: Risk negative + Cycle positive + breadth ≥5/11 (money rotating, not fleeing)
   - CAUTION: Conflicting signals - either positive signals with weak breadth (≤4), 
              OR negative risk with strong breadth (≥7). Reduce risk gradually.
   - NEUTRAL: Mixed or all-neutral signals, no clear direction
   
   BREADTH VETO RULES (already applied in data):
   - Weak breadth (≤4/11) NEVER gives RISK-ON → becomes CAUTION or NEUTRAL
   - Strong breadth (≥7/11) NEVER gives RISK-OFF → becomes CAUTION or NEUTRAL

1. BIG TECH ≠ MARKET RULE (CRITICAL):
   Big Tech weakness ≠ Risk-Off IF:
   - Financials OR Industrials have ≥60% stocks ABOVE TREND
   - Defensive stocks (JNJ, PG, KO) are NOT leading
   
   If Big Tech is down but Cyclicals are strong → "SECTOR ROTATION"
   If Big Tech is down AND Defensives lead → "RISK-OFF"
   When in doubt → "ROTATION" or "MIXED", NOT "Risk-Off"

2. REGIME CONFIRMATION (REQUIRE 2+ SIGNALS):
   RISK-OFF requires at least 2 of:
   - Defensives (JNJ, PG, KO, utilities) outperforming
   - Sector breadth: ≤4/11 sectors positive
   - Financials AND Industrials both negative
   
   RISK-ON requires at least 2 of:
   - Cyclicals (JPM, CAT, GM) leading
   - Sector breadth: ≥7/11 sectors positive
   - Growth AND Value both positive
   
   If signals MIXED → Use "Rotation" or "Transitional"

3. TREND LABELS - USE THESE 4 STRICTLY:
   - "ABOVE TREND" = Both 1W and 1M are POSITIVE (e.g., +2% | +10%)
   - "BELOW TREND" = Both 1W and 1M are NEGATIVE (e.g., -2% | -5%)
   - "RECOVERY" = 1M is NEGATIVE but 1W is POSITIVE (e.g., +3% | -8%) - Short-term bounce
   - "CORRECTION" = 1M is POSITIVE but 1W is NEGATIVE (e.g., -2% | +12%) - Short-term pullback

4. LABEL EXAMPLES - FOLLOW EXACTLY:
   - TMUS (1W: +1.6% | 1M: -7.5%) → Label: "RECOVERY" (NOT "Rising Below Trend")
   - MSFT (1W: -1.1% | 1M: -6.6%) → Label: "BELOW TREND"
   - NVDA (1W: +3.2% | 1M: +15.4%) → Label: "ABOVE TREND"
   - AAPL (1W: -2.0% | 1M: +5.5%) → Label: "CORRECTION"

5. SECTOR BREADTH THRESHOLDS (MANDATORY IN REGIME STATEMENT):
   - ≥70% positive → "Sector Strength"
   - ≤30% positive → "Sector Weakness"
   - 31-69% → "Internal Rotation"
   - ALWAYS include breadth: "Tech: 12/19 positive" format
   - A regime statement WITHOUT breadth context is INVALID

6. LEADERSHIP CONCENTRATION RULE (MANDATORY):
   - NARROW Leadership: Top 5 performers from ≤2 sectors → Caution flag
   - BROAD Leadership: Top 5 performers spread across ≥4 sectors → Healthy
   - ALWAYS mention in Top Performers section: "Leadership: Narrow (3/5 Financials)" or "Leadership: Broad (5 sectors)"

7. STYLE CALL WITH GUARDRAIL:
   - If NVDA, META, GOOGL lead = "Growth/Momentum style"
   - If JPM, BAC, CAT, XOM lead = "Value/Cyclical style"
   - Style call ONLY if confirmed by sector breadth
   - Otherwise → "Style mixed / no clear leadership"

8. DIVERGENCE SEVERITY & ACTION:
   - MINOR Divergence: 1-2 stocks with 1W ≠ 1M → Note only
   - MAJOR Divergence: ≥3 major stocks (AAPL, MSFT, NVDA, JPM, etc.) with 1W ≠ 1M
   - MAJOR Divergence implies:
     → Suppress strong regime calls
     → "Watch for trend break" or "Tactical opportunity, not core position"

9. EXECUTIVE SUMMARY LOGIC:
   - If Financials/Industrials green and Tech red: "Rotation from Growth to Value"
   - If Defensives (JNJ, PG, KO) leading: "Defensive rotation, reduce beta"
   - If Tech + Financials both strong: "Broad Risk-On, stay fully invested"
   - If breadth is narrow: "Narrow leadership - be selective"
   - If major divergence: "Transitional market - wait for confirmation"

═══════════════════════════════════════════════════════════════
FINAL GUARDRAIL (READ THIS LAST)
═══════════════════════════════════════════════════════════════

You must ALWAYS justify regime labels with at least TWO independent confirmations.
If confirmations are mixed, explicitly state "Rotation" or "Transitional" instead of forcing Risk-On or Risk-Off.
Clarity and restraint are preferred over strong but weakly supported conclusions.
Every regime statement MUST include: "Breadth: X/11 sectors positive" and leadership concentration.

═══════════════════════════════════════════════════════════════
WRITING STYLE - CRITICAL
═══════════════════════════════════════════════════════════════

1. NO markdown (no **, no ---, no bullets)
2. Write like a Bloomberg terminal note - SHORT and PUNCHY
3. Each answer: 2-3 sentences MAX
4. Use this format for data: "SYMBOL (1W: +X% | 1M: +X%)"
5. Use ONLY these 4 trend labels: ABOVE TREND, BELOW TREND, RECOVERY, CORRECTION

GOOD STYLE:
"Sector Rotation, not Risk-Off. Breadth: 8/11 sectors positive. Leadership: Broad (4 sectors in Top 5). Tech in CORRECTION: NVDA (1W: -2.1% | 1M: +12.3%). Financials ABOVE TREND: JPM (1W: +3.2% | 1M: +8.5%). Style: Value over Growth."

BAD STYLE (wrong interpretation):
"Risk-Off regime. Tech selling off heavily..." (This ignores Financials strength)

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT - FOLLOW EXACTLY
═══════════════════════════════════════════════════════════════

## 🌡️ MARKET OVERVIEW

**1. What is the prevailing Global Risk Regime?**
[State regime with BREADTH context. Example: "Sector Rotation, not Risk-Off. 7/11 sectors positive. Tech in CORRECTION but Financials and Industrials ABOVE TREND. Value style outperforming Growth."]

**2. Which sectors are leading?**
[Top 3 sectors with best performers and correct labels. Example: "Financials lead: JPM ABOVE TREND (1W: +3.2% | 1M: +8.5%), GS ABOVE TREND (1W: +2.8% | 1M: +10.1%). Industrials strong: CAT ABOVE TREND (1W: +2.1% | 1M: +7.3%)."]

**3. Which sectors are lagging?**
[Bottom 3 sectors with correct labels. Example: "Tech lagging: NVDA in CORRECTION (1W: -2.1% | 1M: +12.3%), MSFT in CORRECTION (1W: -1.5% | 1M: +5.2%). Communication weak: NFLX BELOW TREND (1W: -3.2% | 1M: -8.5%)."]

## 📈 STOCK PERFORMANCE

**4. Top Performing Stocks?**
[Top 5 stocks with correct labels. Note sector concentration. Example: "Top 5: FCX ABOVE TREND (1W: +5.2% | 1M: +21.3%), GM ABOVE TREND (1W: +4.1% | 1M: +18.5%)... Leadership from Materials and Autos - cyclical strength."]

**5. Worst Performing Stocks?**
[Bottom 5 stocks with correct labels. Example: "Bottom 5: ORCL BELOW TREND (1W: -3.2% | 1M: -14.5%), NFLX BELOW TREND (1W: -2.8% | 1M: -12.3%)... Weakness concentrated in high-multiple names."]

**6. Momentum Stocks?**
[Stocks with strongest 1W moves. Flag divergences. Example: "Best 1W momentum: FCX (1W: +5.2%), COF (1W: +4.5%). Watch TMUS in RECOVERY (1W: +1.6% | 1M: -7.5%) - potential trend change."]

## 🏭 SECTOR OUTLOOK

**7. Technology Outlook?**
[Key tech with correct labels. Example: "Mixed with CORRECTION pattern. AAPL in CORRECTION (1W: -1.2% | 1M: +3.5%), NVDA in CORRECTION (1W: -2.1% | 1M: +12.3%). Only META ABOVE TREND (1W: +1.5% | 1M: +8.2%). Sector breadth: 8/19 positive."]

**8. Financials Outlook?**
[Key financials with labels. Example: "Strong, ABOVE TREND across the board. JPM (1W: +3.2% | 1M: +8.5%), GS (1W: +2.8% | 1M: +10.1%), V (1W: +1.5% | 1M: +6.2%) all ABOVE TREND. Sector breadth: 15/20 positive."]

**9. Healthcare Outlook?**
[Key healthcare with labels. Example: "Defensive bid present. JNJ ABOVE TREND (1W: +1.2% | 1M: +4.5%), UNH ABOVE TREND (1W: +0.8% | 1M: +3.2%). LLY in CORRECTION (1W: -1.5% | 1M: +8.5%). Sector breadth: 10/15 positive."]

## 🧭 PORTFOLIO STRATEGY

**10. Portfolio Recommendation?**
[Clear stance with style call. Example: "Rotate to Value: Favor JPM, CAT, FCX. Reduce exposure to NVDA, NFLX, ORCL. Style: Value over Growth. Monitor AAPL - CORRECTION may offer entry."]

## 🔮 NEXT WEEK OUTLOOK

**11. Stocks to Watch Next Week?**
BULLISH: [Stocks with positive setup and conditions]
BEARISH: [Stocks at risk with conditions]

**12. Sectors to Watch Next Week?**
BULLISH: [Sectors with momentum, note breadth]
BEARISH: [Sectors showing weakness, note breadth]

**13. Key Levels & Triggers?**
[3-4 key stock levels. Example: "NVDA 900 resistance (CORRECTION test), AAPL 180 support (CORRECTION base), JPM 200 breakout (ABOVE TREND continuation)."]

## 📝 EXECUTIVE SUMMARY

[Write exactly 3 short sentences - this comes LAST, after all analysis:]
Sentence 1: Use the EXACT regime from data (RISK-ON/RISK-OFF/ROTATION/CAUTION/NEUTRAL) with style call (Growth vs Value).
Sentence 2: Stocks showing relative strength (specific names with labels).
Sentence 3: Key risk or divergence to monitor.

═══════════════════════════════════════════════════════════════
LANGUAGE RESTRICTIONS (COMPLIANCE)
═══════════════════════════════════════════════════════════════

NEVER use: "buy", "sell", "overweight", "underweight", "recommend", "should invest", "bullish on", "bearish on"
INSTEAD use: "favor", "reduce exposure to", "monitor", "watch", "showing strength", "showing weakness", "at risk"

This is ANALYSIS ONLY, not investment advice. Use observational language:
❌ "Buy NVDA" → ✅ "NVDA showing relative strength"
❌ "Sell ORCL" → ✅ "ORCL showing weakness, reduce exposure"
❌ "Overweight Financials" → ✅ "Financials favored in current rotation"
❌ "This is a buying opportunity" → ✅ "This may offer entry for those already positioned"
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
    breadth = r.get('breadth', {})
    lines.append(f"Risk Score: {r['riskScore']} | Cycle Score: {r['cycleScore']} | Breadth: {breadth.get('positive', 0)}/{breadth.get('total', 11)}")
    
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
    
    # === SECTOR SUMMARY (1W bazlı - ETF breadth ile tutarlı) ===
    lines.append(f"\n{'='*60}")
    lines.append("SECTOR SUMMARY (1W Based)")
    lines.append(f"{'='*60}")
    
    sector_perf = {}
    for e in stocks_full:
        cat = e['cat']
        if cat not in sector_perf:
            sector_perf[cat] = {'ret_1w': [], 'ret_1m': []}
        sector_perf[cat]['ret_1w'].append(e['ret_1w'])
        sector_perf[cat]['ret_1m'].append(e['ret_1m'])
    
    sector_avg = []
    breadth_positive = 0
    for cat, data_dict in sector_perf.items():
        avg_1w = sum(data_dict['ret_1w']) / len(data_dict['ret_1w']) if data_dict['ret_1w'] else 0
        avg_1m = sum(data_dict['ret_1m']) / len(data_dict['ret_1m']) if data_dict['ret_1m'] else 0
        sector_avg.append((cat, avg_1w, avg_1m, len(data_dict['ret_1w'])))
        if avg_1w > 0:
            breadth_positive += 1
    
    sector_avg.sort(key=lambda x: x[1], reverse=True)  # 1W bazlı sırala
    
    lines.append(f"\n  📊 SECTOR BREADTH: {breadth_positive}/{len(sector_avg)} sectors positive (1W)")
    lines.append("")
    
    for cat, avg_1w, avg_1m, count in sector_avg:
        status = "✅" if avg_1w > 0 else "❌"
        lines.append(f"  {status} {cat:20}: 1W: {avg_1w:+.2f}% | 1M: {avg_1m:+.2f}% ({count} stocks)")
    
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
