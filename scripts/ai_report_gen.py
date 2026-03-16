import akshare as ak
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 设置 API Key 和 Base URL (Gemini 兼容 OpenAI 格式的接口)
API_KEY = os.environ.get("OPENAI_API_KEY", "your_api_key_here")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") 
MODEL = os.environ.get("OPENAI_MODEL", "gemini-3.0-flash")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_market_data():
    """获取基础市场数据，用于给大模型做背景输入"""
    data_context = ""
    # 1. 大盘表现
    try:
        df_index = ak.stock_zh_index_spot_em()
        indices = df_index[df_index['名称'].isin(['上证指数', '深证成指', '创业板指'])]
        data_context += "【大盘表现】\n"
        for _, row in indices.iterrows():
            data_context += f"{row['名称']}: {row['最新价']} (涨跌幅 {row['涨跌幅']:.2f}%)\n"
    except Exception as e:
        pass
    
    # 2. 行业资金流向
    try:
        sector_flow = ak.stock_board_industry_fund_flow_rank_em()
        top_sectors = sector_flow.sort_values(by='今日主力净额', ascending=False).head(3)
        data_context += "\n【主力资金流入前三板块】\n"
        for _, row in top_sectors.iterrows():
            data_context += f"{row['板块名称']}: 净流入 {row['今日主力净额']/100000000:.2f}亿\n"
    except Exception as e:
        pass

    return data_context

def get_latest_news():
    """获取财联社最新的宏观及行业电报资讯"""
    try:
        # 获取财联社电报
        df_news = ak.stock_info_global_cls()
        # 取最新的前10条重要资讯（可以过滤掉字数太少的）
        df_news['len'] = df_news['内容'].astype(str).str.len()
        top_news = df_news[df_news['len'] > 30].head(10)
        
        news_text = "【今日最新宏观与行业资讯（财联社电报）】\n"
        for idx, row in top_news.iterrows():
            news_text += f"- [{row['发布时间']}] {row['标题']}: {row['内容'][:100]}...\n"
        return news_text
    except Exception as e:
        return f"获取资讯失败: {str(e)}"

def generate_ai_analysis(market_data, custom_news=""):
    """调用大模型生成分析"""
    prompt = f"""
你是一个资深的金融分析师。请结合以下今天的A股市场数据和宏观/行业资讯，写一份专业、深度的股市收盘点评。
要求：
1. 包含对大盘的整体判断，解释涨跌背后的逻辑。
2. 结合主力资金流向，深入剖析当前市场主线。
3. 结合我提供的最新的行业宏观新闻，发掘潜在的政策红利或行业风口，给出对明日或短期的前瞻性操作建议。
4. 语言要专业、客观，结构清晰（使用Markdown）。不要使用免责声明等套话，像一个真正的券商研究员一样输出干货。

【今日市场盘面数据】
{market_data}

【行业与宏观资讯】
{custom_news}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个顶级的量化和基本面股票分析师，能够从繁杂的数据和新闻中抽丝剥茧，发现市场主线。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI 分析生成失败: {str(e)}"

def generate_report():
    print(f"[{datetime.now()}] 1. 正在抓取盘面数据...")
    market_data = get_market_data()
    
    print(f"[{datetime.now()}] 2. 正在抓取财联社最新宏观与行业资讯...")
    news_data = get_latest_news()
    
    print(f"[{datetime.now()}] 3. 正在调用 Gemini 3 Flash 模型生成深度分析...")
    ai_analysis = generate_ai_analysis(market_data, news_data)
    
    report = f"📅 **AI 驱动股市深度研报 - {datetime.now().strftime('%Y-%m-%d')}**\n"
    report += "---\n\n"
    report += ai_analysis
    report += "\n\n---\n"
    report += f"💡 *本报告由 {MODEL} 模型结合智能投研系统自动生成。*"
    
    return report

if __name__ == "__main__":
    report_content = generate_report()
    print("\n" + "="*50 + " 研报输出 " + "="*50 + "\n")
    print(report_content)
