import streamlit as st
import time
import os
import sys
import pandas as pd
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.utils.api_client import APIClient

# Initialize API Client
api_base = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
client = APIClient(api_base)

st.set_page_config(
    page_title="Archaeo Extractor V3.5",
    page_icon="🏺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Components ---

def render_bot_status_indicator():
    """Renders a small status indicator for Bot Pool."""
    try:
        agents = client.list_agents()
        total_structure = len([a for a in agents if a['agent_type'] == 'STRUCTURE' and a['is_active']])
        total_extraction = len([a for a in agents if a['agent_type'] == 'EXTRACTION' and a['is_active']])
        total_dedup = len([a for a in agents if a['agent_type'] == 'DEDUP' and a['is_active']])
        
        st.sidebar.markdown(f"**Bot 资源池**")
        st.sidebar.caption(f"🏗️ 结构化 Agents: {total_structure}")
        st.sidebar.caption(f"⛏️ 抽取 Agents: {total_extraction}")
        st.sidebar.caption(f"⚖️ 判重 Agents: {total_dedup}")
    except:
        st.sidebar.warning("无法连接后端")

def render_new_task_form():
    with st.expander("📝 发起新任务", expanded=False):
        uploaded_files = st.file_uploader("上传报告文件 (支持多文件)", type=["txt", "md"], accept_multiple_files=True)
        
        if uploaded_files:
            c1, c2 = st.columns(2)
            
            # Mode 1: Merge Launch
            if c1.button("🔗 合并启动抽取任务", type="primary", help="将所有文件合并为一个任务进行抽取"):
                with st.spinner("正在上传并分配 Bot 资源..."):
                    try:
                        # Save temp files
                        temp_paths = []
                        for uf in uploaded_files:
                            path = f"temp_{uf.name}"
                            with open(path, "wb") as f:
                                f.write(uf.getbuffer())
                            temp_paths.append(path)
                        
                        # Create Task
                        res = client.create_task(temp_paths)
                        
                        # Cleanup
                        for p in temp_paths:
                            os.remove(p)
                            
                        st.success(f"任务创建成功! ID: {res['task_id']}")
                        st.info(f"状态: {res['status']} - {res['message']}")
                        if res['status'] == "QUEUED":
                            st.warning("资源不足，任务已进入队列，将自动调度。")
                        else:
                            st.info(f"已分配 Bot 对: {res['bot_pair']['structure']} + {res['bot_pair']['extraction']}")
                        
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"创建失败: {e}")

            # Mode 2: Split Launch
            if c2.button("🔀 分任务启动抽取", help="每个文件单独启动一个任务"):
                with st.spinner("正在批量创建任务..."):
                    success_count = 0
                    fail_count = 0
                    
                    for uf in uploaded_files:
                        try:
                            # Save temp file
                            path = f"temp_{uf.name}"
                            with open(path, "wb") as f:
                                f.write(uf.getbuffer())
                            
                            # Create Task (Single file)
                            client.create_task([path])
                            
                            # Cleanup
                            os.remove(path)
                            success_count += 1
                        except Exception as e:
                            st.error(f"文件 {uf.name} 创建失败: {e}")
                            fail_count += 1
                    
                    if success_count > 0:
                        st.success(f"成功创建 {success_count} 个任务！")
                    if fail_count > 0:
                        st.warning(f"{fail_count} 个文件创建失败。")
                        
                    time.sleep(2)
                    st.rerun()

def render_task_list():
    st.subheader("任务列表")
    
    # Filters
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        status_filter = st.selectbox("状态筛选", ["ALL", "QUEUED", "PENDING", "STRUCTURING", "EXTRACTING", "COMPLETED", "STOPPED", "FAILED", "CANCELLED", "SUSPENDED"])
    
    # Sorting (Not implemented in backend yet, doing client-side sorting for V3.5 GUI)
    # Actually client.list_tasks returns list, we can sort it here.
    with col2:
        sort_order = st.selectbox("排序", ["创建时间 (新->旧)", "创建时间 (旧->新)"])
        
    with col3:
        if st.button("🔄 刷新列表"):
            st.rerun()

    # List Tasks
    try:
        tasks = client.list_tasks(status=status_filter if status_filter != "ALL" else None)
        
        # Add defensive check if tasks is None or not a list
        if tasks is None:
            tasks = []
        if not isinstance(tasks, list):
            st.error(f"API returned unexpected format for tasks: {type(tasks)}")
            tasks = []
        
        if not tasks:
            st.info("暂无任务")
            return
            
        # Client-side sort
        if sort_order == "创建时间 (新->旧)":
            tasks.sort(key=lambda x: x['created_at'], reverse=True)
        else:
            tasks.sort(key=lambda x: x['created_at'], reverse=False)

        # Header
        cols = st.columns([2, 1, 2, 2, 3])
        cols[0].markdown("**任务 ID / 文件**")
        cols[1].markdown("**状态**")
        cols[2].markdown("**Bot 配置 / 结果**") # Updated Header
        cols[3].markdown("**时间**")
        cols[4].markdown("**操作**")
        st.divider()

        for task in tasks:
            cols = st.columns([2, 1, 2, 2, 3])
            
            # 1. ID & Files
            with cols[0]:
                st.markdown(f"**{task['id'][:8]}...**")
                
                # Defensive check for target_files
                target_files = task.get('target_files')
                if not target_files:
                    files_str = "Unknown"
                elif isinstance(target_files, str):
                    # Should be parsed JSON, but if API returns raw string (unlikely with V3.5)
                    files_str = target_files
                elif isinstance(target_files, list):
                    # Handle new format (list of dicts) vs old format (list of strings)
                    display_names = []
                    for f in target_files:
                        if isinstance(f, dict):
                            display_names.append(f.get('original', 'Unknown'))
                        else:
                            display_names.append(str(f))
                            
                    file_count = len(display_names)
                    files_str = ", ".join(display_names[:2])
                    if file_count > 2:
                        files_str += f" (+{file_count-2})"
                else:
                    files_str = "Invalid Format"
                    
                st.caption(f"📂 {files_str}")

            # 2. Status
            with cols[1]:
                status_color = {
                    "COMPLETED": "green",
                    "FAILED": "red",
                    "CANCELLED": "grey",
                    "STOPPED": "orange", # Stopped color
                    "SUSPENDED": "orange",
                    "PENDING": "blue",
                    "QUEUED": "grey", # Queued color
                    "STRUCTURING": "blue",
                    "EXTRACTING": "blue"
                }.get(task['status'], "grey")
                
                status_text = f":{status_color}[{task['status']}]"
                if task['is_paused'] and task['status'] not in ["SUSPENDED", "STOPPED"]:
                    status_text += " ⏸️"
                st.markdown(status_text)

            # 3. Bot Info & Results
            with cols[2]:
                # Bot Info
                model_info = task.get('llm_model_info') or {}
                
                s_bot_data = model_info.get('structure_bot', {})
                s_name = s_bot_data.get('name', '-')
                s_model = s_bot_data.get('model', '')
                
                e_bot_data = model_info.get('extraction_bot', {})
                e_name = e_bot_data.get('name', '-')
                e_model = e_bot_data.get('model', '')
                
                # Show bots if assigned
                if task['status'] != "QUEUED":
                    s_display = f"{s_name}"
                    if s_model and s_model != "Unknown":
                        s_display += f" [{s_model}]"
                    st.caption(f"🏗️ {s_display}")
                    
                    e_display = f"{e_name}"
                    if e_model and e_model != "Unknown":
                        e_display += f" [{e_model}]"
                    st.caption(f"⛏️ {e_display}")
                else:
                    st.caption("⏳ 等待资源...")

                # Result Summary
                entity_count = task.get('entity_count', 0)
                if entity_count > 0:
                    st.markdown(f"**📊 已抽取: {entity_count}**")

            # 4. Time
            with cols[3]:
                st.caption(f"创建: {task['created_at'].split('T')[0]}")
                if task['start_time']:
                    st.caption(f"开始: {task['start_time'].split('T')[1][:8]}")

            # 5. Actions
            with cols[4]:
                c1, c2, c3 = st.columns(3)
                
                # Log Button
                with st.popover("📜 日志"):
                    st.markdown(f"**任务日志 ({task['id'][:8]})**")
                    st.text_area("Logs", value=task.get('global_tips') or "暂无日志", height=300, disabled=True, key=f"log_area_{task['id']}")
                
                # View Details (Moved to separate button logic below popover to avoid nesting issues if any)
                if c1.button("👁️ 详情", key=f"view_{task['id']}"):
                    st.session_state['active_task_id'] = task['id']
                    st.rerun()

                # Control Buttons
                if task['status'] == "QUEUED":
                    if c2.button("🚫 取消", key=f"cancel_q_{task['id']}", help="取消排队并删除任务"):
                        try:
                            client.delete_task(task['id'])
                            st.toast("任务已取消并删除")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                elif task['status'] in ["STRUCTURING", "EXTRACTING"]:
                    if task['is_paused']:
                        if c2.button("▶️ 继续", key=f"res_{task['id']}"):
                            client.resume_task(task['id'])
                            st.rerun()
                    else:
                        if c2.button("⏸️ 暂停", key=f"pau_{task['id']}"):
                            client.pause_task(task['id'])
                            st.rerun()
                    
                    if c3.button("⏹️ 终止", key=f"stop_{task['id']}"):
                        client.stop_task(task['id'])
                        st.rerun()
                
                # Resume Suspended
                elif task['status'] == "SUSPENDED":
                    if c2.button("🔄 恢复", key=f"res_sus_{task['id']}"):
                        try:
                            client.resume_task(task['id'])
                            st.success("任务已重新启动")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                    
                    if c3.button("⏹️ 终止", key=f"stop_{task['id']}"):
                        client.stop_task(task['id'])
                        st.rerun()
                
                # Merge (COMPLETED or STOPPED)
                elif task['status'] in ["COMPLETED", "STOPPED"]:
                    if c2.button("💾 入库", key=f"mrg_{task['id']}"):
                        try:
                            res = client.merge_task(task['id'])
                            st.toast(f"合并成功: {res['merged_entities']} 新增, {res['updated_entities']} 更新")
                        except Exception as e:
                            st.error(str(e))

            st.divider()

    except Exception as e:
        st.error(f"加载任务列表失败: {e}")

def render_task_detail_view():
    task_id = st.session_state.get('active_task_id')
    if not task_id:
        return

    st.button("⬅️ 返回列表", on_click=lambda: st.session_state.pop('active_task_id'))
    st.header(f"任务详情: {task_id}")

    try:
        # Fetch Data
        status = client.get_task_status(task_id)
        results = client.get_task_results(task_id) # Only if has results, handled inside? API returns empty list if none
        
        # Header Info
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"状态: {status['status']}")
            if status['global_tips']:
                with st.expander("📝 全局上下文 / 日志 (Global Tips & Logs)"):
                    st.text(status['global_tips']) # Use text to preserve formatting
        
        with col2:
            st.caption(f"创建时间: {status['created_at']}")
            if status.get('llm_model_info'):
                st.json(status['llm_model_info'], expanded=False)

        st.subheader("抽取结果")
        
        # Export Button
        if st.button("📥 准备导出 CSV", help="生成当前任务详情的 CSV 文件"):
             with st.spinner("正在生成 CSV..."):
                 try:
                     csv_data = client.export_task_csv(task_id)
                     st.download_button(
                         label="⬇️ 点击下载 CSV",
                         data=csv_data,
                         file_name=f"task_{task_id}_export.csv",
                         mime="text/csv"
                     )
                 except Exception as e:
                     st.error(f"导出失败: {e}")

        if results and results.get('data'):
            _render_entity_tree(results['data'])
            
            # Allow merge for COMPLETED or STOPPED
            if status['status'] in ["COMPLETED", "STOPPED"]:
                st.divider()
                if st.button("💾 确认结果并入库", type="primary"):
                    try:
                        res = client.merge_task(task_id)
                        st.balloons()
                        st.success(f"合并成功! 新增: {res['merged_entities']}, 更新: {res['updated_entities']}")
                    except Exception as e:
                        st.error(f"合并失败: {e}")
        else:
            st.info("暂无抽取数据")

    except Exception as e:
        st.error(f"加载详情失败: {e}")

def _render_entity_tree(entities):
    """Recursive-like rendering of flat entity list into a tree."""
    roots = [e for e in entities if not e['parent_id']]
    if not roots and entities:
        st.warning("数据结构异常：找不到根节点")
        st.write(entities)
        return

    for root in roots:
        _render_node(root, entities)

def _render_node(node, all_entities, level=0):
    """Render a single node and its children."""
    label = f"**{node['name']}** ({node['type']})"
    children = [e for e in all_entities if e['parent_id'] == node['id']]
    
    with st.expander(label, expanded=(level < 2)):
        if node.get('tips'):
            st.caption(f"💡 {node['tips']}")
        
        attrs = node.get('attributes', {})
        if attrs:
            data = []
            # Sort by code to keep related attributes together
            for code in sorted(attrs.keys()):
                detail = attrs[code]
                data.append({
                    "Code": code, 
                    "Value": detail.get('value', ''), 
                    "Quote": detail.get('quote', '')
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        
        for child in children:
            _render_node(child, all_entities, level + 1)

def render_master_data():
    st.header("📚 数据资产库")
    
    tab1, tab2 = st.tabs(["资产查询", "版本快照 (Backups)"])
    
    with tab1:
        # Filters
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            site_filter = st.text_input("按遗址名称筛选")
        with col2:
            type_filter = st.selectbox("按类型筛选", ["", "SITE", "FEATURE", "POTTERY", "JADE"])
        
        # Pagination Controls
        if 'master_page' not in st.session_state:
            st.session_state['master_page'] = 1
        if 'master_page_size' not in st.session_state:
            st.session_state['master_page_size'] = 30
            
        with col3:
             # Find index for selectbox
             try:
                 idx = [30, 50, 100].index(st.session_state['master_page_size'])
             except:
                 idx = 0
             page_size = st.selectbox("每页显示", [30, 50, 100], index=idx, key="page_size_select")
             
             if page_size != st.session_state['master_page_size']:
                 st.session_state['master_page_size'] = page_size
                 st.session_state['master_page'] = 1 # Reset to page 1
                 st.rerun()

        with col4:
            st.write("") # Spacer
            if st.button("🔍 搜索", type="primary"):
                st.session_state['master_page'] = 1 
                st.rerun()

        # Export Button (Bulk)
        if st.button("📥 导出全部搜索结果 (CSV)", help="导出符合当前筛选条件的所有数据"):
             with st.spinner("正在导出..."):
                 try:
                     csv_data = client.export_master_entities(
                         site_name=site_filter if site_filter else None,
                         entity_type=type_filter if type_filter else None
                     )
                     st.download_button(
                         label="⬇️ 保存导出文件",
                         data=csv_data,
                         file_name=f"master_data_export_{int(time.time())}.csv",
                         mime="text/csv"
                     )
                 except Exception as e:
                     st.error(f"导出失败: {e}")

        st.divider()

        # Fetch Data
        current_page = st.session_state['master_page']
        current_size = st.session_state['master_page_size']

        with st.spinner("查询中..."):
            try:
                res = client.get_master_entities(
                    site_name=site_filter if site_filter else None,
                    entity_type=type_filter if type_filter else None,
                    page=current_page,
                    size=current_size
                )
                
                # Handle response format
                if isinstance(res, list):
                    entities = res
                    total = len(res)
                else:
                    entities = res.get('items', [])
                    total = res.get('total', 0)
                
                if entities:
                    total_pages = (total + current_size - 1) // current_size
                    st.write(f"找到 {total} 条记录。 (第 {current_page} 页 / 共 {total_pages} 页)")
                    
                    # Jump to page
                    c_jump1, c_jump2 = st.columns([1, 4])
                    with c_jump1:
                        target_page = st.number_input("跳转至页码", min_value=1, max_value=max(1, total_pages), value=current_page)
                        if target_page != current_page:
                             st.session_state['master_page'] = target_page
                             st.rerun()

                    # Data Table
                    flat_data = []
                    for e in entities:
                        row = {
                            "遗址": e['site_name'],
                            "名称": e['name'],
                            "类型": e['type'],
                            "最后更新": e['updated_at']
                        }
                        for k, v in e.get('attributes', {}).items():
                            if isinstance(v, dict):
                                row[k] = v.get('value', '')
                            else:
                                row[k] = v
                        flat_data.append(row)
                    
                    df = pd.DataFrame(flat_data)
                    
                    # Configure Columns
                    fixed_cols = ["遗址", "名称", "类型", "最后更新"]
                    other_cols = sorted([c for c in df.columns if c not in fixed_cols])
                    final_order = fixed_cols + other_cols
                    
                    # Calculate height to remove vertical scrollbar
                    # Approx 35px per row + header. 
                    # 100 rows * 35 = 3500px.
                    table_height = (len(df) + 1) * 35 + 3
                    
                    st.dataframe(
                        df, 
                        use_container_width=True, 
                        height=table_height, 
                        column_order=final_order,
                        hide_index=True
                    )
                    
                    # Bottom Pagination
                    c1, c2, c3 = st.columns([1, 4, 1])
                    if current_page > 1:
                        if c1.button("⬅️ 上一页", key="prev_btn"):
                            st.session_state['master_page'] -= 1
                            st.rerun()
                    if current_page < total_pages:
                        if c3.button("下一页 ➡️", key="next_btn"):
                            st.session_state['master_page'] += 1
                            st.rerun()

                else:
                    st.info("未找到实体。")
            except Exception as e:
                st.error(f"获取数据失败: {e}")

    with tab2:
        st.markdown("管理主数据的历史版本快照。")
        if st.button("📸 创建新快照 (Backup)"):
            try:
                res = client.create_snapshot()
                st.success(f"快照创建成功: {res['filename']} ({res['count']} 条记录)")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"创建失败: {e}")
        
        st.divider()
        
        # List Snapshots
        try:
            snapshots = client.list_snapshots()
            if snapshots:
                for snap in snapshots:
                    with st.expander(f"📦 {snap}", expanded=False):
                        c1, c2 = st.columns(2)
                        if c1.button("查看内容", key=f"view_{snap}"):
                            data = client.get_snapshot_content(snap)
                            st.json(data[:3]) # Show first 3 items preview
                            st.caption(f"共 {len(data)} 条记录")
                            
                        if c2.button("⚠️ 恢复此版本 (Restore)", key=f"rest_{snap}"):
                            try:
                                res = client.restore_snapshot(snap)
                                st.success(f"恢复成功! 恢复了 {res['restored_count']} 条记录。")
                            except Exception as e:
                                st.error(f"恢复失败: {e}")
            else:
                st.info("暂无快照")
        except Exception as e:
            st.error(f"无法加载快照列表: {e}")

def render_db_manager():
    st.header("🗄️ 数据库管理")
    tab1, tab2, tab3 = st.tabs(["表结构与预览", "SQL 查询", "危险操作"])
    
    with tab1:
        if st.button("刷新架构"):
            try:
                schema = client.get_db_schema()
                for table, columns in schema.items():
                    with st.expander(f"📋 {table}", expanded=False):
                        st.table(pd.DataFrame(columns))
                        try:
                            preview = client.get_table_preview(table)
                            if preview.get('data'):
                                st.dataframe(pd.DataFrame(preview['data'], columns=preview['columns']))
                        except: pass
            except Exception as e:
                st.error(f"Error: {e}")

    with tab2:
        query = st.text_area("SQL (SELECT only)", height=100)
        if st.button("运行"):
            try:
                res = client.execute_query(query)
                if res.get('data'):
                    st.dataframe(pd.DataFrame(res['data'], columns=res['columns']))
                else:
                    st.info("无结果")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab3:
        if st.button("🔴 重置数据库 (危险)"):
            try:
                client.reset_database()
                st.success("重置成功")
            except Exception as e:
                st.error(str(e))

def render_settings():
    st.header("⚙️ 系统设置")
    
    # Auto Merge Setting
    st.subheader("自动化设置")
    try:
        # Fetch current settings
        settings_list = client.get_settings()
        settings_dict = {s['key']: s['value'] for s in settings_list}
        
        auto_merge = st.toggle("✅ 任务完成后自动入库 (Auto-Merge)", value=(settings_dict.get("auto_merge_enabled") == "true"))
        
        if st.button("保存自动化设置"):
            client.update_setting(
                key="auto_merge_enabled",
                value="true" if auto_merge else "false",
                description="Automatically merge task results to master data upon completion."
            )
            st.success("设置已保存")
            
    except Exception as e:
        st.error(f"无法加载设置: {e}")

    st.divider()
    
    with st.expander("➕ 添加新 Agent", expanded=False):
        with st.form("add_agent"):
            c1, c2 = st.columns(2)
            name = c1.text_input("名称")
            bot_id = c2.text_input("Bot ID")
            atype = st.selectbox("类型", ["STRUCTURE", "EXTRACTION", "DEDUP"])
            token = st.text_input("Token (Optional)", type="password")
            url = st.text_input("Base URL (Optional)")
            
            if st.form_submit_button("添加"):
                try:
                    client.create_agent(name, bot_id, atype, token, url)
                    st.success("添加成功")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.subheader("现有 Agent")
    try:
        agents = client.list_agents()
        if agents:
            df = pd.DataFrame(agents)
            st.dataframe(df[['name', 'bot_id', 'agent_type', 'is_active', 'locked_by_task_id']])
            
            # Simple delete UI
            to_del = st.selectbox("选择删除", options=[a['id'] for a in agents], format_func=lambda x: next(a['name'] for a in agents if a['id']==x))
            if st.button("删除选定 Agent"):
                client.delete_agent(to_del)
                st.rerun()
    except Exception as e:
        st.error(str(e))

def main():
    render_bot_status_indicator()
    
    st.sidebar.title("导航")
    
    # Navigation Logic
    # If active_task_id is set, we are in Detail View, but sidebar can switch us out
    
    page = st.sidebar.radio("前往", ["任务中心", "数据资产", "数据库管理", "系统设置"])
    
    if page == "任务中心":
        if 'active_task_id' in st.session_state:
            render_task_detail_view()
        else:
            render_new_task_form()
            render_task_list()
            
    elif page == "数据资产":
        if 'active_task_id' in st.session_state:
            del st.session_state['active_task_id']
        render_master_data()
        
    elif page == "数据库管理":
        if 'active_task_id' in st.session_state:
            del st.session_state['active_task_id']
        render_db_manager()
        
    elif page == "系统设置":
        if 'active_task_id' in st.session_state:
            del st.session_state['active_task_id']
        render_settings()

if __name__ == "__main__":
    main()
