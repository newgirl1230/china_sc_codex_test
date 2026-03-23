from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4, UUID
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st


class ReportStorage:
    """报表存储服务"""
    
    def __init__(self, engine):
        self.engine = engine
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保必要的表存在"""
        try:
            inspector = inspect(self.engine)
            schemas = inspector.get_schema_names()
            
            if "dbo" not in schemas:
                # 创建 dbo schema
                with self.engine.connect() as conn:
                    conn.execute(text("CREATE SCHEMA dbo"))
                    conn.commit()
            
            tables = inspector.get_table_names(schema="dbo")
            
            if "report_definitions" not in tables:
                self._create_report_tables()
            else:
                # 检查并添加缺失的字段
                self._check_and_add_missing_columns()
                
        except Exception as e:
            st.error(f"初始化报表存储失败: {e}")
    
    def _check_and_add_missing_columns(self):
        """检查并添加缺失的列"""
        try:
            inspector = inspect(self.engine)
            columns = {col['name'] for col in inspector.get_columns('report_definitions', schema='dbo')}
            
            missing_columns = []
            
            # 检查缺失的列
            if 'description' not in columns:
                missing_columns.append("description NVARCHAR(500) NULL")
            if 'aliases' not in columns:
                missing_columns.append("aliases NVARCHAR(MAX) NOT NULL DEFAULT '{}'")
            
            # 添加缺失的列
            if missing_columns:
                for col_def in missing_columns:
                    try:
                        with self.engine.connect() as conn:
                            conn.execute(text(f"ALTER TABLE dbo.report_definitions ADD {col_def}"))
                            conn.commit()
                        st.success(f"已添加缺失列: {col_def.split()[0]}")
                    except Exception as e:
                        st.warning(f"添加列 {col_def.split()[0]} 失败: {e}")
                        
        except Exception as e:
            st.warning(f"检查表结构时发生错误: {e}")
    
    def _create_report_tables(self):
        """创建报表相关的表"""
        ddl = """
        CREATE TABLE dbo.report_definitions (
            id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
            name NVARCHAR(200) NOT NULL,
            description NVARCHAR(500) NULL,
            schema_name NVARCHAR(128) NOT NULL,
            table_name NVARCHAR(128) NOT NULL,
            selected_fields NVARCHAR(MAX) NOT NULL,
            filters NVARCHAR(MAX) NOT NULL,
            computed_fields NVARCHAR(MAX) NOT NULL,
            aliases NVARCHAR(MAX) NOT NULL DEFAULT '{}',
            sort NVARCHAR(MAX) NULL,
            row_limit INT NULL,
            tags NVARCHAR(200) NULL,
            created_by NVARCHAR(128) NULL,
            created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
            updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
            is_deleted BIT NOT NULL DEFAULT 0
        );
        
        CREATE INDEX IX_report_definitions_active ON dbo.report_definitions(is_deleted, updated_at DESC);
        CREATE INDEX IX_report_definitions_name ON dbo.report_definitions(name);
        
        CREATE TABLE dbo.report_runs (
            id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
            report_id UNIQUEIDENTIFIER NOT NULL,
            run_started_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
            run_finished_at DATETIME2 NULL,
            status NVARCHAR(30) NOT NULL,
            row_count INT NULL,
            error_message NVARCHAR(MAX) NULL,
            FOREIGN KEY (report_id) REFERENCES dbo.report_definitions(id)
        );
        
        CREATE INDEX IX_report_runs_reportid_time ON dbo.report_runs(report_id, run_started_at DESC);
        """
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
                st.success("报表存储表创建成功")
        except Exception as e:
            st.error(f"创建报表存储表失败: {e}")
    
    def save_report(self, report_data: Dict[str, Any]) -> Optional[str]:
        """保存报表定义"""
        try:
            # 验证必要字段
            required_fields = ['name', 'schema_name', 'table_name', 'selected_fields', 'filters', 'computed_fields', 'aliases']
            for field in required_fields:
                if field not in report_data:
                    raise ValueError(f"缺少必要字段: {field}")
            
            # 准备数据
            report_id = str(uuid4())
            now = datetime.now()
            
            # 动态构建SQL，只包含存在的字段
            inspector = inspect(self.engine)
            columns = {col['name'] for col in inspector.get_columns('report_definitions', schema='dbo')}
            
            # 过滤存在的字段
            available_fields = []
            available_values = []
            available_params = {}
            
            field_mappings = {
                'id': report_id,
                'name': report_data['name'],
                'description': report_data.get('description', ''),
                'schema_name': report_data['schema_name'],
                'table_name': report_data['table_name'],
                'selected_fields': json.dumps(report_data['selected_fields'], ensure_ascii=False),
                'filters': json.dumps(report_data['filters'], ensure_ascii=False),
                'computed_fields': json.dumps(report_data['computed_fields'], ensure_ascii=False),
                'aliases': json.dumps(report_data['aliases'], ensure_ascii=False),
                'sort': json.dumps(report_data.get('sort', []), ensure_ascii=False),
                'row_limit': report_data.get('row_limit'),
                'tags': report_data.get('tags', ''),
                'created_by': report_data.get('created_by', ''),
                'created_at': now,
                'updated_at': now,
                'is_deleted': 0
            }
            
            for field, value in field_mappings.items():
                if field in columns:
                    available_fields.append(field)
                    available_values.append(f":{field}")
                    available_params[field] = value
            
            insert_sql = f"""
            INSERT INTO dbo.report_definitions (
                {', '.join(available_fields)}
            ) VALUES (
                {', '.join(available_values)}
            )
            """
            
            with self.engine.connect() as conn:
                conn.execute(text(insert_sql), available_params)
                conn.commit()
            
            return report_id
            
        except Exception as e:
            st.error(f"保存报表失败: {e}")
            # 继续抛出给上层（Builder 会捕获并显示具体异常）
            raise
    
    def update_report(self, report_id: str, report_data: Dict[str, Any]) -> bool:
        """更新报表定义"""
        try:
            # 检查表结构
            inspector = inspect(self.engine)
            columns = {col['name'] for col in inspector.get_columns('report_definitions', schema='dbo')}
            
            # 构建更新字段
            update_fields = []
            params = {'id': report_id, 'updated_at': datetime.now()}
            
            field_mappings = {
                'schema_name': report_data.get('schema_name'),
                'table_name': report_data.get('table_name'),
                'name': report_data['name'],
                'description': report_data.get('description', ''),
                'selected_fields': json.dumps(report_data['selected_fields'], ensure_ascii=False),
                'filters': json.dumps(report_data['filters'], ensure_ascii=False),
                'computed_fields': json.dumps(report_data['computed_fields'], ensure_ascii=False),
                'aliases': json.dumps(report_data['aliases'], ensure_ascii=False),
                'sort': json.dumps(report_data.get('sort', []), ensure_ascii=False),
                'row_limit': report_data.get('row_limit'),
                'tags': report_data.get('tags', '')
            }
            
            for field, value in field_mappings.items():
                if field in columns:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = value
            
            if not update_fields:
                st.error("没有可更新的字段")
                return False
            
            update_sql = f"""
            UPDATE dbo.report_definitions 
            SET {', '.join(update_fields)}, updated_at = :updated_at
            WHERE id = :id AND is_deleted = 0
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(update_sql), params)
                conn.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            st.error(f"更新报表失败: {e}")
            return False
    
    def delete_report(self, report_id: str) -> bool:
        """软删除报表"""
        try:
            delete_sql = """
            UPDATE dbo.report_definitions 
            SET is_deleted = 1, updated_at = :updated_at
            WHERE id = :id
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(delete_sql), {
                    'id': report_id,
                    'updated_at': datetime.now()
                })
                conn.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            st.error(f"删除报表失败: {e}")
            return False
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取单个报表定义"""
        try:
            select_sql = """
            SELECT * FROM dbo.report_definitions 
            WHERE id = :id AND is_deleted = 0
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(select_sql), {'id': report_id})
                row = result.fetchone()
                
                if row:
                    return self._row_to_dict(row)
                return None
                
        except Exception as e:
            st.error(f"获取报表失败: {e}")
            return None
    
    def list_reports(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取报表列表"""
        try:
            # 检查表结构，动态构建查询
            inspector = inspect(self.engine)
            columns = {col['name'] for col in inspector.get_columns('report_definitions', schema='dbo')}
            
            # 获取所有可用字段，包括配置字段
            all_fields = ['id', 'name', 'description', 'schema_name', 'table_name', 'selected_fields', 
                         'filters', 'computed_fields', 'aliases', 'sort', 'row_limit', 'tags', 
                         'created_by', 'created_at', 'updated_at']
            available_fields = [f for f in all_fields if f in columns]
            
            select_sql = f"""
            SELECT {', '.join(available_fields)}
            FROM dbo.report_definitions 
            WHERE is_deleted = 0
            ORDER BY updated_at DESC
            OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(select_sql), {'limit': limit})
                rows = result.fetchall()
                
                reports = [self._row_to_dict(row, available_fields) for row in rows]
                return reports
                
        except Exception as e:
            st.error(f"获取报表列表失败: {e}")
            return []
    
    def search_reports(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索报表"""
        try:
            # 检查表结构，动态构建查询
            inspector = inspect(self.engine)
            columns = {col['name'] for col in inspector.get_columns('report_definitions', schema='dbo')}
            
            # 获取所有可用字段，包括配置字段
            all_fields = ['id', 'name', 'description', 'schema_name', 'table_name', 'selected_fields', 
                         'filters', 'computed_fields', 'aliases', 'sort', 'row_limit', 'tags', 
                         'created_by', 'created_at', 'updated_at']
            available_fields = [f for f in all_fields if f in columns]
            
            # 构建搜索条件
            search_conditions = []
            if 'name' in columns:
                search_conditions.append("name LIKE :keyword")
            if 'description' in columns:
                search_conditions.append("description LIKE :keyword")
            if 'tags' in columns:
                search_conditions.append("tags LIKE :keyword")
            
            if not search_conditions:
                # 如果没有可搜索的字段，回退到基本搜索
                search_conditions = ["name LIKE :keyword"]
            
            search_sql = f"""
            SELECT {', '.join(available_fields)}
            FROM dbo.report_definitions 
            WHERE is_deleted = 0 
            AND ({' OR '.join(search_conditions)})
            ORDER BY updated_at DESC
            OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
            """
            
            search_pattern = f"%{keyword}%"
            
            with self.engine.connect() as conn:
                result = conn.execute(text(search_sql), {
                    'keyword': search_pattern,
                    'limit': limit
                })
                rows = result.fetchall()
                
                return [self._row_to_dict(row, available_fields) for row in rows]
                
        except Exception as e:
            st.error(f"搜索报表失败: {e}")
            return []
    
    def _row_to_dict(self, row, fields=None) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        if fields is None:
            # 如果没有指定字段，尝试获取所有字段
            fields = [col.name for col in row._fields] if hasattr(row, '_fields') else []
        
        result = {}
        
        for i, field in enumerate(fields):
            if i < len(row):
                value = row[i]
                
                if field in ['selected_fields', 'filters', 'computed_fields', 'aliases', 'sort']:
                    try:
                        if value and value != '{}' and value != '[]':
                            result[field] = json.loads(value)
                        else:
                            result[field] = [] if field in ['selected_fields', 'filters', 'computed_fields', 'sort'] else {}
                    except Exception as e:
                        # 静默处理JSON解析错误，使用默认值
                        result[field] = [] if field in ['selected_fields', 'filters', 'computed_fields', 'sort'] else {}
                else:
                    result[field] = value
        
        return result
    
    def record_run(self, report_id: str, status: str, row_count: Optional[int] = None, error_message: Optional[str] = None) -> Optional[str]:
        """记录报表运行"""
        try:
            run_id = str(uuid4())
            now = datetime.now()
            
            insert_sql = """
            INSERT INTO dbo.report_runs (id, report_id, run_started_at, run_finished_at, status, row_count, error_message)
            VALUES (:id, :report_id, :run_started_at, :run_finished_at, :status, :row_count, :error_message)
            """
            
            params = {
                'id': run_id,
                'report_id': report_id,
                'run_started_at': now,
                'run_finished_at': now if status in ['completed', 'failed'] else None,
                'status': status,
                'row_count': row_count,
                'error_message': error_message
            }
            
            with self.engine.connect() as conn:
                conn.execute(text(insert_sql), params)
                conn.commit()
            
            return run_id
            
        except Exception as e:
            st.error(f"记录报表运行失败: {e}")
            return None
