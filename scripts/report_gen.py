import akshare as ak
import pandas as pd
import sys
import os
from datetime import datetime

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def generate_report():
    print(f"[{datetime.now()}] 正在生成每日盘后研报...")
    
    report = []
    report.append(f"📅 **每日股市研报 - {datetime.now().strftime('%Y-%m-%d')}**")
    report.append("---")

    # 1. 大盘表现
    try:
        df_index = ak.stock_zh_index_spot_sina()
        indices = df_index[df_index['名称'].isin(['上证指数', '深证成指', '创业板指'])]
        report.append("📈 **大盘表现**")
        for _, row in indices.iterrows():
            # Calculate change pct if not present or for consistency
            # Sina data has '最新价' and usually '涨跌幅' or we calculate from '昨收'
            price = float(row['最新价'])
            prev_close = float(row['昨收'])
            change_pct = (price - prev_close) / prev_close * 100
            emoji = "🔴" if change_pct > 0 else "🟢"
            report.append(f"{emoji} {row['名称']}: {price:.2f} ({change_pct:.2f}%)")
    except Exception as e:
        report.append(f"⚠️ 大盘数据获取失败: {e}")

    report.append("\n🔥 **热点板块 (主力资金净流入)**")
    try:
        # stock_sector_fund_flow_rank is also EM based, might fail. 
        # But let's try it as a fallback exists.
        sector_flow = ak.stock_sector_fund_flow_rank()
        top_sectors = sector_flow.sort_values(by='今日主力净额', ascending=False).head(3)
        for _, row in top_sectors.iterrows():
            report.append(f"• {row['板块名称']}: 净流入 {row['今日主力净额']/100000000:.2f}亿 ({row['涨跌幅']:.2f}%)")
    except Exception as e:
        report.append(f"⚠️ 热点板块数据获取失败: {e}")

    report.append("\n💎 **价值洼地提醒 (低PE/PB)**")
    try:
        # Sina spot is more reliable here
        df_a = ak.stock_zh_a_spot()
        # Convert necessary columns to float
        df_a['mktcap'] = df_a['mktcap'].astype(float)
        df_a['nmc'] = df_a['nmc'].astype(float)
        df_a['pb'] = df_a['pb'].astype(float)
        # Sina spot doesn't have PE directly, but has it in some versions or we skip for now
        # Actually Sina spot HAS 'per' (PE) and 'pb'
        df_a['per'] = df_a['per'].astype(float)
        
        mask = (df_a['per'] > 0) & (df_a['per'] < 10) & (df_a['pb'] > 0) & (df_a['pb'] < 1.0)
        value_stocks = df_a[mask].sort_values(by='per').head(5)
        if not value_stocks.empty:
            for _, row in value_stocks.iterrows():
                report.append(f"• {row['name']} ({row['symbol']}): PE {row['per']:.1f}, PB {row['pb']:.2f}")
        else:
            report.append("• 暂无符合条件的价值洼地股票")
    except Exception as e:
        # Fallback to something else or just report failure
        report.append(f"⚠️ 价值选股数据获取失败: {e}")

    report.append("\n---")
    report.append("💡 *本报告由 Smart Stock Monitor 自动生成，仅供参考。*")
    
    return "\n".join(report)

if __name__ == "__main__":
    content = generate_report()
    print(content)
