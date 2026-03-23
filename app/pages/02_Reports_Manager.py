import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
import pandas as pd
from datetime import datetime
from uuid import uuid4
from sqlalchemy import inspect
from app.datasources.mssql import get_engine
from app.services.report_storage import ReportStorage
from app.services.exporter import to_csv_bytes, to_excel_bytes

st.set_page_config(page_title="报表管理", page_icon="🗂️", layout="wide")

# 添加CSS样式优化行间距
st.markdown("""
<style>
    /* 搜索区域按钮样式 - 高度与搜索框一致，宽度为6个字符 */
    button[data-testid="baseButton-primary"][aria-label="🔍 搜索"],
    button[data-testid="baseButton-secondary"][aria-label="🔄 刷新"] {
        margin: 0 !important;
        padding: 0.375rem 0.75rem !important;
        height: 2.5rem !important;
        min-height: 2.5rem !important;
        max-height: 2.5rem !important;
        width: 6ch !important;
        min-width: 6ch !important;
        max-width: 6ch !important;
        line-height: 1.2 !important;
        font-size: 0.875rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🗂️ 报表管理")
engine = get_engine()
report_storage = ReportStorage(engine)

# 页面状态管理
if "search_keyword" not in st.session_state:
	st.session_state["search_keyword"] = ""
if "selected_report_id" not in st.session_state:
	st.session_state["selected_report_id"] = None
if "show_preview" not in st.session_state:
	st.session_state["show_preview"] = False
if "current_page" not in st.session_state:
	st.session_state["current_page"] = 0
if "confirm_delete_id" not in st.session_state:
	st.session_state["confirm_delete_id"] = None

# 分页设置
PAGE_SIZE = 10

# 搜索和筛选
st.subheader("🔍 搜索报表")

# 使用更合理的列宽比例，并添加垂直对齐
col1, col2, col3, col4 = st.columns([3, 1, 1, 0.5])
with col1:
	st.session_state["search_keyword"] = st.text_input(
		"搜索关键词",  # 添加合适的标签
		value=st.session_state["search_keyword"],
		placeholder="按名称、描述或标签搜索...",
		label_visibility="collapsed"  # 隐藏标签
	)
with col2:
	# 使用st.empty()来创建垂直空间，让按钮与输入框对齐
	st.empty()
	search_btn = st.button("🔍 搜索", type="primary", key="search_button")
with col3:
	st.empty()
	if st.button("🔄 刷新", key="refresh_button"):
		st.rerun()
with col4:
	# 添加一些右侧空间
	st.empty()

# 获取报表列表
if st.session_state["search_keyword"].strip():
	reports = report_storage.search_reports(st.session_state["search_keyword"])
else:
	reports = report_storage.list_reports(limit=100)

# 调试信息（开发阶段使用）
if st.checkbox("显示调试信息", key="debug_info"):
	st.write("**调试信息：**")
	st.write(f"找到报表数量: {len(reports)}")
	if reports:
		st.write("**第一个报表的字段：**")
		st.write(reports[0].keys())
		st.write("**第一个报表的配置数据：**")
		st.write(reports[0])

# 显示报表列表
if reports:
	st.subheader(f"📋 报表列表 ({len(reports)} 个)")
	
	# 计算分页
	total_pages = (len(reports) + PAGE_SIZE - 1) // PAGE_SIZE
	start_idx = st.session_state["current_page"] * PAGE_SIZE
	end_idx = min(start_idx + PAGE_SIZE, len(reports))
	current_reports = reports[start_idx:end_idx]
	
	# 分页控制
	if total_pages > 1:
		col1, col2, col3 = st.columns([1, 2, 1])
		with col1:
			if st.button("◀️ 上一页", disabled=st.session_state["current_page"] == 0, key="prev_page"):
				st.session_state["current_page"] = max(0, st.session_state["current_page"] - 1)
				st.rerun()
		with col2:
			st.write(f"第 {st.session_state['current_page'] + 1} 页，共 {total_pages} 页")
		with col3:
			if st.button("下一页 ▶️", disabled=st.session_state["current_page"] >= total_pages - 1, key="next_page"):
				st.session_state["current_page"] = min(total_pages - 1, st.session_state["current_page"] + 1)
				st.rerun()
	
	# 表头
	head = st.columns([3, 4, 3, 2, 3], gap="small")
	head[0].write("**<span style='font-size: 1.2em; font-weight: bold;'>名称</span>**", unsafe_allow_html=True)
	head[1].write("**<span style='font-size: 1.2em; font-weight: bold;'>描述</span>**", unsafe_allow_html=True)
	head[2].write("**<span style='font-size: 1.2em; font-weight: bold;'>数据源</span>**", unsafe_allow_html=True)
	head[3].write("**<span style='font-size: 1.2em; font-weight: bold;'>更新时间</span>**", unsafe_allow_html=True)
	head[4].write("**<span style='font-size: 1.2em; font-weight: bold;'>操作</span>**", unsafe_allow_html=True)
	
	# 处理报表点击和操作
	for i, report in enumerate(current_reports):
		# 使用更紧凑的列布局
		c1, c2, c3, c4, c5 = st.columns([3, 4, 3, 2, 3], gap="small")
		
		# 名称列：显示为普通文本，无点击功能
		c1.write(f"**{report['name']}**")
		
		c2.write((report.get('description') or '')[:80])
		c3.write(f"{report['schema_name']}.{report['table_name']}")
		c4.write(report['updated_at'].strftime('%Y-%m-%d %H:%M') if report.get('updated_at') else '-')
		
		# 操作按钮 - 使用更紧凑的布局
		b1, b2, b3, b4 = c5.columns(4, gap="small")
		
		# 预览按钮
		if b1.button("👁️", key=f"preview_{report['id']}", help="预览报表配置"):
			st.session_state["preview_report"] = report
			st.session_state["show_preview"] = True
			st.rerun()
		
		# 编辑按钮
		if b2.button("✏️", key=f"edit_{report['id']}", help="编辑报表配置"):
			st.session_state["edit_report"] = report
			st.session_state["edit_mode"] = True
			st.switch_page("pages/01_Builder.py")
		
		# 克隆按钮
		if b3.button("📋", key=f"clone_{report['id']}", help="克隆此报表"):
			try:
				cloned = report.copy()
				cloned['name'] = f"{report['name']}_副本"
				cloned['description'] = f"克隆自: {report['name']}"
				cloned['id'] = None
				newid = report_storage.save_report(cloned)
				if newid:
					st.success("克隆成功")
					st.rerun()
				else:
					st.error("克隆失败")
			except Exception as e:
				st.error(f"克隆失败: {e}")
		
		# 删除按钮：触发二次确认
		if b4.button("🗑️", key=f"del_{report['id']}", help="删除此报表"):
			st.session_state["confirm_delete_id"] = report['id']
			st.rerun()
		
		# 在每个报表行后添加分隔线（除了最后一行）
		if i < len(current_reports) - 1:
			# st.divider()
			color = 'red'
			st.markdown(
			f"<hr style='margin:2px 0; border:none; border-top:1px solid {color};'/>",
			unsafe_allow_html=True
    		)
	
	# 二次确认删除区域（在列表下方统一显示）
	if st.session_state.get("confirm_delete_id"):
		pending_id = st.session_state["confirm_delete_id"]
		# 定位待删除报表
		pending = next((r for r in reports if r.get('id') == pending_id), None)
		if pending:
			st.error(f"确认删除报表：{pending.get('name')} ({pending.get('schema_name')}.{pending.get('table_name')})")
			c1, c2 = st.columns(2)
			with c1:
				if st.button("✅ 确认删除", key=f"confirm_del_{pending_id}"):
					try:
						if report_storage.delete_report(pending_id):
							st.success("删除成功")
							st.session_state["confirm_delete_id"] = None
							st.rerun()
						else:
							st.error("删除失败：未找到或已删除")
					except Exception as e:
						st.error(f"删除失败: {e}")
			with c2:
				if st.button("取消", key=f"cancel_del_{pending_id}"):
					st.session_state["confirm_delete_id"] = None
					st.rerun()

	# 在报表列表下方显示预览内容（避免重复渲染）
	if st.session_state["show_preview"]:
		st.success("✅ 预览模式已激活")
		st.subheader("📊 报表详情")
		preview_report = st.session_state.get("preview_report")
		if not preview_report:
			st.info("请选择一条报表进行预览")
			st.stop()
		
		# 保证本区域内组件 key 唯一：当预览报表切换时，递增计数
		last_id = st.session_state.get("_preview_last_id")
		if last_id != preview_report['id']:
			st.session_state["_preview_key_seq"] = st.session_state.get("_preview_key_seq", 0) + 1
			st.session_state["_preview_last_id"] = preview_report['id']
		
		with st.expander("报表配置信息", expanded=True):
			col1, col2 = st.columns(2)
			with col1:
				st.write(f"**报表名称**: {preview_report['name']}")
				st.write(f"**描述**: {preview_report.get('description', '无')}")
				st.write(f"**数据源**: {preview_report['schema_name']}.{preview_report['table_name']}")
				st.write(f"**标签**: {preview_report.get('tags', '无')}")
			with col2:
				st.write(f"**创建者**: {preview_report.get('created_by', '未知')}")
				st.write(f"**创建时间**: {preview_report['created_at'].strftime('%Y-%m-%d %H:%M:%S') if preview_report['created_at'] else '未知'}")
				st.write(f"**更新时间**: {preview_report['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if preview_report['updated_at'] else '未知'}")
				st.write(f"**预览行数**: {preview_report.get('row_limit', '无限制')}")
		
		# 显示字段信息
		with st.expander("字段配置", expanded=False):
			col1, col2 = st.columns(2)
			with col1:
				st.write("**选择的字段**:")
				selected_fields = preview_report.get('selected_fields', [])
				if selected_fields:
					for field in selected_fields:
						st.write(f"- {field}")
				else:
					st.write("无选择的字段")
				st.write(f"**字段数量**: {len(selected_fields)}")
			with col2:
				st.write("**字段别名**:")
				aliases = preview_report.get('aliases', {})
				if aliases:
					for field, alias in aliases.items():
						st.write(f"- {field} → {alias}")
				else:
					st.write("无字段别名")
				st.write(f"**别名数量**: {len(aliases)}")
			
			# 调试信息（可选显示）——使用一次性唯一 key 避免冲突
			if st.checkbox("显示详细调试信息", key=f"detail_debug_{preview_report['id']}_{uuid4()}"):
				st.write("**调试信息**:")
				st.write(f"selected_fields类型: {type(selected_fields)}")
				st.write(f"aliases类型: {type(aliases)}")
				st.write(f"原始数据: {preview_report}")
		
		# 显示筛选条件
		if preview_report.get('filters'):
			with st.expander("筛选条件", expanded=False):
				for i, filter_cond in enumerate(preview_report['filters']):
					st.write(f"**条件 {i+1}**: {filter_cond.get('field', '')} {filter_cond.get('operator', '')} {filter_cond.get('value', '')}")
		
		# 显示计算字段
		if preview_report.get('computed_fields'):
			with st.expander("计算字段", expanded=False):
				for cf in preview_report['computed_fields']:
					st.write(f"**{cf.get('name', '')}**: {cf.get('expression', '')}")
		
		# 导出报表配置
		st.subheader("📤 导出报表配置")
		col1, col2 = st.columns(2)
		with col1:
			config_json = pd.DataFrame([preview_report])
			st.download_button(
				"下载 JSON 配置",
				data=config_json.to_json(orient="records", force_ascii=False, indent=2),
				file_name=f"{preview_report['name']}_配置.json",
				mime="application/json",
				use_container_width=True,
				key=f"download_json_{preview_report['id']}_{uuid4()}"
			)
		with col2:
			st.download_button(
				"下载 CSV 配置",
				data=to_csv_bytes(config_json),
				file_name=f"{preview_report['name']}_配置.csv",
				mime="text/csv",
				use_container_width=True,
				key=f"download_csv_{preview_report['id']}_{uuid4()}"
			)

else:
	if st.session_state["search_keyword"].strip():
		st.warning(f"没有找到包含 '{st.session_state['search_keyword']}' 的报表")
	else:
		st.info("📭 还没有保存的报表。请先在『报表构建器』中创建并保存报表。")
		if st.button("🚀 前往报表构建器"):
			st.switch_page("pages/01_Builder.py") 