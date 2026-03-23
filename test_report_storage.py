#!/usr/bin/env python3
"""
测试报表存储功能的脚本
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.datasources.mssql import get_engine
from app.services.report_storage import ReportStorage

def test_report_storage():
    """测试报表存储功能"""
    try:
        print("🔍 测试报表存储功能...")
        
        # 获取数据库连接
        engine = get_engine()
        print("✅ 数据库连接成功")
        
        # 创建报表存储服务
        report_storage = ReportStorage(engine)
        print("✅ 报表存储服务初始化成功")
        
        # 测试获取报表列表
        reports = report_storage.list_reports(limit=10)
        print(f"📋 找到 {len(reports)} 个报表")
        
        if reports:
            print("\n📊 第一个报表信息:")
            first_report = reports[0]
            for key, value in first_report.items():
                if key in ['selected_fields', 'filters', 'computed_fields', 'aliases']:
                    print(f"  {key}: {type(value)} - 长度: {len(value) if hasattr(value, '__len__') else 'N/A'}")
                else:
                    print(f"  {key}: {value}")
        
        # 测试搜索功能
        if reports:
            search_results = report_storage.search_reports(reports[0]['name'][:3])
            print(f"\n🔍 搜索 '{reports[0]['name'][:3]}' 找到 {len(search_results)} 个结果")
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_report_storage()
