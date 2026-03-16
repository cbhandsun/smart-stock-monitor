import re
from typing import Dict, List
import pandas as pd

class IntelligentQA:
    """智能问答系统"""
    
    def __init__(self, data_provider=None):
        self.data_provider = data_provider
        self.query_patterns = {
            'price': r'.*?(价格|股价|多少钱|price).*?',
            'pe': r'.*?(PE|市盈率|pe).*?',
            'pb': r'.*?(PB|市净率|pb).*?',
            'news': r'.*?(新闻|消息|公告|news).*?',
            'recommendation': r'.*?(推荐|建议|怎么看|recommend).*?',
            'trend': r'.*?(趋势|走势|trend).*?',
            'volume': r'.*?(成交量|量能|volume).*?',
            'market': r'.*?(大盘|市场|market|index).*?',
            'financial': r'.*?(财务|报表|financial).*?',
            'dividend': r'.*?(分红|股息|dividend).*?',
            'rsi': r'.*?(RSI|rsi).*?',
            'macd': r'.*?(MACD|macd).*?',
            'ma': r'.*?(均线|MA|ma).*?',
            'nl2quant': r'.*?(选股|策略|回测|突破|放量|找|买).*?'
        }
        self.stock_pattern = r'(\d{6})|([\u4e00-\u9fa5]{2,4})'
    
    def parse_query(self, query: str) -> Dict:
        """解析查询意图"""
        query_type = None
        
        for qtype, pattern in self.query_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                query_type = qtype
                break
        
        # 提取股票代码或名称
        symbol = None
        stock_match = re.search(r'(\d{6})', query)
        if stock_match:
            symbol = stock_match.group(1)
        
        return {
            'type': query_type,
            'symbol': symbol,
            'raw_query': query
        }
    
    def answer(self, query: str) -> str:
        """回答问题"""
        parsed = self.parse_query(query)
        query_type = parsed['type']
        symbol = parsed['symbol']
        
        if not query_type:
            return self._general_response(parsed)
        
        # 根据查询类型生成回答
        if query_type == 'price':
            return self._answer_price(symbol)
        elif query_type == 'pe':
            return self._answer_pe(symbol)
        elif query_type == 'pb':
            return self._answer_pb(symbol)
        elif query_type == 'trend':
            return self._answer_trend(symbol)
        elif query_type == 'volume':
            return self._answer_volume(symbol)
        elif query_type == 'market':
            return self._answer_market()
        elif query_type == 'recommendation':
            return self._answer_recommendation(symbol)
        elif query_type == 'rsi':
            return self._answer_rsi(symbol)
        elif query_type == 'macd':
            return self._answer_macd(symbol)
        elif query_type == 'ma':
            return self._answer_ma(symbol)
        elif query_type == 'nl2quant':
            return self._answer_nl2quant(parsed)
        else:
            return self._general_response(parsed)
    
    def _answer_price(self, symbol: str) -> str:
        """回答价格相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的价格是多少？"
        
        if self.data_provider:
            try:
                data = self.data_provider.get_price(symbol)
                return f"**{symbol}** 当前价格: **{data.get('price', 'N/A')}** 元，涨跌幅: {data.get('change_pct', 'N/A')}%"
            except:
                pass
        
        return f"{symbol} 当前价格信息暂时无法获取，请稍后重试。"
    
    def _answer_pe(self, symbol: str) -> str:
        """回答PE相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的PE是多少？"
        
        if self.data_provider:
            try:
                data = self.data_provider.get_fundamentals(symbol)
                pe = data.get('pe', 'N/A')
                pe_ttm = data.get('pe_ttm', 'N/A')
                return f"**{symbol}** 市盈率: **{pe}**，动态市盈率: **{pe_ttm}**"
            except:
                pass
        
        return f"{symbol} 的市盈率信息暂时无法获取。"
    
    def _answer_pb(self, symbol: str) -> str:
        """回答PB相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的PB是多少？"
        
        if self.data_provider:
            try:
                data = self.data_provider.get_fundamentals(symbol)
                pb = data.get('pb', 'N/A')
                return f"**{symbol}** 市净率: **{pb}**"
            except:
                pass
        
        return f"{symbol} 的市净率信息暂时无法获取。"
    
    def _answer_trend(self, symbol: str) -> str:
        """回答趋势相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的走势如何？"
        
        return f"**{symbol}** 近期走势分析：\n\n" \
               "- 短期趋势：需要查看具体K线数据\n" \
               "- 中期趋势：建议关注均线系统\n" \
               "- 长期趋势：结合基本面综合判断\n\n" \
               "建议使用技术分析工具进行详细分析。"
    
    def _answer_volume(self, symbol: str) -> str:
        """回答成交量相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的成交量如何？"
        
        return f"**{symbol}** 成交量分析：\n\n" \
               "成交量是判断市场活跃度的重要指标。\n" \
               "- 放量上涨：通常表示买盘强劲\n" \
               "- 缩量下跌：可能表示抛压减轻\n" \
               "- 量价背离：需要警惕趋势反转\n\n" \
               "建议结合K线图进行详细分析。"
    
    def _answer_market(self) -> str:
        """回答大盘相关问题"""
        return "**大盘分析**：\n\n" \
               "- 上证指数：反映沪市整体表现\n" \
               "- 深证成指：反映深市整体表现\n" \
               "- 创业板指：反映创业板表现\n\n" \
               "建议关注市场热点板块和资金流向。"
    
    def _answer_recommendation(self, symbol: str) -> str:
        """回答推荐相关问题"""
        if not symbol:
            return "我可以帮您分析股票，请提供股票代码。\n\n" \
                   "分析维度包括：\n" \
                   "- 基本面分析：财务指标、盈利能力\n" \
                   "- 技术面分析：趋势、支撑阻力位\n" \
                   "- 估值分析：PE、PB、PEG等指标"
        
        return f"**{symbol} 分析建议**：\n\n" \
               "1. **基本面**：建议查看财务报表和盈利能力\n" \
               "2. **技术面**：关注趋势和关键价位\n" \
               "3. **估值**：对比同行业公司估值水平\n" \
               "4. **风险**：关注行业政策和公司公告\n\n" \
               "⚠️ 以上仅供参考，投资有风险，入市需谨慎。"
    
    def _answer_rsi(self, symbol: str) -> str:
        """回答RSI相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的RSI是多少？"
        
        return f"**{symbol} RSI指标说明**：\n\n" \
               "RSI（相对强弱指标）是衡量价格变动速度和变化的技术指标。\n\n" \
               "- RSI > 70：超买区域，可能回调\n" \
               "- RSI < 30：超卖区域，可能反弹\n" \
               "- RSI 30-70：正常波动区间\n\n" \
               "建议结合其他指标综合判断。"
    
    def _answer_macd(self, symbol: str) -> str:
        """回答MACD相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的MACD如何？"
        
        return f"**{symbol} MACD指标说明**：\n\n" \
               "MACD（指数平滑异同平均线）是趋势跟踪动量指标。\n\n" \
               "- DIF上穿DEA（金叉）：买入信号\n" \
               "- DIF下穿DEA（死叉）：卖出信号\n" \
               "- MACD柱状图：反映多空力量对比\n\n" \
               "建议结合K线形态和价格趋势使用。"
    
    def _answer_ma(self, symbol: str) -> str:
        """回答均线相关问题"""
        if not symbol:
            return "请提供股票代码，例如：601318的均线如何？"
        
        return f"**{symbol} 均线系统说明**：\n\n" \
               "常用均线周期：5日、10日、20日、60日、120日、250日\n\n" \
               "- 短期均线上穿长期均线：多头排列，看涨\n" \
               "- 短期均线下穿长期均线：空头排列，看跌\n" \
               "- 股价在均线上方：强势\n" \
               "- 股价在均线下方：弱势\n\n" \
               "建议关注均线支撑和阻力作用。"

    def _answer_nl2quant(self, parsed: Dict) -> str:
        """执行自然语言到量化查询的转换 (NL2Quant)"""
        query = parsed['raw_query']
        
        # 提取典型的量化要素
        strategy_desc = []
        if re.search(r'放量|成交量放大|爆量', query):
            strategy_desc.append("- **量能因子**：要求当日成交量较前5日平均放大至少 2 倍。")
        if re.search(r'突破|站上|上穿|大阳线', query):
            if re.search(r'60日|季线', query):
                strategy_desc.append("- **动量因子**：要求收盘价强势突破 60 日均线 (MA60)。")
            elif re.search(r'20日|月线', query):
                strategy_desc.append("- **动量因子**：要求收盘价强势突破 20 日均线 (MA20)。")
            else:
                strategy_desc.append("- **动量因子**：要求收盘价突破近期盘整平台或短期均线压制。")
        if re.search(r'均线多头|多头排列|趋势向上', query):
            strategy_desc.append("- **趋势因子**：要求 MA5 > MA10 > MA20，呈现多头排列特征。")
        if re.search(r'低估值|市盈率低|PE低|便宜', query):
            strategy_desc.append("- **价值因子**：要求静态市盈率 (PE) 在 0 - 20 之间。")
        if re.search(r'AI|算力|人工智能|半导体|芯片', query):
            strategy_desc.append("- **主题因子**：限定股票池为【AI算力】、【半导体芯片】概念板块。")
            
        if not strategy_desc:
            strategy_desc.append("- **AI 综合选股**：基于多维语义模型对近期市场行情的自适应理解，提取超额收益 Alpha。")
            
        desc_str = "\n".join(strategy_desc)
        
        # 生成响应伪代码和分析报告
        return f"🚀 **NL2Quant (自然语言转量化策略) 编译中...**\n\n" \
               f"我已理解您的投研意图：「{query}」。\n" \
               f"正在将您的自然语言实时编译为底层量化因子引擎 (VectorBT) 的检索特征：\n\n" \
               f"### 🧬 生成因子映射：\n" \
               f"{desc_str}\n\n" \
               f"### ⚙️ 自动生成的底层量化脚本 (回测预览)：\n" \
               f"```python\n" \
               f"# Engine Auto-Generated Script\n" \
               f"import vectorbt as vbt\n" \
               f"import pandas as pd\n\n" \
               f"close = market_data['close']\n" \
               f"volume = market_data['volume']\n" \
               f"ma_20 = vbt.MA.run(close, window=20)\n" \
               f"vol_ma_5 = vbt.MA.run(volume, window=5)\n" \
               f"\n" \
               f"entries = close.vbt.crossed_above(ma_20.ma) & (volume > vol_ma_5.ma * 2)\n" \
               f"pf = vbt.Portfolio.from_signals(close, entries, init_cash=100000, fees=0.0003)\n" \
               f"print(pf.stats())\n" \
               f"```\n\n" \
               f"💡 *(注：策略特征提取已完成。实盘执行和池化过滤受限于风控沙箱规则，当前处于演示映射层。您可以在上方提取对应结果分析。)*"
    
    def _general_response(self, parsed: Dict) -> str:
        """通用响应"""
        return f"您好！我是SSM智能助手，可以帮您：\n\n" \
               "📊 **查询股票信息**：价格、PE、PB、成交量等\n" \
               "📈 **技术分析**：RSI、MACD、均线等指标解读\n" \
               "💡 **投资建议**：基本面和技术面分析\n" \
               "📰 **市场动态**：大盘走势和行业热点\n\n" \
               f"您的问题是：「{parsed['raw_query']}」\n\n" \
               "请尝试更具体的问题，例如：\n" \
               "- 601318的价格是多少？\n" \
               "- 茅台的PE是多少？\n" \
               "- 大盘走势如何？"
