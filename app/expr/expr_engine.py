from __future__ import annotations

import re
from typing import Iterable, List, Dict
import pandas as pd

_ALLOWED_FUNCTIONS = {"abs", "round"}
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def extract_identifiers(expression: str) -> List[str]:
	return _IDENTIFIER_RE.findall(expression or "")


def validate_expression(expression: str, allowed_names: Iterable[str]) -> None:
	allowed = set(allowed_names) | _ALLOWED_FUNCTIONS
	idents = extract_identifiers(expression)
	for name in idents:
		if name not in allowed and not name.isdigit():
			raise ValueError(f"非法标识符: {name}")


def evaluate_computed_fields(df: pd.DataFrame, computed_fields: List[Dict[str, str]]) -> pd.DataFrame:
	if not computed_fields:
		return df
	local_series = df.to_dict("series")
	for cf in computed_fields:
		name = cf.get("name", "").strip()
		expr = cf.get("expression", "").strip()
		if not name or not expr:
			continue
		validate_expression(expr, allowed_names=list(local_series.keys()))
		# 计算列
		df[name] = pd.eval(expr, engine="numexpr", local_dict=local_series)
		# 新增列可参与后续表达式
		local_series[name] = df[name]
	return df 