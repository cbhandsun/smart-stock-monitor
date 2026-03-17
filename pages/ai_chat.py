"""
🤖 AI智能问答页面 — V2.0
欢迎面板 + 快捷问题 + 清除历史 + 对话轮次
"""
import streamlit as st
from modules.ai.intelligent_qa import IntelligentQA

qa_system = IntelligentQA()

# 快捷问题
QUICK_QUESTIONS = [
    ("📊 今天大盘怎么样?", "今天A股大盘走势如何？请分析三大指数表现"),
    ("💎 推荐低估值股票", "请推荐几只当前低估值的优质A股标的"),
    ("🔥 最近有什么热点?", "最近A股有哪些热点板块和概念？"),
    ("📈 分析自选股", "帮我分析一下自选股的整体表现和风险"),
]


def render(L):
    from components.ui_components import page_header
    page_header("AI 智能问答", subtitle="自然语言转量化因子", icon="🤖")

    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []

    history = st.session_state['chat_history']

    # ---- 头部: 对话轮次 + 清除 ----
    if history:
        rounds = len([m for m in history if m['role'] == 'user'])
        hdr1, hdr2 = st.columns([4, 1])
        with hdr1:
            st.caption(f"💬 对话轮次: {rounds}")
        with hdr2:
            if st.button("🗑️ 清除", key="clear_chat", use_container_width=True,
                        help="清除所有对话记录"):
                st.session_state['chat_history'] = []
                st.rerun()

    # ---- 欢迎面板 (无历史时显示) ----
    if not history:
        st.markdown('''<div class="chat-welcome">
    <div class="chat-welcome-icon">🤖</div>
    <div class="chat-welcome-title">欢迎使用 AI 智能问答</div>
    <div class="chat-welcome-desc">
        我可以帮您分析大盘走势、筛选股票、解读技术指标、<br>
        评估投资组合风险。试试下面的快捷问题开始对话 👇
    </div>
</div>''', unsafe_allow_html=True)

        # 快捷问题按钮
        q_cols = st.columns(len(QUICK_QUESTIONS))
        for i, (label, question) in enumerate(QUICK_QUESTIONS):
            with q_cols[i]:
                if st.button(label, key=f"quick_{i}", use_container_width=True):
                    st.session_state['chat_history'].append({'role': 'user', 'content': question})
                    # 立即流式获取回复
                    with st.spinner("AI 思考中..."):
                        response = qa_system.answer(question)
                    st.session_state['chat_history'].append({'role': 'assistant', 'content': response})
                    st.rerun()
        return

    # ---- 对话历史 ----
    for msg in history:
        with st.chat_message(msg['role']):
            st.write(msg['content'])

    # ---- 输入框 ----
    user_input = st.chat_input("输入您的问题... (支持中文自然语言)")
    if user_input:
        st.session_state['chat_history'].append({'role': 'user', 'content': user_input})

        with st.chat_message('user'):
            st.write(user_input)

        with st.chat_message('assistant'):
            with st.spinner("🧠 AI 思考中..."):
                response = qa_system.answer(user_input)
                st.write(response)

        st.session_state['chat_history'].append({'role': 'assistant', 'content': response})
