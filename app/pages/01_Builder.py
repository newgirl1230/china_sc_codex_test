def _find_index_case_insensitive(options, target, fallback_index=0):
    """Return index of target in options ignoring case; fallback if not found."""
    if not target:
        return fallback_index
    try:
        return options.index(target)
    except ValueError:
        target_lower = str(target).lower()
        for i, opt in enumerate(options):
            if str(opt).lower() == target_lower:
                return i
    return fallback_index

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
import pandas as pd
from uuid import uuid4
import re

from app.datasources.mssql import get_engine, list_schemas, list_tables, list_columns, fetch_preview, count_rows
from app.services.exporter import to_csv_bytes, to_excel_bytes
from app.expr.expr_engine import evaluate_computed_fields
from app.services.report_storage import ReportStorage

st.set_page_config(page_title="报表构建器", page_icon="🧩", layout="wide")

st.title("🧩 报表构建器")
engine = get_engine()
report_storage = ReportStorage(engine)

SAFE_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def make_safe_alias(name: str) -> str:
	alias = re.sub(r"[^A-Za-z0-9_]", "_", name or "")
	if not alias or not re.match(r"^[A-Za-z_]", alias):
		alias = f"c_{alias}"
	return alias

# 初始化状态
if "filters" not in st.session_state:
	st.session_state["filters"] = []
if "computed_fields" not in st.session_state:
	st.session_state["computed_fields"] = []
if "aliases" not in st.session_state:
	st.session_state["aliases"] = {}
if "current_report_id" not in st.session_state:
	st.session_state["current_report_id"] = None
if "report_name" not in st.session_state:
	st.session_state["report_name"] = ""
if "report_description" not in st.session_state:
	st.session_state["report_description"] = ""
if "report_tags" not in st.session_state:
	st.session_state["report_tags"] = ""

# 检查是否有编辑模式的报表配置
if "edit_report" in st.session_state and st.session_state.get("edit_mode"):
	edit_report = st.session_state["edit_report"]
	
	# 加载配置到session state
	st.session_state["current_report_id"] = edit_report["id"]
	st.session_state["loaded_report_name"] = edit_report["name"]
	st.session_state["report_name"] = edit_report["name"]
	st.session_state["report_description"] = edit_report.get("description", "")
	st.session_state["report_tags"] = edit_report.get("tags", "")
	st.session_state["filters"] = edit_report.get("filters", [])
	st.session_state["computed_fields"] = edit_report.get("computed_fields", [])
	st.session_state["aliases"] = edit_report.get("aliases", {})
	# 保存已选数据源与字段，供侧栏控件默认值使用
	st.session_state["schema_pref"] = edit_report.get("schema_name")
	st.session_state["table_pref"] = edit_report.get("table_name")
	st.session_state["selected_cols_pref"] = edit_report.get("selected_fields", [])
	
	# 清除编辑模式标记
	st.session_state["edit_mode"] = False
	del st.session_state["edit_report"]
	
	st.success(f"✅ 报表配置加载完成：{edit_report['name']}")
	
	# 显示加载的配置详情（可折叠）
	with st.expander("加载的配置详情", expanded=False):
		st.write("**字段配置**:")
		st.write(edit_report.get('selected_fields', []))
		st.write("**筛选条件**:")
		st.write(edit_report.get('filters', []))
		st.write("**计算字段**:")
		st.write(edit_report.get('computed_fields', []))
		st.write("**字段别名**:")
		st.write(edit_report.get('aliases', {}))

# 侧栏：对象选择
with st.sidebar:
	st.header("选择数据源对象")
	schema_default = st.secrets.get("mssql", {}).get("default_schema", "dbo")
	schemas = list_schemas(engine)
	# 优先使用编辑/加载的 schema
	_schema_pref = st.session_state.get("schema_pref", schema_default)
	schema = st.selectbox(
		"Schema",
		options=schemas,
		index=_find_index_case_insensitive(
			schemas,
			_schema_pref if _schema_pref in schemas else (schema_default if schema_default in schemas else schemas[0] if schemas else "dbo"),
			fallback_index=(schemas.index(schema_default) if schema_default in schemas else 0)
		),
		key="builder_schema_select"
	)
	tables = list_tables(engine, schema)
	if not tables:
		st.stop()
	# 优先使用编辑/加载的 table
	_table_pref = st.session_state.get("table_pref") if st.session_state.get("schema_pref") == schema else None
	table = st.selectbox(
		"表",
		options=tables,
		index=_find_index_case_insensitive(tables, _table_pref, fallback_index=0),
		key="builder_table_select"
	)

	cols_meta = list_columns(engine, schema, table)
	all_cols = [c["name"] for c in cols_meta]
	labels = {c["name"]: c["full_name"] for c in cols_meta}
	kinds = {c["name"]: c["kind"] for c in cols_meta}
	# 默认选中编辑/加载时的字段（与当前表字段求交集，避免不存在字段报错）
	_selected_cols_pref = st.session_state.get("selected_cols_pref", [])
	_selected_default = [c for c in _selected_cols_pref if c in all_cols] or all_cols
	selected_cols = st.multiselect(
		"选择字段",
		options=all_cols,
		default=_selected_default,
		format_func=lambda x: labels.get(x, x),
		max_selections=None,
	)

	# 别名编辑（可折叠）
	st.caption("为含空格/中文/特殊字符的列生成或编辑安全别名；表达式中请使用别名。")
	alias_rows = []
	for col in selected_cols:
		if col not in st.session_state["aliases"]:
			st.session_state["aliases"][col] = make_safe_alias(col)
		alias_rows.append((col, st.session_state["aliases"][col]))
	# 一键展开/收起
	expanded = st.session_state.get("alias_expanded", False)
	toggle_label = "收起全部别名" if expanded else "展开全部别名"
	if st.button(toggle_label, key="alias_toggle_btn"):
		st.session_state["alias_expanded"] = not expanded
		st.rerun()
	if alias_rows:
		with st.expander("字段别名（可折叠）", expanded=st.session_state.get("alias_expanded", False)):
			for col, alias in alias_rows:
				# 使用 schema/table 作为命名空间，避免不同表同名列的状态冲突
				alias_input_key = f"alias_{schema}_{table}_{col}"
				new_alias = st.text_input(f"{col}", value=alias, key=alias_input_key)
				if SAFE_ALIAS_RE.match(new_alias or ""):
					st.session_state["aliases"][col] = new_alias
				else:
					st.warning(f"无效别名，已自动修正：{make_safe_alias(new_alias)}")
					st.session_state["aliases"][col] = make_safe_alias(new_alias)

	st.divider()
	st.subheader("筛选条件")
	delete_filter_uid = None
	# 渲染每一条筛选（使用稳定 UID 作为控件 key）
	for cond in st.session_state["filters"]:
		if "uid" not in cond:
			cond["uid"] = str(uuid4())
		uid = cond["uid"]
		c1, c2, c3, c4 = st.columns([1.6, 1.1, 2.2, 0.6])
		with c1:
			field = st.selectbox(
				f"字段",
				options=all_cols,
				index=(all_cols.index(cond.get("field")) if cond.get("field") in all_cols else 0),
				key=f"f_field_{uid}",
			)
			cond["field"] = field
			kind = kinds.get(field, "text")
		with c2:
			ops = ["=", "!=", ">", ">=", "<", "<=", "between", "in", "like", "is null", "is not null"] if kind != "bool" else ["=", "is null", "is not null"]
			operator = st.selectbox(
				f"操作",
				options=ops,
				index=(ops.index(cond.get("operator")) if cond.get("operator") in ops else 0),
				key=f"f_op_{uid}",
			)
			cond["operator"] = operator
		with c3:
			val = cond.get("value")
			if operator in ("is null", "is not null"):
				st.text_input("值", value="(N/A)", disabled=True, key=f"f_val_dummy_{uid}")
				cond["value"] = None
			elif operator == "between":
				if kind == "number":
					v1 = st.number_input("起始", value=float(val[0]) if isinstance(val, (list, tuple)) and len(val) == 2 else 0.0, key=f"f_v1_{uid}")
					v2 = st.number_input("结束", value=float(val[1]) if isinstance(val, (list, tuple)) and len(val) == 2 else 0.0, key=f"f_v2_{uid}")
					cond["value"] = [v1, v2]
				else:
					date_range = st.date_input("日期范围", key=f"f_date_range_{uid}")
					if isinstance(date_range, tuple) or isinstance(date_range, list):
						cond["value"] = list(date_range)
					else:
						cond["value"] = [date_range, date_range]
			elif operator == "in":
				text = st.text_area("取值列表(逗号分隔)", value=("" if val is None else (", ".join(val) if isinstance(val, (list, tuple)) else str(val))), key=f"f_in_{uid}")
				cond["value"] = [v.strip() for v in text.split(",") if v.strip()]
			else:
				if kind == "number":
					num = st.number_input("值", value=float(val) if isinstance(val, (int, float)) else 0.0, key=f"f_num_{uid}")
					cond["value"] = num
				else:
					text = st.text_input("值", value=str(val) if val is not None else "", key=f"f_text_{uid}")
					cond["value"] = text
		with c4:
			if st.button("删除", key=f"f_del_{uid}"):
				delete_filter_uid = uid
	if st.button("添加条件"):
		st.session_state["filters"].append({"uid": str(uuid4()), "field": all_cols[0] if all_cols else "", "operator": "=", "value": None})
	if delete_filter_uid:
		st.session_state["filters"] = [f for f in st.session_state["filters"] if f.get("uid") != delete_filter_uid]
		st.rerun()

	st.divider()
	st.subheader("计算字段")
	with st.expander("可用表达式与示例", expanded=False):
		st.markdown("""
		### 支持
		- 列名、数字常量、括号、+-*/ 运算
		- 函数：abs(x)
		
		### 示例
		- 总价：`quantity * price`
		- 含税价：`price * 1.13`
		- 毛利：`revenue - cost`
		- 毛利率：`(revenue - cost) / cost`
		- 绝对变化：`abs(current - previous)`
		- 链式：先定义 `subtotal = quantity * price`，再 `grand_total = subtotal * 1.06`
		""")
	delete_cf_uid = None
	for cf in st.session_state["computed_fields"]:
		if "uid" not in cf:
			cf["uid"] = str(uuid4())
		uid = cf["uid"]
		c1, c2, c3 = st.columns([1.2, 2.6, 0.6])
		with c1:
			cf["name"] = st.text_input("名称", value=cf.get("name", ""), key=f"cf_name_{uid}")
		with c2:
			cf["expression"] = st.text_input("表达式", value=cf.get("expression", ""), placeholder="例如: quantity * price", key=f"cf_expr_{uid}")
		with c3:
			if st.button("删除", key=f"cf_del_{uid}"):
				delete_cf_uid = uid
	if st.button("添加计算字段"):
		st.session_state["computed_fields"].append({"uid": str(uuid4()), "name": "", "expression": ""})
	if delete_cf_uid:
		st.session_state["computed_fields"] = [c for c in st.session_state["computed_fields"] if c.get("uid") != delete_cf_uid]
		st.rerun()

	st.divider()
	
	# 报表信息
	st.subheader("报表信息")
	col1, col2 = st.columns([2, 1])
	with col1:
		st.session_state["report_name"] = st.text_input(
			"报表名称", 
			value=st.session_state["report_name"], 
			placeholder="请输入报表名称",
			help="必填，用于保存和识别报表"
		)
		st.session_state["report_description"] = st.text_area(
			"报表描述", 
			value=st.session_state["report_description"], 
			placeholder="可选，描述报表用途",
			height=80
		)
	with col2:
		st.session_state["report_tags"] = st.text_input(
			"标签", 
			value=st.session_state["report_tags"], 
			placeholder="用逗号分隔，如：销售,月度,库存",
			help="可选，用于分类和搜索"
		)
	
	# 保存和运行按钮（单一保存按钮）
	col1, col2, col3 = st.columns([1, 1, 2])
	with col1:
		save_report = st.button("💾 保存", type="secondary", disabled=not st.session_state["report_name"].strip())
	with col2:
		load_report = st.button("📂 加载报表", type="secondary")
	with col3:
		row_limit_input = st.text_input("预览行数 (留空=全部)", value="1000", help="留空表示不限制，返回全部数据(谨慎)")
		row_limit = int(row_limit_input) if row_limit_input.strip() != "" else None
		run = st.button("▶️ 运行预览", type="primary")

# 主区：保存、加载、预览与导出

# 保存报表逻辑
if save_report:
	if not st.session_state["report_name"].strip():
		st.error("请输入报表名称")
	else:
		try:
			# 仅保存本次所选字段的别名，防止把其他表的历史别名一并写入
			aliases_all = st.session_state["aliases"] or {}
			aliases_filtered = {c: (aliases_all.get(c) or make_safe_alias(c)) for c in selected_cols}
			report_data = {
				'name': st.session_state["report_name"].strip(),
				'description': st.session_state["report_description"].strip(),
				'schema_name': schema,
				'table_name': table,
				'selected_fields': selected_cols,
				'filters': st.session_state["filters"],
				'computed_fields': st.session_state["computed_fields"],
				'aliases': aliases_filtered,
				'sort': [],
				'row_limit': row_limit,
				'tags': st.session_state["report_tags"].strip(),
				'created_by': 'current_user'
			}
			
			# 根据是否存在ID决定：存在即更新；不存在即新增
			existing_id = st.session_state.get("current_report_id")
			loaded_name = st.session_state.get("loaded_report_name")
			current_name = st.session_state["report_name"].strip()
			# 规则：若存在ID但名称已与加载时不同，则视为“另存为/新建”
			if existing_id and loaded_name and current_name != loaded_name:
				existing_id = None
			
			if existing_id:
				# 更新现有报表
				success = report_storage.update_report(existing_id, report_data)
				if success:
					st.success(f"报表 '{st.session_state['report_name']}' 更新成功！")
					st.session_state["loaded_report_name"] = current_name
				else:
					st.error("更新报表失败")
			else:
				# 创建新报表
				report_id = None
				try:
					report_id = report_storage.save_report(report_data)
				except Exception as err:
					st.error(f"保存失败：{err}")
					report_id = None
				if report_id:
					st.session_state["current_report_id"] = report_id
					st.success(f"报表 '{st.session_state['report_name']}' 保存成功！(ID: {report_id})")
					st.session_state["loaded_report_name"] = current_name
				else:
					st.error("保存报表失败")
		except Exception as e:
			st.error(f"保存报表时发生错误: {e}")

# 加载报表逻辑
if load_report:
	# 显示报表选择对话框
	reports = report_storage.list_reports(limit=50)
	if reports:
		st.subheader("选择要加载的报表")
		report_options = {f"{r['name']} ({r['schema_name']}.{r['table_name']})": r for r in reports}
		selected_report_key = st.selectbox("选择报表", options=list(report_options.keys()), key="load_report_select")
		
		if st.button("加载选中报表", key="load_report_btn"):
			selected_report = report_options[selected_report_key]
			try:
				# 加载报表配置到session state
				st.session_state["current_report_id"] = selected_report["id"]
				st.session_state["loaded_report_name"] = selected_report["name"]
				st.session_state["report_name"] = selected_report["name"]
				st.session_state["report_description"] = selected_report.get("description", "")
				st.session_state["report_tags"] = selected_report.get("tags", "")
				
				# 注意：这里需要重新选择schema和table，因为当前页面可能显示不同的表
				st.info(f"已加载报表配置。请确保选择了正确的数据源：{selected_report['schema_name']}.{selected_report['table_name']}")
				st.rerun()
			except Exception as e:
				st.error(f"加载报表失败: {e}")
	else:
		st.warning("没有找到已保存的报表")

# 预览逻辑
if run:
	try:
		with st.spinner("正在查询 SQL Server ..."):
			# 别名映射为数据层可识别格式
			cols_with_alias = [
				{"src": c, "alias": st.session_state["aliases"].get(c) or c}
				for c in selected_cols
			]
			# 当不限制行数时先做 COUNT，超过 10 万则终止
			if row_limit is None:
				total = count_rows(engine, schema, table, st.session_state["filters"])
				if total > 100_000:
					st.error("数据量超过上限 100000，已终止预览。请添加筛选或设置预览行数。")
					st.stop()
				df = fetch_preview(engine, schema, table, cols_with_alias, st.session_state["filters"], row_limit)
				st.success(f"查询完成：{len(df)} 行（已拉取全部，合计 {total} 行）")
			else:
				df = fetch_preview(engine, schema, table, cols_with_alias, st.session_state["filters"], row_limit)
				st.success(f"查询完成：{len(df)} 行（最多 {row_limit} 行）")
			if st.session_state["computed_fields"]:
				# 计算字段在别名列名空间中生效
				df = evaluate_computed_fields(df, st.session_state["computed_fields"])
			# 根据列名长度给出列宽建议
			col_widths = {c: max(80, min(300, len(str(c)) * 14)) for c in df.columns}
			st.dataframe(
				df,
				use_container_width=True,
				hide_index=True,
				height=700,
				column_config={c: st.column_config.Column(width=int(col_widths.get(c, 120))) for c in df.columns},
			)

			c1, c2 = st.columns(2)
			with c1:
				st.download_button(
					"下载 CSV",
					data=to_csv_bytes(df),
					file_name=f"{schema}_{table}.csv",
					mime="text/csv",
					use_container_width=True,
				)
			with c2:
				st.download_button(
					"下载 Excel",
					data=to_excel_bytes(df),
					file_name=f"{schema}_{table}.xlsx",
					mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
					use_container_width=True,
				)
	except Exception as e:
		st.error(f"运行失败：{e}")
else:
	st.info("在左侧选择表与字段，可添加筛选和计算列，然后点击『运行预览』。") 