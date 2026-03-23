# ReportsBuilder (Streamlit)

简体中文 | This project provides a Streamlit-based report builder and manager for SQL Server.

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置 Streamlit Secrets（用于 SQL Server 连接）
- 复制 `.streamlit/secrets.example.toml` 为 `.streamlit/secrets.toml`
- 填入真实连接参数

3. 启动应用
```bash
streamlit run app/streamlit_app.py
```

## SQL Server 准备（可选：启用报表持久化）
执行以下 DDL 创建持久化表：
- `app/sql/report_storage.sql`

## 功能（第一阶段完成）
- ✅ 连接 SQL Server，浏览模式/表/字段
- ✅ 选择字段并预览（默认 1000 行）
- ✅ 导出 CSV/Excel
- ✅ 报表持久化存储（自动创建表结构）
- ✅ 报表保存、加载、更新功能
- ✅ 报表管理页面（列表、搜索、预览、编辑、克隆、删除）
- ✅ 字段别名管理
- ✅ 筛选条件配置
- ✅ 计算字段支持
- ✅ 报表配置导入导出

## 注意
- 建议安装 Microsoft ODBC Driver 18 for SQL Server
- Windows 开发环境可在"ODBC 数据源"中检查驱动是否可用
- 首次运行时会自动创建必要的数据库表结构
- 确保 SQL Server 用户有创建表的权限

## 第一阶段开发完成
✅ **报表持久化存储功能** - 已完成
- 自动创建数据库表结构
- 报表保存、加载、更新
- 智能表结构检查和字段添加

✅ **报表管理功能** - 已完成  
- 报表列表展示和搜索
- 报表预览、编辑、克隆、删除
- 配置导入导出

## 下一步开发计划
🚧 **第二阶段：报表管理增强**
- 报表运行历史记录
- 报表权限管理
- 报表模板功能

🚧 **第三阶段：高级功能**
- 高级筛选和排序
- 聚合计算字段
- 报表调度和自动化 