from __future__ import annotations

import streamlit as st
from sqlalchemy import create_engine, inspect, Table, MetaData, select, and_, or_, func
from sqlalchemy.engine import Engine
from typing import List, Dict, Any, Optional


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
	cfg = st.secrets.get("mssql", {})
	driver = cfg.get("odbc_driver", "ODBC Driver 18 for SQL Server").replace(" ", "+")
	trust = "Yes" if cfg.get("trust_cert", False) else "No"
	if cfg.get("windows_auth", False):
		uri = (
			f"mssql+pyodbc://@{cfg.get('server')}:{cfg.get('port', 1433)}/{cfg.get('database')}"
			f"?driver={driver}&Trusted_Connection=yes&TrustServerCertificate={trust}"
		)
	else:
		uri = (
			f"mssql+pyodbc://{cfg.get('username')}:{cfg.get('password')}"
			f"@{cfg.get('server')}:{cfg.get('port', 1433)}/{cfg.get('database')}"
			f"?driver={driver}&TrustServerCertificate={trust}"
		)
	return create_engine(uri, pool_pre_ping=True, fast_executemany=True)


@st.cache_data(show_spinner=False)
def list_schemas(_engine: Engine) -> List[str]:
	ins = inspect(_engine)
	# 过滤系统 schema，可按需扩展
	schemas = [s for s in ins.get_schema_names() if s not in ("INFORMATION_SCHEMA", "sys")]
	return sorted(schemas)


@st.cache_data(show_spinner=False)
def list_tables(_engine: Engine, schema: str) -> List[str]:
	ins = inspect(_engine)

	# TODO: 先手动去掉会有别名问题的table
	tables = ins.get_table_names(schema=schema)
	if tables.__contains__('App_Test'):
		tables.remove('App_Test')

	return sorted(tables)


@st.cache_data(show_spinner=False)
def list_columns(_engine: Engine, schema: str, table: str) -> List[Dict[str, Any]]:
	ins = inspect(_engine)
	cols = ins.get_columns(table, schema=schema)
	for c in cols:
		c["full_name"] = f"{c['name']} ({str(c.get('type'))})"
		c["kind"] = _infer_col_kind(str(c.get("type", "")).lower())
	return cols


def _infer_col_kind(type_str: str) -> str:
	ts = type_str
	if any(k in ts for k in ["int", "numeric", "decimal", "float", "real", "money"]):
		return "number"
	if any(k in ts for k in ["date", "time"]):
		return "date"
	if "bit" in ts:
		return "bool"
	return "text"


def _build_conditions(tbl: Table, filters: Optional[List[Dict[str, Any]]]):
	conds = []
	if not filters:
		return conds
	for f in filters:
		field = f.get("field")
		op = (f.get("operator") or "").lower()
		val = f.get("value")
		if not field or field not in tbl.c:
			continue
		col = tbl.c[field]
		if op == "=":
			conds.append(col == val)
		elif op == "!=":
			conds.append(col != val)
		elif op == ">":
			conds.append(col > val)
		elif op == ">=":
			conds.append(col >= val)
		elif op == "<":
			conds.append(col < val)
		elif op == "<=":
			conds.append(col <= val)
		elif op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
			conds.append(col.between(val[0], val[1]))
		elif op == "in":
			if isinstance(val, str):
				vals = [v.strip() for v in val.split(",") if v.strip()]
			else:
				vals = list(val or [])
			if vals:
				conds.append(col.in_(vals))
		elif op == "like":
			conds.append(col.like(val))
		elif op == "ilike":
			conds.append(func.upper(col).like(func.upper(val)))
		elif op == "is null":
			conds.append(col.is_(None))
		elif op == "is not null":
			conds.append(col.is_not(None))
	return conds


def build_select_statement(_engine: Engine, schema: str, table: str, columns: List[Any], filters: Optional[List[Dict[str, Any]]] = None, limit: Optional[int] = 1000):
	md = MetaData(schema=schema)
	tbl = Table(table, md, autoload_with=_engine)
	selected: List[Any] = []
	if columns:
		if isinstance(columns[0], dict):
			for item in columns:
				src = item.get("src")
				alias = item.get("alias") or src
				if src in tbl.c:
					col = tbl.c[src]
					selected.append(col.label(alias) if alias and alias != src else col)
		else:
			selected = [tbl.c[c] for c in columns if c in tbl.c]
	else:
		selected = list(tbl.c)
	stmt = select(*selected)
	conds = _build_conditions(tbl, filters)
	if conds:
		stmt = stmt.where(and_(*conds))
	if limit and isinstance(limit, int):
		stmt = stmt.limit(limit)  # SQL Server 会编译为 TOP n
	return stmt


def fetch_preview(_engine: Engine, schema: str, table: str, columns: List[Any], filters: Optional[List[Dict[str, Any]]] = None, limit: int | None = 1000):
	import pandas as pd
	stmt = build_select_statement(_engine, schema, table, columns, filters, limit)
	return pd.read_sql(stmt, _engine)


def count_rows(_engine: Engine, schema: str, table: str, filters: Optional[List[Dict[str, Any]]] = None) -> int:
	md = MetaData(schema=schema)
	tbl = Table(table, md, autoload_with=_engine)
	stmt = select(func.count()).select_from(tbl)
	conds = _build_conditions(tbl, filters)
	if conds:
		stmt = stmt.where(and_(*conds))
	with _engine.begin() as conn:
		val = conn.execute(stmt).scalar()
	return int(val or 0) 