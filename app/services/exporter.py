from __future__ import annotations

import io
import pandas as pd


def to_csv_bytes(df: pd.DataFrame) -> bytes:
	return df.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
	buffer = io.BytesIO()
	with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
		df.to_excel(writer, index=False, sheet_name="Report")
	return buffer.getvalue() 