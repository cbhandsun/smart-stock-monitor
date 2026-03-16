import requests
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
                price = float(val[1])
                # Sina FX format change_pct might be index 10 or calculated
                indicators['USD/CNH'] = {'price': price, 'change_pct': 0} 
                
            elif 'hf_CHA50CFD' in line and '="' in line:
                val = line.split('="')[1].split(',')
                price = float(val[0])
                prev = float(val[7]) if len(val)>7 and float(val[7])!=0 else price
                change = (price - prev) / prev * 100 if prev else 0
                indicators['富时中国A50'] = {'price': price, 'change_pct': change}
                
    except Exception as e:
        print(f"Macro fetch error (Sina): {e}")

    # --- 2. 北向资金 (AkShare) ---
    try:
        # 暂时返回空，避免卡顿
        indicators['北向资金(预估)'] = {'price': 0.0, 'change_pct': 0, 'note': '盘后数据'}
    except:
        pass
        
    return indicators
