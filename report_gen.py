import akshare as ak
import pandas as pd
from datetime import datetime

def generate_report():
    print(f"[{datetime.now()}] 正在生成每日盘后研报...")
    
    report = []
    report.append(f"📅 **每日股市研报 - {datetime.now().strftime('%Y-%m-%d')}**")
    report.append("---")

    # 1. 大盘表现
    try:
        df_index = ak.stock_zh_index_spot_em()
        indices = df_index[df_index['名称'].isin(['上证指数', '深证成指', '创业板指'])]
        report.append("📈 **大盘表现**")
        for _, row in indices.iterrows():
            emoji = "🔴" if row['涨跌幅'] > 0 else "🟢"
            report.append(f"{emoji} {row['名称']}: {row['最新价']} ({row['涨跌幅']:.2f}%)")
    except:
        report.append("⚠️ 大盘数据获取失败")

    report.append("\n🔥 **热点板块 (主力资金净流入)**")
    try:
        sector_flow = ak.stock_board_industry_fund_flow_rank_em()
        top_sectors = sector_flow.sort_values(by='今日主力净额', ascending=False).head(3)
        for _, row in top_sectors.iterrows():
            report.append(f"• {row['板块名称']}: 净流入 {row['今日主力净额']/100000000:.2f}亿 ({row['涨跌幅']:.2f}%)")
    except:
        report.append("⚠️ 热点板块数据获取失败")

    report.append("\n💎 **价值洼地提醒 (低PE/PB)**")
    try:
        df_a = ak.stock_zh_a_spot_em()
        mask = (df_a['市盈率-动态'] > 0) & (df_a['市盈率-动态'] < 10) & (df_a['市净率'] > 0) & (df_a['市净率'] < 1.0)
        value_stocks = df_a[mask].sort_values(by='市盈率-动态').head(5)
        for _, row in value_stocks.iterrows():
            report.append(f"• {row['名称']} ({row['代码']}): PE {row['市盈率-动态']:.1f}, PB {row['市净率']:.2f}")
    except:
        report.append("⚠️ 价值选股数据获取失败")

    report.append("\n---")
    report.append("💡 *本报告由 Smart Stock Monitor 自动生成，仅供参考。*")
    
    return "\n".join(report)

if __name__ == "__main__":
    content = generate_report()
    print(content)
