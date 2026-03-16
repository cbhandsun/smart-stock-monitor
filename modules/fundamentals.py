import requests
import akshare as ak
import pandas as pd

def get_macro_indicators():
    """
    获取 A股核心宏观与流动性指标：
    1. 北向资金 (模拟/或通过 akshare 获取)
    2. 富时中国A50期货 (Sentiment)
    3. 美元/离岸人民币 (USD/CNH) - 资金流向风向标
    """
    indicators = {}
    
    # --- 1. Sina JS 实时行情 ---
    try:
        # fx_susdcnh (离岸人民币), hf_CHA50CFD (A50期货)
        url = "https://hq.sinajs.cn/list=fx_susdcnh,hf_CHA50CFD"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        r = requests.get(url, headers=headers, timeout=3)
        lines = r.text.strip().split(';')
        
        for line in lines:
            if 'fx_susdcnh' in line and '="' in line:
                val = line.split('="')[1].split(',')
                if len(val) > 1:
                    price = float(val[1])
                    indicators['USD/CNH'] = {'price': price, 'change_pct': 0} 
                
            elif 'hf_CHA50CFD' in line and '="' in line:
                val = line.split('="')[1].split(',')
                if len(val) > 7:
                    price = float(val[0])
                    prev = float(val[7])
                    change = (price - prev) / prev * 100 if prev != 0 else 0
                    indicators['富时中国A50'] = {'price': price, 'change_pct': change}
                
    except Exception as e:
        print(f"Macro fetch error (Sina): {e}")

    return indicators

def get_financial_health_score(symbol):
    """
    获取个股财务健康度 (杜邦分析 + 估值)
    Fallback to mocked/estimated data if API fails to avoid empty UI.
    """
    try:
        code = symbol
        if symbol.startswith(('sh', 'sz')):
            code = symbol[2:]
            
        # Try to fetch real data
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code)
            if not df.empty:
                latest = df.iloc[0]
                metrics = {
                    'ROE': latest.get('净资产收益率(%)', 0),
                    'NetMargin': latest.get('销售净利率(%)', 0),
                    'AssetTurnover': latest.get('总资产周转率(次)', 0),
                    'DebtRatio': latest.get('资产负债率(%)', 0),
                }
                score = 60
                if metrics['ROE'] > 15: score += 20
                if metrics['NetMargin'] > 15: score += 10
                if metrics['DebtRatio'] < 50: score += 10
                
                return {
                    'score': score, 
                    'analysis': f"基于最新财报：ROE {metrics['ROE']}%, 净利率 {metrics['NetMargin']}%.", 
                    'metrics': metrics
                }
        except:
            pass
            
        # Fallback: Try alternative data source - stock_yjbb_em (业绩快报)
        try:
            df_yjbb = ak.stock_yjbb_em(date="20241231")  # 最新业绩快报
            stock_row = df_yjbb[df_yjbb['股票代码'] == code]
            if not stock_row.empty:
                row = stock_row.iloc[0]
                metrics = {
                    'ROE': row.get('净资产收益率', 0),
                    'NetMargin': row.get('销售净利率', 0),
                    'RevenueGrowth': row.get('营业收入同比增长率', 0),
                    'ProfitGrowth': row.get('净利润同比增长率', 0),
                }
                
                # 计算健康分
                score = 50
                if metrics['ROE'] > 10: score += 15
                elif metrics['ROE'] > 5: score += 10
                if metrics['NetMargin'] > 10: score += 10
                elif metrics['NetMargin'] > 5: score += 5
                if metrics['RevenueGrowth'] > 0: score += 10
                if metrics['ProfitGrowth'] > 0: score += 10
                score = min(100, max(0, score))
                
                return {
                    'score': int(score),
                    'analysis': f"基于业绩快报：ROE {metrics['ROE']:.1f}%, 营收增长 {metrics['RevenueGrowth']:.1f}%", 
                    'metrics': metrics,
                    'source': '业绩快报'
                }
        except Exception as e2:
            print(f"Alternative data fetch error: {e2}")
        
        # Final fallback with warning
        return {
            'score': 50,
            'analysis': "⚠️ 财务数据获取失败，请检查网络连接或稍后重试",
            'metrics': {},
            'source': 'unavailable'
        }
        
    except Exception as e:
        return {'score': 50, 'analysis': "数据获取失败", 'metrics': {}}
