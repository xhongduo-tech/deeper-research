"""配置文件解析器 — 将 .json/.yaml/.toml/.env/.ini 展平为 Key-Value 字典."""
from __future__ import annotations

import configparser
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _flatten(obj: Any, prefix: str = "", sep: str = ".") -> dict[str, str]:
    """递归展平嵌套结构为点分隔的 key-value."""
    items: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}{sep}{k}" if prefix else str(k)
            items.update(_flatten(v, new_key, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            items.update(_flatten(v, f"{prefix}[{i}]", sep))
    else:
        items[prefix] = str(obj)
    return items


class ConfigParser:
    """解析配置文件，返回展平的 key-value 字典 + 摘要文本."""

    @classmethod
    def parse(cls, filename: str, content: bytes) -> dict:
        """
        Returns:
            {
                "format": str,
                "kv": dict[str, str],      # 展平后的 kv
                "summary": str,            # 供 LLM 消费的摘要
                "raw": str,                # 原始内容（截断）
            }
        """
        text = ""
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            pass

        lower = filename.lower()
        fmt = "unknown"
        kv: dict[str, str] = {}

        try:
            if lower.endswith(".json"):
                fmt = "json"
                kv = _flatten(json.loads(text))
            elif lower.endswith((".yaml", ".yml")):
                fmt = "yaml"
                kv = cls._parse_yaml(text)
            elif lower.endswith(".toml"):
                fmt = "toml"
                kv = cls._parse_toml(text)
            elif lower.endswith((".env", ".env.example", ".env.local")):
                fmt = "dotenv"
                kv = cls._parse_dotenv(text)
            elif lower.endswith((".ini", ".cfg", ".conf")):
                fmt = "ini"
                kv = cls._parse_ini(text)
            else:
                # 尝试 JSON 兜底
                try:
                    kv = _flatten(json.loads(text))
                    fmt = "json"
                except Exception:
                    fmt = "plaintext"
                    kv = {}
        except Exception as exc:
            logger.warning("ConfigParser failed for %s: %s", filename, exc)
            kv = {}

        summary_lines = [f"[{fmt}] {filename} — {len(kv)} 个配置项"]
        for k, v in list(kv.items())[:30]:
            # 屏蔽敏感值
            display_v = "***" if any(s in k.lower() for s in ("password", "secret", "token", "key", "pwd")) else v[:80]
            summary_lines.append(f"  {k} = {display_v}")
        if len(kv) > 30:
            summary_lines.append(f"  ... 还有 {len(kv) - 30} 项")

        return {
            "format": fmt,
            "kv": kv,
            "summary": "\n".join(summary_lines),
            "raw": text[:2000],
        }

    @staticmethod
    def _parse_yaml(text: str) -> dict[str, str]:
        try:
            import yaml
            obj = yaml.safe_load(text)
            return _flatten(obj) if obj else {}
        except ImportError:
            # yaml not available — basic key: value parsing
            kv: dict[str, str] = {}
            for line in text.splitlines():
                m = re.match(r"^([\w.-]+)\s*:\s*(.+)$", line.strip())
                if m:
                    kv[m.group(1)] = m.group(2).strip().strip("\"'")
            return kv

    @staticmethod
    def _parse_toml(text: str) -> dict[str, str]:
        try:
            import tomllib  # Python 3.11+
            obj = tomllib.loads(text)
            return _flatten(obj)
        except ImportError:
            try:
                import tomli
                obj = tomli.loads(text)
                return _flatten(obj)
            except ImportError:
                pass
        # Fallback: basic key = value
        kv: dict[str, str] = {}
        for line in text.splitlines():
            m = re.match(r'^([\w.-]+)\s*=\s*(.+)$', line.strip())
            if m:
                kv[m.group(1)] = m.group(2).strip().strip("\"'")
        return kv

    @staticmethod
    def _parse_dotenv(text: str) -> dict[str, str]:
        kv: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^([\w]+)\s*=\s*(.*)$', line)
            if m:
                kv[m.group(1)] = m.group(2).strip().strip("\"'")
        return kv

    @staticmethod
    def _parse_ini(text: str) -> dict[str, str]:
        kv: dict[str, str] = {}
        try:
            parser = configparser.ConfigParser()
            parser.read_string(text)
            for section in parser.sections():
                for k, v in parser[section].items():
                    kv[f"{section}.{k}"] = v
        except Exception as exc:
            logger.debug("INI parse failed: %s", exc)
        return kv
