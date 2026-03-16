"""
🤖 AI智能问答页面
"""
import streamlit as st
from modules.ai.intelligent_qa import IntelligentQA

qa_system = IntelligentQA()


def render(L):
    from components.ui_components import page_header
    page_header("AI 智能问答", subtitle="自然语言转量化因子", icon="🤖")

    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []

    for msg in st.session_state['chat_history']:
        with st.chat_message(msg['role']):
            st.write(msg['content'])

    user_input = st.chat_input("请输入您的问题...")
    if user_input:
        st.session_state['chat_history'].append({'role': 'user', 'content': user_input})

        with st.chat_message('user'):
            st.write(user_input)

        with st.chat_message('assistant'):
            with st.spinner("AI思考中..."):
                response = qa_system.answer(user_input)
                st.write(response)

        st.session_state['chat_history'].append({'role': 'assistant', 'content': response})
