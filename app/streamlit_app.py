import streamlit as st

st.set_page_config(page_title="报表平台", page_icon="📊", layout="wide")

st.title("📊 报表平台")
st.markdown("欢迎使用：从左侧页面导航进入『报表构建器』或『报表管理』。")

with st.expander("环境自检"):
	try:
		import pyodbc  # noqa: F401
		st.success("pyodbc 已安装")
	except Exception as e:
		st.error(f"pyodbc 缺失或异常：{e}")

	if "mssql" in st.secrets:
		cfg = st.secrets["mssql"]
		masked = {**cfg}
		if "password" in masked:
			masked["password"] = "***"
		st.json(masked)
	else:
		st.warning("未检测到 secrets.mssql，请参考 .streamlit/secrets.toml 配置")

st.info("提示：首次使用请先进入『报表构建器』测试连接与预览。") 