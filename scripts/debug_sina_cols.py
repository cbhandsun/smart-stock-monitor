import akshare as ak
import os

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

df = ak.stock_zh_a_spot()
print(df.columns.tolist())
