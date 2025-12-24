#!/usr/bin/env python3
"""
WEEKLY PORTFOLIO REVIEW v2.0
Python-Driven Decision Engine

Tüm kararlar Python tarafından alınır.
GPT sadece yorum/reasoning için kullanılır.

Author: Navimod
Date: 2024
"""

import json
import os
from datetime import datetime
from collections import Counter
from statistics import mean

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = {
    # Position Limits
    'MAX_POSITION': 25.0,        # Tek varlık max ağırlık %
    'MAX_CHANGE': 10.0,          # Tek seferde max değişim %
    'MIN_POSITION': 0.5,         # Min pozisyon %
    
    # Sector Limits
    'MAX_SECTOR': 30.0,          # Tek sektör max ağırlık %
    
    # ETF Limits
    'MAX_ETF_TOTAL': 10.0,       # Toplam ETF max ağırlık %
    'MAX_ETF_SINGLE': 5.0,       # Tek ETF max ağırlık %
    
    # New Position
    'MIN_NEW_POSITION': 2.0,     # Yeni pozisyon min ağırlık %
    'MAX_NEW_POSITIONS': 10,     # Max yeni pozisyon sayısı
    
    # Candidate Criteria
    'MIN_SCORE': 70,             # Aday için min skor
    'MIN_SECTOR_HEALTH': 3,      # Aday sektör için min health
    
    # Momentum Thresholds
    'CRITICAL_SENTIMENT': -50,   # Bu altında REMOVE
    
    # Reduce Percentages
    'LOSING_MOMENTUM_REDUCE': 0.20,  # Losing momentum'da %20 azalt
}

# Known ETF symbols
ETF_SYMBOLS = {
    'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'VEA', 'VWO',
    'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLP', 'XLY', 'XLB', 'XLU', 'XLRE', 'XLC',
    'SKYY', 'XBI', 'IBB', 'ARKK', 'ARKG',
    'GLD', 'SLV', 'USO', 'UNG',
    'TLT', 'IEF', 'SHY', 'BND', 'AGG',
    'VNQ', 'IYR'
}

# Model for GPT commentary
MODEL = "gpt-5-mini"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def classify_momentum(ret_2w, ret_1m, ret_3m=0):
    """
    Momentum sınıflandırması.
    
    Returns:
        STRONG: 2W > 0 AND 1M > 0
        RECOVERING: 2W > 0 AND 1M < 0
        LOSING: 2W < 0 AND 1M > 0
        WEAK: 2W < 0 AND 1M < 0
    """
    if ret_2w > 0 and ret_1m > 0:
        return 'STRONG'
    elif ret_2w > 0 and ret_1m < 0:
        return 'RECOVERING'
    elif ret_2w < 0 and ret_1m > 0:
        return 'LOSING'
    else:
        return 'WEAK'


def calculate_sector_health_from_rankings(sector_data, avg_2w_ret=0, avg_1m_ret=0, avg_2w_trend=0, avg_1m_trend=0):
    """
    Sector health hesaplama - quant_rankings.top10_sectors verisinden.
    
    Kurallar:
    1. Disqualified = true → Health 0
    2. Score < 50  → Weak (2)
    3. Score 50-75 → Neutral (3)
    4. Score > 75  → Strong (4)
    5. Momentum koşulu (hepsi > 0 olmalı):
       - 2W Return > 0, 1M Return > 0, 2W Trend > 0, 1M Trend > 0
       - Sağlanmıyorsa → bir alt gruba düşer
    """
    # Disqualified kontrolü
    if sector_data.get('Disqualified', False):
        return 0
    
    score = sector_data.get('QuantScore') or 0
    
    # Momentum check: 2W/1M Return ve Trend hepsi > 0 olmalı
    has_momentum = (
        avg_2w_ret > 0 and 
        avg_1m_ret > 0 and 
        avg_2w_trend > 0 and 
        avg_1m_trend > 0
    )
    
    # Base kategori + momentum penalty
    if score > 75:
        return 4 if has_momentum else 3  # Strong → Neutral
    elif score >= 50:
        return 3 if has_momentum else 2  # Neutral → Weak
    else:
        return 2  # Weak (zaten en düşük)


def get_sentiment(symbol, news_data):
    """
    Haber sentiment skorunu al.
    """
    if not news_data:
        return 0
    
    # Handle dict format with 'news' key
    if isinstance(news_data, dict):
        news_items = news_data.get('news', [])
    elif isinstance(news_data, list):
        news_items = news_data
    else:
        return 0
    
    # Find sentiment for this symbol
    sentiments = []
    for item in news_items:
        if isinstance(item, dict) and item.get('symbol') == symbol:
            sent = item.get('sentiment', 0)
            if sent is not None:
                sentiments.append(sent)
    
    if sentiments:
        return round(sum(sentiments) / len(sentiments), 0)
    
    return 0


def find_asset_in_etf_data(symbol, etf_data):
    """
    ETF data içinde varlık bul.
    """
    # Check stocks list
    for stock in etf_data.get('stocks', []):
        if stock.get('Symbol') == symbol:
            return {
                **stock, 
                'Sector': stock.get('Category', 'Unknown'),
                'Type': 'Stock',
                'SCORE': stock.get('QuantScore') or stock.get('SCORE') or 0
            }
    
    # Check ETFs list
    for etf in etf_data.get('etfs', []):
        if etf.get('Symbol') == symbol:
            return {
                **etf, 
                'Sector': etf.get('Category', 'ETF'),
                'Type': 'ETF',
                'SCORE': etf.get('QuantScore') or etf.get('SCORE') or 0
            }
    
    # Check grouped sectors (created in phase1)
    for sector, stocks in etf_data.get('sectors', {}).items():
        if isinstance(stocks, list):
            for stock in stocks:
                if stock.get('Symbol') == symbol:
                    return {
                        **stock, 
                        'Sector': sector,
                        'Type': 'Stock',
                        'SCORE': stock.get('QuantScore') or stock.get('SCORE') or 0
                    }
    
    return None


# =============================================================================
# PHASE 1: DATA PREPARATION
# =============================================================================

def phase1_prepare_data(portfolio, etf_data, news_data):
    """
    Tüm verileri hazırla ve zenginleştir.
    
    Returns:
        dict: Enriched data with assets, sector health, candidates
    """
    print("\n" + "=" * 60)
    print("📊 PHASE 1: Data Preparation")
    print("=" * 60)
    
    # ─────────────────────────────────────────────────────────────
    # 1.1 Group stocks by sector and Calculate Sector Health
    # ─────────────────────────────────────────────────────────────
    print("\n   📈 Grouping stocks by sector and calculating health...")
    
    # Group stocks by Category (sector)
    stocks_by_sector = {}
    all_stocks = etf_data.get('stocks', [])
    
    for stock in all_stocks:
        sector = stock.get('Category', 'Unknown')
        if sector not in stocks_by_sector:
            stocks_by_sector[sector] = []
        stocks_by_sector[sector].append(stock)
    
    # Store for later use
    etf_data['sectors'] = stocks_by_sector
    
    # ─────────────────────────────────────────────────────────────
    # 1.1b Use quant_rankings.top10_sectors for Sector Health
    # ─────────────────────────────────────────────────────────────
    print("\n   📈 Loading sector scores from quant_rankings...")
    
    sector_rankings = etf_data.get('quant_rankings', {}).get('top10_sectors', [])
    sector_health = {}
    
    for sector_data in sector_rankings:
        sector_name = sector_data.get('Sector', 'Unknown')
        quant_score = sector_data.get('QuantScore') or 0
        is_disqualified = sector_data.get('Disqualified', False)
        reason = sector_data.get('Reason', '')
        
        # Get return and trend data from stocks_by_sector
        sector_stocks = stocks_by_sector.get(sector_name, [])
        if sector_stocks:
            returns_2w = [s.get('2W', {}).get('RETURN', 0) or 0 for s in sector_stocks]
            returns_1m = [s.get('1M', {}).get('RETURN', 0) or 0 for s in sector_stocks]
            trends_2w = [s.get('2W', {}).get('TREND', 0) or 0 for s in sector_stocks]
            trends_1m = [s.get('1M', {}).get('TREND', 0) or 0 for s in sector_stocks]
            avg_2w_ret = mean(returns_2w) if returns_2w else 0
            avg_1m_ret = mean(returns_1m) if returns_1m else 0
            avg_2w_trend = mean(trends_2w) if trends_2w else 0
            avg_1m_trend = mean(trends_1m) if trends_1m else 0
        else:
            avg_2w_ret = 0
            avg_1m_ret = 0
            avg_2w_trend = 0
            avg_1m_trend = 0
        
        # Calculate health with momentum check
        health = calculate_sector_health_from_rankings(
            sector_data, avg_2w_ret, avg_1m_ret, avg_2w_trend, avg_1m_trend
        )
        
        # Momentum check for display
        has_momentum = (avg_2w_ret > 0 and avg_1m_ret > 0 and avg_2w_trend > 0 and avg_1m_trend > 0)
        
        sector_health[sector_name] = {
            'health': health,
            'quant_score': quant_score,
            'avg_2w': round(avg_2w_ret, 2),
            'avg_1m': round(avg_1m_ret, 2),
            'avg_2w_trend': round(avg_2w_trend, 2),
            'avg_1m_trend': round(avg_1m_trend, 2),
            'has_momentum': has_momentum,
            'stock_count': sector_data.get('StockCount', 0),
            'disqualified': is_disqualified,
            'reason': reason
        }
        
        status = f"DQ: {reason}" if is_disqualified else f"Score: {quant_score}"
        mom_status = "✓" if has_momentum else "✗"
        print(f"      {sector_name:20} Health: {health}/5, {status}, Mom:{mom_status}")
    
    # ─────────────────────────────────────────────────────────────
    # 1.2 Classify Sectors
    # ─────────────────────────────────────────────────────────────
    disqualified_sectors = [s for s, h in sector_health.items() if h['health'] <= 1]
    weak_sectors = [s for s, h in sector_health.items() if h['health'] == 2]
    neutral_sectors = [s for s, h in sector_health.items() if h['health'] == 3]
    strong_sectors = [s for s, h in sector_health.items() if h['health'] >= 4]
    eligible_sectors = [s for s, h in sector_health.items() if h['health'] >= CONFIG['MIN_SECTOR_HEALTH']]
    
    print(f"\n   🚫 Disqualified (Health ≤1): {disqualified_sectors}")
    print(f"   ⚠️  Weak (Health = 2): {weak_sectors}")
    print(f"   ⚖️  Neutral (Health = 3): {neutral_sectors}")
    print(f"   ✅ Strong (Health ≥4): {strong_sectors}")
    print(f"   📋 Eligible for new positions: {eligible_sectors}")
    
    # ─────────────────────────────────────────────────────────────
    # 1.3 Enrich Portfolio Assets
    # ─────────────────────────────────────────────────────────────
    print("\n   📦 Enriching portfolio assets...")
    enriched_assets = []
    current_etf_weight = 0
    sector_weights = {}
    
    for symbol, weight in portfolio.items():
        asset_data = find_asset_in_etf_data(symbol, etf_data)
        
        if not asset_data:
            print(f"      ⚠️ {symbol}: Not found in ETF data, using defaults")
            asset_data = {
                'Symbol': symbol,
                'Name': symbol,
                'Sector': 'Unknown',
                'Type': 'Stock',
                '2W': {'RETURN': 0},
                '1M': {'RETURN': 0},
                '3M': {'RETURN': 0},
                'SCORE': 0
            }
        
        # Determine if ETF
        is_etf = asset_data.get('Type') == 'ETF' or symbol in ETF_SYMBOLS
        
        # Get returns
        ret_2w = asset_data.get('2W', {}).get('RETURN', 0) or 0
        ret_1m = asset_data.get('1M', {}).get('RETURN', 0) or 0
        ret_3m = asset_data.get('3M', {}).get('RETURN', 0) or 0
        
        # Get sector
        if is_etf:
            sector = asset_data.get('Category', asset_data.get('Sector', 'ETF'))
            sub_category = asset_data.get('SubCategory', '')
        else:
            sector = asset_data.get('Sector', 'Unknown')
            sub_category = ''
        
        # Track weights
        if is_etf:
            current_etf_weight += weight
        
        sector_key = 'ETF' if is_etf else sector
        sector_weights[sector_key] = sector_weights.get(sector_key, 0) + weight
        
        # Momentum classification
        momentum = classify_momentum(ret_2w, ret_1m, ret_3m)
        
        # Sentiment
        sentiment = get_sentiment(symbol, news_data)
        
        # Sector health for this asset
        asset_sector_health = sector_health.get(sector, {'health': 3, 'quant_score': 50})
        
        enriched = {
            'symbol': symbol,
            'name': asset_data.get('Name', symbol),
            'sector': sector,
            'sub_category': sub_category,
            'is_etf': is_etf,
            'current_weight': weight,
            'return_2w': round(ret_2w, 2),
            'return_1m': round(ret_1m, 2),
            'return_3m': round(ret_3m, 2),
            'momentum': momentum,
            'score': asset_data.get('SCORE', 0) or asset_data.get('QuantScore', 0) or 0,
            'sentiment': sentiment,
            'sector_health': asset_sector_health.get('health', 3),
            'sector_quant_score': asset_sector_health.get('quant_score', 50),
            'in_disqualified_sector': sector in disqualified_sectors,
            'in_weak_sector': sector in weak_sectors,
            'in_strong_sector': sector in strong_sectors
        }
        
        enriched_assets.append(enriched)
        
        status = "🔴" if enriched['in_disqualified_sector'] else "🟡" if enriched['in_weak_sector'] else "🟢"
        print(f"      {status} {symbol:6} {weight:5.1f}% | {momentum:10} | {sector}")
    
    # ─────────────────────────────────────────────────────────────
    # 1.4 Build STOCK Candidate Pool
    # ─────────────────────────────────────────────────────────────
    print("\n   🎯 Building stock candidate pool...")
    stock_candidates = []
    portfolio_symbols = set(portfolio.keys())
    
    for sector in eligible_sectors:
        for stock in etf_data.get('sectors', {}).get(sector, []):
            symbol = stock.get('Symbol', '')
            
            # Skip if already in portfolio
            if symbol in portfolio_symbols:
                continue
            
            ret_2w = stock.get('2W', {}).get('RETURN', 0) or 0
            ret_1m = stock.get('1M', {}).get('RETURN', 0) or 0
            ret_3m = stock.get('3M', {}).get('RETURN', 0) or 0
            
            # Get score - use QuantScore if available
            score = stock.get('QuantScore') or stock.get('SCORE') or 0
            if score == 0 or score is None:
                # Estimate score from momentum
                score = 50 + min(max(ret_2w + ret_1m, -30), 30)
            
            # Must be STRONG momentum and good score
            if ret_2w > 0 and ret_1m > 0 and score >= CONFIG['MIN_SCORE']:
                stock_candidates.append({
                    'symbol': symbol,
                    'name': stock.get('Name', symbol),
                    'sector': sector,
                    'is_etf': False,
                    'score': score,
                    'return_2w': round(ret_2w, 2),
                    'return_1m': round(ret_1m, 2),
                    'return_3m': round(ret_3m, 2),
                    'momentum': 'STRONG',
                    'sector_health': sector_health[sector]['health'],
                    'sector_quant_score': sector_health[sector]['quant_score']
                })
    
    # Sort by: 1) sector_health (en güçlü sektör önce), 2) score
    stock_candidates.sort(key=lambda x: (x['sector_health'], x['score']), reverse=True)
    stock_candidates = stock_candidates[:20]  # Top 20
    
    print(f"      Found {len(stock_candidates)} eligible stock candidates")
    for c in stock_candidates[:5]:
        print(f"         {c['symbol']:6} Score: {c['score']:3.0f} | {c['sector']}")
    
    # ─────────────────────────────────────────────────────────────
    # 1.5 Build ETF Candidate Pool
    # ─────────────────────────────────────────────────────────────
    print("\n   🎯 Building ETF candidate pool...")
    etf_candidates = []
    
    for etf in etf_data.get('etfs', []):
        symbol = etf.get('Symbol', '')
        
        # Skip if already in portfolio
        if symbol in portfolio_symbols:
            continue
        
        category = etf.get('Category', '')
        sub_category = etf.get('SubCategory', '')
        
        # Skip ETFs exposed to disqualified/weak sectors
        if category in disqualified_sectors or sub_category in disqualified_sectors:
            continue
        if category in weak_sectors or sub_category in weak_sectors:
            continue
        
        ret_2w = etf.get('2W', {}).get('RETURN', 0) or 0
        ret_1m = etf.get('1M', {}).get('RETURN', 0) or 0
        ret_3m = etf.get('3M', {}).get('RETURN', 0) or 0
        
        # Get score - handle None
        quant_score = etf.get('QuantScore') or etf.get('SCORE') or 0
        if quant_score == 0 or quant_score is None:
            # Estimate score from momentum
            quant_score = 50 + min(max(ret_2w + ret_1m, -30), 30)
        
        # Must be STRONG momentum and good score
        if ret_2w > 0 and ret_1m > 0 and quant_score >= CONFIG['MIN_SCORE']:
            etf_candidates.append({
                'symbol': symbol,
                'name': etf.get('Name', symbol),
                'sector': category,
                'sub_category': sub_category,
                'is_etf': True,
                'score': quant_score,
                'return_2w': round(ret_2w, 2),
                'return_1m': round(ret_1m, 2),
                'return_3m': round(ret_3m, 2),
                'momentum': 'STRONG'
            })
    
    # Sort by score
    etf_candidates.sort(key=lambda x: x['score'], reverse=True)
    etf_candidates = etf_candidates[:10]  # Top 10
    
    print(f"      Found {len(etf_candidates)} eligible ETF candidates")
    for c in etf_candidates[:3]:
        print(f"         {c['symbol']:6} Score: {c['score']:3.0f} | {c['sector']}")
    
    # ─────────────────────────────────────────────────────────────
    # 1.6 Summary
    # ─────────────────────────────────────────────────────────────
    print(f"\n   📊 Current Sector Weights:")
    for sec, w in sorted(sector_weights.items(), key=lambda x: -x[1]):
        status = "🔴 OVER" if w > CONFIG['MAX_SECTOR'] else "✅"
        print(f"      {sec:20} {w:5.1f}% {status}")
    
    print(f"\n   📊 Current ETF Weight: {current_etf_weight:.1f}%", end="")
    if current_etf_weight > CONFIG['MAX_ETF_TOTAL']:
        print(f" 🔴 OVER {CONFIG['MAX_ETF_TOTAL']}% limit!")
    else:
        print(" ✅")
    
    return {
        'assets': enriched_assets,
        'sector_health': sector_health,
        'sector_weights': sector_weights,
        'current_etf_weight': current_etf_weight,
        'disqualified_sectors': disqualified_sectors,
        'weak_sectors': weak_sectors,
        'neutral_sectors': neutral_sectors,
        'strong_sectors': strong_sectors,
        'eligible_sectors': eligible_sectors,
        'stock_candidates': stock_candidates,
        'etf_candidates': etf_candidates
    }


# =============================================================================
# PHASE 2: APPLY HARD RULES
# =============================================================================

def phase2_apply_hard_rules(data):
    """
    Kural tabanlı kararlar - GPT yok, sadece mantık.
    
    Priority Order:
    1. BLACKLISTED_SECTOR → REMOVE
    2. ETF_BLACKLISTED_EXPOSURE → REMOVE
    3. WEAK_MOMENTUM (2W<0 AND 1M<0) → REMOVE
    4. CRITICAL_NEWS (sentiment < -50) → REMOVE
    5. ETF_CONCENTRATION (total ETF > 10%) → REDUCE
    6. SINGLE_ETF_LIMIT (ETF > 5%) → REDUCE
    7. SECTOR_CONCENTRATION (sector > 30%) → REDUCE
    8. POSITION_CONCENTRATION (position > 25%) → REDUCE
    9. LOSING_MOMENTUM (2W<0, 1M>0) → REDUCE 20%
    """
    print("\n" + "=" * 60)
    print("⚖️ PHASE 2: Applying HARD RULES")
    print("=" * 60)
    
    assets = data['assets']
    sector_weights = data['sector_weights'].copy()
    current_etf_weight = data['current_etf_weight']
    
    # Track reductions needed
    etf_excess = max(0, current_etf_weight - CONFIG['MAX_ETF_TOTAL'])
    
    # Process each asset
    for asset in assets:
        symbol = asset['symbol']
        decision = 'KEEP'
        hard_rule = None
        reduce_amount = 0
        
        # ═══════════════════════════════════════════════════════════
        # RULE 1: Blacklisted Sector → REMOVE
        # ═══════════════════════════════════════════════════════════
        if asset['in_disqualified_sector']:
            decision = 'REMOVE'
            hard_rule = 'BLACKLISTED_SECTOR'
            print(f"   🔴 {symbol}: REMOVE - Blacklisted sector ({asset['sector']})")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 2: ETF Exposed to Blacklisted/Weak Sector → REMOVE
        # ═══════════════════════════════════════════════════════════
        elif asset['is_etf']:
            etf_sector = asset['sector']
            etf_sub = asset.get('sub_category', '')
            
            if etf_sector in data['disqualified_sectors'] or etf_sub in data['disqualified_sectors']:
                decision = 'REMOVE'
                hard_rule = 'ETF_BLACKLISTED_SECTOR'
                print(f"   🔴 {symbol}: REMOVE - ETF exposed to blacklisted {etf_sector}/{etf_sub}")
            
            elif etf_sector in data['weak_sectors'] or etf_sub in data['weak_sectors']:
                decision = 'REMOVE'
                hard_rule = 'ETF_WEAK_SECTOR'
                print(f"   🟠 {symbol}: REMOVE - ETF exposed to weak {etf_sector}/{etf_sub}")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 3: Weak Momentum (2W<0 AND 1M<0) → REMOVE
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['momentum'] == 'WEAK':
            decision = 'REMOVE'
            hard_rule = 'WEAK_MOMENTUM'
            print(f"   🔴 {symbol}: REMOVE - WEAK momentum (2W:{asset['return_2w']:+.1f}%, 1M:{asset['return_1m']:+.1f}%)")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 4: Critical News (sentiment < -50) → REMOVE
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['sentiment'] < CONFIG['CRITICAL_SENTIMENT']:
            decision = 'REMOVE'
            hard_rule = 'CRITICAL_NEWS'
            print(f"   🔴 {symbol}: REMOVE - Critical news (sentiment: {asset['sentiment']})")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 5: ETF Total Concentration > 10% → REDUCE ETFs
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['is_etf'] and etf_excess > 0:
            reduce_amount = min(asset['current_weight'], etf_excess, CONFIG['MAX_CHANGE'])
            if reduce_amount >= 0.5:
                decision = 'REDUCE'
                hard_rule = 'ETF_CONCENTRATION'
                etf_excess -= reduce_amount
                print(f"   🟠 {symbol}: REDUCE {reduce_amount:.1f}% - ETF total exceeds {CONFIG['MAX_ETF_TOTAL']}%")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 6: Single ETF > 5% → REDUCE
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['is_etf'] and asset['current_weight'] > CONFIG['MAX_ETF_SINGLE']:
            reduce_amount = asset['current_weight'] - CONFIG['MAX_ETF_SINGLE']
            decision = 'REDUCE'
            hard_rule = 'ETF_POSITION_LIMIT'
            print(f"   🟠 {symbol}: REDUCE {reduce_amount:.1f}% - Single ETF exceeds {CONFIG['MAX_ETF_SINGLE']}%")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 7: Sector Concentration > 30% → REDUCE
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and not asset['is_etf']:
            sector = asset['sector']
            sector_weight = sector_weights.get(sector, 0)
            
            if sector_weight > CONFIG['MAX_SECTOR']:
                excess = sector_weight - CONFIG['MAX_SECTOR']
                # Proportional reduction based on position size
                asset_share = asset['current_weight'] / sector_weight
                reduce_amount = min(excess * asset_share * 1.2, CONFIG['MAX_CHANGE'], asset['current_weight'] * 0.5)
                reduce_amount = round(reduce_amount, 1)
                
                if reduce_amount >= 0.5:
                    decision = 'REDUCE'
                    hard_rule = 'SECTOR_CONCENTRATION'
                    sector_weights[sector] -= reduce_amount
                    print(f"   🟠 {symbol}: REDUCE {reduce_amount:.1f}% - {sector} at {sector_weight:.1f}% exceeds {CONFIG['MAX_SECTOR']}%")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 8: Position > 25% → REDUCE
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['current_weight'] > CONFIG['MAX_POSITION']:
            reduce_amount = asset['current_weight'] - CONFIG['MAX_POSITION']
            decision = 'REDUCE'
            hard_rule = 'POSITION_CONCENTRATION'
            print(f"   🟠 {symbol}: REDUCE {reduce_amount:.1f}% - Position exceeds {CONFIG['MAX_POSITION']}%")
        
        # ═══════════════════════════════════════════════════════════
        # RULE 9: Losing Momentum (2W<0, 1M>0) → REDUCE 20%
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP' and asset['momentum'] == 'LOSING':
            reduce_amount = round(asset['current_weight'] * CONFIG['LOSING_MOMENTUM_REDUCE'], 1)
            if reduce_amount >= 0.5:
                decision = 'REDUCE'
                hard_rule = 'LOSING_MOMENTUM'
                print(f"   🟡 {symbol}: REDUCE {reduce_amount:.1f}% - Losing momentum (2W:{asset['return_2w']:+.1f}%)")
        
        # ═══════════════════════════════════════════════════════════
        # Mark INCREASE candidates (strong momentum + strong sector)
        # ═══════════════════════════════════════════════════════════
        if decision == 'KEEP':
            if asset['momentum'] == 'STRONG' and asset['in_strong_sector']:
                decision = 'INCREASE'
                print(f"   🟢 {symbol}: INCREASE candidate - Strong momentum in strong sector")
            elif asset['momentum'] == 'STRONG':
                print(f"   ⚪ {symbol}: KEEP - Strong momentum")
            else:
                print(f"   ⚪ {symbol}: KEEP")
        
        # Store decision
        asset['decision'] = decision
        asset['hard_rule'] = hard_rule
        asset['reduce_amount'] = reduce_amount
    
    # Summary
    decisions = Counter(a['decision'] for a in assets)
    print(f"\n   📊 Decision Summary: {dict(decisions)}")
    
    return data


# =============================================================================
# PHASE 3: WEIGHT CALCULATION
# =============================================================================

def phase3_calculate_weights(data):
    """
    Weight değişimlerini hesapla.
    
    Constraints:
    - Max position: 25%
    - Max change: ±10%
    - Total: 100%
    - Max sector: 30%
    - Max ETF total: 10%
    """
    print("\n" + "=" * 60)
    print("📐 PHASE 3: Weight Calculation")
    print("=" * 60)
    
    assets = data['assets']
    
    # ─────────────────────────────────────────────────────────────
    # STEP 1: Calculate freed weight from REMOVE and REDUCE
    # ─────────────────────────────────────────────────────────────
    print("\n   💰 Calculating freed weight...")
    freed_weight = 0
    
    for asset in assets:
        if asset['decision'] == 'REMOVE':
            freed_weight += asset['current_weight']
            asset['new_weight'] = 0
            asset['weight_change'] = -asset['current_weight']
            print(f"      {asset['symbol']}: REMOVE {asset['current_weight']:.1f}% → 0%")
        
        elif asset['decision'] == 'REDUCE':
            reduce = min(asset['reduce_amount'], CONFIG['MAX_CHANGE'])
            reduce = round(reduce, 1)
            asset['new_weight'] = round(asset['current_weight'] - reduce, 1)
            asset['weight_change'] = -reduce
            freed_weight += reduce
            print(f"      {asset['symbol']}: REDUCE {asset['current_weight']:.1f}% → {asset['new_weight']:.1f}% (-{reduce:.1f}%)")
        
        else:  # KEEP or INCREASE
            asset['new_weight'] = asset['current_weight']
            asset['weight_change'] = 0
    
    print(f"\n   💰 Total freed weight: {freed_weight:.1f}%")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Identify eligible recipients (prefer stocks over ETFs)
    # ─────────────────────────────────────────────────────────────
    print("\n   🎯 Identifying eligible recipients...")
    
    eligible = [a for a in assets 
                if a['decision'] in ['KEEP', 'INCREASE']
                and not a['is_etf']  # Prefer stocks
                and a['momentum'] in ['STRONG', 'RECOVERING']
                and a['new_weight'] < CONFIG['MAX_POSITION']]
    
    # Sort by priority: STRONG > RECOVERING, Strong sector > others, higher score
    eligible.sort(key=lambda x: (
        x['momentum'] == 'STRONG',
        x['in_strong_sector'],
        x['score']
    ), reverse=True)
    
    for e in eligible[:5]:
        print(f"      {e['symbol']:6} {e['momentum']:10} | {e['sector']} | Score: {e['score']:.0f}")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 3: Distribute freed weight to existing positions
    # ─────────────────────────────────────────────────────────────
    print("\n   📊 Distributing freed weight...")
    remaining = freed_weight
    
    for asset in eligible:
        if remaining < 0.5:
            break
        
        current = asset['new_weight']
        current_change = asset['weight_change']
        
        # Calculate how much we can add
        room_position = CONFIG['MAX_POSITION'] - current
        room_change = CONFIG['MAX_CHANGE'] - current_change
        
        max_add = min(remaining, room_position, room_change)
        max_add = round(max_add, 1)
        
        if max_add >= 0.5:
            asset['new_weight'] = round(current + max_add, 1)
            asset['weight_change'] = round(asset['weight_change'] + max_add, 1)
            asset['decision'] = 'INCREASE'
            remaining -= max_add
            print(f"      {asset['symbol']}: +{max_add:.1f}% → {asset['new_weight']:.1f}%")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 4: Check ETF allocation - can we add to ETFs?
    # ─────────────────────────────────────────────────────────────
    new_etf_weight = sum(a['new_weight'] for a in assets if a['is_etf'])
    etf_room = CONFIG['MAX_ETF_TOTAL'] - new_etf_weight
    
    if remaining > 0.5 and etf_room > 0.5:
        print(f"\n   📊 ETF room available: {etf_room:.1f}%")
        
        eligible_etfs = [a for a in assets 
                        if a['is_etf'] 
                        and a['decision'] in ['KEEP', 'INCREASE']
                        and a['momentum'] in ['STRONG', 'RECOVERING']
                        and a['new_weight'] < CONFIG['MAX_ETF_SINGLE']]
        
        for etf in eligible_etfs:
            if remaining < 0.5 or etf_room < 0.5:
                break
            
            max_add = min(
                remaining,
                etf_room,
                CONFIG['MAX_ETF_SINGLE'] - etf['new_weight'],
                CONFIG['MAX_CHANGE'] - etf['weight_change']
            )
            max_add = round(max_add, 1)
            
            if max_add >= 0.5:
                etf['new_weight'] = round(etf['new_weight'] + max_add, 1)
                etf['weight_change'] = round(etf['weight_change'] + max_add, 1)
                etf['decision'] = 'INCREASE'
                remaining -= max_add
                etf_room -= max_add
                print(f"      {etf['symbol']}: +{max_add:.1f}% → {etf['new_weight']:.1f}%")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 5: Summary
    # ─────────────────────────────────────────────────────────────
    total_allocated = sum(a['new_weight'] for a in assets)
    
    # Fix: INCREASE ile işaretlenmiş ama gerçekte artmamış olanları KEEP yap
    for asset in assets:
        if asset['decision'] == 'INCREASE' and asset['weight_change'] == 0:
            asset['decision'] = 'KEEP'
            print(f"      ℹ️ {asset['symbol']}: INCREASE → KEEP (no actual change)")
        elif asset['decision'] == 'REDUCE' and asset['weight_change'] == 0:
            asset['decision'] = 'KEEP'
            print(f"      ℹ️ {asset['symbol']}: REDUCE → KEEP (no actual change)")
    
    # CRITICAL FIX: remaining_weight = 100% - allocated (not just freed weight)
    remaining_for_new = round(100.0 - total_allocated, 1)
    
    data['remaining_weight'] = remaining_for_new
    data['total_before_new'] = round(total_allocated, 1)
    data['new_etf_weight'] = round(sum(a['new_weight'] for a in assets if a['is_etf']), 1)
    
    print(f"\n   📊 Summary:")
    print(f"      Allocated to existing: {total_allocated:.1f}%")
    print(f"      Remaining for new: {remaining_for_new:.1f}%")
    print(f"      ETF weight: {data['new_etf_weight']:.1f}%")
    
    return data


# =============================================================================
# PHASE 4: REPLACEMENT CANDIDATES
# =============================================================================

def phase4_find_candidates(data):
    """
    Kalan weight için yeni pozisyon adaylarını seç.
    """
    print("\n" + "=" * 60)
    print("🔍 PHASE 4: Finding Replacement Candidates")
    print("=" * 60)
    
    remaining = data['remaining_weight']
    
    if remaining < CONFIG['MIN_NEW_POSITION']:
        print(f"\n   ✅ No remaining weight to allocate ({remaining:.1f}%)")
        data['new_positions'] = []
        return data
    
    print(f"\n   💰 Remaining weight to allocate: {remaining:.1f}%")
    
    current_symbols = set(a['symbol'] for a in data['assets'])
    new_etf_weight = data['new_etf_weight']
    etf_room = CONFIG['MAX_ETF_TOTAL'] - new_etf_weight
    
    # Calculate new sector weights
    sector_weights = {}
    for asset in data['assets']:
        sec = 'ETF' if asset['is_etf'] else asset['sector']
        sector_weights[sec] = sector_weights.get(sec, 0) + asset['new_weight']
    
    selected = []
    weight_allocated = 0
    
    # ─────────────────────────────────────────────────────────────
    # PRIORITY 1: Stocks from STRONGEST sectors first
    # ─────────────────────────────────────────────────────────────
    print("\n   🎯 Priority 1: Stocks from strongest sectors...")
    
    # Sort eligible sectors by health (strongest first)
    sector_health_map = data.get('sector_health', {})
    sorted_sectors = sorted(
        data['eligible_sectors'],
        key=lambda s: sector_health_map.get(s, {}).get('health', 0),
        reverse=True  # En güçlü sektör önce
    )
    
    print(f"      Sector priority: {', '.join(sorted_sectors[:5])}")
    
    for sector in sorted_sectors:
        if weight_allocated >= remaining:
            break
        if len(selected) >= CONFIG['MAX_NEW_POSITIONS']:
            break
        
        # Find best candidate from this sector
        sector_candidates = [
            c for c in data['stock_candidates']
            if c['sector'] == sector and c['symbol'] not in current_symbols
        ]
        
        if sector_candidates:
            candidate = sector_candidates[0]
            
            sector_room = CONFIG['MAX_SECTOR'] - sector_weights.get(sector, 0)
            alloc = min(
                remaining - weight_allocated,
                sector_room,
                CONFIG['MAX_CHANGE']
            )
            alloc = round(alloc, 1)
            
            if alloc >= CONFIG['MIN_NEW_POSITION']:
                candidate['new_weight'] = alloc
                candidate['decision'] = 'NEW'
                candidate['weight_change'] = alloc
                candidate['hard_rule'] = None
                selected.append(candidate)
                current_symbols.add(candidate['symbol'])
                weight_allocated += alloc
                sector_weights[sector] = sector_weights.get(sector, 0) + alloc
                print(f"      ✅ {candidate['symbol']} ({sector}): {alloc:.1f}% | Score: {candidate['score']:.0f}")
    
    # ─────────────────────────────────────────────────────────────
    # PRIORITY 2: ETFs if room under 10%
    # ─────────────────────────────────────────────────────────────
    if weight_allocated < remaining and etf_room > CONFIG['MIN_NEW_POSITION']:
        print(f"\n   🎯 Priority 2: ETFs (room: {etf_room:.1f}%)...")
        
        for etf_candidate in data['etf_candidates']:
            if weight_allocated >= remaining:
                break
            if etf_room < CONFIG['MIN_NEW_POSITION']:
                break
            if etf_candidate['symbol'] in current_symbols:
                continue
            if len(selected) >= CONFIG['MAX_NEW_POSITIONS']:
                break
            
            alloc = min(
                remaining - weight_allocated,
                etf_room,
                CONFIG['MAX_ETF_SINGLE'],
                CONFIG['MAX_CHANGE']
            )
            alloc = round(alloc, 1)
            
            if alloc >= CONFIG['MIN_NEW_POSITION']:
                etf_candidate['new_weight'] = alloc
                etf_candidate['decision'] = 'NEW'
                etf_candidate['weight_change'] = alloc
                etf_candidate['hard_rule'] = None
                selected.append(etf_candidate)
                current_symbols.add(etf_candidate['symbol'])
                weight_allocated += alloc
                etf_room -= alloc
                print(f"      ✅ {etf_candidate['symbol']} (ETF): {alloc:.1f}% | Score: {etf_candidate['score']:.0f}")
    
    # ─────────────────────────────────────────────────────────────
    # PRIORITY 3: More stocks if still remaining
    # ─────────────────────────────────────────────────────────────
    if weight_allocated < remaining:
        print(f"\n   🎯 Priority 3: Additional stocks...")
        
        for candidate in data['stock_candidates']:
            if weight_allocated >= remaining:
                break
            if candidate['symbol'] in current_symbols:
                continue
            if len(selected) >= CONFIG['MAX_NEW_POSITIONS']:
                break
            
            sector = candidate['sector']
            sector_room = CONFIG['MAX_SECTOR'] - sector_weights.get(sector, 0)
            
            alloc = min(
                remaining - weight_allocated,
                sector_room,
                CONFIG['MAX_CHANGE'],
                8
            )
            alloc = round(alloc, 1)
            
            if alloc >= CONFIG['MIN_NEW_POSITION']:
                candidate['new_weight'] = alloc
                candidate['decision'] = 'NEW'
                candidate['weight_change'] = alloc
                candidate['hard_rule'] = None
                selected.append(candidate)
                current_symbols.add(candidate['symbol'])
                weight_allocated += alloc
                sector_weights[sector] = sector_weights.get(sector, 0) + alloc
                print(f"      ✅ {candidate['symbol']} ({sector}): {alloc:.1f}% | Score: {candidate['score']:.0f}")
    
    # ─────────────────────────────────────────────────────────────
    # PRIORITY 4: Distribute remaining to EXISTING strong positions
    # ─────────────────────────────────────────────────────────────
    still_remaining = remaining - weight_allocated
    
    if still_remaining >= 0.5:
        print(f"\n   🎯 Priority 4: Distribute {still_remaining:.1f}% to existing positions...")
        
        # Get existing KEEP/INCREASE assets with strong momentum, sorted by score
        existing_strong = [
            a for a in data['assets']
            if a['decision'] in ['KEEP', 'INCREASE']
            and a['momentum'] in ['STRONG', 'RECOVERING']
            and not a['is_etf']  # ETF'lere değil
            and a['new_weight'] < CONFIG['MAX_POSITION']
        ]
        existing_strong.sort(key=lambda x: (x.get('score', 0) or 0), reverse=True)
        
        for asset in existing_strong:
            if still_remaining < 0.5:
                break
            
            sector = asset['sector']
            current_sector_weight = sector_weights.get(sector, 0)
            
            max_add = min(
                still_remaining,
                CONFIG['MAX_POSITION'] - asset['new_weight'],
                CONFIG['MAX_SECTOR'] - current_sector_weight,
                CONFIG['MAX_CHANGE'] - abs(asset['weight_change']),
                5.0  # Max 5% per iteration
            )
            max_add = round(max_add, 1)
            
            if max_add >= 0.5:
                asset['new_weight'] = round(asset['new_weight'] + max_add, 1)
                asset['weight_change'] = round(asset['weight_change'] + max_add, 1)
                asset['decision'] = 'INCREASE'
                sector_weights[sector] = current_sector_weight + max_add
                still_remaining -= max_add
                weight_allocated += max_add
                print(f"      ✅ {asset['symbol']}: +{max_add:.1f}% → {asset['new_weight']:.1f}%")
    
    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    data['new_positions'] = selected
    data['total_new_weight'] = weight_allocated
    data['final_remaining'] = round(remaining - weight_allocated, 1)
    
    print(f"\n   📊 Summary:")
    print(f"      New positions: {len(selected)}")
    print(f"      Weight allocated: {weight_allocated:.1f}%")
    print(f"      Still remaining: {data['final_remaining']:.1f}%")
    
    return data


# =============================================================================
# PHASE 5: GPT COMMENTARY
# =============================================================================

def phase5_get_commentary(data, client):
    """
    GPT'yi SADECE yorum için kullan.
    Kararlar zaten alındı - GPT onları açıklayacak.
    """
    print("\n" + "=" * 60)
    print("💬 PHASE 5: GPT Commentary")
    print("=" * 60)
    
    # Build decision summary for GPT
    decision_summary = []
    for asset in data['assets']:
        decision_summary.append({
            'symbol': asset['symbol'],
            'name': asset['name'],
            'sector': asset['sector'],
            'sector_health': asset.get('sector_health', 0),
            'decision': asset['decision'],
            'hard_rule': asset['hard_rule'],
            'current_weight': asset['current_weight'],
            'new_weight': asset['new_weight'],
            'return_2w': asset['return_2w'],
            'return_1m': asset['return_1m'],
            'momentum': asset['momentum'],
            'sentiment': asset['sentiment']
        })
    
    for np in data.get('new_positions', []):
        decision_summary.append({
            'symbol': np['symbol'],
            'name': np['name'],
            'sector': np['sector'],
            'sector_health': np.get('sector_health', 0),
            'decision': 'NEW',
            'new_weight': np['new_weight'],
            'return_2w': np['return_2w'],
            'return_1m': np['return_1m'],
            'score': np['score']
        })
    
    prompt = f"""You are a Senior Quantitative Strategist at a top-tier hedge fund.
Your task is to explain portfolio rebalancing decisions with institutional-grade insight, strictly adhering to the provided data.

=== OBJECTIVE ===
Provide commentary on ALREADY EXECUTED decisions.
Do NOT describe what happened (we can see the weight change); explain WHY it matters in the context of momentum, sector health, and risk.

=== MARKET CONTEXT ===
- Disqualified Sectors (Health ≤ 1): {data.get('disqualified_sectors', [])}
- Weak Sectors (Health = 2): {data.get('weak_sectors', [])}
- Strong Sectors (Health ≥ 4): {data.get('strong_sectors', [])}

=== DECISIONS DATA ===
{json.dumps(decision_summary, indent=2)}

=== DECISION PRIORITY RULE (CRITICAL) ===
For each asset, identify ONE dominant driver:
1) Sector Health / 2) Momentum / 3) Risk Control
Secondary metrics may be mentioned ONLY to reinforce the dominant thesis.
Never present multiple causes as equally important.

=== DEPTH REQUIREMENT (SECOND-ORDER THINKING) ===
Always explain the second-order implication of the signal:
- What does this suggest about capital flows or marginal buyers/sellers?
- What risk becomes asymmetric if ignored (downside skew, crowding, correlation spike)?
- Why does this matter NOW (timing)?

=== REGIME CLASSIFICATION RULE (DETERMINISTIC) ===
Derive market_regime using sector counts only:
- BULL: Strong sectors ≥ 2x Disqualified
- BEAR: Disqualified sectors ≥ 2x Strong
- ROTATION: Strong and Weak both present, Disqualified limited
- CAUTION: Weak dominant OR Strong ≤ Disqualified with mixed breadth

Derive risk_level using sector counts only:
- NORMAL: Strong > (Weak + Disqualified)
- CAUTION: Weak is dominant OR Disqualified present with mixed breadth
- HIGH_ALERT: Disqualified is dominant OR broad deterioration (Disqualified ≥ Strong)

=== CRITICAL STYLE GUIDELINES ===
1) NO ROBOTIC LANGUAGE:
   Never use phrases like "Based on the rule," "Algorithm decided," "Triggered a constraint," or "Hard rule."
2) DATA SYNTHESIS:
   Combine metrics; do not list them. Every number must support a conviction statement.
3) CONTRAST IS KEY:
   Always contrast the asset vs its sector backdrop:
   - Stock strong but sector weak: "alpha/divergence despite sector headwinds."
   - Stock weak and sector weak: "broad sector weakness dragging the asset."
4) PRECISION:
   Always cite the specific "Before -> After" weight.
5) SENTIMENT INSIGHT:
   If sentiment is notable (>+20 or <-20), weave it naturally:
   - "Bullish news flow (+28) reinforces momentum thesis."
   - "Negative sentiment (-35) adds to downside conviction."
6) PM VOICE:
   Write like a portfolio manager addressing an investment committee.
   Favor capital rotation, concentration, asymmetry, and flow language.

=== SCENARIO-SPECIFIC INSTRUCTIONS ===
- REMOVALS: Be ruthless.
  If sector ban: "Capital reallocation from disqualified [Sector] to higher-conviction areas."
  If momentum: "Thesis invalidated due to trend deterioration and adverse asymmetry."
- REDUCE: Specify whether it is:
  (a) Risk Management (concentration / exposure control) or
  (b) Profit Taking (locking gains as momentum decelerates).
  Mention the exact cap if provided (e.g., "Trimmed to cap single-name exposure at 25%").
- INCREASE / NEW: Emphasize relative strength vs alternatives.
  Cite Quant Score and short-term momentum. Mention sector tailwind if health ≥ 4.
- KEEP: Explain the holding thesis.
  Clarify if it is a defensive anchor or a momentum leader.

=== HARD CONSTRAINTS ===
- Do not invent metrics that are not present in DECISIONS DATA.
- If a metric is missing, do not mention it.
- Max 25 words per asset commentary (strict).
- Output must be strictly valid JSON (no markdown, no filler).

=== EXPECTED OUTPUT FORMAT (JSON ONLY) ===
Return strictly valid JSON:
{{
  "market_regime": "BULL / BEAR / ROTATION / CAUTION",
  "risk_level": "NORMAL / CAUTION / HIGH_ALERT",
  "regime_analysis": "Max 2 sentences. Synthesize sector health and breadth.",
  "executive_summary": "IC-style. Start with action, then reason, then risk implication. Include exactly 2-3 numbers.",
  "asset_commentary": {{
    "SYMBOL": "Institutional commentary. Must include weight Before -> After. Max 25 words."
  }}
}}
"""
    
    try:
        print("   🤖 Calling GPT for commentary...")
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=6000
        )
        
        content = response.choices[0].message.content
        
        if not content:
            raise ValueError("Empty GPT response")
        
        content = content.strip()
        
        # Clean markdown if present
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines).strip()
        
        # Parse JSON
        json_start = content.find('{')
        json_end = content.rfind('}')
        if json_start != -1 and json_end != -1:
            content = content[json_start:json_end+1]
        
        commentary = json.loads(content)
        
        # Merge commentary into data
        asset_comments = commentary.get('asset_commentary', {})
        
        for asset in data['assets']:
            symbol = asset['symbol']
            asset['reasoning'] = asset_comments.get(symbol, f"{asset['decision']} based on {asset['hard_rule'] or asset['momentum']} momentum.")
        
        for np in data.get('new_positions', []):
            symbol = np['symbol']
            np['reason'] = asset_comments.get(symbol, f"New position: Strong momentum, diversifies to {np['sector']}.")
        
        data['market_regime'] = commentary.get('market_regime', 'CAUTION')
        data['risk_level'] = commentary.get('risk_level', 'CAUTION')
        data['regime_analysis'] = commentary.get('regime_analysis', 'Market conditions require careful positioning.')
        data['executive_summary'] = commentary.get('executive_summary', 'Portfolio rebalanced according to hard rules.')
        
        print(f"   ✅ Market Regime: {data['market_regime']}")
        print(f"   ✅ Risk Level: {data['risk_level']}")
        
    except Exception as e:
        print(f"   ⚠️ GPT error: {e}")
        print("   ⚠️ Using default commentary...")
        
        # Default commentary
        for asset in data['assets']:
            rule = asset['hard_rule']
            if rule:
                asset['reasoning'] = f"{asset['decision']} due to {rule}. Momentum: 2W:{asset['return_2w']:+.1f}%, 1M:{asset['return_1m']:+.1f}%."
            else:
                asset['reasoning'] = f"{asset['decision']}. Momentum: {asset['momentum']} (2W:{asset['return_2w']:+.1f}%, 1M:{asset['return_1m']:+.1f}%)."
        
        for np in data.get('new_positions', []):
            np['reason'] = f"New position with STRONG momentum (2W:{np['return_2w']:+.1f}%, 1M:{np['return_1m']:+.1f}%). Diversifies to {np['sector']}."
        
        data['market_regime'] = 'CAUTION'
        data['risk_level'] = 'CAUTION'
        data['regime_analysis'] = 'Market analysis unavailable.'
        data['executive_summary'] = 'Portfolio rebalanced according to hard rules.'
    
    return data


# =============================================================================
# FINAL ASSEMBLY
# =============================================================================

def assemble_final_json(data):
    """
    Final JSON çıktısını oluştur.
    """
    print("\n" + "=" * 60)
    print("📦 Assembling Final JSON")
    print("=" * 60)
    
    # Build assets list
    assets_output = []
    for asset in data['assets']:
        assets_output.append({
            'symbol': asset['symbol'],
            'name': asset['name'],
            'sector': asset['sector'],
            'sub_category': asset.get('sub_category', ''),
            'is_etf': asset['is_etf'],
            'current_weight': asset['current_weight'],
            'new_weight': asset['new_weight'],
            'weight_change': asset['weight_change'],
            'decision': asset['decision'],
            'hard_rule_triggered': asset.get('hard_rule'),
            'score': asset.get('score', 0),
            'asset_score': asset.get('score', 0),
            'return_2w': asset['return_2w'],
            'return_1m': asset['return_1m'],
            'return_3m': asset['return_3m'],
            'short_term_trend': asset['momentum'],
            'medium_term_trend': 'UPTREND' if asset['return_1m'] > 0 and asset['return_3m'] > 0 else 'DOWNTREND' if asset['return_1m'] < 0 and asset['return_3m'] < 0 else 'MIXED',
            'sentiment': asset['sentiment'],
            'sector_health': asset['sector_health'],
            'sector_quant_score': asset['sector_quant_score'],
            'in_top10': asset.get('score', 0) >= 80,
            'reasoning': asset.get('reasoning', '')
        })
    
    # Build new positions list
    new_positions_output = []
    for np in data.get('new_positions', []):
        new_positions_output.append({
            'symbol': np['symbol'],
            'name': np['name'],
            'sector': np['sector'],
            'sub_category': np.get('sub_category', ''),
            'is_etf': np['is_etf'],
            'current_weight': 0,
            'new_weight': np['new_weight'],
            'weight_change': np['new_weight'],
            'decision': 'NEW',
            'hard_rule_triggered': None,
            'score': np['score'],
            'asset_score': np['score'],
            'return_2w': np['return_2w'],
            'return_1m': np['return_1m'],
            'return_3m': np['return_3m'],
            'short_term_trend': np['momentum'],
            'medium_term_trend': 'UPTREND' if np['return_1m'] > 0 and np['return_3m'] > 0 else 'MIXED',
            'sector_health': np.get('sector_health', 0),
            'sector_quant_score': np.get('sector_quant_score', 0),
            'sentiment': 0,
            'reasoning': np.get('reason', f"New position in {np['sector']} with score {np['score']:.0f}")
        })
    
    # Build removals list
    removals_output = []
    for asset in data['assets']:
        if asset['decision'] == 'REMOVE':
            removals_output.append({
                'remove': asset['symbol'],
                'replace_with': 'REDISTRIBUTED',
                'reason': asset.get('hard_rule', 'Hard rule triggered'),
                'weight_redistributed_to': []
            })
    
    # Calculate sector allocation
    sector_before = {}
    sector_after = {}
    
    for asset in data['assets']:
        sec = 'ETF' if asset['is_etf'] else asset['sector']
        sector_before[sec] = sector_before.get(sec, 0) + asset['current_weight']
        sector_after[sec] = sector_after.get(sec, 0) + asset['new_weight']
    
    for np in data.get('new_positions', []):
        sec = 'ETF' if np['is_etf'] else np['sector']
        sector_after[sec] = sector_after.get(sec, 0) + np['new_weight']
    
    # Calculate totals
    total = sum(a['new_weight'] for a in assets_output) + sum(p['new_weight'] for p in new_positions_output)
    
    # Decision counts
    decisions = Counter(a['decision'] for a in assets_output)
    
    # Build final result
    result = {
        'review_date': datetime.now().strftime('%Y-%m-%d'),
        'generated_at': datetime.now().isoformat(),
        'model': MODEL,
        'engine': 'Python-Driven v2.0',
        
        'market_regime': data.get('market_regime', 'CAUTION'),
        'risk_level': data.get('risk_level', 'CAUTION'),
        'regime_analysis': data.get('regime_analysis', ''),
        'executive_summary': data.get('executive_summary', ''),
        
        'portfolio_score': 75,  # Could calculate based on weighted scores
        
        'disqualified_sectors': data['disqualified_sectors'],
        'weak_sectors': data['weak_sectors'],
        'neutral_sectors': data.get('neutral_sectors', []),
        'strong_sectors': data['strong_sectors'],
        
        'hard_rules_applied': list(set(a.get('hard_rule') for a in data['assets'] if a.get('hard_rule'))),
        'critical_alerts': [
            f"ETF: {a['symbol']} exposed to {a.get('hard_rule', 'issue')}"
            for a in data['assets'] 
            if a['decision'] == 'REMOVE' and a['is_etf']
        ] + [
            f"STOCK: {a['symbol']} - {a.get('hard_rule', 'issue')}"
            for a in data['assets']
            if a['decision'] == 'REMOVE' and not a['is_etf']
        ],
        
        'total_new_weight': round(total, 1),
        'weight_changes': {
            'reduced': round(sum(-a['weight_change'] for a in assets_output if a['weight_change'] < 0), 1),
            'increased': round(sum(a['weight_change'] for a in assets_output if a['weight_change'] > 0), 1),
            'new_positions': round(sum(p['new_weight'] for p in new_positions_output), 1)
        },
        
        'decision_counts': {
            'keep': decisions.get('KEEP', 0),
            'increase': decisions.get('INCREASE', 0),
            'reduce': decisions.get('REDUCE', 0),
            'remove': decisions.get('REMOVE', 0),
            'new': len(new_positions_output)
        },
        
        'sector_allocation': {
            sec: {
                'before': round(sector_before.get(sec, 0), 1),
                'after': round(sector_after.get(sec, 0), 1)
            }
            for sec in set(list(sector_before.keys()) + list(sector_after.keys()))
        },
        
        'assets': assets_output,
        'new_positions': new_positions_output,
        'removals': removals_output
    }
    
    # Verify total
    print(f"\n   📊 Final Verification:")
    print(f"      Total weight: {total:.1f}%")
    print(f"      Assets: {len(assets_output)}")
    print(f"      New positions: {len(new_positions_output)}")
    print(f"      Decisions: {dict(decisions)}")
    
    if len(assets_output) == 0 and len(new_positions_output) == 0:
        print(f"   ⚠️ WARNING: No assets in portfolio!")
        result['total_new_weight'] = 0.0
        return result
    
    if abs(total - 100) > 0.5:
        print(f"   ⚠️ WARNING: Total is {total:.1f}%, not 100%!")
        # Try to fix by adjusting largest position
        all_positions = assets_output + new_positions_output
        if total < 100 and len(all_positions) > 0:
            diff = 100 - total
            largest = max(all_positions, key=lambda x: x['new_weight'])
            if largest['new_weight'] + diff <= CONFIG['MAX_POSITION']:
                largest['new_weight'] = round(largest['new_weight'] + diff, 1)
                largest['weight_change'] = round(largest['weight_change'] + diff, 1)
                result['total_new_weight'] = 100.0
                print(f"   ✅ Fixed: Added {diff:.1f}% to {largest['symbol']}")
    
    return result


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_portfolio_review(portfolio, etf_data, news_data, client):
    """
    Ana orkestrasyon fonksiyonu.
    """
    print("\n" + "=" * 70)
    print("🚀 WEEKLY PORTFOLIO REVIEW v2.0")
    print("   Python-Driven Decision Engine")
    print("=" * 70)
    
    # Phase 1: Data Preparation
    data = phase1_prepare_data(portfolio, etf_data, news_data)
    
    # Phase 2: Apply Hard Rules
    data = phase2_apply_hard_rules(data)
    
    # Phase 3: Calculate Weights
    data = phase3_calculate_weights(data)
    
    # Phase 4: Find Candidates
    data = phase4_find_candidates(data)
    
    # Phase 5: GPT Commentary
    data = phase5_get_commentary(data, client)
    
    # Final Assembly
    result = assemble_final_json(data)
    
    print("\n" + "=" * 70)
    print("✅ PORTFOLIO REVIEW COMPLETE")
    print("=" * 70)
    
    return result


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """
    Ana giriş noktası.
    """
    from openai import OpenAI
    
    print("=" * 70)
    print("📊 WEEKLY PORTFOLIO REVIEW v2.0")
    print("   Python-Driven Decision Engine")
    print("=" * 70)
    
    # Load API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        api_key_file = os.path.expanduser('~/openai_api_key.txt')
        if os.path.exists(api_key_file):
            with open(api_key_file, 'r', encoding='utf-8-sig') as f:
                api_key = f.read().strip()
    
    if not api_key:
        print("❌ OPENAI_API_KEY not found!")
        return
    
    client = OpenAI(api_key=api_key)
    
    # Load portfolio (supports both .txt and .json)
    portfolio_file = 'portfolio.txt'
    portfolio_json = 'portfolio.json'
    
    portfolio = {}
    
    # Try JSON first
    if os.path.exists(portfolio_json):
        print(f"\n📂 Reading {portfolio_json}...")
        with open(portfolio_json, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        if isinstance(data, dict):
            # Format: {"AAPL": 15.0, "MSFT": 12.5}
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    portfolio[k.upper()] = float(v)
                elif isinstance(v, dict) and 'weight' in v:
                    portfolio[k.upper()] = float(v['weight'])
        elif isinstance(data, list):
            # Format: [{"symbol": "AAPL", "weight": 15.0}, ...]
            for item in data:
                if isinstance(item, dict):
                    sym = item.get('symbol', item.get('Symbol', '')).upper()
                    wt = item.get('weight', item.get('Weight', item.get('allocation', 0)))
                    if sym and wt:
                        portfolio[sym] = float(wt)
    
    # Try TXT if no JSON or JSON was empty
    elif os.path.exists(portfolio_file):
        print(f"\n📂 Reading {portfolio_file}...")
        with open(portfolio_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        print(f"   Found {len(lines)} lines")
        
        # Show first few lines for debugging
        if lines:
            print(f"   First lines preview:")
            for i, line in enumerate(lines[:3]):
                print(f"      [{i+1}] '{line.strip()}'")
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Skip header lines
            if any(h in line.lower() for h in ['symbol', 'ticker', 'weight', 'allocation']):
                continue
            
            # Try different separators: comma first (common), then tab, space, semicolon
            parsed = False
            for sep in [',', '\t', ';', None]:
                if sep:
                    parts = line.split(sep)
                else:
                    parts = line.split()
                
                if len(parts) >= 2:
                    symbol = parts[0].strip().upper()
                    weight_str = parts[1].strip().replace('%', '').replace(',', '.')
                    try:
                        weight = float(weight_str)
                        if weight > 0:
                            portfolio[symbol] = weight
                            parsed = True
                            break
                    except ValueError:
                        continue
            
            if not parsed and line:
                print(f"   ⚠️ Could not parse line {i+1}: '{original_line.strip()}'")
    else:
        print(f"\n❌ No portfolio file found!")
        print(f"   Looked for: {portfolio_file} or {portfolio_json}")
        return
    
    print(f"\n📂 Loaded portfolio: {len(portfolio)} assets")
    if portfolio:
        for sym, wt in list(portfolio.items())[:5]:
            print(f"      {sym}: {wt}%")
        if len(portfolio) > 5:
            print(f"      ... and {len(portfolio) - 5} more")
    print(f"   Total weight: {sum(portfolio.values()):.1f}%")
    
    # Validate portfolio
    if len(portfolio) == 0:
        print(f"\n❌ ERROR: No assets loaded from {portfolio_file}!")
        print("   Expected format: SYMBOL WEIGHT%")
        print("   Example:")
        print("      AAPL 15.0%")
        print("      MSFT 12.5%")
        print("      SPY 10.0%")
        return
    
    if sum(portfolio.values()) < 50:
        print(f"\n⚠️  WARNING: Total weight is only {sum(portfolio.values()):.1f}%")
        print("   Expected ~100%. Check portfolio.txt format.")
    
    # Load ETF data
    etf_file = 'etf_data.json'
    if not os.path.exists(etf_file):
        print(f"❌ {etf_file} not found!")
        return
    
    with open(etf_file, 'r', encoding='utf-8-sig') as f:
        etf_data = json.load(f)
    
    print(f"📂 Loaded ETF data: {len(etf_data.get('stocks', []))} stocks")
    
    # Load news data (optional)
    news_data = {}
    news_file = 'news_data.json'
    if os.path.exists(news_file):
        with open(news_file, 'r', encoding='utf-8-sig') as f:
            news_data = json.load(f)
        news_count = len(news_data.get('news', [])) if isinstance(news_data, dict) else len(news_data)
        print(f"📂 Loaded news data: {news_count} items")
    
    # Run review
    result = run_portfolio_review(portfolio, etf_data, news_data, client)
    
    # Save JSON result
    output_file = 'portfolio_review.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved: {output_file}")
    
    # HTML artık ayrı dosya - JSON'u fetch edecek
    # generate_html_report kaldırıldı
    
    # Print summary
    print(f"\n{'=' * 70}")
    print("📊 SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Market Regime: {result['market_regime']}")
    print(f"   Risk Level: {result['risk_level']}")
    print(f"   Total Weight: {result['total_new_weight']:.1f}%")
    print(f"\n   Decisions:")
    for dec, count in result['decision_counts'].items():
        if count > 0:
            print(f"      {dec.upper():10} {count}")


def generate_html_report(result, output_file):
    """
    Generate HTML report from review result.
    Embeds JSON directly into HTML for local file:// compatibility.
    """
    print(f"\n📄 Generating HTML report...")
    
    # Read template
    template_file = 'portfolio_review_template.html'
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8-sig') as f:
            html = f.read()
    else:
        # Use minimal embedded template
        html = get_html_template()
    
    # Embed JSON into HTML (replace placeholder)
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    
    if '__JSON_DATA__' in html:
        html = html.replace('__JSON_DATA__', json_str)
    elif '{}' in html:
        # Fallback for old template format
        html = html.replace('{}', json_str, 1)
    
    # Save HTML with embedded JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Saved: {output_file}")
    print(f"📌 JSON embedded in HTML (works with file://)")


def get_html_template():
    """Return the embedded HTML template."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Portfolio Review v2.0</title>
<style>
:root{--bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a24;--border:#2a2a3a;--text:#f1f1f1;--text2:#a0a0b0;--muted:#6b7280;--green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--cyan:#06b6d4;--purple:#8b5cf6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:var(--bg);color:var(--text);padding:20px}
.container{max-width:1200px;margin:0 auto}
.header{text-align:center;padding:24px;background:var(--bg2);border-radius:12px;margin-bottom:20px}
.header h1{font-size:1.5rem;color:var(--cyan)}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;margin-bottom:16px;overflow:hidden}
.card-header{padding:14px 18px;background:var(--bg3);border-bottom:1px solid var(--border);font-weight:600}
.card-body{padding:18px}
table{width:100%;border-collapse:collapse;font-size:0.85rem}
th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}
th{background:var(--bg3);color:var(--text2)}
.badge{padding:4px 10px;border-radius:6px;font-size:0.75rem;font-weight:600}
.badge-green{background:rgba(34,197,94,0.2);color:var(--green)}
.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.badge-yellow{background:rgba(245,158,11,0.2);color:var(--yellow)}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.stat{background:var(--bg3);padding:16px;border-radius:8px;text-align:center}
.stat-value{font-size:1.5rem;font-weight:700;color:var(--cyan)}
.stat-label{font-size:0.8rem;color:var(--text2)}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>Weekly Portfolio Review v2.0</h1>
<p style="color:var(--text2);margin-top:8px" id="date"></p>
</div>
<div class="stat-grid">
<div class="stat"><div class="stat-value" id="total">-</div><div class="stat-label">Total Weight</div></div>
<div class="stat"><div class="stat-value" id="keep">-</div><div class="stat-label">Keep</div></div>
<div class="stat"><div class="stat-value" style="color:var(--red)" id="remove">-</div><div class="stat-label">Remove</div></div>
<div class="stat"><div class="stat-value" style="color:var(--yellow)" id="adjust">-</div><div class="stat-label">Adjust</div></div>
</div>
<div class="card">
<div class="card-header">Portfolio Analysis</div>
<table>
<thead><tr><th>Asset</th><th>Sector</th><th>Momentum</th><th>Decision</th><th>Weight</th></tr></thead>
<tbody id="table"></tbody>
</table>
</div>
</div>
<script id="reviewData" type="application/json">
{}
</script>
<script>
var R=JSON.parse(document.getElementById('reviewData').textContent||'{}');
document.getElementById('date').textContent=R.review_date||'-';
document.getElementById('total').textContent=(R.total_new_weight||0).toFixed(1)+'%';
var c=R.decision_counts||{};
document.getElementById('keep').textContent=(c.keep||0)+(c.increase||0);
document.getElementById('remove').textContent=c.remove||0;
document.getElementById('adjust').textContent=(c.reduce||0)+(c.new||0);
var h='';
(R.assets||[]).concat(R.new_positions||[]).forEach(function(a){
var d=a.decision||'KEEP';
var bc=d==='REMOVE'?'badge-red':d==='REDUCE'?'badge-yellow':'badge-green';
var cw=a.current_weight||0;
var nw=a.new_weight||cw;
var ch=nw-cw;
var ar=ch>0?'↑':ch<0?'↓':'→';
h+='<tr><td><b>'+a.symbol+'</b><br><small style="color:var(--text2)">'+a.name+'</small></td>';
h+='<td>'+a.sector+'</td>';
h+='<td>'+a.momentum+'</td>';
h+='<td><span class="badge '+bc+'">'+d+'</span>'+(a.hard_rule_triggered?'<br><small style="color:var(--yellow)">'+a.hard_rule_triggered+'</small>':'')+'</td>';
h+='<td>'+cw.toFixed(1)+'% '+ar+' <b>'+nw.toFixed(1)+'%</b></td></tr>';
});
document.getElementById('table').innerHTML=h;
</script>
</body>
</html>'''


if __name__ == '__main__':
    main()
