import asyncio
import base64
import logging
import os
import sys
import io
import tempfile
import time
import traceback
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


# ── Staging directory for large dataset injection (Parquet over JSON) ──────
# JSON injection of a 50MB CSV blows out the prompt + sandbox memory. We
# instead pre-stage large datasets as Parquet files in a per-session temp dir
# and inject only the file path. Saves 10-100x I/O and unlocks GB-scale analysis.

def _staging_dir() -> Path:
    base = Path(getattr(settings, "sandbox_workspace", None) or tempfile.gettempdir()) / "sandbox_staging"
    base.mkdir(parents=True, exist_ok=True)
    return base


def stage_dataframe(df, session_id: str | None = None) -> str:
    """Write a pandas DataFrame to Parquet under the staging dir; return path.

    Use this when injecting >5MB datasets into the sandbox — Parquet is 5-10x
    smaller than CSV/JSON and pandas reads it 50x faster.
    """
    sid = session_id or uuid.uuid4().hex[:8]
    path = _staging_dir() / f"data_{sid}.parquet"
    try:
        df.to_parquet(path, index=False, compression="snappy")
    except Exception:
        # Parquet may fail on dtypes openpyxl produces; fall back to CSV
        path = _staging_dir() / f"data_{sid}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def cleanup_staged(path: str) -> None:
    """Remove a staged dataset after the sandbox call returns."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


async def execute_python(
    code: str,
    timeout: int | None = None,
    *,
    staged_data_path: str | None = None,
    capture_figures: bool = True,
) -> dict:
    """Execute Python code in a restricted sandbox and return results.

    Args:
        code: Python source to execute
        timeout: max seconds (default: settings.sandbox_timeout)
        staged_data_path: optional Parquet/CSV file path injected as DATA_PATH
            global; the user code reads via `pd.read_parquet(DATA_PATH)`
        capture_figures: when True, matplotlib figures are intercepted and
            returned as base64-encoded PNGs in result["figures"]
    """
    timeout = timeout or settings.sandbox_timeout
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = {
        "stdout": "",
        "stderr": "",
        "error": None,
        "artifacts": [],
        "figures": [],  # list of {"format": "png", "base64": "...", "size_kb": N}
        "variables": {},  # default empty so callers can always .get('variables') safely
        "exec_ms": 0,
    }
    _t_start = time.monotonic()

    try:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout
        sys.stderr = stderr

        try:
            exec_globals = {
                "__builtins__": {
                    "print": print,
                    "range": range,
                    "len": len,
                    "int": int,
                    "float": float,
                    "str": str,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "frozenset": frozenset,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "abs": abs,
                    "round": round,
                    "sorted": sorted,
                    "reversed": reversed,
                    "enumerate": enumerate,
                    "zip": zip,
                    "map": map,
                    "filter": filter,
                    "any": any,
                    "all": all,
                    "isinstance": isinstance,
                    "issubclass": issubclass,
                    "type": type,
                    "hasattr": hasattr,
                    "getattr": getattr,
                    "setattr": setattr,
                    "vars": vars,
                    "dir": dir,
                    "repr": repr,
                    "hash": hash,
                    "id": id,
                    "callable": callable,
                    "iter": iter,
                    "next": next,
                    "open": open,
                    "Exception": Exception,
                    "ValueError": ValueError,
                    "TypeError": TypeError,
                    "KeyError": KeyError,
                    "IndexError": IndexError,
                    "AttributeError": AttributeError,
                    "RuntimeError": RuntimeError,
                    "StopIteration": StopIteration,
                    "NotImplementedError": NotImplementedError,
                    "ZeroDivisionError": ZeroDivisionError,
                    "OverflowError": OverflowError,
                    "ImportError": ImportError,
                    "OSError": OSError,
                    "IOError": IOError,
                    "FileNotFoundError": FileNotFoundError,
                    "PermissionError": PermissionError,
                    "__import__": __import__,
                },
            }

            # Inject DATA_PATH if a staged dataset was provided
            if staged_data_path:
                exec_globals["DATA_PATH"] = staged_data_path

            # ── Pre-inject the full visualization stack ────────────────────
            # Every library is injected unconditionally; missing packages are
            # silently skipped so the sandbox never hard-fails on import.
            if capture_figures:
                # matplotlib / seaborn ─────────────────────────────────────
                try:
                    import matplotlib
                    matplotlib.use("Agg")  # headless — no display required
                    import matplotlib.pyplot as plt
                    import matplotlib.patches as mpatches
                    import matplotlib.ticker as mticker
                    from matplotlib.gridspec import GridSpec
                    # Configure CJK fonts to prevent tofu boxes in Chinese text
                    try:
                        from matplotlib import rcParams
                        _CJK_FONTS = [
                            "Noto Sans CJK SC", "Noto Sans CJK", "Source Han Sans SC",
                            "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                            "SimHei", "WenQuanYi Micro Hei", "Arial Unicode MS",
                            "DejaVu Sans", "Arial", "sans-serif",
                        ]
                        rcParams["font.family"] = "sans-serif"
                        rcParams["font.sans-serif"] = _CJK_FONTS
                        rcParams["axes.unicode_minus"] = False
                    except Exception:
                        pass
                    plt.close("all")
                    exec_globals["plt"] = plt
                    exec_globals["mpatches"] = mpatches
                    exec_globals["mticker"] = mticker
                    exec_globals["GridSpec"] = GridSpec
                    exec_globals["matplotlib"] = matplotlib
                except ImportError:
                    pass

                try:
                    import seaborn as sns
                    sns.set_theme(style="whitegrid", font_scale=1.1)
                    exec_globals["sns"] = sns
                except ImportError:
                    pass

                # numpy / pandas ───────────────────────────────────────────
                try:
                    import numpy as np
                    exec_globals["np"] = np
                except ImportError:
                    pass
                try:
                    import pandas as pd
                    exec_globals["pd"] = pd
                except ImportError:
                    pass

                # scipy ────────────────────────────────────────────────────
                try:
                    import scipy.stats as scipy_stats
                    from scipy import interpolate as scipy_interpolate
                    exec_globals["scipy_stats"] = scipy_stats
                    exec_globals["scipy_interpolate"] = scipy_interpolate
                except ImportError:
                    pass

                # plotly ───────────────────────────────────────────────────
                try:
                    import plotly.express as px
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    exec_globals["px"] = px
                    exec_globals["go"] = go
                    exec_globals["make_subplots"] = make_subplots
                except ImportError:
                    pass

                # squarify (treemap) ───────────────────────────────────────
                try:
                    import squarify
                    exec_globals["squarify"] = squarify
                except ImportError:
                    pass

                # wordcloud ────────────────────────────────────────────────
                try:
                    from wordcloud import WordCloud, STOPWORDS
                    exec_globals["WordCloud"] = WordCloud
                    exec_globals["STOPWORDS"] = STOPWORDS
                except ImportError:
                    pass

                # networkx ─────────────────────────────────────────────────
                try:
                    import networkx as nx
                    exec_globals["nx"] = nx
                except ImportError:
                    pass

                # mplfinance (candlestick / OHLC) ──────────────────────────
                try:
                    import mplfinance as mpf
                    exec_globals["mpf"] = mpf
                except ImportError:
                    pass

                # pywaffle (waffle charts) ─────────────────────────────────
                try:
                    from pywaffle import Waffle
                    exec_globals["Waffle"] = Waffle
                except ImportError:
                    pass

                # calplot (calendar heatmaps) ──────────────────────────────
                try:
                    import calplot
                    exec_globals["calplot"] = calplot
                except ImportError:
                    pass

                # joypy (ridgeline / joy plots) ────────────────────────────
                try:
                    import joypy
                    exec_globals["joypy"] = joypy
                except ImportError:
                    pass

                # plotnine (grammar of graphics) ───────────────────────────
                try:
                    import plotnine as p9
                    exec_globals["p9"] = p9
                except ImportError:
                    pass

                # matplotlib-venn ──────────────────────────────────────────
                try:
                    from matplotlib_venn import venn2, venn3
                    exec_globals["venn2"] = venn2
                    exec_globals["venn3"] = venn3
                except ImportError:
                    pass

                # adjustText (label de-overlap) ────────────────────────────
                try:
                    from adjustText import adjust_text
                    exec_globals["adjust_text"] = adjust_text
                except ImportError:
                    pass

                # statsmodels ──────────────────────────────────────────────
                try:
                    import statsmodels.api as sm
                    exec_globals["sm"] = sm
                except ImportError:
                    pass

            # ── Scientific / precision computing (always injected) ──────────
            # Built-in precision modules — no ImportError possible
            from decimal import Decimal, ROUND_HALF_UP, getcontext as _getcontext
            import math as _math
            import statistics as _statistics
            import fractions as _fractions
            exec_globals["Decimal"] = Decimal
            exec_globals["ROUND_HALF_UP"] = ROUND_HALF_UP
            exec_globals["decimal_getcontext"] = _getcontext
            exec_globals["math"] = _math
            exec_globals["statistics"] = _statistics
            exec_globals["Fraction"] = _fractions.Fraction

            # mpmath — arbitrary-precision arithmetic ───────────────────────
            try:
                import mpmath
                exec_globals["mpmath"] = mpmath
                exec_globals["mp"] = mpmath.mp        # precision context
            except ImportError:
                pass

            # sympy — symbolic mathematics / CAS ────────────────────────────
            try:
                import sympy as sp
                exec_globals["sp"] = sp
                exec_globals["sympy"] = sp
            except ImportError:
                pass

            # numexpr — fast array expression evaluator ─────────────────────
            try:
                import numexpr as ne
                exec_globals["ne"] = ne
                exec_globals["numexpr"] = ne
            except ImportError:
                pass

            # bottleneck — fast NaN-aware aggregations ─────────────────────
            try:
                import bottleneck as bn
                exec_globals["bn"] = bn
            except ImportError:
                pass

            # tabulate — pretty-print tables ────────────────────────────────
            try:
                from tabulate import tabulate as _tabulate
                exec_globals["tabulate"] = _tabulate
            except ImportError:
                pass

            # ── Excel / spreadsheet direct reading ─────────────────────────
            # openpyxl — Excel .xlsx/.xlsm read/write
            try:
                import openpyxl
                exec_globals["openpyxl"] = openpyxl
            except ImportError:
                pass

            # xlrd — legacy .xls (Excel 97-2003) reader
            try:
                import xlrd
                exec_globals["xlrd"] = xlrd
            except ImportError:
                pass

            # pyxlsb — Excel Binary Workbook (.xlsb) reader
            try:
                import pyxlsb
                exec_globals["pyxlsb"] = pyxlsb
            except ImportError:
                pass

            # odfpy — OpenDocument Spreadsheet (.ods) reader
            try:
                import odf.opendocument as _odf
                exec_globals["odf"] = _odf
            except ImportError:
                pass

            # duckdb — in-process analytical SQL engine
            try:
                import duckdb
                exec_globals["duckdb"] = duckdb
            except ImportError:
                pass

            # polars — fast DataFrame library (complement to pandas)
            try:
                import polars as pl
                exec_globals["pl"] = pl
            except ImportError:
                pass

            # io / StringIO / json always available
            import json as _json_mod
            from io import StringIO as _StringIO
            exec_globals["json"] = _json_mod
            exec_globals["StringIO"] = _StringIO

            exec(code, exec_globals)

            # ── Capture figures ─────────────────────────────────────────────
            if capture_figures:
                # 1. matplotlib figures
                try:
                    import matplotlib.pyplot as plt
                    for fig_num in plt.get_fignums():
                        fig = plt.figure(fig_num)
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight",
                                    facecolor=fig.get_facecolor())
                        buf.seek(0)
                        png_bytes = buf.read()
                        result["figures"].append({
                            "format": "png",
                            "base64": base64.b64encode(png_bytes).decode("ascii"),
                            "size_kb": round(len(png_bytes) / 1024, 1),
                        })
                        if len(result["figures"]) >= 8:  # up from 4
                            break
                    plt.close("all")
                except Exception as exc:
                    logger.debug("Matplotlib figure capture failed: %s", exc)

                # 2. plotly figures stored in exec_globals["_plotly_fig"]
                #    (user code should do: _plotly_fig = fig)
                try:
                    import plotly.graph_objects as go
                    import kaleido  # noqa: F401 — ensures kaleido is available
                    for _var_name in ("_plotly_fig", "_fig", "fig"):
                        _pf = exec_globals.get(_var_name)
                        if isinstance(_pf, go.Figure):
                            png_bytes = _pf.to_image(
                                format="png", width=1400, height=900, scale=2
                            )
                            result["figures"].append({
                                "format": "png",
                                "base64": base64.b64encode(png_bytes).decode("ascii"),
                                "size_kb": round(len(png_bytes) / 1024, 1),
                            })
                            if len(result["figures"]) >= 8:
                                break
                except Exception as exc:
                    logger.debug("Plotly figure capture failed: %s", exc)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        result["stdout"] = stdout.getvalue()
        result["stderr"] = stderr.getvalue()

        # Capture named output variables so callers can access result/chart_data/etc.
        captured: dict = {}
        for key in (
            "result", "chart_labels", "chart_data", "chart_series",
            "output", "summary", "table_md", "metrics", "df_summary",
            # Extended set for precision / scientific analysis outputs
            "calculations", "stats_table", "comparison_table", "pivot_table",
            "forecast_table", "anomaly_table", "ranking_table", "corr_matrix",
            "precision_result", "analysis", "report",
        ):
            val = exec_globals.get(key)
            if val is not None:
                captured[key] = _safe_serialize(val)
        result["variables"] = captured

    except Exception as e:
        result["error"] = traceback.format_exc()

    result["exec_ms"] = int((time.monotonic() - _t_start) * 1000)
    return result


def _safe_serialize(val):
    """Convert pandas/numpy objects to JSON-safe Python primitives."""
    try:
        import pandas as pd
        import numpy as np
        if isinstance(val, pd.DataFrame):
            return val.head(200).to_dict(orient="records")
        if isinstance(val, pd.Series):
            return val.head(200).tolist()
        if isinstance(val, np.ndarray):
            return val.tolist()
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
    except ImportError:
        pass
    return val


def execute_sandbox(code: str, injected_globals: dict | None = None) -> any:
    """Synchronous sandbox execution with injected globals (e.g. pandas)."""
    import io
    import sys
    import traceback

    stdout = io.StringIO()
    stderr = io.StringIO()
    result = None

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = stdout
    sys.stderr = stderr

    try:
        safe_builtins = {
            "print": print,
            "range": range, "len": len, "int": int, "float": float,
            "str": str, "bool": bool, "list": list, "dict": dict,
            "tuple": tuple, "set": set, "sum": sum, "min": min,
            "max": max, "abs": abs, "round": round, "sorted": sorted,
            "enumerate": enumerate, "zip": zip, "map": map,
            "filter": filter, "any": any, "all": all,
            "isinstance": isinstance, "type": type,
            "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "KeyError": KeyError,
            "IndexError": IndexError,
        }
        exec_globals = {"__builtins__": safe_builtins}
        if injected_globals:
            exec_globals.update(injected_globals)
        exec(code, exec_globals)
        result = exec_globals.get("result")
    except Exception:
        result = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return result
