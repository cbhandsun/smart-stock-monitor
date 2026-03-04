import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") 
MODEL = os.environ.get("OPENAI_MODEL", "gemini-2.5-flash")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def call_ai_for_stock_diagnosis(symbol, name, reports_df, signals):
    """
    使用大模型生成个股诊断报告
    """
    reports_text = "暂无近期研报"
    if not reports_df.empty:
        reports_text = reports_df.to_string()
        
    prompt = f"""
你是一个资深的A股量化与基本面分析师。请根据以下我提供的数据，为股票 {name} ({symbol}) 撰写一份简短、专业、犀利的 AI 智能诊断摘要。

【技术面信号】
{signals}

【近期机构研报摘要】
{reports_text}

要求：
1. 给出明确的市场情绪研判（如偏向乐观/悲观/中性震荡）。
2. 给出深度逻辑分析，结合技术面和机构观点，分析支撑或阻力逻辑。
3. 给出具体且客观的操作建议。
4. 格式：使用Markdown排版。不要使用免责声明等套话。
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个顶级的量化和基本面股票分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI 诊断生成失败: {str(e)}"
