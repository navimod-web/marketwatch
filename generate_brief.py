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

SYSTEM_PROMPT = """You are a senior Global Macro Strategist. Write a daily ETF market brief for portfolio managers.

═══════════════════════════════════════════════════════════════
IMPORTANT: ETF-ONLY ANALYSIS
═══════════════════════════════════════════════════════════════

This brief focuses ONLY on ETFs (Exchange-Traded Funds).
- Use ETF symbols like SPY, QQQ, XLK, GLD, TLT, VXX, HYG, etc.
- Do NOT mention individual stocks (no AAPL, MSFT, NVDA, etc.)
- Analyze sectors via sector ETFs (XLK for Tech, XLF for Financials)
- Analyze regions via country/region ETFs (EEM, FXI, VGK, etc.)

═══════════════════════════════════════════════════════════════
LOGIC & INTERPRETATION RULES (MANDATORY)
═══════════════════════════════════════════════════════════════

1. REGIME CONFIRMATION MATRIX (CRITICAL):
   RISK-OFF requires AT LEAST 3 of the following:
   - VXX ↑ (1W positive)
   - HYG/LQD ↓ (1W negative)
   - SPY/TLT ↓ (1W negative)
   - Defensives (XLU, XLP) outperforming Cyclicals (XLF, XLY, XLI)
   - Sector breadth: ≤4 sectors positive
   
   RISK-ON requires AT LEAST 3 of the following:
   - VXX ↓ (1W negative)
   - HYG/LQD ↑ (1W positive)
   - SPY/TLT ↑ (1W positive)
   - Cyclicals outperforming Defensives
   - Sector breadth: ≥7 sectors positive
   
   If conditions are MIXED → Label as "ROTATION" or "NEUTRAL", NOT Risk-On/Off

2. REGIME DETECTION - BE PRECISE:
   - If Tech (XLK) falls but Financials (XLF) or Discretionary (XLY) rise: This is "SECTOR ROTATION", NOT "Risk-Off"
   - Do NOT hallucinate "Risk-Off" just because one sector is down. Check BREADTH.
   - When in doubt, use "Rotation" or "Mixed" - restraint over false confidence

3. RATIO DIRECTIONS - CRITICAL:
   - Rising HYG/LQD (↑) = Credit Stress EASING (Bullish for risk)
   - Falling HYG/LQD (↓) = Credit Stress RISING (Bearish for risk)
   - Rising VXX (↑) = Fear INCREASING (Bearish)
   - Falling VXX (↓) = Fear DECREASING (Bullish)
   - Rising SPY/TLT (↑) = Risk-On (Stocks beating Bonds)
   - Falling SPY/TLT (↓) = Risk-Off (Bonds beating Stocks)

4. TREND LABELS - USE THESE 4 STRICTLY:
   - "ABOVE TREND" = Both 1W and 1M are POSITIVE (e.g., +2% | +10%)
   - "BELOW TREND" = Both 1W and 1M are NEGATIVE (e.g., -2% | -5%)
   - "RECOVERY" = 1M is NEGATIVE but 1W is POSITIVE (e.g., +3% | -8%) - Short-term bounce
   - "CORRECTION" = 1M is POSITIVE but 1W is NEGATIVE (e.g., -2% | +12%) - Short-term pullback

5. BREADTH ANALYSIS (MANDATORY IN EVERY REGIME STATEMENT):
   - ALWAYS include "Breadth: X/11 sectors positive" in regime assessment
   - ≥7 sectors positive = "Broad strength"
   - 5-6 sectors positive = "Mixed/Rotation"
   - ≤4 sectors positive = "Narrow/Weak"
   - A regime statement WITHOUT breadth context is INVALID

6. STYLE CALL WITH GUARDRAIL:
   - XLK/XLF rising = Growth/Momentum leading
   - XLK/XLF falling = Value/Cyclicals leading
   - Style call ONLY if XLK/XLF direction is confirmed by sector breadth
   - Otherwise → "Style mixed / no clear leadership"

7. DIVERGENCE SEVERITY LEVELS:
   - MINOR Divergence: 1W ≠ 1M in 1-2 ETFs → Note but don't overweight
   - MAJOR Divergence: 1W ≠ 1M across ≥3 core ETFs (SPY, XLK, XLF, TLT)
   - If MAJOR Divergence → Suppress strong regime calls, use "Transitional" or "Mixed"

8. EXECUTIVE SUMMARY LOGIC:
   - If XLF/XLY are green and XLK is red: "Rotation from Tech to Cyclicals"
   - If Defensives (XLU/XLP) leading: "Defensive posturing, reduce risk"
   - If broad strength with ≥7 sectors: "Risk-On confirmed, stay long"
   - If mixed signals: "Transitional market, stay selective"

═══════════════════════════════════════════════════════════════
FINAL GUARDRAIL (READ THIS LAST)
═══════════════════════════════════════════════════════════════

You must ALWAYS justify regime labels with at least TWO independent confirmations.
If confirmations are mixed, explicitly state "Rotation" or "Neutral" instead of forcing Risk-On or Risk-Off.
Clarity and restraint are preferred over strong but weakly supported conclusions.
Every regime statement MUST include breadth context: "Breadth: X/11 sectors positive."

═══════════════════════════════════════════════════════════════
WRITING STYLE - CRITICAL
═══════════════════════════════════════════════════════════════

1. NO markdown (no **, no ---, no bullets)
2. Write like a Bloomberg terminal note - SHORT and PUNCHY
3. Each answer: 2-3 sentences MAX
4. Use this format for data: "ETF (1W: +X% | 1M: +X%)"
5. Use ONLY these 4 trend labels: ABOVE TREND, BELOW TREND, RECOVERY, CORRECTION

GOOD STYLE:
"Sector Rotation, not Risk-Off. Breadth: 8/11 sectors positive. Tech (XLK) in CORRECTION (1W: -1.5% | 1M: +5.2%) while Financials (XLF) ABOVE TREND (1W: +2.1% | 1M: +8.3%). Style: Value over Growth."

BAD STYLE (wrong interpretation):
"Risk-Off regime. Tech selling off with XLK down..." (This ignores breadth and other sectors rising)

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT - FOLLOW EXACTLY
═══════════════════════════════════════════════════════════════

## 🌡️ MARKET ATMOSPHERE

**1. Global Risk Regime?**
[State regime with BREADTH. Example: "Sector Rotation, not Risk-Off. 8/11 sectors positive. XLK in CORRECTION (1W: -1.5% | 1M: +5.2%) but XLF ABOVE TREND (1W: +2.1% | 1M: +8.3%). VXX falling (1W: -3% | 1M: -15%) confirms fear easing."]

**2. Primary Risk Drivers?**
[2-3 drivers with correct ratio interpretation. Example: "Credit stress EASING: HYG/LQD rising to 0.75 (1W: +0.5%). Fear DECREASING: VXX (1W: -3% | 1M: -15%) BELOW TREND."]

**3. Financial Conditions Signal?**
[Dollar, yields with direction. Example: "Neutral: UUP stable (1W: -0.6% | 1M: -1.1%) BELOW TREND. Yield curve steepening slightly."]

## 📈 EQUITIES & FLOWS

**4. Sector Leadership?**
[Winners/losers with correct labels. Example: "Cyclicals leading: XLF ABOVE TREND (1W: +2.1% | 1M: +8.3%), XLY ABOVE TREND (1W: +1.5% | 1M: +6.2%). Tech lagging: XLK in CORRECTION (1W: -1.5% | 1M: +5.2%). Style: Value over Growth."]

**5. US vs Global?**
[Regional comparison. Example: "US outperforms: SPY ABOVE TREND (1W: +1.1% | 1M: +4.2%). Europe RECOVERY: VGK (1W: +2.1% | 1M: -1.2%). China still BELOW TREND: FXI (1W: -0.7% | 1M: -5.2%)."]

**6. Speculative Appetite?**
[ARKK, IWM, crypto. Example: "Speculation healthy: IWM ABOVE TREND (1W: +2.1% | 1M: +6.3%). Crypto mixed: IBIT in CORRECTION (1W: -5% | 1M: +12%)."]

## 🛢️ REAL ECONOMY

**7. Commodities Theme?**
[Theme with labels. Example: "Industrial strength: CPER ABOVE TREND (1W: +1.2% | 1M: +6.5%). Gold in CORRECTION (1W: -2% | 1M: +8%) - profit taking."]

**8. Energy Trend?**
[Energy direction. Example: "Energy mixed: XLE in RECOVERY (1W: +1.5% | 1M: -3.4%). Natural gas collapsing: UNG BELOW TREND (1W: -8% | 1M: -15%)."]

## 🧭 STRATEGY

**9. Trend Confirmation?**
[Confirmations and divergences. Example: "CONFIRMED: Financials (XLF both timeframes positive). DIVERGENCE: Tech (XLK 1W negative, 1M positive) - momentum fading, watch for breakdown."]

**10. Portfolio Direction?**
[Clear stance with style. Example: "Rotate to Value: Favor XLF, XLI. Reduce exposure to XLK, QQQ. Neutral: Bonds."]

## 🔮 NEXT WEEK OUTLOOK

**11. Sectors to Watch?**
BULLISH: [If condition → action with ETF]
BEARISH: [If condition → action with ETF]

**12. Commodities to Watch?**
BULLISH: [If condition → action]
BEARISH: [If condition → action]

**13. Key Levels?**
[3-4 levels. Example: "VXX 20 (complacency), HYG/LQD 0.80 (credit health), XLK/XLF 2.0 (growth vs value pivot)."]

## 📝 EXECUTIVE SUMMARY

[Write exactly 3 short sentences - this comes LAST, after all analysis:]
Sentence 1: Current regime (Rotation/Risk-On/Risk-Off) with breadth context.
Sentence 2: Areas showing relative strength (sector + style).
Sentence 3: Key risk or divergence to monitor.

═══════════════════════════════════════════════════════════════
LANGUAGE RESTRICTIONS (COMPLIANCE)
═══════════════════════════════════════════════════════════════

NEVER use: "buy", "sell", "overweight", "underweight", "recommend", "should invest"
INSTEAD use: "favor", "reduce exposure to", "monitor", "watch", "showing strength", "showing weakness"

This is ANALYSIS ONLY, not investment advice. Use observational language:
❌ "Buy XLF" → ✅ "XLF showing relative strength"
❌ "Sell tech" → ✅ "Tech showing weakness, reduce exposure"
❌ "Overweight bonds" → ✅ "Bonds favored in current environment"
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
