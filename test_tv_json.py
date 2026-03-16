import pandas as pd
from modules.data_loader import fetch_kline
import json
import math

df = fetch_kline("sh600519")
if '日期' in df.columns:
    df['time'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')

kline_data = []
for _, row in df.iterrows():
    open_p = row.get('开盘', 0)
    if math.isnan(open_p): print("FOUND NAN in OPEN")
    kline_data.append({
        "time": row['time'],
        "open": float(open_p)
    })

print("Length of kline:", len(kline_data))
js_string = json.dumps(kline_data[:2])
print("Sample JSON:", js_string)

