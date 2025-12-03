"""
文物数据抽取系统 GUI V3.0
支持多主体抽取、任务管理、数据浏览
"""

import streamlit as st
import os
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gui.db_helper import DatabaseHelper, get_column_mapping
from src.workflow import ExtractionWorkflow
from datetime import datetime, timedelta

def format_time(time_str):
    """将UTC时间转换为本地时间（+8）"""
    if not time_str:
        return ""
    try:
        # 尝试解析数据库时间字符串
        utc_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        local_dt = utc_dt + timedelta(hours=8)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return time_str

# 应用配置
st.set_page_config(
    page_title="文物数据抽取系统 V3.0",
    page_icon="🏺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全局配置
CONFIG_PATH = "config.json"
DB_PATH = "database/artifacts_v3.db"

# ========== 配置管理 ==========

def load_config():
    """加载配置文件"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 初始化
if 'config' not in st.session_state:
    st.session_state.config = load_config()

if 'db_helper' not in st.session_state:
    st.session_state.db_helper = DatabaseHelper(DB_PATH)

config = st.session_state.config
db = st.session_state.db_helper

# ========== 侧边栏 ==========

with st.sidebar:
    st.title("⚙️ 系统配置")
    
    # LLM配置
    with st.expander("🤖 LLM服务 & 资源池", expanded=False):
        provider = config['llm'].get('provider', 'coze')
        st.info(f"当前提供商: **{provider}**")
        
        tab1, tab2 = st.tabs(["基本配置", "Bot 资源池"])
        
        with tab1:
            api_url = st.text_input("API URL", value=config['llm'].get('api_url', ''))
            # 默认 API Key
            default_api_key = st.text_input("默认 API Key", value=config['llm'].get('api_key', ''), type="password")
            
            if provider == 'coze':
                default_bot_id = st.text_input("默认 Bot ID", value=config['llm'].get('bot_id', ''))
            elif provider in ['anthropic', 'gemini']:
                model = st.text_input("模型", value=config['llm'].get('model', ''))
            
            if st.button("💾 保存基本配置"):
                config['llm']['api_url'] = api_url
                config['llm']['api_key'] = default_api_key
                if provider == 'coze':
                    config['llm']['bot_id'] = default_bot_id
                elif provider in ['anthropic', 'gemini']:
                    config['llm']['model'] = model
                save_config(config)
                st.success("✅ 基本配置已保存")
                

        with tab2:
            st.markdown("配置多 Bot 资源池以支持并发抽取")
            
            # 加载现有池
            bot_pool = config['llm'].get('bot_pool', [])
            
            # 显示列表
            for i, bot in enumerate(bot_pool):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{i+1}. {bot.get('name', 'Unnamed')} ({bot.get('bot_id')})")
                with col2:
                    if st.button("❌", key=f"del_bot_{i}"):
                        bot_pool.pop(i)
                        config['llm']['bot_pool'] = bot_pool
                        save_config(config)
                        st.rerun()
            
            st.divider()
            
            # 添加新 Bot
            st.markdown("**添加新 Bot**")
            new_name = st.text_input("名称 (如: Bot 1)", key="new_bot_name")
            new_bot_id = st.text_input("Bot ID", key="new_bot_id")
            new_token = st.text_input("API Token (留空使用默认)", key="new_bot_token", type="password")
            
            if st.button("➕ 添加到资源池"):
                if new_name and new_bot_id:
                    new_bot = {
                        "name": new_name,
                        "bot_id": new_bot_id,
                        "api_key": new_token if new_token else config['llm'].get('api_key', '')
                    }
                    if 'bot_pool' not in config['llm']:
                        config['llm']['bot_pool'] = []
                    config['llm']['bot_pool'].append(new_bot)
                    save_config(config)
                    st.success("✅ 已添加")
                    st.rerun()
                else:
                    st.error("名称和 ID 必填")
    
    # 数据库配置
    with st.expander("💾 数据库", expanded=False):
        st.text_input("数据库路径", value=DB_PATH, disabled=True)
        
        st.warning("⚠️ 初始化将清空所有数据并应用 V3.2 Schema")
        if st.button("🔄 重置并初始化数据库 (V3.2)"):
            try:
                from src.database_manager_v3 import DatabaseManagerV3
                # 先尝试删除旧文件
                if os.path.exists(DB_PATH):
                    try:
                        os.remove(DB_PATH)
                        st.toast("已删除旧数据库文件")
                    except:
                        pass
                
                db_manager = DatabaseManagerV3(DB_PATH)
                db_manager.connect()
                db_manager.initialize_database()
                db_manager.close()
                st.success("✅ 数据库重置成功 (Schema V3.2)")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 初始化失败: {str(e)}")
    
    st.divider()
    
    # 统计信息
    try:
        stats = db.get_statistics()
        st.metric("总任务数", stats['task_count'])
        st.metric("文物总数", stats['artifact_count'])
        # 修复：显示去重后的图片数
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(DISTINCT image_hash) as count FROM images')
        unique_image_count = cursor.fetchone()['count']
        conn.close()
        st.metric("图片总数", unique_image_count)
    except:
        st.warning("⚠️ 数据库未初始化")

# ========== 主页面 ==========

# 页面选择
page = st.sidebar.radio(
    "导航",
    ["🚀 数据抽取", "📋 任务管理", "📊 数据浏览"],
    label_visibility="collapsed"
)

# ========== 页面1: 数据抽取 ==========

if page == "🚀 数据抽取":
    st.title("🚀 数据抽取")
    st.markdown("从考古报告中抽取遗址、时期、陶器、玉器信息")
    
    # 报告文件夹选择
    st.subheader("1. 选择报告文件夹 (支持多选)")
    
    reports_base = "遗址出土报告"
    selected_reports = []
    
    if os.path.exists(reports_base):
        # 列出所有子文件夹
        all_folders = [f for f in os.listdir(reports_base) 
                      if os.path.isdir(os.path.join(reports_base, f))]
        
        if all_folders:
            # 使用多选框
            selected_folder_names = st.multiselect(
                "选择要处理的报告",
                all_folders,
                help="可同时选择多个报告进行批量抽取"
            )
            
            if selected_folder_names:
                st.info(f"已选择 {len(selected_folder_names)} 个报告")
                for name in selected_folder_names:
                    selected_reports.append(os.path.join(reports_base, name))
                    
                # 只展示第一个报告的信息作为预览
                first_report_path = selected_reports[0]
                with st.expander(f"📄 预览: {os.path.basename(first_report_path)}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        has_md = os.path.exists(os.path.join(first_report_path, "full.md"))
                        st.metric("Markdown文件", "✅" if has_md else "❌")
                    with col2:
                        images_path = os.path.join(first_report_path, "images")
                        has_images = os.path.exists(images_path)
                        if has_images:
                            image_count = len([f for f in os.listdir(images_path) 
                                             if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                            st.metric("图片文件夹", f"✅ ({image_count}张)")
                        else:
                            st.metric("图片文件夹", "❌")
                    with col3:
                        content_list = [f for f in os.listdir(first_report_path) 
                                       if f.endswith('_content_list.json')]
                        st.metric("内容索引", "✅" if content_list else "⚠️ 可选")
        else:
            st.warning(f"⚠️ {reports_base} 文件夹中没有报告")
    else:
        st.error(f"❌ 报告目录不存在: {reports_base}")
    
    st.divider()
    
    # 模板选择
    st.subheader("2. 选择抽取模板")
    
    templates_base = "抽取模版"
    if os.path.exists(templates_base):
        # 过滤掉临时文件(~$开头)
        template_files = [f for f in os.listdir(templates_base) 
                         if f.endswith('.xlsx') and not f.startswith('~$')]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**主体信息**")
            site_template = st.selectbox(
                "遗址模板",
                ["不抽取"] + [f for f in template_files if '遗址' in f],
                help="抽取遗址的基本信息"
            )
            period_template = st.selectbox(
                "时期模板",
                ["不抽取"] + [f for f in template_files if '时期' in f],
                help="抽取时期划分信息"
            )
        
        with col2:
            st.markdown("**文物信息**")
            pottery_template = st.selectbox(
                "陶器模板",
                ["不抽取"] + [f for f in template_files if '陶器' in f],
                help="抽取陶器文物信息"
            )
            jade_template = st.selectbox(
                "玉器模板",
                ["不抽取"] + [f for f in template_files if '玉器' in f],
                help="抽取玉器文物信息"
            )
    else:
        st.error(f"❌ 模板目录不存在: {templates_base}")
    
    st.divider()
    
    # 开始抽取
    st.subheader("3. 执行抽取")
    
    # 检查是否可以开始
    can_start = (
        len(selected_reports) > 0 and
        any([
            site_template != "不抽取",
            period_template != "不抽取",
            pottery_template != "不抽取",
            jade_template != "不抽取"
        ])
    )
    
    if not can_start:
        st.info("ℹ️ 请选择至少一个报告文件夹和至少一个抽取模板")
    
    if st.button("🚀 开始批量抽取", type="primary", disabled=not can_start):
        from src.scheduler import BatchScheduler
        
        # 构建模板映射
        templates = {}
        if site_template != "不抽取":
            templates['site'] = os.path.join(templates_base, site_template)
        if period_template != "不抽取":
            templates['period'] = os.path.join(templates_base, period_template)
        if pottery_template != "不抽取":
            templates['pottery'] = os.path.join(templates_base, pottery_template)
        if jade_template != "不抽取":
            templates['jade'] = os.path.join(templates_base, jade_template)
        
        # 构建任务列表
        batch_tasks = []
        for report_path in selected_reports:
            batch_tasks.append({
                'report_folder': report_path,
                'templates': templates,
                'report_name': os.path.basename(report_path)
            })
            
        # 显示配置
        with st.expander("📋 批量任务配置", expanded=True):
            st.write(f"**报告数量**: {len(batch_tasks)}")
            st.write(f"**模板**: {', '.join(templates.keys())}")
            st.write("**并行模式**: 开启 (多Bot并发)")
        
        # 执行抽取
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        try:
            with st.spinner(f"正在并发处理 {len(batch_tasks)} 个任务..."):
                scheduler = BatchScheduler(DB_PATH)
                results = scheduler.execute_batch(batch_tasks)
                
                progress_bar.progress(100)
                status_text.text("✅ 批量任务完成！")
                
                # 显示结果摘要
                success_count = sum(1 for r in results if r['status'] == 'success')
                st.success(f"✅ 完成: {success_count} / {len(results)}")
                
                with results_container:
                    for res in results:
                        if res['status'] == 'success':
                            st.success(f"✅ {res['name']} (ID: {res['task_id']})")
                        else:
                            st.error(f"❌ {res['name']}: {res.get('error')}")
                
                st.info("💡 可以在「任务管理」页面查看详细信息")
                
        except Exception as e:
            st.error(f"❌ 批量执行失败: {str(e)}")
            import traceback
            with st.expander("错误详情"):
                st.code(traceback.format_exc())

# ========== 页面2: 任务管理 ==========

elif page == "📋 任务管理":
    st.title("📋 任务管理")
    st.markdown("查看和管理所有抽取任务")
    
    # 筛选
    col1, col2 = st.columns([3, 1])
    with col1:
        status_filter = st.multiselect(
            "状态筛选",
            ["pending", "running", "completed", "failed", "aborted"],
            default=["running", "completed", "failed"]
        )
    with col2:
        st.metric("任务总数", len(db.get_all_tasks()))
    
    # 获取任务列表
    tasks = db.get_all_tasks(status_filter if status_filter else None)
    
    if not tasks:
        st.info("ℹ️ 暂无任务记录")
    else:
        # 显示任务列表
        for task in tasks:
            # 根据状态设置颜色
            status_color = {
                "running": "🔵",
                "completed": "🟢",
                "failed": "🔴",
                "aborted": "⚫",
                "pending": "⚪"
            }.get(task['status'], "⚪")
            
            with st.expander(
                f"{status_color} {task['report_name']} (ID: {task['task_id']})",
                expanded=task['status'] == 'running'
            ):
                # --- 任务详情面板 (整合原详情功能) ---
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**状态**: {task['status']}")
                    st.write(f"**创建时间**: {format_time(task['created_at'])}")
                    if task.get('updated_at'):
                        st.write(f"**最后更新**: {format_time(task['updated_at'])}")
                
                with col2:
                    st.write(f"**陶器**: {task['total_pottery']}件")
                    st.write(f"**玉器**: {task['total_jade']}件")
                    st.write(f"**图片**: {task['total_images']}张")
                
                with col3:
                    # 操作按钮区
                    
                    # 中止任务 (仅限运行中)
                    if task['status'] == 'running':
                        if st.button("🛑 中止任务", key=f"abort_{task['id']}", type="primary"):
                            if db.abort_task(task['task_id']):
                                st.warning(f"⚠️ 已发送中止信号给任务 {task['task_id']}")
                                st.rerun()
                            else:
                                st.error("❌ 操作失败")
                    
                    # 删除任务 (所有非运行中任务均可删除)
                    if task['status'] != 'running':
                        if st.button("🗑️ 删除任务", key=f"delete_{task['id']}", type="secondary"):
                            if db.delete_task(task['task_id']):
                                st.success(f"✅ 任务 {task['task_id']} 已删除")
                                st.rerun()
                            else:
                                st.error("❌ 删除失败")
                
                st.divider()
                
                # --- 异常恢复工具 (V3.12 新增) ---
                import glob
                log_dir = os.path.join(os.path.dirname(DB_PATH), '..', 'logs', 'failed_responses')
                # 查找当前任务的失败文件
                # 文件名格式: failed_{task_id}_{timestamp}_{chunk_idx}_{...}.txt
                failed_files = glob.glob(os.path.join(log_dir, f"failed_{task['task_id']}_*.txt"))
                
                if failed_files:
                    # 修复嵌套 expander 问题，改用 container + subheader
                    st.markdown(f"#### ⚠️ 发现 {len(failed_files)} 个异常响应 (可尝试恢复)")
                    with st.container():
                        st.warning("检测到部分LLM响应解析失败。您可以查看原始内容，手动修正JSON格式并尝试恢复入库。")
                        
                        selected_file = st.selectbox(
                            "选择异常文件", 
                            failed_files,
                            format_func=lambda x: os.path.basename(x),
                            key=f"fail_sel_{task['id']}"
                        )
                        
                        if selected_file:
                            with open(selected_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                            # 分离元数据和响应体
                            parts = content.split('-' * 50 + '\n')
                            meta_info = parts[0]
                            raw_response = parts[1] if len(parts) > 1 else content
                            
                            # 解析元数据中的 artifact_type
                            artifact_type = 'pottery' # 默认
                            for line in meta_info.split('\n'):
                                if line.startswith('Artifact Type:'):
                                    artifact_type = line.split(':')[1].strip()
                                    break
                            
                            st.text(meta_info)
                            
                            # 编辑区域
                            edited_response = st.text_area(
                                "✏️ 编辑原始响应 (请确保为合法JSON或包含JSON的代码块)",
                                value=raw_response,
                                height=300,
                                key=f"edit_area_{task['id']}"
                            )
                            
                            col_r1, col_r2 = st.columns([1, 3])
                            with col_r1:
                                if st.button("🛠️ 尝试恢复并入库", key=f"recover_{task['id']}"):
                                    try:
                                        # 尝试解析
                                        parsed_data = json.loads(edited_response)
                                        if isinstance(parsed_data, dict):
                                            parsed_data = [parsed_data]
                                            
                                        # 获取映射定义
                                        mappings = db.get_template_mappings(artifact_type)
                                        # 构建映射字典: CN -> EN
                                        key_map = {}
                                        for m in mappings:
                                            if m['field_name_cn']:
                                                key_map[m['field_name_cn']] = m['field_name_en']
                                        
                                        success_count = 0
                                        
                                        # 处理每条数据
                                        for item in parsed_data:
                                            # 1. 映射键名
                                            mapped_item = {}
                                            for k, v in item.items():
                                                # 尝试直接匹配英文键
                                                if k in key_map.values():
                                                    mapped_item[k] = v
                                                # 尝试映射中文键
                                                elif k in key_map:
                                                    mapped_item[key_map[k]] = v
                                                # 尝试归一化匹配
                                                else:
                                                    # 简单模糊匹配
                                                    found = False
                                                    for cn_k, en_k in key_map.items():
                                                        if k.replace(' ', '') in cn_k.replace(' ', ''):
                                                            mapped_item[en_k] = v
                                                            found = True
                                                            break
                                                    if not found:
                                                        # 保留未映射字段作为 raw_attributes 的一部分
                                                        pass
                                            
                                            # 2. 补充必要字段
                                            mapped_item['task_id'] = task['task_id']
                                            mapped_item['site_id'] = task.get('site_id') # 从任务获取site_id
                                            # 如果没有site_id (任务可能未完全完成)，尝试查询
                                            if not mapped_item['site_id']:
                                                site = db.get_site_by_id(task.get('site_id')) if task.get('site_id') else None
                                                if site:
                                                    mapped_item['site_id'] = site['id']
                                            
                                            mapped_item['raw_attributes'] = json.dumps(item, ensure_ascii=False)
                                            
                                            # 3. 入库
                                            try:
                                                # 使用 DatabaseManager 的方法 (但这里只有 DatabaseHelper)
                                                # DatabaseHelper 没有 insert 方法，我们需要扩展 DatabaseHelper 或直接操作
                                                # 简单起见，直接使用 SQL 插入，或者给 DatabaseHelper 加个 wrapper
                                                # 最好是给 DatabaseHelper 加个通用 insert
                                                
                                                # 这里为了快速实现，直接调用底层 insert_pottery/jade 逻辑的简化版
                                                table_name = f"{artifact_type}_artifacts"
                                                
                                                # 过滤有效字段
                                                _, cols, _ = db.get_table_data(table_name, limit=0)
                                                valid_keys = [c for c in cols if c not in ['id', 'created_at']]
                                                
                                                # 确保 artifact_code
                                                if 'artifact_code' not in mapped_item:
                                                    mapped_item['artifact_code'] = f"RECOVERED_{datetime.now().strftime('%H%M%S')}_{success_count}"
                                                
                                                final_data = {k: v for k, v in mapped_item.items() if k in valid_keys}
                                                
                                                # 构造 SQL
                                                columns = ', '.join(final_data.keys())
                                                placeholders = ', '.join(['?' for _ in final_data])
                                                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                                                
                                                conn = db._get_connection()
                                                cursor = conn.cursor()
                                                cursor.execute(sql, list(final_data.values()))
                                                conn.commit()
                                                conn.close()
                                                
                                                success_count += 1
                                                
                                            except Exception as db_err:
                                                st.error(f"入库失败 ({item.get('artifact_code')}): {db_err}")
                                        
                                        if success_count > 0:
                                            st.success(f"✅ 成功恢复并入库 {success_count} 条数据！")
                                            # 标记文件已处理 (重命名)
                                            new_name = selected_file.replace("failed_", "recovered_")
                                            os.rename(selected_file, new_name)
                                            st.rerun()
                                        else:
                                            st.warning("未成功入库任何数据，请检查JSON结构或映射。")
                                            
                                    except json.JSONDecodeError:
                                        st.error("❌ JSON解析失败，请检查格式是否正确")
                                    except Exception as e:
                                        st.error(f"❌ 恢复过程出错: {str(e)}")
                
                # --- 日志区域 (整合原日志功能) ---
                st.subheader("📜 任务日志")
                
                # 获取日志
                logs = db.get_task_logs(task['task_id'])
                
                if logs:
                    # 构建日志文本
                    log_text = ""
                    for log in logs: # 显示所有日志，不再限制50条
                        level_icon = {
                            'INFO': 'ℹ️',
                            'WARNING': '⚠️',
                            'ERROR': '❌'
                        }.get(log['log_level'], '📝')
                        time_str = format_time(log['created_at']).split(' ')[1] # 只显示时间
                        log_text += f"{time_str} {level_icon} {log['message']}\n"
                    
                    # 使用文本框作为可滚动容器
                    st.text_area(
                        "日志内容",
                        value=log_text,
                        height=300,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"log_area_{task['id']}"
                    )
                else:
                    st.info("暂无日志记录")

# ========== 页面3: 数据浏览 ==========

elif page == "📊 数据浏览":
    st.title("📊 数据浏览")
    st.markdown("浏览数据库中的所有数据")
    
    # 选择浏览模式
    view_mode = st.radio(
        "浏览模式",
        ["文物浏览", "表格浏览", "📚 知识图谱定义"],
        horizontal=True
    )
    
    if view_mode == "文物浏览":
        # 文物浏览模式
        artifact_type = st.selectbox(
            "文物类型",
            ["陶器", "玉器"]
        )
        
        # 筛选
        with st.expander("🔍 筛选条件"):
            col1, col2 = st.columns(2)
            with col1:
                search = st.text_input("搜索（文物编号、类型）")
                has_images = st.checkbox("仅显示有图片的")
            with col2:
                tasks = db.get_all_tasks()
                if tasks:
                    task_filter = st.selectbox(
                        "任务",
                        ["全部"] + [t['task_id'] for t in tasks]
                    )
                else:
                    task_filter = "全部"
        
        # 构建筛选条件
        filters = {}
        if search:
            filters['search'] = search
        if has_images:
            filters['has_images'] = True
        if task_filter != "全部":
            filters['task_id'] = task_filter
        
        # 获取文物列表
        artifact_type_en = 'pottery' if artifact_type == "陶器" else 'jade'
        artifacts, total = db.get_artifacts(artifact_type_en, filters, limit=50)
        
        st.info(f"📊 共找到 **{total}** 件{artifact_type}（显示前50件）")
        
        if artifacts:
            # 显示文物列表
            for artifact in artifacts:
                with st.container():
                    col1, col2, col3 = st.columns([1, 3, 1])
                    
                    with col1:
                        # 显示主图片
                        if artifact.get('has_images'):
                            images = db.get_artifact_images(artifact['id'], artifact_type_en)
                            if images:
                                try:
                                    st.image(images[0]['image_path'], use_column_width=True)
                                except:
                                    st.write("🖼️ 图片")
                        else:
                            st.write("📦")
                    
                    with col2:
                        st.subheader(artifact['artifact_code'])
                        if artifact_type == "陶器":
                            st.write(f"器型: {artifact.get('subtype', '未知')}")
                            st.write(f"陶土: {artifact.get('clay_type', '未知')}")
                            st.write(f"尺寸: 高{artifact.get('height', '?')}cm × 径{artifact.get('diameter', '?')}cm")
                        else:
                            st.write(f"分类: {artifact.get('category_level1', '未知')}")
                            st.write(f"玉料: {artifact.get('jade_type', '未知')}")
                            st.write(f"尺寸: {artifact.get('length', '?')} × {artifact.get('width', '?')} × {artifact.get('thickness', '?')} cm")
                        st.write(f"出土: {artifact.get('found_in_tomb', '未知')}")
                        
                        # V3.2: 展示知识图谱三元组
                        with st.expander("🔗 语义三元组 (Knowledge Graph)"):
                            triples = db.get_artifact_triples(artifact['id'], artifact_type_en)
                            if triples:
                                for t in triples:
                                    st.markdown(f"""
                                    **{t['field_name_cn']}**: {t['object_value']}  
                                    <small style='color:gray'>{t['cidoc_entity']} --[{t['cidoc_property']}]--> {t['target_class']}</small>
                                    """, unsafe_allow_html=True)
                            else:
                                st.info("暂无语义数据")
                                
                        # V3.2: 展示原始数据
                        with st.expander("📝 原始数据 (Raw JSON)"):
                            if artifact.get('raw_attributes'):
                                try:
                                    st.json(json.loads(artifact['raw_attributes']))
                                except:
                                    st.text(artifact['raw_attributes'])
                            else:
                                st.info("暂无原始数据")
                    
                    with col3:
                        if artifact.get('has_images'):
                            image_count = len(db.get_artifact_images(artifact['id'], artifact_type_en))
                            st.metric("图片", f"{image_count}张")
                    
                    st.divider()
        else:
            st.info("ℹ️ 暂无数据")
    
    elif view_mode == "表格浏览":
        # 表格浏览模式
        tables = db.get_table_list()
        
        selected_table = st.selectbox("选择数据表", tables)
        
        # 检查表是否切换，如果是则重置分页
        if 'last_selected_table' not in st.session_state:
            st.session_state.last_selected_table = selected_table
        
        if st.session_state.last_selected_table != selected_table:
            st.session_state.page_number = 1
            st.session_state.last_selected_table = selected_table
        
        if selected_table:
            # 初始化 Session State 中的分页
            if 'page_number' not in st.session_state:
                st.session_state.page_number = 1
            
            # 搜索功能
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("🔍 搜索内容", placeholder="输入搜索关键词")
            with col2:
                # 获取列名用于选择搜索字段
                _, columns, _ = db.get_table_data(selected_table, limit=1)
                search_col = st.selectbox("搜索字段", columns, index=0 if columns else None)

            # 分页设置
            items_per_page = 100
            
            # 获取数据
            offset = (st.session_state.page_number - 1) * items_per_page
            data, columns, total_count = db.get_table_data(
                selected_table, 
                limit=items_per_page, 
                offset=offset,
                search_term=search_term,
                search_col=search_col
            )
            
            st.info(f"📊 共有 **{total_count}** 条记录（当前显示第 {offset+1} - {min(offset+items_per_page, total_count)} 条）")
            
            # 分页控件
            total_pages = (total_count + items_per_page - 1) // items_per_page
            if total_pages > 1:
                c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
                with c2:
                    if st.button("◀️ 上一页", disabled=st.session_state.page_number == 1):
                        st.session_state.page_number -= 1
                        st.rerun()
                with c3:
                    st.markdown(f"<div style='text-align: center'>第 {st.session_state.page_number} / {total_pages} 页</div>", unsafe_allow_html=True)
                with c4:
                    if st.button("下一页 ▶️", disabled=st.session_state.page_number == total_pages):
                        st.session_state.page_number += 1
                        st.rerun()

            # 获取列名映射
            column_mapping = get_column_mapping(selected_table)
            
            import pandas as pd
            
            # 构建 DataFrame (始终显示表头)
            if data:
                df = pd.DataFrame(data)
                # 确保列顺序与数据库一致
                if columns:
                    # 过滤掉可能不在 data 中的列 (虽然理论上不会发生)
                    valid_cols = [c for c in columns if c in df.columns]
                    df = df[valid_cols]
            else:
                # 空数据时，使用 columns 创建空 DataFrame
                df = pd.DataFrame(columns=columns)
            
            # 重命名列 (应用中文映射)
            if column_mapping:
                df = df.rename(columns=column_mapping)
            
            # 显示数据表格
            st.dataframe(df, use_container_width=True, height=600)
            
            if not data:
                st.info("ℹ️ 当前无数据")
            
            # 导出功能 (全量导出)
            if st.button("📥 导出全量数据为CSV"):
                with st.spinner("正在准备全量数据..."):
                    full_data, _, _ = db.get_table_data(selected_table, limit=-1, search_term=search_term, search_col=search_col)
                    
                    if full_data:
                        full_df = pd.DataFrame(full_data)
                    else:
                        full_df = pd.DataFrame(columns=columns)
                        
                    if column_mapping:
                        full_df = full_df.rename(columns=column_mapping)
                        
                    csv = full_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 点击下载CSV",
                        data=csv,
                        file_name=f"{selected_table}_export_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime='text/csv'
                    )

    elif view_mode == "📚 知识图谱定义":
        st.subheader("📚 CIDOC-CRM 映射定义")
        st.markdown("查看当前系统中注册的模版字段及其对应的知识图谱实体关系")
        
        type_filter = st.selectbox("文物类型", ["全部", "pottery", "jade", "site", "period"])
        
        mappings = db.get_template_mappings(None if type_filter == "全部" else type_filter)
        
        if mappings:
            import pandas as pd
            df = pd.DataFrame(mappings)
            # 选择展示列
            cols = ['artifact_type', 'field_name_cn', 'field_name_en', 'cidoc_entity', 'cidoc_property', 'target_class', 'description']
            df = df[cols]
            
            st.dataframe(
                df, 
                use_container_width=True, 
                height=600,
                column_config={
                    "artifact_type": "类型",
                    "field_name_cn": "属性名",
                    "field_name_en": "数据库字段",
                    "cidoc_entity": "Entity",
                    "cidoc_property": "Property",
                    "target_class": "Target Class",
                    "description": "说明"
                }
            )
        else:
            st.info("暂无已注册的映射定义。请先运行一次抽取任务以注册模版。")

# ========== 页脚 ==========

st.markdown("---")
st.caption("🏺 考古文物数据抽取系统 V3.0 | 支持遗址、时期、陶器、玉器多主体抽取")
