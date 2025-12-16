"""
Daily Brief Generator v5.0
==========================
ETF verilerini OpenAI'a gönderir ve brief JSON üretir.

v5.0 Yenilikler:
- Zaman Etiketleri (1W vs 1M karşılaştırma)
- Delta (Değişim Yönü - nereden nereye)
- Trend Durumu (Above/Below Trend)

Kullanım:
    python generate_brief.py

Girdi:
    etf_data.json

Çıktı:
    brief.json
"""

import json
import os
from datetime import datetime
from openai import OpenAI

DATA_FILE = 'etf_data.json'
OUTPUT_FILE = 'brief.json'
MODEL = 'gpt-5-mini'

SYSTEM_PROMPT = """You are a senior Global Macro Strategist. Write a daily market brief for portfolio managers.

═══════════════════════════════════════════════════════════════
WRITING STYLE - CRITICAL
═══════════════════════════════════════════════════════════════

1. NO markdown (no **, no ---, no bullets)
2. Write like a Bloomberg terminal note - SHORT and PUNCHY
3. Each answer: 2-3 sentences MAX
4. Use this format for data: "ETF at X.XX (1W: +X% | 1M: +X%)"
5. Only use these trend labels: ABOVE TREND, BELOW TREND (nothing else)

GOOD STYLE:
"Risk-Off regime. VIX at 29.6 (1W: -4.5% | 1M: -15.7%) - fear easing but still elevated. Credit stress persists: HYG/LQD at 0.73, BELOW TREND."

BAD STYLE (too verbose):
"The market remains in a Risk-Off regime with VIX sitting at 29.69 which represents a decline of 4.47% on a weekly basis..."

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

1. ALWAYS USE DUAL TIME-FRAME FORMAT:
   ❌ Wrong: "XBI +9.82%"
   ✅ Right: "XBI showing strong momentum (1W: +3.2% | 1M: +9.8%)"
   
   This is MANDATORY for every ETF mention. Readers must know if it's weekly or monthly.

2. ALWAYS SHOW DELTA (Direction of Change):
   ❌ Wrong: "VXX at 29.86 signaling panic"
   ✅ Right: "VXX spiked to 29.86 (↑ from 25.2 last week), signaling rising panic"
   ✅ Right: "VXX dropped to 29.86 (↓ from 35.1 last week), signaling easing fear"
   
   The DIRECTION matters more than the level. Same number can mean opposite things.

3. ALWAYS INDICATE TREND POSITION:
   ❌ Wrong: "SPY is positive"
   ✅ Right: "SPY is positive but BELOW TREND (1M trend negative despite 1W bounce)"
   ✅ Right: "SPY is strong and ABOVE TREND (both 1W and 1M aligned positive)"
   
   Use: "ABOVE TREND" when 1W and 1M both positive and aligned
   Use: "BELOW TREND" when 1M negative or diverging from 1W
   Use: "TREND REVERSAL" when 1W and 1M have opposite signs

4. INTERPRETATION GUIDE:
   - VXX > 25 = PANIC, 20-25 = Elevated, 15-20 = Normal, < 15 = Complacent
   - If VXX 1W change is POSITIVE = Fear INCREASING (bad)
   - If VXX 1W change is NEGATIVE = Fear DECREASING (good)
   - HYG/LQD < 0.85 = Credit stress
   - When 1W and 1M signs MATCH = Confirmed trend
   - When 1W and 1M signs DIFFER = Divergence/Reversal signal

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT - FOLLOW EXACTLY
═══════════════════════════════════════════════════════════════

## 🌡️ MARKET ATMOSPHERE

**1. Global Risk Regime?**
[State regime. Include VXX level WITH delta direction. Example: "Risk-Off with VXX at 29.9 (↑ from 25.2, fear RISING). SPY/TLT ratio improving (1W: +0.3% | 1M: +3.4%) but HYG/LQD at 0.73 shows persistent credit stress."]

**2. Primary Risk Drivers?**
[2-3 drivers with delta. Example: "Credit stress persists with HYG/LQD at 0.73 (unchanged from last week). Volatility trending down (VXX 1W: -5%, 1M: -16%) suggesting fear is peaking."]

**3. Financial Conditions Signal?**
[Dollar, yields with direction. Example: "Tightening: UUP stable at 28 (1W: -0.6%), yield curve flattening with TLT/SHY at 1.05 (↓ from 1.08 last week)."]

## 📈 EQUITIES & FLOWS

**4. Sector Leadership?**
[Winners/losers with DUAL timeframe. Example: "Tech leading: XLK (1W: +1.2% | 1M: +5.2%) ABOVE TREND. Energy lagging: XLE (1W: -0.5% | 1M: -2.1%) BELOW TREND."]

**5. US vs Global?**
[Regional comparison with dual timeframe. Example: "US outperforms: SPY (1W: +1.1% | 1M: +4.2%) ABOVE TREND. China weak: FXI (1W: -0.7% | 1M: -5.2%) BELOW TREND, trend deteriorating."]

**6. Speculative Appetite?**
[ARKK, IWM, crypto with delta. Example: "Speculation mixed: IWM strong (1W: +2.1% | 1M: +6.3%) but crypto collapsing - IBIT (1W: -5% | 1M: -12%) BELOW TREND, trend accelerating down."]

## 🛢️ REAL ECONOMY

**7. Commodities Theme?**
[Theme with dual timeframe. Example: "Safe haven bid: SLV surging (1W: +5.2% | 1M: +21%) ABOVE TREND. Industrial metals diverging: CPER (1W: -2% | 1M: +6%) showing trend exhaustion."]

**8. Energy Trend?**
[Energy with direction. Example: "Energy weakening: BNO (1W: -1.5% | 1M: -3.4%) BELOW TREND. Natural gas collapsing: UNG (1W: -8% | 1M: -15%) in confirmed downtrend."]

## 🧭 STRATEGY

**9. Trend Confirmation?**
[Compare 1W vs 1M. Example: "CONFIRMED: Precious metals (SLV 1W/1M both positive). DIVERGENCE: Semis (1W down, 1M up) - momentum fading."]

**10. Portfolio Direction?**
[Clear stance. Example: "Overweight: SLV, XBI. Underweight: FXI, IBIT. Neutral: Bonds."]

## 🔮 NEXT WEEK OUTLOOK

**11. Sectors to Watch?**
BULLISH: [If condition → action with ETF]
BEARISH: [If condition → action with ETF]

**12. Commodities to Watch?**
BULLISH: [If condition → action]
BEARISH: [If condition → action]

**13. Key Levels?**
[3-4 levels to watch. Example: "VIX 25 (fear threshold), HYG/LQD 0.70 (credit stress), SPY/TLT 8.0 (risk pivot)."]

## 📝 EXECUTIVE SUMMARY

[Write exactly 3 short sentences - this comes LAST, after all analysis:]
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
    lines.append("ETF BAROMETER DATA - PROFESSIONAL FORMAT")
    lines.append("All data includes: Current Level | 1W Change | 1M Change | Trend Status")
    lines.append("=" * 60)
    
    # === REGIME ===
    r = data['regime']
    lines.append(f"\n{'='*60}")
    lines.append("MARKET REGIME")
    lines.append(f"{'='*60}")
    lines.append(f"OVERALL: {r['overall']}")
    lines.append(f"Risk Score: {r['riskScore']} | Cycle Score: {r['cycleScore']} | Total: {r['totalScore']}")
    lines.append("\nREGIME SIGNALS:")
    for sig, val in r['signals'].items():
        lines.append(f"  • {sig}: {val['value']} (score: {val['score']:+d})")
    
    # === KEY RATIOS with Delta ===
    lines.append(f"\n{'='*60}")
    lines.append("KEY MARKET RATIOS (with Delta Direction)")
    lines.append(f"{'='*60}")
    
    ratio_by_cat = {}
    for ratio in data['ratios']:
        cat = ratio['category']
        if cat not in ratio_by_cat:
            ratio_by_cat[cat] = []
        ratio_by_cat[cat].append(ratio)
    
    for cat, ratios in ratio_by_cat.items():
        lines.append(f"\n📊 {cat}:")
        for r in ratios:
            val_1m = r['values'].get('1M') or 0
            chg_1w = r['changes'].get('1W') or 0
            chg_1m = r['changes'].get('1M') or 0
            delta = get_delta_direction(chg_1w)
            trend = get_trend_status(chg_1w, chg_1m)
            lines.append(f"  • {r['name']}")
            lines.append(f"    Level: {val_1m:.4f} | 1W: {chg_1w:+.2f}% | 1M: {chg_1m:+.2f}% | {delta} | {trend}")
    
    # === ETF RANKINGS with Full Data ===
    lines.append(f"\n{'='*60}")
    lines.append("ETF PERFORMANCE (1W vs 1M Comparison)")
    lines.append(f"{'='*60}")
    
    etfs_full = []
    for e in data['etfs']:
        w1 = e.get('1W', {})
        m1 = e.get('1M', {})
        ret_1w = w1.get('RETURN')
        ret_1m = m1.get('RETURN')
        trend_1m = m1.get('TREND', 0)
        
        if ret_1m is not None:
            etfs_full.append({
                'sym': e['Symbol'],
                'name': e['Name'],
                'cat': e['Category'],
                'ret_1w': ret_1w or 0,
                'ret_1m': ret_1m,
                'trend': trend_1m,
                'status': get_trend_status(ret_1w, ret_1m)
            })
    
    etfs_full.sort(key=lambda x: x['ret_1m'], reverse=True)
    
    lines.append("\n🏆 TOP 10 PERFORMERS:")
    for i, e in enumerate(etfs_full[:10], 1):
        lines.append(f"  {i}. {e['sym']:6} ({e['cat']:8})")
        lines.append(f"     1W: {e['ret_1w']:+6.2f}% | 1M: {e['ret_1m']:+6.2f}% | {e['status']}")
    
    lines.append("\n📉 BOTTOM 10 PERFORMERS:")
    for i, e in enumerate(etfs_full[-10:], 1):
        lines.append(f"  {i}. {e['sym']:6} ({e['cat']:8})")
        lines.append(f"     1W: {e['ret_1w']:+6.2f}% | 1M: {e['ret_1m']:+6.2f}% | {e['status']}")
    
    # === KEY ETFs Detail ===
    lines.append(f"\n{'='*60}")
    lines.append("KEY ETFs DETAILED VIEW")
    lines.append(f"{'='*60}")
    
    key_etfs = ['SPY', 'QQQ', 'IWM', 'TLT', 'VXX', 'GLD', 'SLV', 'XLK', 'XLE', 
                'HYG', 'LQD', 'FXI', 'EEM', 'ARKK', 'IBIT', 'XBI', 'CPER', 'BNO', 'UNG']
    
    for sym in key_etfs:
        for e in data['etfs']:
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
    
    # === DIVERGENCE ALERTS ===
    lines.append(f"\n{'='*60}")
    lines.append("⚠️ DIVERGENCE ALERTS (1W vs 1M mismatch)")
    lines.append(f"{'='*60}")
    
    divergences = []
    for e in etfs_full:
        if 'REVERSAL' in e['status'] or 'EXHAUSTION' in e['status']:
            divergences.append(e)
    
    if divergences:
        for e in divergences[:10]:
            lines.append(f"  • {e['sym']}: 1W: {e['ret_1w']:+.2f}% vs 1M: {e['ret_1m']:+.2f}% → {e['status']}")
    else:
        lines.append("  No major divergences detected")
    
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
1. Every ETF mention MUST have dual timeframe: (1W: X% | 1M: Y%)
2. Every ratio/indicator MUST show direction (↑ rising / ↓ falling)
3. Every asset MUST have trend status (ABOVE/BELOW TREND)
4. Compare 1W vs 1M to identify confirmations and divergences

Generate the Daily Market Brief now."""}
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
    print("🤖 Daily Brief Generator v5.0")
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
        print(f"✅ Loaded: {data['etf_count']} ETFs, {data['ratio_count']} ratios")
        print(f"   Regime: {data['regime']['overall']}")
        
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
