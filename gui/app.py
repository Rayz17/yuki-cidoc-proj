import streamlit as st
import os
import json
import sqlite3
import pandas as pd
import sys
import os

# 构建src目录的绝对路径
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.append(src_path)
print("添加到sys.path:", src_path)

from main import main as run_extraction

# 应用配置
st.set_page_config(page_title="文物数据抽取系统", page_icon="🏺", layout="wide")

# -------------------
# 配置文件读写功能
# -------------------

def load_config():
    """加载配置文件"""
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    """保存配置文件"""
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 初始化配置
config = load_config()

def main():
    """
    Streamlit 主应用
    """
    st.title("文物文化特征单元数据抽取系统")
    st.markdown("*利用LLM技术，从考古报告中智能抽取结构化数据*")

    # 每次 app 重新加载（如用户操作后）
    # 都动态刷新文件列表
    report_files = [f for f in os.listdir(config['reports_dir']) if f.endswith('.md')]
    template_files = [f for f in os.listdir(config['templates_dir']) if f.endswith('.xlsx')]

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 系统配置")
        # 报告与模板选择
        st.subheader("选择报告和模板")
        selected_report = st.selectbox("报告文件", ["请选择..."] + report_files, key="report")
        selected_template = st.selectbox("数据结构模板", ["请选择..."] + template_files, key="template")

        st.divider()

        # LLM配置
        st.subheader("LLM 服务")
        
        # 显示当前提供商
        provider = config['llm'].get('provider', 'unknown')
        st.info(f"当前LLM提供商: **{provider}**")
        
        # 根据提供商显示不同的配置项
        if provider == 'coze':
            bot_id = st.text_input("Bot ID", value=config['llm'].get('bot_id', ''), help="Coze Bot的ID")
        elif provider in ['anthropic', 'gemini']:
            # 使模型选择框可编辑（未来可以动态加载）
            available_models = [config['llm'].get('model', 'claude-3-sonnet-20240229')]  # 后期可以调用API获取
            selected_model = st.selectbox("模型", available_models, key="model_choice")

        # 输入API URL和API Key
        new_api_url = st.text_input("API URL", value=config['llm'].get('api_url', ''), help="LLM服务的API地址，例如 https://api.anthropic.com")
        new_api_key = st.text_input("API Key (Token)", value=config['llm'].get('api_key', ''), type="password", help="输入您的API Key或Token")

        # 保存配置的按钮
        if st.button("💾 保存 LLM 配置"):
            if new_api_url and new_api_key:
                # 更新配置
                config['llm']['api_url'] = new_api_url.strip()
                config['llm']['api_key'] = new_api_key.strip()
                
                # 根据提供商保存不同的配置
                if provider == 'coze':
                    config['llm']['bot_id'] = bot_id.strip()
                elif provider in ['anthropic', 'gemini']:
                    config['llm']['model'] = selected_model
                
                save_config(config)
                st.success("LLM 配置已更新！")
            else:
                st.error("API URL 和 API Key 都不能为空。")

    # 主页面 - 选项卡
    tab1, tab2 = st.tabs(["🔍 数据抽取", "📊 数据库浏览"])

    with tab1:
        st.header("执行数据抽取")
        # 这里会放置抽取控件和日志
        st.info("选择报告和模板后，点击『开始抽取』按钮。")
        if st.button("开始抽取", type="primary"):
            if selected_report == "请选择..." or selected_template == "请选择...":
                st.error("请先选择报告文件和数据结构模板。")
            else:
                # 构建完整的文件路径
                report_path = os.path.join(config['reports_dir'], selected_report)
                template_path = os.path.join(config['templates_dir'], selected_template)

                # 调用后端的抽取流程
                with st.spinner(f"正在抽取 `{selected_report}` 中的信息，请稍候..."):
                    try:
                        run_extraction(report_path, template_path)
                        st.success(f"✅ 成功完成对 `{selected_report}` 的抽取流程。结果已存入数据库。")
                    except Exception as e:
                        st.error(f"❌ 处理过程中发生错误: {str(e)}")

    with tab2:
        st.header("数据库浏览")
        # 连接数据库
        conn = sqlite3.connect(config['database']['path'])
        # 获取所有表名
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            st.warning("数据库为空或没有表。")
        else:
            table_names = [table[0] for table in tables]
            selected_table = st.selectbox("选择数据表", table_names)
            
            # 定义列名的中英文映射
            column_mapping = {
                'id': 'ID',
                'artifact_code': '单品编码',
                'artifact_type': '文物类型',
                'subtype': '子类型',
                'material_type': '材料种类',
                'process': '工艺',
                'found_in_tomb': '出土墓葬'
            }
            
            # 读取并显示表数据
            if selected_table:
                df = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
                
                # 显示数据统计
                st.info(f"📊 共有 **{len(df)}** 条记录")
                
                # 重命名列为中文
                df_display = df.rename(columns=column_mapping)
                
                # 显示数据表
                st.dataframe(df_display, use_container_width=True)
                
                # 导出功能（使用中文列名）
                csv = df_display.to_csv(index=False).encode('utf-8-sig')  # 使用utf-8-sig以支持Excel
                st.download_button(
                    label="📥 导出为 CSV",
                    data=csv,
                    file_name=f"{selected_table}_export.csv",
                    mime='text/csv',
                )
    conn.close()
    st.markdown("---")
    st.caption("GUI v1.0 | 使用LLM技术从考古报告中智能抽取结构化数据")
if __name__ == "__main__":
    main()
