import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") 
MODEL = os.environ.get("OPENAI_MODEL", "gemini-3-flash")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def call_ai_for_stock_diagnosis(symbol, name, reports_df, signals, dna_score=0, dna_tags=None):
    """
    使用大模型生成个股诊断报告 - 增加 DNA 引擎结论
    """
    return "".join(list(call_ai_for_stock_diagnosis_stream(symbol, name, reports_df, signals, dna_score, dna_tags)))

def call_ai_for_stock_diagnosis_stream(symbol, name, reports_df, signals, dna_score=0, dna_tags=None):
    """
    流式生成个股诊断报告 - 增加 DNA 引擎结论
    """
    if dna_tags is None: dna_tags = []
    
    reports_text = "暂无近期研报"
    if not reports_df.empty:
        reports_text = reports_df.to_string()
        
    prompt = f"""
你是一个资深的A股量化与基本面分析师。请根据以下我提供的数据，为股票 {name} ({symbol}) 撰写一份简短、专业、犀利的 AI 智能诊断摘要。

【内部量化评分结论】
- DNA 技术综合评分: {dna_score} (范围 -10 到 +10，正分看多，负分看空)
- 系统侦测标签: {', '.join(dna_tags)}

【基础技术面数据】
{signals}

【近期机构研报摘要】
{reports_text}

要求：
1. **一致性原则**: 你的情绪判读必须参考「内部量化评分」。如果评分较高（>3）但你认为悲观，必须给出极其充分的逻辑支持（如重大利空、财务造假嫌疑等），否则应保持多维度一致。
2. 给出明确的市场情绪研判（如偏向乐观/悲观/中性震荡）。
3. 给出深度逻辑分析，结合量化评分和机构观点，分析支撑或阻力逻辑。
4. 给出具体且客观的操作建议。
5. 格式：使用Markdown排版。不要使用免责声明等套话。
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个顶级的量化和基本面股票分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"⚠️ AI 诊断生成失败: {str(e)}"
