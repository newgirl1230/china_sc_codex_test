import os
import sys
import traceback
import pandas as pd


def auto_adjust_column_width(worksheet, dataframe):
    """根据内容自动调整列宽。"""
    for idx, col in enumerate(dataframe.columns):
        max_len = max(
            len(str(col)),
            dataframe[col].astype(str).map(len).max() if not dataframe.empty else 0,
        )
        worksheet.set_column(idx, idx, min(max_len + 2, 40))


def validate_columns(df, required_cols):
    """校验输入数据列是否完整。"""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要列: {missing}")


def build_weekly_report(input_file, output_file, sheet_name="RawData"):
    """读取原始数据并生成周度销售分析报告。"""
    required_cols = ["下单日期", "订单金额", "产品类别", "销售区域"]

    # 读取源数据，并进行基础清洗
    df = pd.read_excel(input_file, sheet_name=sheet_name)
    validate_columns(df, required_cols)

    df = df.copy()
    df["下单日期"] = pd.to_datetime(df["下单日期"], errors="coerce")
    df["订单金额"] = pd.to_numeric(df["订单金额"], errors="coerce")
    df = df.dropna(subset=["下单日期", "订单金额"])

    if df.empty:
        raise ValueError("清洗后数据为空，无法生成报告。")

    # 生成周度字段（以周一为每周起始）
    df["周度"] = df["下单日期"].dt.to_period("W-MON").apply(lambda r: r.start_time)

    # 工作表1：周度汇总
    weekly_summary = (
        df.groupby("周度", as_index=False)
        .agg(
            总销售额=("订单金额", "sum"),
            订单数=("订单金额", "count"),
        )
        .sort_values("周度")
    )
    weekly_summary["平均销售额"] = weekly_summary["总销售额"] / weekly_summary["订单数"]
    weekly_summary["环比增长"] = weekly_summary["总销售额"].pct_change()

    # 每周销售额最高产品
    weekly_product_sales = (
        df.groupby(["周度", "产品类别"], as_index=False)
        .agg(销售额=("订单金额", "sum"))
        .sort_values(["周度", "销售额"], ascending=[True, False])
    )
    top1_product = weekly_product_sales.drop_duplicates(subset=["周度"], keep="first")
    top1_product = top1_product.rename(columns={"产品类别": "周冠军产品", "销售额": "冠军产品销售额"})
    weekly_summary = weekly_summary.merge(
        top1_product[["周度", "周冠军产品", "冠军产品销售额"]], on="周度", how="left"
    )

    # 工作表2：产品销售分析（每周Top 5）
    weekly_product_sales["排名"] = weekly_product_sales.groupby("周度")["销售额"].rank(
        method="first", ascending=False
    )
    top5_products = weekly_product_sales[weekly_product_sales["排名"] <= 5].copy()
    top5_products = top5_products.sort_values(["周度", "排名"])

    # 使用数据透视（辅助展示）
    product_pivot = pd.pivot_table(
        df,
        index="周度",
        columns="产品类别",
        values="订单金额",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    # 工作表3：区域分析
    region_weekly = (
        df.groupby(["周度", "销售区域"], as_index=False)
        .agg(销售额=("订单金额", "sum"))
        .sort_values(["周度", "销售区域"])
    )

    region_total = (
        df.groupby("销售区域", as_index=False)
        .agg(总销售额=("订单金额", "sum"))
        .sort_values("总销售额", ascending=False)
    )
    region_total["销售占比"] = region_total["总销售额"] / region_total["总销售额"].sum()

    # 写入Excel并设置格式
    with pd.ExcelWriter(output_file, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        weekly_summary.to_excel(writer, sheet_name="周度汇总", index=False)
        top5_products.to_excel(writer, sheet_name="产品销售分析", index=False, startrow=0)
        product_pivot.to_excel(writer, sheet_name="产品销售分析", index=False, startrow=len(top5_products) + 3)
        region_weekly.to_excel(writer, sheet_name="区域分析", index=False)
        weekly_summary[["周度", "总销售额"]].to_excel(writer, sheet_name="趋势图表", index=False)

        workbook = writer.book
        ws_summary = writer.sheets["周度汇总"]
        ws_product = writer.sheets["产品销售分析"]
        ws_region = writer.sheets["区域分析"]
        ws_trend = writer.sheets["趋势图表"]

        # 通用样式
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#D9EAF7", "border": 1, "align": "center", "valign": "vcenter"}
        )
        money_fmt = workbook.add_format({"num_format": "#,##0.00"})
        int_fmt = workbook.add_format({"num_format": "#,##0"})
        pct_fmt = workbook.add_format({"num_format": "0.00%"})

        # 标题样式
        for ws, df_sheet in [
            (ws_summary, weekly_summary),
            (ws_product, top5_products),
            (ws_region, region_weekly),
            (ws_trend, weekly_summary[["周度", "总销售额"]]),
        ]:
            for i, col in enumerate(df_sheet.columns):
                ws.write(0, i, col, header_fmt)

        # 周度汇总格式
        auto_adjust_column_width(ws_summary, weekly_summary)
        ws_summary.set_column("B:B", 14, money_fmt)
        ws_summary.set_column("C:C", 12, int_fmt)
        ws_summary.set_column("D:D", 14, money_fmt)
        ws_summary.set_column("E:E", 12, pct_fmt)
        ws_summary.set_column("G:G", 14, money_fmt)
        ws_summary.conditional_format(
            1,
            4,
            len(weekly_summary),
            4,
            {"type": "cell", "criteria": ">", "value": 0, "format": workbook.add_format({"font_color": "green"})},
        )
        ws_summary.conditional_format(
            1,
            4,
            len(weekly_summary),
            4,
            {"type": "cell", "criteria": "<", "value": 0, "format": workbook.add_format({"font_color": "red"})},
        )

        # 产品分析格式
        auto_adjust_column_width(ws_product, top5_products)
        ws_product.set_column("C:C", 14, money_fmt)
        ws_product.set_column("D:D", 10, int_fmt)

        pivot_start_row = len(top5_products) + 3
        ws_product.write(pivot_start_row, 0, "数据透视表（周度-产品销售额）", header_fmt)
        for i, col in enumerate(product_pivot.columns):
            ws_product.write(pivot_start_row + 1, i, col, header_fmt)
        for c in range(1, len(product_pivot.columns)):
            ws_product.set_column(c, c, 14, money_fmt)

        # 区域分析格式
        auto_adjust_column_width(ws_region, region_weekly)
        ws_region.set_column("C:C", 14, money_fmt)

        # 将区域汇总写到区域分析右侧，用于饼图源数据
        region_table_start_col = 5
        ws_region.write(0, region_table_start_col, "销售区域", header_fmt)
        ws_region.write(0, region_table_start_col + 1, "总销售额", header_fmt)
        ws_region.write(0, region_table_start_col + 2, "销售占比", header_fmt)
        for r, (_, row) in enumerate(region_total.iterrows(), start=1):
            ws_region.write(r, region_table_start_col, row["销售区域"])
            ws_region.write_number(r, region_table_start_col + 1, float(row["总销售额"]), money_fmt)
            ws_region.write_number(r, region_table_start_col + 2, float(row["销售占比"]), pct_fmt)

        # 饼图
        pie_chart = workbook.add_chart({"type": "pie"})
        pie_chart.add_series(
            {
                "name": "各区域销售占比",
                "categories": ["区域分析", 1, region_table_start_col, len(region_total), region_table_start_col],
                "values": ["区域分析", 1, region_table_start_col + 1, len(region_total), region_table_start_col + 1],
                "data_labels": {"percentage": True},
            }
        )
        pie_chart.set_title({"name": "各区域销售占比"})
        ws_region.insert_chart("J2", pie_chart, {"x_scale": 1.2, "y_scale": 1.2})

        # 趋势图
        auto_adjust_column_width(ws_trend, weekly_summary[["周度", "总销售额"]])
        ws_trend.set_column("B:B", 14, money_fmt)
        line_chart = workbook.add_chart({"type": "line"})
        line_chart.add_series(
            {
                "name": "周度销售额",
                "categories": ["趋势图表", 1, 0, len(weekly_summary), 0],
                "values": ["趋势图表", 1, 1, len(weekly_summary), 1],
                "line": {"color": "#2F5597", "width": 2.25},
                "marker": {"type": "circle", "size": 5},
            }
        )
        line_chart.set_title({"name": "周度销售额趋势"})
        line_chart.set_x_axis({"name": "周度"})
        line_chart.set_y_axis({"name": "销售额", "num_format": "#,##0.00"})
        ws_trend.insert_chart("D2", line_chart, {"x_scale": 1.4, "y_scale": 1.2})


def main():
    """命令行入口。"""
    input_file = (
        sys.argv[1]
        if len(sys.argv) > 1
        else r"C:\Users\yueqi.lu\OneDrive - Thermo Fisher Scientific\Desktop\Codex\SO Analysis.xlsx"
    )
    output_file = (
        sys.argv[2] if len(sys.argv) > 2 else "SO_Analysis_周度报告.xlsx"
    )

    try:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入文件不存在: {input_file}")

        build_weekly_report(input_file=input_file, output_file=output_file, sheet_name="RawData")
        print(f"报告生成成功: {os.path.abspath(output_file)}")
    except Exception as e:
        print(f"报告生成失败: {e}")
        print("详细错误信息如下：")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
