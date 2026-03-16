import sys
import os
import pandas as pd
from utils.tv_charts import render_tv_chart
from modules.data_loader import fetch_kline
import streamlit.components.v1 as components

df = fetch_kline("sh600519")
html_output = []
def mock_html(html, height=500):
    html_output.append(html)

components.html = mock_html
render_tv_chart(df)

if html_output:
    with open("test_tv.html", "w") as f:
        f.write(html_output[0])
    print("HTML written to test_tv.html")
else:
    print("NO HTML OUTPUT")
