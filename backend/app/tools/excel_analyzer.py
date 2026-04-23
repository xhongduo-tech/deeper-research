import csv
import json
import math
import os
from collections import Counter
from typing import Any, Dict, List, Optional


class ExcelAnalyzer:
    """
    Builds compact, structured profiles for spreadsheet-like files.
    The profile is designed for LLM context, so it favors completeness signals
    and representative samples over dumping every cell.
    """

    MAX_SAMPLE_ROWS = 12
    MAX_DISTINCT_VALUES = 8

    async def profile_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        file_type = file_type.lower()
        if file_type in ("xlsx", "xls"):
            return await self._profile_excel(file_path, file_type)
        if file_type == "csv":
            return await self._profile_csv(file_path)
        return {"type": file_type, "sheets": []}

    def format_profile(self, profile: Dict[str, Any]) -> str:
        """Render the profile as readable markdown for agent context."""
        if not profile.get("sheets"):
            return "[表格画像] 未识别到可分析的工作表或数据行。"

        parts = ["\n\n## 表格数据完整性画像"]
        parts.append(f"- 文件类型: {profile.get('type', 'unknown')}")
        parts.append(f"- 工作表/数据集数量: {len(profile.get('sheets', []))}")

        for sheet in profile["sheets"]:
            parts.append(f"\n### 数据集: {sheet['name']}")
            parts.append(
                f"- 规模: {sheet['row_count']} 行 x {sheet['column_count']} 列"
            )
            parts.append(f"- 推断表头: {'是' if sheet.get('has_header') else '否'}")
            if sheet.get("duplicate_rows") is not None:
                parts.append(f"- 完全重复行: {sheet['duplicate_rows']}")

            if sheet.get("warnings"):
                parts.append("- 数据质量提示:")
                for warning in sheet["warnings"]:
                    parts.append(f"  - {warning}")

            parts.append("- 字段画像:")
            for col in sheet.get("columns", []):
                line = (
                    f"  - {col['name']} | 类型: {col['semantic_type']} | "
                    f"非空: {col['non_empty']}/{sheet['row_count']} | "
                    f"缺失率: {col['missing_rate']:.1%}"
                )
                if col.get("min") is not None and col.get("max") is not None:
                    line += (
                        f" | 范围: {col['min']} ~ {col['max']} | "
                        f"均值: {col.get('mean')}"
                    )
                if col.get("top_values"):
                    values = ", ".join(
                        f"{item['value']}({item['count']})"
                        for item in col["top_values"][: self.MAX_DISTINCT_VALUES]
                    )
                    line += f" | 高频值: {values}"
                parts.append(line)

            if sheet.get("chart_suggestions"):
                parts.append("- 推荐可视化:")
                for item in sheet["chart_suggestions"]:
                    parts.append(f"  - {item}")

            if sheet.get("sample_rows"):
                parts.append("- 样例行:")
                parts.append(json.dumps(sheet["sample_rows"], ensure_ascii=False, indent=2))

        return "\n".join(parts)

    async def _profile_excel(self, file_path: str, file_type: str) -> Dict[str, Any]:
        if file_type == "xlsx":
            return self._profile_xlsx(file_path)
        return self._profile_xls(file_path)

    def _profile_xlsx(self, file_path: str) -> Dict[str, Any]:
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            sheets = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    values = [self._normalize_value(v) for v in row]
                    if any(v not in ("", None) for v in values):
                        rows.append(values)
                sheets.append(self._profile_rows(ws.title, rows))
            return {"type": "xlsx", "sheets": sheets}
        finally:
            wb.close()

    def _profile_xls(self, file_path: str) -> Dict[str, Any]:
        import xlrd

        wb = xlrd.open_workbook(file_path)
        sheets = []
        for sheet in wb.sheets():
            rows = []
            for row_idx in range(sheet.nrows):
                values = [self._normalize_value(v) for v in sheet.row_values(row_idx)]
                if any(v not in ("", None) for v in values):
                    rows.append(values)
            sheets.append(self._profile_rows(sheet.name, rows))
        return {"type": "xls", "sheets": sheets}

    async def _profile_csv(self, file_path: str) -> Dict[str, Any]:
        encoding = self._detect_encoding(file_path)
        rows = []
        with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(f, dialect)
            for row in reader:
                values = [self._normalize_value(v) for v in row]
                if any(v not in ("", None) for v in values):
                    rows.append(values)
        return {"type": "csv", "sheets": [self._profile_rows(os.path.basename(file_path), rows)]}

    def _profile_rows(self, name: str, rows: List[List[Any]]) -> Dict[str, Any]:
        if not rows:
            return {
                "name": name,
                "row_count": 0,
                "column_count": 0,
                "has_header": False,
                "columns": [],
                "sample_rows": [],
                "warnings": ["空表或未发现有效数据行"],
                "chart_suggestions": [],
                "duplicate_rows": 0,
            }

        width = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (width - len(row)) for row in rows]
        has_header = self._looks_like_header(normalized_rows)
        headers = self._build_headers(normalized_rows[0], width) if has_header else [
            f"字段{i + 1}" for i in range(width)
        ]
        data_rows = normalized_rows[1:] if has_header else normalized_rows

        columns = []
        for idx, header in enumerate(headers):
            values = [row[idx] for row in data_rows]
            columns.append(self._profile_column(header, values))

        duplicate_rows = len(data_rows) - len({tuple(row) for row in data_rows})
        warnings = self._build_warnings(columns, len(data_rows), width, duplicate_rows)
        sample_rows = [
            {headers[i]: row[i] for i in range(width)}
            for row in data_rows[: self.MAX_SAMPLE_ROWS]
        ]

        return {
            "name": name,
            "row_count": len(data_rows),
            "column_count": width,
            "has_header": has_header,
            "columns": columns,
            "sample_rows": sample_rows,
            "warnings": warnings,
            "chart_suggestions": self._suggest_charts(columns),
            "duplicate_rows": duplicate_rows,
        }

    def _profile_column(self, name: str, values: List[Any]) -> Dict[str, Any]:
        non_empty_values = [v for v in values if v not in ("", None)]
        semantic_type = self._infer_type(non_empty_values)
        result = {
            "name": str(name),
            "semantic_type": semantic_type,
            "non_empty": len(non_empty_values),
            "missing": len(values) - len(non_empty_values),
            "missing_rate": (len(values) - len(non_empty_values)) / len(values) if values else 0,
            "distinct_count": len({str(v) for v in non_empty_values}),
        }

        if semantic_type == "numeric":
            nums = [self._to_float(v) for v in non_empty_values]
            nums = [n for n in nums if n is not None and math.isfinite(n)]
            if nums:
                result.update({
                    "min": round(min(nums), 4),
                    "max": round(max(nums), 4),
                    "mean": round(sum(nums) / len(nums), 4),
                })
        else:
            counts = Counter(str(v) for v in non_empty_values)
            result["top_values"] = [
                {"value": value, "count": count}
                for value, count in counts.most_common(self.MAX_DISTINCT_VALUES)
            ]
        return result

    def _build_warnings(
        self,
        columns: List[Dict[str, Any]],
        row_count: int,
        column_count: int,
        duplicate_rows: int,
    ) -> List[str]:
        warnings = []
        if row_count == 0:
            warnings.append("没有数据行，仅识别到表头或空内容")
        if column_count > 40:
            warnings.append("字段数量较多，建议先确认核心字段和分析口径")
        if duplicate_rows:
            warnings.append(f"发现 {duplicate_rows} 行完全重复数据，需确认是否保留")
        high_missing = [
            col["name"] for col in columns if col.get("missing_rate", 0) >= 0.3
        ]
        if high_missing:
            warnings.append("以下字段缺失率较高: " + ", ".join(high_missing[:10]))
        unnamed = [col["name"] for col in columns if col["name"].startswith("未命名字段")]
        if unnamed:
            warnings.append("存在疑似空表头字段，建议补充字段名称")
        return warnings

    def _suggest_charts(self, columns: List[Dict[str, Any]]) -> List[str]:
        categorical = [
            col for col in columns
            if col["semantic_type"] in ("text", "date") and col.get("distinct_count", 0) <= 30
        ]
        numeric = [col for col in columns if col["semantic_type"] == "numeric"]
        suggestions = []
        if categorical and numeric:
            suggestions.append(
                f"柱状图: 使用「{categorical[0]['name']}」作为分类轴，对比「{numeric[0]['name']}」"
            )
        if len(numeric) >= 2:
            suggestions.append(
                f"散点/相关性分析: 检查「{numeric[0]['name']}」与「{numeric[1]['name']}」的关系"
            )
        if numeric:
            suggestions.append(f"分布分析: 查看「{numeric[0]['name']}」的异常值和集中区间")
        return suggestions

    def _looks_like_header(self, rows: List[List[Any]]) -> bool:
        if len(rows) < 2:
            return True
        first = rows[0]
        second = rows[1]
        first_text_ratio = sum(self._to_float(v) is None for v in first if v not in ("", None))
        second_numeric_ratio = sum(self._to_float(v) is not None for v in second if v not in ("", None))
        first_non_empty = max(1, sum(v not in ("", None) for v in first))
        second_non_empty = max(1, sum(v not in ("", None) for v in second))
        return (first_text_ratio / first_non_empty) >= 0.6 and (
            second_numeric_ratio / second_non_empty >= 0.2 or first != second
        )

    def _build_headers(self, row: List[Any], width: int) -> List[str]:
        headers = []
        seen = Counter()
        for idx in range(width):
            raw = str(row[idx]).strip() if idx < len(row) else ""
            name = raw or f"未命名字段{idx + 1}"
            seen[name] += 1
            if seen[name] > 1:
                name = f"{name}_{seen[name]}"
            headers.append(name)
        return headers

    def _infer_type(self, values: List[Any]) -> str:
        if not values:
            return "empty"
        numeric_hits = sum(self._to_float(v) is not None for v in values)
        if numeric_hits / len(values) >= 0.8:
            return "numeric"
        date_hits = sum(self._looks_like_date(v) for v in values)
        if date_hits / len(values) >= 0.6:
            return "date"
        return "text"

    def _looks_like_date(self, value: Any) -> bool:
        text = str(value)
        return any(sep in text for sep in ("-", "/", "年")) and any(ch.isdigit() for ch in text)

    def _to_float(self, value: Any) -> Optional[float]:
        if value in ("", None):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "").replace("%", "")
        try:
            return float(text)
        except ValueError:
            return None

    def _normalize_value(self, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    def _detect_encoding(self, file_path: str) -> str:
        try:
            import chardet

            with open(file_path, "rb") as f:
                raw = f.read(10000)
            return chardet.detect(raw).get("encoding") or "utf-8"
        except Exception:
            return "utf-8"
