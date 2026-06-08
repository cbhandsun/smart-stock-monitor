"""
舆情与事件分析模块 — SSM Quantum Pro
获取个股最新新闻舆情并调用大模型进行情感评分和突发事件风险识别
"""
import logging
import json
import pandas as pd
from typing import Dict, Any, List, Tuple
from datetime import datetime

import akshare as ak
from core.ai_client import client, MODEL
from core.cache import RedisCache

logger = logging.getLogger(__name__)

try:
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
except Exception:
    _redis = None


def get_stock_news(symbol: str) -> pd.DataFrame:
    """
    获取个股最新新闻 (Eastmoney) — 缓存 2 小时
    """
    cache_key = f"stock:news:{symbol}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    # 转换股票代码格式，akshare 接收纯数字代码
    code = symbol
    if symbol.startswith(('sh', 'sz')):
        code = symbol[2:]
    elif '.' in symbol:
        code = symbol.split('.')[0]

    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            df = df.copy()
            # 仅保留需要的字段并限制前 5 条新闻
            df = df[['新闻标题', '新闻内容', '发布时间', '文章来源']].head(5)
            if _redis:
                _redis.set(cache_key, df, expire=7200)
            return df
    except Exception as e:
        logger.error(f"Failed to fetch stock news for {symbol}: {e}")
        
    return pd.DataFrame()


def analyze_stock_sentiment(symbol: str, name: str) -> Dict[str, Any]:
    """
    分析个股新闻舆情情感与爆雷事件
    返回：
      {
         "sentiment_score": float,  # 范围 -1.5 到 1.5 (正分多，负分空，中性 0)
         "sentiment_label": str,    # "积极" / "中性" / "消极"
         "events": List[str],        # 催化剂/风险事件列表
         "is_circuit_break": bool,  # 是否触发风控一票否决 (如重大立案调查、违约)
         "reason": str              # 舆情摘要或风控报警原因
      }
    """
    cache_key = f"stock:sentiment:{symbol}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    default_result = {
        "sentiment_score": 0.0,
        "sentiment_label": "中性",
        "events": [],
        "is_circuit_break": False,
        "reason": "暂无近期重大舆情"
    }

    # 1. 获取近期个股新闻
    news_df = get_stock_news(symbol)
    if news_df.empty:
        if _redis:
            _redis.set(cache_key, default_result, expire=7200)
        return default_result

    # 2. 拼接新闻文本供大模型分析 (只取前 3 条以防超出上下文和消耗过多 Token)
    news_items = []
    for idx, row in news_df.head(3).iterrows():
        title = row["新闻标题"]
        content = row["新闻内容"][:120] if isinstance(row["新闻内容"], str) else ""
        news_items.append(f"【新闻 {idx+1}】\n标题：{title}\n摘要：{content}\n")
    
    news_context = "\n".join(news_items)

    prompt = f"""
你是一个资深的金融风控与证券舆情分析师。请对以下个股的最新媒体报道进行情感倾向分析和风险排查：
股票名称：{name}
股票代码：{symbol}

新闻内容：
{news_context}

请严格按以下 JSON 格式进行回复，不需要任何其他解释，确保输出可以被 json.loads 解析：
{{
  "sentiment_score": 0.0,  // 情感得分，范围从 -1.5 (极度悲观/重大利空) 到 1.5 (极度乐观/重大利好)，中性为 0.0。
  "sentiment_label": "中性", // 积极 / 中性 / 消极 之一
  "events": [], // 提取的催化事件或潜在风险事件（如“签署亿元合同”、“业绩超预期”、“股东大额减持”、“因涉嫌信披违规被立案调查”等），不超过3条。
  "is_circuit_break": false, // 是否触发重大风控一票否决。当且仅当新闻包含以下事件时为 true：重大涉嫌信披违规立案调查、公司债严重违约、核心高管涉嫌刑事犯罪、控股股东涉嫌非法操纵证券市场被捕等高风险爆雷事件。
  "reason": "" // 一句话简短总结舆情概况或一票否决原因（限制在 40 字以内）。
}}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a professional financial risk controller and output only raw JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)
        
        # 结果完整性校验和值限制
        score = float(parsed.get("sentiment_score", 0.0))
        score = max(min(score, 1.5), -1.5)
        
        result = {
            "sentiment_score": score,
            "sentiment_label": parsed.get("sentiment_label", "中性"),
            "events": parsed.get("events", []),
            "is_circuit_break": bool(parsed.get("is_circuit_break", False)),
            "reason": parsed.get("reason", "舆情分析完成")
        }
        
        if _redis:
            _redis.set(cache_key, result, expire=7200) # 缓存 2 小时
        return result

    except Exception as e:
        logger.error(f"LLM sentiment analysis failed for {symbol}: {e}")
        return default_result
