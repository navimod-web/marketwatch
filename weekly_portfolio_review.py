# -*- coding: utf-8 -*-
"""
Weekly Portfolio Review v1.1
============================
Haftalık portföy analizi - JSON çıktı

Kullanım:
    python weekly_portfolio_review.py

Girdi:
    - etf_data.json
    - news_data.json

Çıktı:
    - portfolio_review.json (HTML bu dosyayı okur)
"""

import json
import os
from datetime import datetime
from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
PORTFOLIO_FILE = "portfolio.txt"

def load_portfolio(filepath=PORTFOLIO_FILE):
    """
    Portföyü txt dosyasından yükle.
    Format: SYMBOL,WEIGHT (her satırda bir hisse)
    # ile başlayan satırlar yorum
    
    Örnek portfolio.txt:
    # Weekly Portfolio - 2024
    BMY,18.0
    C,17.3
    CAT,11.0
    """
    portfolio = {}
    
    if not os.path.exists(filepath):
        print(f"⚠️ {filepath} bulunamadı! Örnek dosya oluşturuluyor...")
        create_sample_portfolio(filepath)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Boş satır veya yorum
                if not line or line.startswith('#'):
                    continue
                
                # Parse: SYMBOL,WEIGHT
                parts = line.split(',')
                if len(parts) != 2:
                    print(f"⚠️ Line {line_num}: Geçersiz format '{line}' - Beklenen: SYMBOL,WEIGHT")
                    continue
                
                symbol = parts[0].strip().upper()
                try:
                    weight = float(parts[1].strip())
                except ValueError:
                    print(f"⚠️ Line {line_num}: Geçersiz ağırlık '{parts[1]}' - {symbol} atlandı")
                    continue
                
                if weight <= 0:
                    print(f"⚠️ Line {line_num}: Ağırlık 0 veya negatif - {symbol} atlandı")
                    continue
                
                portfolio[symbol] = weight
        
        # Validasyon
        total = sum(portfolio.values())
        if abs(total - 100) > 0.5:
            print(f"⚠️ Toplam ağırlık: {total:.1f}% (100% olmalı)")
        
        return portfolio
        
    except Exception as e:
        print(f"❌ Portföy yükleme hatası: {e}")
        return {}

def create_sample_portfolio(filepath):
    """Örnek portfolio.txt oluştur"""
    sample = """# Weekly Portfolio
# Format: SYMBOL,WEIGHT
# Toplam ağırlık 100% olmalı
# Her satırda bir hisse

# Healthcare
BMY,18.0

# Financials
C,17.3
GS,11.0
COF,7.0
USB,7.0
PNC,0.7

# Industrials
CAT,11.0
FDX,11.0
GM,7.0

# ETFs
SPY,7.5
SKYY,2.5
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(sample)
    print(f"✅ Örnek portföy dosyası oluşturuldu: {filepath}")

# ============================================================
# DATA LOADERS
# ============================================================
def load_json(filepath):
    if not os.path.exists(filepath):
        print(f"⚠️ {filepath} bulunamadı")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_stock_data(symbol, etf_data):
    """Belirli bir hisse/ETF için veri çek"""
    for stock in etf_data.get('stocks', []):
        if stock.get('Symbol') == symbol:
            return {'type': 'stock', 'data': stock}
    for etf in etf_data.get('etfs', []):
        if etf.get('Symbol') == symbol:
            return {'type': 'etf', 'data': etf}
    return None

def get_sentiment_data(symbol, news_data):
    """Belirli bir hisse için sentiment verisi"""
    if not news_data or not news_data.get('news'):
        return None
    
    news_items = [n for n in news_data['news'] if n.get('symbol') == symbol]
    if not news_items:
        return None
    
    total = sum(n.get('sentiment', 0) for n in news_items)
    headlines = [{"title": n.get('title', '')[:100], "sentiment": n.get('sentiment', 0)} for n in news_items[:3]]
    
    return {
        'count': len(news_items),
        'total': total,
        'headlines': headlines
    }

# ============================================================
# MARKET REGIME & RISK ANALYSIS
# ============================================================
def analyze_market_regime(etf_data):
    """
    Piyasa rejimini analiz eder ve HARD RULES oluşturur.
    LLM'in kurallara uymasını zorlar.
    """
    regime = etf_data.get('regime', {})
    overall = regime.get('overall', 'NEUTRAL')
    risk = regime.get('risk', 'NEUTRAL')
    
    # VXX ve Credit sinyallerini kontrol et
    signals = regime.get('signals', {})
    vxx_signal = ''
    credit_signal = ''
    if isinstance(signals, dict):
        vxx_data = signals.get('VXX', {})
        credit_data = signals.get('HYG_LQD', {})
        vxx_signal = vxx_data.get('value', '') if isinstance(vxx_data, dict) else ''
        credit_signal = credit_data.get('value', '') if isinstance(credit_data, dict) else ''
    
    # Default
    risk_level = "NORMAL"
    instruction = "MAINTAIN: Mevcut stratejiyi koru. Momentum ve sektör sağlığına odaklan."
    hard_rules = []
    
    # PANIC / BEAR Market
    if "PANIC" in str(vxx_signal).upper() or "STRESS" in str(credit_signal).upper() or overall == "BEAR":
        risk_level = "HIGH_ALERT"
        instruction = (
            "⚠️ ACİL DURUM: Piyasa PANIC/BEAR modunda. "
            "Sermayeyi koru. Spekülatif pozisyonları kapat."
        )
        hard_rules = [
            "MUST REDUCE: Tüm pozisyonları minimum %30 azalt",
            "MUST REMOVE: Weak momentum (2W<0, 1M<0) olan tüm hisseleri sat",
            "FAVOR: Defansif sektörler (Healthcare, Consumer Staples)",
            "AVOID: Spekülatif ve yüksek beta hisseler"
        ]
    
    # ROTATION Market
    elif overall == "ROTATION":
        risk_level = "ROTATION"
        instruction = (
            "🔄 ROTASYON MODU: Para sektörler arası hareket ediyor. "
            "Sadece güçlü momentum sektörlerinde kal."
        )
        hard_rules = [
            "MUST REMOVE: Disqualified sektörlerdeki tüm hisseler",
            "MUST REMOVE: Sector Health ≤ 2 olan sektörlerdeki hisseler",
            "FAVOR: Sector Quant Score ≥ 70 olan sektörler",
            "REDUCE: Sector Quant Score < 50 olan sektörlerdeki pozisyonlar"
        ]
    
    # RISK-OFF / CAUTION
    elif risk == "RISK-OFF" or overall == "CAUTION":
        risk_level = "CAUTION"
        instruction = (
            "⚠️ DİKKATLİ MOD: Risk iştahı düşük. "
            "Defansif pozisyonları koru, agresif alımlardan kaçın."
        )
        hard_rules = [
            "REDUCE: Weakening momentum hisseleri (2W<0)",
            "FAVOR: Güçlü sektör desteği olan hisseler",
            "AVOID: Yeni spekülatif pozisyonlar"
        ]
    
    # RISK-ON / BULL
    elif risk == "RISK-ON" or overall == "BULL":
        risk_level = "RISK_ON"
        instruction = (
            "🚀 RİSK AÇIK: Piyasa güçlü. "
            "Momentum hisselerine yüklen, fırsatları değerlendir."
        )
        hard_rules = [
            "INCREASE: Top 10 Quant hisseleri",
            "FAVOR: STRONG momentum + STRONG sector kombinasyonu",
            "OK TO: Agresif pozisyonlar kabul edilebilir"
        ]
    
    return {
        'risk_level': risk_level,
        'instruction': instruction,
        'hard_rules': hard_rules,
        'regime': overall
    }

def get_critical_news(news_data, portfolio_tickers, threshold=-40):
    """
    Portföydeki hisseler için KRİTİK negatif haberleri filtreler.
    Bu haberler VETO yetkisine sahip - teknik ne derse desin satış önerilir.
    """
    alerts = []
    if not news_data or not news_data.get('news'):
        return alerts
    
    for news in news_data.get('news', []):
        sym = news.get('symbol')
        sentiment = news.get('sentiment', 0)
        if sym in portfolio_tickers and sentiment <= threshold:
            alerts.append({
                'symbol': sym,
                'title': news.get('title', '')[:100],
                'sentiment': sentiment,
                'severity': 'CRITICAL' if sentiment <= -60 else 'WARNING'
            })
    
    return alerts

# ============================================================
# SECTOR ANALYSIS
# ============================================================
def get_sector_quant_data(etf_data):
    """Quant rankings'den sektör skorlarını al"""
    rankings = etf_data.get('quant_rankings', {})
    sectors = rankings.get('top10_sectors', [])
    
    sector_quant = {}
    for s in sectors:
        name = s.get('Sector')
        if name:
            sector_quant[name] = {
                'quant_score': s.get('QuantScore') or 0,
                'stock_count': s.get('StockCount') or 0,
                'disqualified': s.get('Disqualified', False),
                'reason': s.get('Reason') or ''
            }
    return sector_quant

# ============================================================
# MARKET ANALYSIS FUNCTIONS (Pre-LLM Decision Support)
# ============================================================

def analyze_market_regime(etf_data):
    """
    Piyasa rejimini analiz eder ve LLM için katı talimatlar oluşturur.
    Returns: (risk_level, instruction, regime_details)
    """
    regime = etf_data.get('regime', {})
    overall = regime.get('overall', 'NEUTRAL')
    risk = regime.get('risk', 'N/A')
    cycle = regime.get('cycle', 'N/A')
    breadth = regime.get('breadth', 'N/A')
    
    # Sinyalleri kontrol et
    signals = regime.get('signals', {})
    vxx_signal = signals.get('VXX', {}).get('value', '') if isinstance(signals.get('VXX'), dict) else ''
    credit_signal = signals.get('HYG_LQD', {}).get('value', '') if isinstance(signals.get('HYG_LQD'), dict) else ''
    
    # Risk seviyesi ve talimat belirleme
    risk_level = "NORMAL"
    instruction = "MAINTAIN: Mevcut stratejiyi koru. Momentum ve sektör sağlığına odaklan."
    
    # PANIC / BEAR durumu
    if "PANIC" in str(vxx_signal).upper() or "STRESS" in str(credit_signal).upper() or overall == "BEAR":
        risk_level = "HIGH_ALERT"
        instruction = (
            "⚠️ ACİL DURUM (HARD RULE): Piyasa PANIC/BEAR modunda. "
            "1) Tüm spekülatif pozisyonları REMOVE et. "
            "2) Zayıf sektörlerdeki varlıkları REDUCE et. "
            "3) Sadece defensif sektörleri (Healthcare, Consumer Staples) tut. "
            "4) SPY/Cash pozisyonunu artırmayı öner."
        )
    # ROTATION durumu
    elif overall == "ROTATION" or "ROTATION" in str(overall).upper():
        risk_level = "ROTATION"
        instruction = (
            "🔄 ROTASYON MODU: Para sektör değiştiriyor. "
            "1) Sadece STRONG momentum sektörlerindeki hisseleri tut. "
            "2) WEAK/WEAKENING sektörleri portföyden çıkar. "
            "3) Disqualified sektörleri kesinlikle SAT. "
            "4) Top 10 Quant hisselerine rotasyon yap."
        )
    # RISK-OFF durumu
    elif "RISK-OFF" in str(overall).upper() or "OFF" in str(risk).upper():
        risk_level = "CAUTION"
        instruction = (
            "⚠️ RISK-OFF MODU: Piyasa defansif. "
            "1) Agresif pozisyonları REDUCE et. "
            "2) Volatil hisseleri azalt. "
            "3) Defensif sektörlere ağırlık ver."
        )
    # RISK-ON durumu
    elif "RISK-ON" in str(overall).upper() or "ON" in str(risk).upper():
        risk_level = "OPPORTUNITY"
        instruction = (
            "✅ RISK-ON MODU: Piyasa agresif. "
            "1) Strong momentum hisselerini INCREASE et. "
            "2) Top 10 Quant hisselerine ağırlık ver. "
            "3) Zayıf performans gösterenleri yine de değerlendir."
        )
    
    regime_details = {
        'overall': overall,
        'risk': risk,
        'cycle': cycle,
        'breadth': breadth,
        'vxx_signal': vxx_signal,
        'credit_signal': credit_signal
    }
    
    return risk_level, instruction, regime_details

def get_blacklisted_sectors(etf_data):
    """
    Diskalifiye olmuş sektörleri listeler - bu sektörlerdeki hisseler REMOVE edilmeli.
    """
    blacklist = []
    rankings = etf_data.get('quant_rankings', {})
    sectors = rankings.get('top10_sectors', [])
    
    for s in sectors:
        if s.get('Disqualified') is True:
            blacklist.append({
                'sector': s.get('Sector', 'Unknown'),
                'reason': s.get('Reason', 'Poor performance'),
                'quant_score': s.get('QuantScore', 0)
            })
    return blacklist

def get_critical_news_alerts(news_data, portfolio_tickers):
    """
    Portföydeki hisseler için KRİTİK haberleri filtreler.
    Sentiment < -50 → VETO (Ciddi olumsuz haber)
    Sentiment < -30 → WARNING (Dikkat gerektiren haber)
    """
    alerts = []
    warnings = []
    
    if not news_data or not news_data.get('news'):
        return alerts, warnings
    
    for news in news_data.get('news', []):
        sym = news.get('symbol')
        sentiment = news.get('sentiment', 0)
        title = news.get('title', '')[:80]
        
        if sym in portfolio_tickers:
            if sentiment <= -50:
                alerts.append({
                    'symbol': sym,
                    'title': title,
                    'sentiment': sentiment,
                    'action': 'VETO - Consider immediate REMOVE'
                })
            elif sentiment <= -30:
                warnings.append({
                    'symbol': sym,
                    'title': title,
                    'sentiment': sentiment,
                    'action': 'WARNING - Monitor closely'
                })
    
    return alerts, warnings

# ============================================================
# MARKET ANALYSIS FUNCTIONS (Rule-Based Pre-Processing)
# ============================================================

def analyze_market_regime(etf_data):
    """
    Piyasa rejimini analiz eder ve LLM için HARD RULES oluşturur.
    Returns: dict with risk_level, instruction, hard_rules, details
    """
    regime = etf_data.get('regime', {})
    overall = regime.get('overall', 'NEUTRAL')
    risk = regime.get('risk', 'NORMAL')
    breadth = regime.get('breadth', 'NEUTRAL')
    
    # Signals kontrolü
    signals = regime.get('signals', {})
    vxx_signal = signals.get('VXX', {}).get('value', '') if isinstance(signals.get('VXX'), dict) else ''
    credit_signal = signals.get('HYG_LQD', {}).get('value', '') if isinstance(signals.get('HYG_LQD'), dict) else ''
    
    # Default
    risk_level = "NORMAL"
    instruction = "MAINTAIN: Mevcut stratejiyi koru. Momentum ve sektör rotasyonuna odaklan."
    hard_rules = []
    
    # PANIC / BEAR durumu
    if "PANIC" in str(vxx_signal).upper() or "STRESS" in str(credit_signal).upper() or overall == "BEAR":
        risk_level = "HIGH_ALERT"
        instruction = (
            "⚠️ HIGH ALERT: Piyasa PANIC/BEAR modunda. "
            "Riskli varlıkları AZALT veya SAT. Defensive sektörlere yönel."
        )
        hard_rules = [
            "WEAK momentum (2W<0, 1M<0) olan hisseler REMOVE edilmeli",
            "Blacklisted sektör hisseleri REMOVE edilmeli",
            "ETF ağırlığı artırılmalı, bireysel hisse riski azaltılmalı",
            "INCREASE kararı yalnızca defensive sektörler için verilebilir"
        ]
    # RISK-OFF durumu
    elif risk == "RISK-OFF" or overall == "RISK-OFF":
        risk_level = "CAUTIOUS"
        instruction = (
            "🛡️ RISK-OFF MODE: Savunmaya geç. "
            "Zayıf momentum hisselerini SAT, sadece Top 10 ve güçlü sektörleri tut."
        )
        hard_rules = [
            "WEAK sektör hisseleri REDUCE veya REMOVE edilmeli",
            "Top 10 dışı ve Score<70 olan hisseler değerlendirilmeli",
            "INCREASE kararı çok seçici verilmeli"
        ]
    # ROTATION durumu
    elif overall == "ROTATION":
        risk_level = "ACTIVE"
        instruction = (
            "🔄 ROTATION MODE: Sektör rotasyonu aktif. "
            "Zayıf/Blacklisted sektörleri SAT, güçlü momentum sektörlerine taşı."
        )
        hard_rules = [
            "Blacklisted sektör hisseleri REMOVE edilmeli",
            "WEAK trend sektörleri REDUCE edilmeli",
            "STRONG sektör + Top 10 hisseler KEEP veya INCREASE"
        ]
    # RISK-ON durumu
    elif risk == "RISK-ON" or overall == "RISK-ON":
        risk_level = "AGGRESSIVE"
        instruction = (
            "🚀 RISK-ON MODE: Agresif pozisyon al. "
            "Momentum güçlü hisseleri ARTIR, Top 10'a girenleri ekle."
        )
        hard_rules = [
            "STRONG momentum hisseler KEEP veya INCREASE",
            "Top 10 hisseler öncelikli",
            "Defensive sektörler REDUCE edilebilir"
        ]
    else:
        hard_rules = [
            "Standart analiz kriterleri uygula",
            "Sektör ve momentum dengesini koru"
        ]
    
    return {
        'risk_level': risk_level,
        'instruction': instruction,
        'hard_rules': hard_rules,
        'overall': overall,
        'risk': risk,
        'breadth': breadth,
        'vxx': vxx_signal,
        'credit': credit_signal
    }

def get_blacklisted_sectors(etf_data):
    """
    Diskalifiye (MUST SELL) sektörleri listeler.
    """
    blacklist = []
    rankings = etf_data.get('quant_rankings', {})
    sectors = rankings.get('top10_sectors', [])
    
    for s in sectors:
        if s.get('Disqualified') is True:
            blacklist.append({
                'sector': s.get('Sector'),
                'reason': s.get('Reason', 'Poor performance'),
                'quant_score': s.get('QuantScore', 0)
            })
    return blacklist

def get_critical_news_alerts(news_data, portfolio_tickers):
    """
    Portföydeki hisseler için KRİTİK negatif haberleri filtreler.
    Sentiment < -50: CRITICAL (VETO candidate)
    Sentiment < -30: WARNING
    """
    alerts = []
    warnings = []
    
    if not news_data or not news_data.get('news'):
        return alerts, warnings
    
    for news in news_data.get('news', []):
        sym = news.get('symbol')
        sentiment = news.get('sentiment', 0)
        title = news.get('title', '')[:80]
        
        if sym in portfolio_tickers:
            if sentiment <= -50:
                alerts.append({
                    'symbol': sym,
                    'sentiment': sentiment,
                    'title': title,
                    'level': 'CRITICAL'
                })
            elif sentiment <= -30:
                warnings.append({
                    'symbol': sym,
                    'sentiment': sentiment,
                    'title': title,
                    'level': 'WARNING'
                })
    
    return alerts, warnings

def get_critical_news(news_data, portfolio_tickers):
    """
    Kritik haberleri birleşik liste olarak döndürür (prompt için).
    """
    alerts, warnings = get_critical_news_alerts(news_data, portfolio_tickers)
    combined = []
    for a in alerts:
        combined.append({
            'symbol': a['symbol'],
            'sentiment': a['sentiment'],
            'title': a['title'],
            'severity': 'CRITICAL'
        })
    for w in warnings:
        combined.append({
            'symbol': w['symbol'],
            'sentiment': w['sentiment'],
            'title': w['title'],
            'severity': 'WARNING'
        })
    return combined

def get_concentration_risk(portfolio, etf_data):
    """
    Konsantrasyon riskini hesaplar.
    HARD RULES:
    - Tek sektör > 30% = MUST REDUCE
    - Toplam ETF > 10% = MUST REDUCE
    """
    sector_weights = {}
    etf_total = 0
    etf_list = []
    
    for symbol, weight in portfolio.items():
        asset = get_stock_data(symbol, etf_data)
        if asset:
            asset_type = asset['type']
            sector = asset['data'].get('Category', 'Other')
            
            if asset_type == 'etf':
                etf_total += weight
                etf_list.append(f"{symbol}: {weight}%")
                sector = 'ETF'
        else:
            # Symbol bulunamadı - muhtemelen ETF
            etf_total += weight
            etf_list.append(f"{symbol}: {weight}%")
            sector = 'ETF'
        
        if sector != 'ETF':
            sector_weights[sector] = sector_weights.get(sector, 0) + weight
    
    risks = []
    hard_rule_violations = []
    
    # Sektör konsantrasyon kontrolü (HARD RULE: max 30%)
    for sector, weight in sector_weights.items():
        if weight > 30:
            risks.append(f"🔴 HARD RULE VIOLATION: {sector} = {weight:.1f}% (MAX 30% - MUST REDUCE)")
            hard_rule_violations.append({
                'type': 'SECTOR_CONCENTRATION',
                'sector': sector,
                'current': weight,
                'max': 30,
                'action': f"REDUCE {sector} exposure by {weight - 30:.1f}%"
            })
        elif weight > 25:
            risks.append(f"🟠 WARNING: {sector} = {weight:.1f}% (approaching 30% limit)")
    
    # ETF konsantrasyon kontrolü (HARD RULE: max 10%)
    if etf_total > 10:
        risks.append(f"🔴 HARD RULE VIOLATION: Total ETF = {etf_total:.1f}% (MAX 10% - MUST REDUCE)")
        risks.append(f"   ETFs: {', '.join(etf_list)}")
        hard_rule_violations.append({
            'type': 'ETF_CONCENTRATION',
            'current': etf_total,
            'max': 10,
            'etfs': etf_list,
            'action': f"REDUCE total ETF exposure by {etf_total - 10:.1f}%"
        })
    elif etf_total > 8:
        risks.append(f"🟠 WARNING: Total ETF = {etf_total:.1f}% (approaching 10% limit)")
    
    return sector_weights, risks, hard_rule_violations, etf_total

def calculate_portfolio_risk_score(portfolio, etf_data, sector_health):
    """
    Portföy risk skorunu hesaplar (0-100, düşük = daha az riskli)
    """
    total_weight = 0
    risk_weighted = 0
    
    for symbol, weight in portfolio.items():
        asset = get_stock_data(symbol, etf_data)
        if asset:
            data = asset['data']
            sector = data.get('Category', 'Other')
            score = data.get('SCORE', 50) or 50
            
            # Sector risk
            sec_health = sector_health.get(sector, {})
            sec_risk = 100 - (sec_health.get('health', 2) * 20)  # 0-100
            
            # Asset risk (inverse of quant score)
            asset_risk = 100 - score
            
            # Combined risk
            combined = (sec_risk * 0.4) + (asset_risk * 0.6)
            risk_weighted += combined * weight
            total_weight += weight
    
    return round(risk_weighted / total_weight, 1) if total_weight > 0 else 50

def get_sector_performance(sector, etf_data, sector_quant=None):
    """Sektör performansını hesapla - 2W, 1M, 3M + Quant Score"""
    stocks = [s for s in etf_data.get('stocks', []) if s.get('Category') == sector]
    if not stocks:
        return None
    
    ret_2w = [s.get('2W', {}).get('RETURN', 0) or 0 for s in stocks]
    ret_1m = [s.get('1M', {}).get('RETURN', 0) or 0 for s in stocks]
    ret_3m = [s.get('3M', {}).get('RETURN', 0) or 0 for s in stocks]
    
    avg_2w = sum(ret_2w) / len(ret_2w) if ret_2w else 0
    avg_1m = sum(ret_1m) / len(ret_1m) if ret_1m else 0
    avg_3m = sum(ret_3m) / len(ret_3m) if ret_3m else 0
    
    positive_2w = len([r for r in ret_2w if r > 0])
    positive_1m = len([r for r in ret_1m if r > 0])
    
    # Trend belirleme (2W ve 1M bazlı)
    if avg_2w > 0 and avg_1m > 0:
        trend = "STRONG"
    elif avg_2w > 0 and avg_1m < 0:
        trend = "RECOVERING"
    elif avg_2w < 0 and avg_1m > 0:
        trend = "WEAKENING"
    else:
        trend = "WEAK"
    
    # Quant data from rankings
    quant_score = 0
    disqualified = False
    disq_reason = ''
    if sector_quant and sector in sector_quant:
        sq = sector_quant[sector]
        quant_score = sq.get('quant_score', 0)
        disqualified = sq.get('disqualified', False)
        disq_reason = sq.get('reason', '')
    
    # Sektör sağlık skoru (0-5) - quant score dahil
    health = 0
    if avg_2w > 0: health += 1
    if avg_1m > 0: health += 1
    if avg_3m > 0: health += 1
    if positive_2w >= len(stocks) / 2: health += 1
    if quant_score >= 70: health += 1  # Quant score bonus
    
    # Disqualified sektörler için health düşür
    if disqualified:
        health = max(0, health - 2)
    
    return {
        'avg_2w': round(avg_2w, 2),
        'avg_1m': round(avg_1m, 2),
        'avg_3m': round(avg_3m, 2),
        'breadth_2w': f"{positive_2w}/{len(stocks)}",
        'breadth_1m': f"{positive_1m}/{len(stocks)}",
        'trend': trend,
        'health': health,  # 0-5 arası (quant bonus ile)
        'quant_score': round(quant_score, 1),
        'disqualified': disqualified,
        'disq_reason': disq_reason,
        'stock_count': len(stocks)
    }

# ============================================================
# PROMPT BUILDER
# ============================================================
def build_analysis_prompt(portfolio, etf_data, news_data):
    lines = []
    
    # ============================================================
    # 1. ROLE & OBJECTIVE
    # ============================================================
    lines.append("=" * 70)
    lines.append("ROLE: Senior Risk Manager for Weekly Swing Trading Portfolio")
    lines.append("OBJECTIVE: Preserve capital first, generate alpha second. Be DECISIVE.")
    lines.append("=" * 70)
    
    # ============================================================
    # 2. MARKET REGIME & HARD RULES (ZORUNLU KURALLAR)
    # ============================================================
    regime_analysis = analyze_market_regime(etf_data)
    regime = etf_data.get('regime', {})
    
    lines.append(f"\n{'=' * 70}")
    lines.append("🚨 MARKET REGIME & HARD RULES (MUST FOLLOW)")
    lines.append(f"{'=' * 70}")
    lines.append(f"\nRISK LEVEL: {regime_analysis['risk_level']}")
    lines.append(f"REGIME: {regime.get('overall', 'N/A')} | Risk: {regime.get('risk', 'N/A')} | Breadth: {regime.get('breadth', 'N/A')}")
    lines.append(f"\n⚡ INSTRUCTION: {regime_analysis['instruction']}")
    
    if regime_analysis['hard_rules']:
        lines.append("\n📋 HARD RULES (Violation = Error):")
        for rule in regime_analysis['hard_rules']:
            lines.append(f"   • {rule}")
    
    # ============================================================
    # 3. CRITICAL NEWS ALERTS (VETO POWER)
    # ============================================================
    critical_news = get_critical_news(news_data, portfolio.keys())
    if critical_news:
        lines.append(f"\n{'=' * 70}")
        lines.append("🔴 CRITICAL NEWS ALERTS (VETO POWER)")
        lines.append(f"{'=' * 70}")
        lines.append("RULE: Any stock with CRITICAL news MUST be evaluated for immediate REMOVAL.")
        for alert in critical_news:
            severity_icon = "🔴" if alert['severity'] == 'CRITICAL' else "🟠"
            lines.append(f"\n   {severity_icon} {alert['symbol']} [{alert['sentiment']:+d}]: {alert['title']}")
    
    # ============================================================
    # 4. CONCENTRATION RISK (HARD RULES)
    # ============================================================
    sector_weights, concentration_risks, hard_rule_violations, etf_total = get_concentration_risk(portfolio, etf_data)
    
    if concentration_risks or hard_rule_violations:
        lines.append(f"\n{'=' * 70}")
        lines.append("🚨 CONCENTRATION RISK (HARD RULES)")
        lines.append(f"{'=' * 70}")
        lines.append("\n   HARD RULES:")
        lines.append("   • MAX 30% per sector - exceeding = MUST REDUCE")
        lines.append("   • MAX 10% total ETF weight - exceeding = MUST REDUCE")
        lines.append(f"\n   Current ETF Total: {etf_total:.1f}% {'⚠️ EXCEEDS LIMIT!' if etf_total > 10 else '✅'}")
        
        if concentration_risks:
            lines.append("\n   ALERTS:")
            for risk in concentration_risks:
                lines.append(f"   {risk}")
        
        if hard_rule_violations:
            lines.append("\n   ⛔ REQUIRED ACTIONS:")
            for violation in hard_rule_violations:
                lines.append(f"   • {violation['action']}")
    
    # ============================================================
    # 5. SECTOR PERFORMANCE (Blacklist & Whitelist)
    # ============================================================
    sector_quant = get_sector_quant_data(etf_data)
    
    lines.append(f"\n{'=' * 70}")
    lines.append("🏭 SECTOR STATUS (2W / 1M / 3M + Quant Score)")
    lines.append(f"{'=' * 70}")
    
    all_sectors = set()
    for stock in etf_data.get('stocks', []):
        sec = stock.get('Category')
        if sec:
            all_sectors.add(sec)
    
    sector_health = {}
    weak_sectors = []
    strong_sectors = []
    disqualified_sectors = []
    
    for sector in sorted(all_sectors):
        perf = get_sector_performance(sector, etf_data, sector_quant)
        if perf:
            sector_health[sector] = perf
            
            if perf['disqualified']:
                status = "🚫 BLACKLISTED"
                disqualified_sectors.append(sector)
            elif perf['trend'] == "STRONG":
                status = "🟢 STRONG"
            elif perf['trend'] == "RECOVERING":
                status = "🟡 RECOVERING"
            elif perf['trend'] == "WEAKENING":
                status = "🟠 WEAKENING"
            else:
                status = "🔴 WEAK"
            
            lines.append(f"\n   {status} {sector}")
            lines.append(f"      Returns: 2W: {perf['avg_2w']:+.2f}% | 1M: {perf['avg_1m']:+.2f}% | 3M: {perf['avg_3m']:+.2f}%")
            lines.append(f"      Quant Score: {perf['quant_score']:.1f} | Health: {perf['health']}/5")
            
            if perf['disqualified']:
                lines.append(f"      ⛔ BLACKLISTED: {perf['disq_reason']}")
                weak_sectors.append(sector)
            elif perf['trend'] in ["WEAK", "WEAKENING"] or perf['health'] <= 2 or perf['quant_score'] < 50:
                weak_sectors.append(sector)
            if perf['trend'] == "STRONG" and perf['health'] >= 4 and perf['quant_score'] >= 70:
                strong_sectors.append(sector)
    
    # Sector Summary
    lines.append(f"\n   {'─' * 50}")
    lines.append(f"   ⛔ BLACKLIST (MUST SELL): {', '.join(disqualified_sectors) if disqualified_sectors else 'None'}")
    lines.append(f"   🔴 WEAK (Consider Exit): {', '.join([s for s in weak_sectors if s not in disqualified_sectors]) if weak_sectors else 'None'}")
    lines.append(f"   🟢 STRONG (Favor): {', '.join(strong_sectors) if strong_sectors else 'None'}")
    
    # Top 10 Quant Stocks
    rankings = etf_data.get('quant_rankings', {})
    top_stocks = rankings.get('top10_stocks', [])[:10]
    top_symbols = [s.get('symbol') for s in top_stocks if s.get('symbol')]
    
    if top_stocks:
        lines.append(f"\n🏆 TOP 10 QUANT STOCKS:")
        for i, s in enumerate(top_stocks, 1):
            sym = s.get('symbol') or 'N/A'
            scr = s.get('score') or 0
            sec = s.get('sector') or ''
            lines.append(f"   {i}. {sym:6} | Score: {scr:.1f} | {sec}")
    
    # Portfolio Detail
    lines.append(f"\n{'=' * 70}")
    lines.append("PORTFOLIO ASSETS (Weekly Trade Analysis - 2W/1M/3M)")
    lines.append(f"{'=' * 70}")
    
    for symbol, weight in sorted(portfolio.items(), key=lambda x: -x[1]):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"📌 {symbol} (Weight: {weight}%)")
        
        asset = get_stock_data(symbol, etf_data)
        if asset:
            data = asset['data']
            name = data.get('Name', symbol)
            sector = data.get('Category', 'N/A')
            
            w2 = data.get('2W', {}) or {}
            m1 = data.get('1M', {}) or {}
            m3 = data.get('3M', {}) or {}
            m6 = data.get('6M', {}) or {}
            
            ret_2w = w2.get('RETURN', 0) or 0
            ret_1m = m1.get('RETURN', 0) or 0
            ret_3m = m3.get('RETURN', 0) or 0
            ret_6m = m6.get('RETURN', 0) or 0
            
            # Asset Quant Score - stocks için SCORE, ETF'ler için QuantScore
            score = data.get('SCORE', 0) or data.get('QuantScore', 0) or 0
            
            # Short-term Trend (2W vs 1M)
            if ret_2w > 0 and ret_1m > 0:
                short_trend = "STRONG MOMENTUM ✅"
            elif ret_2w > 0 and ret_1m < 0:
                short_trend = "RECOVERING 🔄"
            elif ret_2w < 0 and ret_1m > 0:
                short_trend = "LOSING MOMENTUM ⚠️"
            else:
                short_trend = "WEAK ❌"
            
            # Medium-term Trend (1M vs 3M)
            if ret_1m > 0 and ret_3m > 0:
                med_trend = "UPTREND"
            elif ret_1m < 0 and ret_3m < 0:
                med_trend = "DOWNTREND"
            else:
                med_trend = "MIXED"
            
            in_top10 = symbol in top_symbols
            in_weak_sector = sector in weak_sectors
            in_strong_sector = sector in strong_sectors
            
            # ETF-specific check for disqualified sector exposure
            is_etf = asset['type'] == 'etf'
            subcat = data.get('SubCategory', '')
            etf_disq_warning = ""
            if is_etf:
                # Check if ETF category or subcategory matches disqualified/weak sectors
                if sector in disqualified_sectors or subcat in disqualified_sectors:
                    etf_disq_warning = f"🚫 ETF EXPOSED TO DISQUALIFIED SECTOR ({sector}/{subcat}) - MUST REPLACE OR REMOVE!"
                elif sector in weak_sectors or subcat in weak_sectors:
                    etf_disq_warning = f"⚠️ ETF exposed to WEAK sector ({sector}/{subcat}) - consider replacement"
            
            # Display asset info
            if is_etf:
                lines.append(f"   📊 ETF | Category: {sector} | SubCategory: {subcat}")
                lines.append(f"   ETF Quant Score: {score:.1f}")
            else:
                lines.append(f"   Name: {name} | Sector: {sector}")
                lines.append(f"   Asset Quant Score: {score:.1f} | In Top 10: {'YES ✅' if in_top10 else 'NO'}")
            
            lines.append(f"   SHORT-TERM: 2W: {ret_2w:+.2f}% | 1M: {ret_1m:+.2f}% → {short_trend}")
            lines.append(f"   MEDIUM-TERM: 3M: {ret_3m:+.2f}% | 6M: {ret_6m:+.2f}% → {med_trend}")
            
            # ETF disqualified sector warning (priority)
            if etf_disq_warning:
                lines.append(f"   {etf_disq_warning}")
            # Sector warning
            elif in_weak_sector:
                lines.append(f"   ⚠️ WARNING: {sector} sector is WEAK - consider reducing exposure!")
            elif in_strong_sector:
                lines.append(f"   ✅ TAILWIND: {sector} sector is STRONG")
            
            # Sector perf
            sec_perf = sector_health.get(sector)
            if sec_perf:
                disq_warn = " ⚠️ DISQUALIFIED!" if sec_perf.get('disqualified') else ""
                lines.append(f"   Sector: Quant {sec_perf['quant_score']:.1f} | 2W: {sec_perf['avg_2w']:+.2f}% | 1M: {sec_perf['avg_1m']:+.2f}% | Health: {sec_perf['health']}/5{disq_warn}")
        
        # Sentiment
        sent = get_sentiment_data(symbol, news_data)
        if sent:
            lines.append(f"   Sentiment: {sent['total']:+d} ({sent['count']} news)")
            for h in sent['headlines'][:2]:
                lines.append(f"      [{h['sentiment']:+d}] {h['title'][:60]}...")
        else:
            lines.append(f"   Sentiment: No news")
    
    # Current sector allocation for replacement guidance
    lines.append(f"\n{'=' * 70}")
    lines.append("📊 CURRENT SECTOR ALLOCATION (for replacement guidance)")
    lines.append(f"{'=' * 70}")
    lines.append("   RULE: Max 30% per sector | Replacement should diversify to underweight sectors")
    
    for sec, weight in sorted(sector_weights.items(), key=lambda x: -x[1]):
        if sec != 'ETF':
            status = "🔴 OVERWEIGHT" if weight > 30 else "🟠 HIGH" if weight > 20 else "🟢 OK" if weight > 10 else "⚪ UNDERWEIGHT"
            lines.append(f"   {sec:20} {weight:5.1f}% {status}")
    
    lines.append(f"   {'─' * 40}")
    lines.append(f"   Total ETF:          {etf_total:5.1f}% {'🔴 EXCEEDS 10%' if etf_total > 10 else '✅'}")
    
    # Alternatives with detailed info
    lines.append(f"\n{'=' * 70}")
    lines.append("🎯 ALTERNATIVE CANDIDATES (for replacements)")
    lines.append(f"{'=' * 70}")
    lines.append("   Selection Criteria: Score ≥75, Sector Health ≥3, STRONG/RECOVERING momentum")
    lines.append("   Priority: Underweight sectors > Neutral sectors > Never from overweight")
    
    overweight_sectors = [s for s, w in sector_weights.items() if w > 30 and s != 'ETF']
    underweight_sectors = [s for s, w in sector_weights.items() if w < 15 and s != 'ETF']
    
    for s in top_stocks:
        sym = s.get('symbol') or 'N/A'
        if sym not in portfolio and sym != 'N/A':
            scr = s.get('score') or 0
            sec = s.get('sector') or ''
            
            # Get stock data for momentum
            stock_data = get_stock_data(sym, etf_data)
            momentum_str = ""
            if stock_data:
                data = stock_data['data']
                w2 = data.get('2W', {}) or {}
                m1 = data.get('1M', {}) or {}
                ret_2w = w2.get('RETURN', 0) or 0
                ret_1m = m1.get('RETURN', 0) or 0
                
                if ret_2w > 0 and ret_1m > 0:
                    momentum_str = "STRONG ✅"
                elif ret_2w > 0:
                    momentum_str = "RECOVERING 🔄"
                elif ret_2w < 0 and ret_1m < 0:
                    momentum_str = "WEAK ❌"
                else:
                    momentum_str = "MIXED"
                
                momentum_str += f" (2W:{ret_2w:+.1f}%, 1M:{ret_1m:+.1f}%)"
            
            # Sector health
            sec_perf = sector_health.get(sec, {})
            sec_health_score = sec_perf.get('health', 0) if sec_perf else 0
            
            # Diversification tag
            if sec in overweight_sectors:
                div_tag = "⛔ SAME OVERWEIGHT"
            elif sec in underweight_sectors:
                div_tag = "✅ DIVERSIFIES"
            elif sec in weak_sectors:
                div_tag = "⚠️ WEAK SECTOR"
            elif sec in strong_sectors:
                div_tag = "🟢 STRONG SECTOR"
            else:
                div_tag = ""
            
            sent = get_sentiment_data(sym, news_data)
            sent_str = f"Sent:{sent['total']:+d}" if sent else ""
            
            lines.append(f"\n   {sym:6} | Score: {scr:.1f} | {sec}")
            lines.append(f"          Momentum: {momentum_str}")
            lines.append(f"          Sector Health: {sec_health_score}/5 | {sent_str} {div_tag}")
    
    # ETF Alternatives (for ETF replacement)
    lines.append(f"\n{'=' * 70}")
    lines.append("📈 ETF ALTERNATIVES (for ETF replacement if needed)")
    lines.append(f"{'=' * 70}")
    lines.append("   Criteria: Category NOT disqualified, 2W>0, 1M>0, 3M>0, QuantScore≥70")
    
    etfs = etf_data.get('etfs', [])
    qualified_etfs = []
    
    for etf in etfs:
        sym = etf.get('Symbol', '')
        if sym in portfolio:  # Skip if already in portfolio
            continue
        
        cat = etf.get('Category', '')
        subcat = etf.get('SubCategory', '')
        qscore = etf.get('QuantScore', 0) or 0
        
        # Skip if category matches weak/disqualified sectors
        if cat in weak_sectors or cat in disqualified_sectors:
            continue
        if subcat in weak_sectors or subcat in disqualified_sectors:
            continue
        
        # Get returns
        w2 = etf.get('2W', {}) or {}
        m1 = etf.get('1M', {}) or {}
        m3 = etf.get('3M', {}) or {}
        
        ret_2w = w2.get('RETURN', 0) or 0
        ret_1m = m1.get('RETURN', 0) or 0
        ret_3m = m3.get('RETURN', 0) or 0
        
        # Must have strong momentum (all positive) and good score
        if ret_2w > 0 and ret_1m > 0 and ret_3m > 0 and qscore >= 70:
            qualified_etfs.append({
                'symbol': sym,
                'name': etf.get('Name', ''),
                'category': cat,
                'subcategory': subcat,
                'score': qscore,
                'ret_2w': ret_2w,
                'ret_1m': ret_1m,
                'ret_3m': ret_3m
            })
    
    # Sort by score
    qualified_etfs.sort(key=lambda x: -x['score'])
    
    if qualified_etfs:
        for etf in qualified_etfs[:5]:  # Top 5
            lines.append(f"\n   {etf['symbol']:6} | Score: {etf['score']:.1f} | {etf['category']}/{etf['subcategory']}")
            lines.append(f"          {etf['name']}")
            lines.append(f"          Momentum: 2W:{etf['ret_2w']:+.1f}%, 1M:{etf['ret_1m']:+.1f}%, 3M:{etf['ret_3m']:+.1f}% ✅ ALL POSITIVE")
    else:
        lines.append("\n   ⚠️ No qualified ETF alternatives found - redistribute to stocks if ETF removal needed")
    
    return "\n".join(lines)

# ============================================================
# GPT ANALYSIS
# ============================================================
SYSTEM_PROMPT = """ROLE: Senior Risk Manager for Weekly Swing Trading Portfolio
OBJECTIVE: Preserve capital FIRST, generate alpha SECOND. Be DECISIVE.

🚫 ABSOLUTE CONSTRAINTS (MATHEMATICAL REQUIREMENT):

1. TOTAL WEIGHT = 100%:
   - Sum of ALL new_weight values MUST equal EXACTLY 100.0%
   - This is NON-NEGOTIABLE. Double-check your math before responding.
   - If you REDUCE a position by X%, you MUST add X% to other positions.
   - If you REMOVE a position (new_weight=0), its ENTIRE weight MUST go elsewhere.

2. NO CASH / NO MISSING WEIGHT:
   - Portfolio must be FULLY INVESTED at all times.
   - Every percentage point must be allocated to a stock or ETF.
   - "Cash" is NOT a valid allocation.

3. WEIGHT REDISTRIBUTION RULES:
   - When REDUCING: Add the reduced amount to KEEP or INCREASE positions
   - When REMOVING: Either add a REPLACEMENT stock OR distribute weight to existing positions
   - Prefer adding to: Top 10 stocks > Strong sector stocks > Existing KEEP positions

4. REPLACEMENT REQUIREMENT:
   - If decision = "REMOVE", you MUST either:
     a) Provide a "replacement" with symbol from ALTERNATIVE CANDIDATES, OR
     b) Explicitly redistribute weight to other positions (increase their new_weight)
   - replacement = null is ONLY allowed if weight is redistributed to other assets

5. VALIDATION CHECK (Do this before outputting):
   - Add up all new_weight values: SUM = ?
   - If SUM ≠ 100.0, STOP and fix it before outputting

📝 EXAMPLE - How to handle REDUCE and REMOVE:

INPUT Portfolio (100%):
  BMY: 18%, C: 17%, SKYY: 5%, Others: 60% = 100%

DECISIONS:
  - C: REDUCE from 17% → 12% (freed: 5%)
  - SKYY: REMOVE 5% → 0% (freed: 5%)
  - Total freed: 10%

OUTPUT (must still = 100%):
  BMY: 18% → 23% (INCREASE, +5%)
  C: 17% → 12% (REDUCE, -5%)
  SKYY: 5% → 0% (REMOVE, -5%)
  NEW_STOCK: 0% → 5% (NEW from alternatives)
  Others: 60% → 60% (KEEP)
  TOTAL: 23 + 12 + 0 + 5 + 60 = 100% ✅

🛡️ CONSERVATIVE CHANGE RULES (VERY IMPORTANT):

1. MAXIMUM POSITION SIZE: 25%
   - NO single stock can exceed 25% of portfolio
   - If redistribution would push a stock above 25%, spread to multiple stocks instead

2. MAXIMUM WEIGHT CHANGE PER STOCK: ±10%
   - Do NOT increase any stock by more than 10% in a single review
   - Example: If BMY is 18%, max new_weight is 28% (not 40%!)
   - Spread large redistributions across multiple KEEP/INCREASE positions

3. SECTOR CONCENTRATION FIX = REDUCE, NOT REMOVE:
   - If Financials at 43%, goal is to bring it to ~30%
   - REDUCE multiple positions proportionally, do NOT remove all
   - Example: C 17%→12%, GS 11%→8%, USB 7%→5% = total reduction 10%
   - NEVER remove a stock with STRONG momentum just for concentration

4. PREFER REDUCE OVER REMOVE:
   - REMOVE only for: Blacklisted sector, Critical news (< -40), WEAK momentum (2W<0 AND 1M<0)
   - For concentration issues: use REDUCE
   - KEEP as many diversified positions as possible

5. PROPORTIONAL REDISTRIBUTION:
   - When reducing/removing X%, distribute proportionally to multiple stocks
   - Prefer: Underweight sectors > Strong momentum > Top 10 candidates
   - Example: If freeing 15%, distribute as: +5% to 3 different stocks, not +15% to 1 stock

⚠️ HARD RULES (MUST FOLLOW - No Exceptions):

1. BLACKLISTED SECTORS:
   - If sector is marked "BLACKLISTED" or "DISQUALIFIED" → decision MUST be "REMOVE"
   - No exceptions. Do not argue. Just REMOVE.

2. CRITICAL NEWS VETO (Only for REAL news, not sector issues):
   - ONLY applies when: A stock has actual negative NEWS with sentiment < -40
   - In critical_alerts, format as: "STOCK: [symbol] critical news (sentiment -XX)"
   - Do NOT use "critical news" for ETF sector exposure or blacklisted sectors
   - Bad news overrides good technicals in short-term

3. ETF BLACKLISTED SECTOR EXPOSURE:
   - If ETF's sector/category is BLACKLISTED → MUST REMOVE
   - In critical_alerts, format as: "ETF: [symbol] exposed to blacklisted [sector] sector"
   - This is NOT "critical news" - it's sector exposure issue

4. MARKET REGIME COMPLIANCE:
   - If RISK_LEVEL = "HIGH_ALERT" → Be more conservative, prefer defensive sectors
   - If RISK_LEVEL = "ROTATION" → Reduce weak sector exposure

5. SECTOR HEALTH THRESHOLD:
   - Sector Health ≤ 2 → REDUCE or REMOVE (no KEEP)
   - Sector Quant < 50 → REDUCE exposure

6. SECTOR CONCENTRATION (MAX 30%):
   - If any single sector weight > 30% → MUST REDUCE (not REMOVE!) stocks in that sector
   - Target: Bring sector to ~28-30%, not eliminate entirely
   - REDUCE proportionally from multiple stocks in the sector
   - In "reasoning", cite: "Sector concentration X% exceeds 30% limit → REDUCE by Y%"

7. ETF CONCENTRATION (MAX 10%):
   - If total ETF weight > 10% → MUST REDUCE ETF positions
   - Prioritize reducing lowest-performing ETFs first
   - In "reasoning", cite: "Total ETF weight X% exceeds 10% limit"

8. ETF SECTOR QUALITY:
   - If ETF's Category/SubCategory matches a DISQUALIFIED or WEAK sector → MUST REMOVE or REPLACE
   - Replacement ETF criteria (ALL must be met):
     * Category NOT in disqualified/weak sectors
     * STRONG momentum: 2W > 0 AND 1M > 0 AND 3M > 0
     * QuantScore ≥ 70
   - If no qualified ETF replacement available → REMOVE and redistribute to stocks

9. WEAK MOMENTUM = REMOVE TRIGGER:
   - ONLY remove stocks where: 2W < 0 AND (1M < 0 OR 3M < 0)
   - If 2W < 0 but 1M > 0 and 3M > 0 → REDUCE, not REMOVE (temporary dip)

ANALYSIS FRAMEWORK:

1. SHORT-TERM MOMENTUM (2W vs 1M):
   - STRONG: Both 2W and 1M positive → OK to KEEP/INCREASE
   - RECOVERING: 2W positive, 1M negative → Cautious KEEP
   - WEAKENING: 2W negative, 1M positive → Consider REDUCE
   - WEAK: Both negative → MUST REMOVE

2. MEDIUM-TERM TREND (1M vs 3M):
   - UPTREND: Both positive → Supportive
   - DOWNTREND: Both negative → Negative bias
   - MIXED: Conflicting → Neutral

3. SECTOR HEALTH (0-5 scale):
   - Health 4-5: Strong tailwind
   - Health 2-3: Neutral
   - Health 0-1: Strong headwind → AVOID

4. QUANT SCORE:
   - Top 10: Strong buy signal
   - >80: Good
   - 70-80: Acceptable
   - <70: Weak

DECISION MATRIX:
- KEEP: Strong/Recovering momentum AND Sector Health ≥ 3 AND Score ≥ 70
- INCREASE: Top 10 AND Strong momentum AND Strong sector (Health ≥ 4)
- REDUCE: Weakening momentum OR Sector Health = 2 OR mixed signals
- REMOVE: BLACKLISTED sector OR Weak momentum OR Sector Health ≤ 1 OR Critical news

CRITICAL: In "reasoning" field, you MUST cite ALL relevant numbers for a convincing analysis:
- Momentum: "2W: +X.X%, 1M: +Y.Y%, 3M: +Z.Z% → [STRONG/WEAK/RECOVERING] momentum"
- Sector: "Sector Health: X/5, Sector Quant: YY → [STRONG/WEAK] sector support"
- Asset Score: "Quant Score: XX → [above/below] threshold"
- Hard Rule: "HARD RULE: [rule name] triggered → MUST [action]"
- Concentration: "Sector at XX% (>30% limit) → MUST REDUCE"

REASONING EXAMPLES:
- KEEP: "Strong momentum (2W: +5.8%, 1M: +19.0%, 3M: +23.4%), excellent sector health (5/5, Quant: 84), asset score 85 in Top 10. KEEP position."
- REMOVE: "WEAK momentum (2W: -0.3%, 1M: +7.8%, 3M: -2.3%) with deteriorating trend. ETF exposed to weak sector. HARD RULE: WEAK_MOMENTUM triggered. REMOVE and redistribute."
- REDUCE: "Strong momentum but Financials sector at 43% exceeds 30% limit. HARD RULE: SECTOR_CONCENTRATION. REDUCE by 5% to diversify."

OUTPUT FORMAT (JSON only, no markdown):
{
  "review_date": "YYYY-MM-DD",
  "risk_level": "NORMAL/CAUTION/ROTATION/HIGH_ALERT/RISK_ON",
  "market_regime": "ROTATION/RISK-ON/RISK-OFF/CAUTION/BULL/BEAR",
  "regime_analysis": "1-2 sentence explaining how market regime affects decisions",
  "hard_rules_applied": ["BLACKLISTED sector removal", "Sector concentration fix"],
  "critical_alerts": [
    "STOCK: Critical news (sentiment -60)",
    "SECTOR: Technology blacklisted", 
    "ETF: SKYY exposed to blacklisted Technology sector"
  ],
  "disqualified_sectors": ["Sector1"],
  "weak_sectors": ["Sector2", "Sector3"],
  "strong_sectors": ["Sector4", "Sector5"],
  "portfolio_score": 75,
  "total_new_weight": 100.0,
  "weight_changes": {
    "reduced": 12.5,
    "increased": 10.0,
    "new_positions": 2.5
  },
  "assets": [
    {
      "symbol": "XXX",
      "name": "Full Name",
      "sector": "Sector",
      "sub_category": "SubCategory (for ETFs)",
      "is_etf": false,
      "current_weight": 18.0,
      "decision": "KEEP/REMOVE/REDUCE/INCREASE",
      "new_weight": 18.0,
      "weight_change": 0.0,
      "score": 85.5,
      "asset_score": 85.5,
      "return_2w": 2.5,
      "return_1m": 4.1,
      "return_3m": 8.2,
      "short_term_trend": "STRONG/RECOVERING/WEAKENING/WEAK/LOSING",
      "medium_term_trend": "UPTREND/DOWNTREND/MIXED",
      "sentiment": 45,
      "sector_health": 4,
      "sector_quant_score": 79.4,
      "sector_disqualified": false,
      "sector_trend": "STRONG/WEAK/WEAKENING/RECOVERING",
      "in_top10": true,
      "hard_rule_triggered": null or "BLACKLISTED_SECTOR/CRITICAL_NEWS/WEAK_MOMENTUM/SECTOR_CONCENTRATION/ETF_CONCENTRATION/ETF_BLACKLISTED_SECTOR",
      "reasoning": "DETAILED reasoning with ALL numbers cited. See examples above.",
      "replacement": null or {"symbol": "YYY", "score": 90.1, "reason": "Better momentum + stronger sector"}
    }
  ],
  "new_positions": [
    {
      "symbol": "NEW_STOCK",
      "name": "New Stock Full Name",
      "sector": "Sector Name",
      "is_etf": false,
      "new_weight": 5.0,
      "score": 88.5,
      "return_2w": 2.5,
      "return_1m": 5.0,
      "return_3m": 8.0,
      "short_term_trend": "STRONG",
      "medium_term_trend": "UPTREND",
      "sector_health": 4,
      "sector_quant_score": 79.0,
      "sentiment": 0,
      "reason": "Replacement for REMOVED stock. Momentum: 2W +2.5%, 1M +5.0%. Diversifies to underweight Consumer Staples sector."
    }
  ],
  "removals": [
    {
      "remove": "OLD",
      "replace_with": "NEW or REDISTRIBUTED",
      "weight_redistributed_to": ["BMY +2%", "FDX +3%"],
      "reason": "Cite HARD RULE if applicable"
    }
  ],
  "sector_allocation": {"Financials": 28.0, "Industrials": 22.0, "Healthcare": 20.0},
  "summary": "3-4 sentence executive summary. Start with regime impact, then key actions. END with: Total: 100.0%"
}

⚠️ CRITICAL VALIDATION:
Before outputting, verify: sum of all new_weight = 100.0
If not 100.0, ADJUST positions until it equals exactly 100.0!

REPLACEMENT SELECTION CRITERIA (Priority Order):

1. SECTOR DIVERSIFICATION (Highest Priority):
   - If removing from overweight sector (>30%), replacement MUST be from underweight sector
   - NEVER suggest replacement from same overweight sector
   - Prefer sectors with <15% current weight

2. QUANT SCORE:
   - Replacement must have Score ≥ 75 (prefer Top 10)
   - Replacement score should be HIGHER than removed stock's score

3. SECTOR HEALTH:
   - Replacement sector Health must be ≥ 3/5
   - NEVER suggest replacement from WEAK or BLACKLISTED sector
   - Prefer STRONG sectors (Health ≥ 4)

4. MOMENTUM ALIGNMENT:
   - Replacement should have STRONG or RECOVERING momentum (2W > 0)
   - Avoid WEAK momentum replacements (2W < 0 AND 1M < 0)

5. SENTIMENT:
   - Prefer positive or neutral sentiment
   - Avoid stocks with negative sentiment (< -20)

6. ETF vs STOCK:
   - If ETF total > 10%, do NOT suggest ETF as replacement
   - Prefer individual stocks for better alpha potential

REPLACEMENT REASONING FORMAT:
"Replace [OLD] (Score: X, [Sector] at Y%) with [NEW] (Score: Z, [Sector] at W%) - diversifies from overweight [Sector], stronger momentum (2W: +A%, 1M: +B%), sector health 4/5"

⚠️ CRITICAL REMINDERS - READ CAREFULLY:

1. CONSERVATIVE LIMITS (ENFORCED BY POST-PROCESSING):
   - MAX position: 25% (no stock can exceed this)
   - MAX change: ±10% per stock per review
   - MAX sector: 30%
   - System will auto-cap violations, so follow these to avoid unexpected adjustments

2. WEIGHT MATH:
   - Calculate: sum of all new_weight values
   - If sum ≠ 100.0, FIX IT before responding
   - Example: If you REDUCE C from 17.3% to 12.3%, that's -5.0% that MUST go somewhere else

3. REDISTRIBUTION:
   - Spread freed weight across MULTIPLE positions (not all to one)
   - Example: If freeing 15%, do +5% to 3 stocks, NOT +15% to 1 stock
   - Prefer underweight sectors for redistribution

4. REMOVE vs REDUCE:
   - REMOVE only: Blacklisted sector, Critical news, WEAK momentum (2W<0 AND 1M<0)
   - REDUCE for: Sector concentration, mild weakness
   - For concentration: REDUCE proportionally, don't eliminate positions

5. VALIDATION BEFORE OUTPUT:
   - Check: No position > 25%
   - Check: No change > ±10%
   - Check: Total = 100%
"""

def validate_and_fix_weights(result, etf_data=None):
    """
    Post-process GPT output to ensure:
    1. Total weight = 100%
    2. No single position > 25%
    3. No single change > 10%
    4. No sector > 30%
    """
    assets = result.get('assets', [])
    if not assets:
        return result
    
    # STEP 1: Enforce max position size (25%) and max change (10%)
    print(f"   🔒 Checking position limits...")
    for asset in assets:
        symbol = asset.get('symbol', '')
        current = asset.get('current_weight', 0) or 0
        new = asset.get('new_weight', 0) if isinstance(asset.get('new_weight'), (int, float)) else current
        
        # Max position size: 25%
        if new > 25:
            print(f"      ⚠️ {symbol}: {new:.1f}% exceeds 25% max → capping to 25%")
            asset['new_weight'] = 25.0
            asset['weight_change'] = 25.0 - current
            new = 25.0
        
        # Max change: ±10%
        change = new - current
        if change > 10:
            print(f"      ⚠️ {symbol}: +{change:.1f}% exceeds +10% max change → capping")
            asset['new_weight'] = round(current + 10, 1)
            asset['weight_change'] = 10.0
        elif change < -10 and asset.get('decision', '').upper() != 'REMOVE':
            # Allow REMOVE to go to 0, but REDUCE should not exceed -10%
            print(f"      ⚠️ {symbol}: {change:.1f}% exceeds -10% max change → adjusting")
            asset['new_weight'] = round(current - 10, 1)
            asset['weight_change'] = -10.0
    
    # Calculate total new_weight from assets
    total = sum(a.get('new_weight', 0) or 0 for a in assets)
    
    # Add new_positions if present
    new_positions = result.get('new_positions', [])
    for np in new_positions:
        total += np.get('new_weight', 0) or 0
    
    print(f"   📊 Weight validation: Total = {total:.1f}%")
    
    if abs(total - 100.0) < 0.1:
        result['total_new_weight'] = 100.0
        print(f"   ✅ Weight OK: {total:.1f}%")
        # Sync removals even when weight is OK
        result = sync_removals_with_decisions(result)
        return result
    
    # Need to fix
    diff = 100.0 - total
    print(f"   ⚠️ Weight mismatch! Missing: {diff:+.1f}%")
    
    if diff > 0:
        # Under 100% - distribute to KEEP/INCREASE positions proportionally
        eligible = [a for a in assets 
                    if a.get('decision') in ['KEEP', 'INCREASE'] 
                    and (a.get('new_weight', 0) or 0) > 0]
        
        if not eligible:
            # Fallback: use any position with weight > 0
            eligible = [a for a in assets if (a.get('new_weight', 0) or 0) > 0]
        
        if eligible:
            # Calculate total eligible weight
            eligible_total = sum(a.get('new_weight', 0) or 0 for a in eligible)
            
            print(f"   📊 Distributing {diff:.1f}% to {len(eligible)} positions")
            
            distributed = 0
            for i, a in enumerate(eligible):
                current = a.get('new_weight', 0) or 0
                # Proportional share
                share = (current / eligible_total) * diff if eligible_total > 0 else diff / len(eligible)
                
                # Last one gets remainder to ensure exactly 100%
                if i == len(eligible) - 1:
                    share = diff - distributed
                
                new_weight = round(current + share, 1)
                
                # Update in assets list
                for asset in assets:
                    if asset.get('symbol') == a.get('symbol'):
                        old_decision = asset.get('decision', 'KEEP')
                        asset['new_weight'] = new_weight
                        asset['weight_change'] = round(new_weight - asset.get('current_weight', 0), 1)
                        
                        # Update decision if significantly increased
                        if asset['weight_change'] > 2:
                            asset['decision'] = 'INCREASE'
                        
                        print(f"      {a['symbol']}: {current:.1f}% → {new_weight:.1f}% (+{share:.1f}%)")
                        distributed += share
                        break
    else:
        # Over 100% - reduce proportionally from largest positions
        diff = abs(diff)
        sorted_assets = sorted(assets, key=lambda x: -(x.get('new_weight', 0) or 0))
        
        distributed = 0
        for i, a in enumerate(sorted_assets[:3]):  # Top 3 positions
            current = a.get('new_weight', 0) or 0
            share = min(current * 0.1, diff - distributed)  # Max 10% reduction each
            
            if i == 2 or distributed + share >= diff:
                share = diff - distributed
            
            new_weight = round(current - share, 1)
            
            for asset in assets:
                if asset.get('symbol') == a.get('symbol'):
                    asset['new_weight'] = new_weight
                    asset['weight_change'] = round(new_weight - asset.get('current_weight', 0), 1)
                    print(f"      {a['symbol']}: {current:.1f}% → {new_weight:.1f}% (-{share:.1f}%)")
                    distributed += share
                    break
            
            if distributed >= diff:
                break
    
    # Recalculate final total
    new_total = sum(a.get('new_weight', 0) or 0 for a in assets)
    for np in new_positions:
        new_total += np.get('new_weight', 0) or 0
    
    result['total_new_weight'] = round(new_total, 1)
    result['weight_adjusted'] = True
    result['adjustment_note'] = f"Auto-adjusted {diff:+.1f}% to reach 100%"
    
    print(f"   ✅ Adjusted total: {result['total_new_weight']}%")
    
    # Final validation
    if abs(result['total_new_weight'] - 100.0) > 0.5:
        print(f"   ❌ WARNING: Still not 100%! Manual review needed.")
    
    # Sync removals with REMOVE decisions
    result = sync_removals_with_decisions(result)
    
    return result

def sync_removals_with_decisions(result):
    """
    Ensure all REMOVE decisions appear in removals list.
    GPT sometimes forgets to add all removals.
    """
    assets = result.get('assets', [])
    removals = result.get('removals', [])
    new_positions = result.get('new_positions', [])
    
    # Get existing removal symbols
    existing_removals = set(r.get('remove', '') for r in removals)
    
    # Find all REMOVE decisions
    remove_assets = [a for a in assets if a.get('decision', '').upper() == 'REMOVE']
    
    # Get new position symbols for replacement matching
    new_pos_symbols = [np.get('symbol', '') for np in new_positions]
    
    # Add missing removals
    for asset in remove_assets:
        symbol = asset.get('symbol', '')
        if symbol and symbol not in existing_removals:
            # Determine replacement
            replacement = asset.get('replacement')
            replace_with = None
            
            if replacement:
                replace_with = replacement.get('symbol', 'REDISTRIBUTED')
            elif new_pos_symbols:
                replace_with = new_pos_symbols[0]  # Use first new position
            else:
                replace_with = 'REDISTRIBUTED'
            
            # Create removal entry
            new_removal = {
                'remove': symbol,
                'replace_with': replace_with,
                'weight_redistributed_to': [],
                'reason': asset.get('reasoning', 'See analysis above')
            }
            
            # Find where weight was redistributed (INCREASE decisions)
            increases = [a for a in assets if a.get('decision', '').upper() == 'INCREASE']
            for inc in increases:
                weight_change = inc.get('weight_change', 0)
                if weight_change > 0:
                    new_removal['weight_redistributed_to'].append(
                        f"{inc.get('symbol')} +{weight_change:.1f}%"
                    )
            
            # Add new positions to redistribution
            for np in new_positions:
                new_removal['weight_redistributed_to'].append(
                    f"{np.get('symbol')} +{np.get('new_weight', 0):.1f}% (NEW)"
                )
            
            removals.append(new_removal)
            print(f"   📝 Added missing removal: {symbol} → {replace_with}")
    
    result['removals'] = removals
    return result

def analyze_portfolio(prompt_data, client, retries=3):
    print(f"   📝 Prompt size: {len(prompt_data)} chars")
    
    for attempt in range(retries):
        try:
            print(f"   🔄 Attempt {attempt + 1}/{retries}...")
            
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{prompt_data}\n\nReturn ONLY valid JSON, no markdown."}
                ],
                max_completion_tokens=16000
            )
            
            # Debug: Full response info
            print(f"   📊 Response object: choices={len(response.choices)}")
            if response.choices:
                choice = response.choices[0]
                print(f"   📊 Finish reason: {choice.finish_reason}")
                print(f"   📊 Message role: {choice.message.role if choice.message else 'None'}")
            
            if response.usage:
                print(f"   📊 Usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
            
            content = response.choices[0].message.content
            
            # Debug: Yanıtı göster
            print(f"   📥 Response length: {len(content) if content else 0}")
            
            if not content:
                print("   ❌ Empty response from GPT!")
                print(f"   📊 Full message: {response.choices[0].message}")
                if attempt < retries - 1:
                    import time
                    time.sleep(3)
                    continue
                raise ValueError("GPT returned empty response")
            
            content = content.strip()
            
            # Debug: İlk 200 karakter
            print(f"   📄 Response preview: {content[:200]}...")
            
            # Markdown temizle
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()
            
            # JSON başlangıcını bul
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start == -1 or json_end == -1:
                print(f"   ❌ No JSON found in response!")
                if attempt < retries - 1:
                    import time
                    time.sleep(2)
                    continue
                raise ValueError("No valid JSON in response")
            
            content = content[json_start:json_end+1]
            
            result = json.loads(content)
            
            # POST-PROCESSING: Validate and fix total weight
            result = validate_and_fix_weights(result)
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parse error: {e}")
            if attempt < retries - 1:
                import time
                time.sleep(2)
                continue
            raise
        except Exception as e:
            print(f"   ❌ Error: {e}")
            if attempt < retries - 1:
                import time
                time.sleep(2)
                continue
            raise
    
    raise ValueError("All retries failed")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("📊 Weekly Portfolio Review v1.2")
    print(f"   Model: {MODEL}")
    print("=" * 60)
    
    # Load portfolio from txt
    print(f"\n📂 Loading portfolio from {PORTFOLIO_FILE}...")
    portfolio = load_portfolio()
    
    if not portfolio:
        print("❌ Portfolio boş veya yüklenemedi!")
        return
    
    print(f"✅ {PORTFOLIO_FILE} | {len(portfolio)} assets | Total: {sum(portfolio.values()):.1f}%")
    for sym, wgt in sorted(portfolio.items(), key=lambda x: -x[1]):
        print(f"   {sym:6} {wgt:5.1f}%")
    
    # Load data
    etf_data = load_json('etf_data.json')
    news_data = load_json('news_data.json')
    
    if not etf_data:
        print("❌ etf_data.json required!")
        return
    
    print(f"\n✅ etf_data.json | Regime: {etf_data.get('regime', {}).get('overall', 'N/A')}")
    if news_data:
        print(f"✅ news_data.json | {news_data.get('news_count', 0)} news")
    
    # API check
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set!")
        return
    
    client = OpenAI(api_key=api_key)
    print(f"✅ OpenAI connected")
    
    # Build & Analyze
    print(f"\n🤖 Analyzing...")
    prompt = build_analysis_prompt(portfolio, etf_data, news_data)
    
    try:
        analysis = analyze_portfolio(prompt, client)
        
        # Add metadata
        analysis['generated_at'] = datetime.now().isoformat()
        analysis['model'] = MODEL
        analysis['portfolio_input'] = portfolio
        
        # Save
        with open('portfolio_review.json', 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved: portfolio_review.json")
        
        # Summary
        print(f"\n{'=' * 60}")
        decisions = {}
        for a in analysis.get('assets', []):
            d = a.get('decision', 'KEEP')
            decisions[d] = decisions.get(d, 0) + 1
        
        for d, c in decisions.items():
            icon = "✅" if d == "KEEP" else "❌" if d == "REMOVE" else "⚠️"
            print(f"   {icon} {d}: {c}")
        
        print(f"\n{analysis.get('summary', '')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
