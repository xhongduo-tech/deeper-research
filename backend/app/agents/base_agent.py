"""
BaseAgent — 数字员工的基础执行层。

所有子智能体（员工）继承此类。负责：
- LLM 通信（流式 + 非流式）
- 工具调用分发（sandbox / file_reader / chart_renderer）
- 进度回调推送

注意：browser_tool / search_tool 已从工具白名单中永久移除。
本系统部署在银行内网离线环境，所有信息源 = 用户上传材料。
"""
from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings


class BaseAgent:
    """所有数字员工的基础类。核心负责 LLM 通信与工具执行。"""

    # 离线安全工具白名单（永不包含 browser/search）
    ALLOWED_TOOLS = frozenset({
        "file_reader", "sandbox", "excel_parser",
        "pdf_parser", "office_converter", "ocr",
        "chart_renderer", "docx_writer", "template_engine",
    })

    def __init__(
        self,
        employee_def: Dict[str, Any],
        llm_config: Dict[str, Any],
        tools: Optional[List[str]] = None,
    ):
        self.employee_def = employee_def
        self.employee_id = employee_def["id"]
        self.employee_name = employee_def["name"]
        self.system_prompt = employee_def.get("system_prompt", "")
        self.llm_config = llm_config
        # Enforce whitelist — silently drop any tool not in ALLOWED_TOOLS
        self.available_tools = [t for t in (tools or []) if t in self.ALLOWED_TOOLS]

        self._client = AsyncOpenAI(
            api_key=llm_config.get("api_key") or settings.DEFAULT_LLM_API_KEY,
            base_url=llm_config.get("base_url") or settings.DEFAULT_LLM_BASE_URL,
        )
        self.model = (
            llm_config.get("model")
            or employee_def.get("default_model")
            or settings.DEFAULT_LLM_MODEL
        )

    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        context = context or {}
        messages = self._build_messages(task, context)
        full_response = ""

        if callback:
            await callback({
                "type": "employee_progress",
                "employee_id": self.employee_id,
                "content": f"[{self.employee_name}] 开始分析任务…",
            })

        try:
            parts: List[str] = []
            async for chunk in self._call_llm(messages, stream=True):
                parts.append(chunk)
                if callback:
                    await callback({
                        "type": "employee_progress",
                        "employee_id": self.employee_id,
                        "content": chunk,
                    })
            full_response = "".join(parts)

            tool_results = await self._process_tool_calls(full_response, context, callback)
            if tool_results:
                messages.append({"role": "assistant", "content": full_response})
                tool_summary = "\n\n".join(
                    f"[工具执行结果 - {r['tool']}]:\n{r['output']}"
                    for r in tool_results
                )
                messages.append({
                    "role": "user",
                    "content": f"以下是工具执行结果，请基于这些结果完成分析：\n\n{tool_summary}",
                })
                synthesis: List[str] = []
                async for chunk in self._call_llm(messages, stream=True):
                    synthesis.append(chunk)
                    if callback:
                        await callback({
                            "type": "employee_progress",
                            "employee_id": self.employee_id,
                            "content": chunk,
                        })
                full_response = "".join(synthesis)

        except Exception as e:
            err = f"[{self.employee_name}] 执行出错: {e}"
            if callback:
                await callback({"type": "employee_progress", "employee_id": self.employee_id, "content": err})
            full_response = f"执行过程中遇到错误: {e}"

        return full_response

    # ------------------------------------------------------------------
    # LLM communication
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        if self.llm_config.get("temperature") is not None:
            temperature = self.llm_config["temperature"]
        if self.llm_config.get("max_tokens"):
            max_tokens = self.llm_config["max_tokens"]

        if stream:
            response = await self._client.chat.completions.create(
                model=self.model, messages=messages, stream=True,
                temperature=temperature, max_tokens=max_tokens,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            response = await self._client.chat.completions.create(
                model=self.model, messages=messages, stream=False,
                temperature=temperature, max_tokens=max_tokens,
            )
            yield response.choices[0].message.content or ""

    async def _call_llm_full(
        self, messages: List[Dict[str, Any]],
        temperature: float = 0.7, max_tokens: int = 4096,
    ) -> str:
        parts: List[str] = []
        async for chunk in self._call_llm(messages, stream=False, temperature=temperature, max_tokens=max_tokens):
            parts.append(chunk)
        return "".join(parts)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        if tool_name not in self.ALLOWED_TOOLS:
            return f"工具 '{tool_name}' 不在离线安全工具白名单中"

        if tool_name == "sandbox":
            from app.services.sandbox_service import execute as sandbox_exec, SandboxSecurityError
            code = params.get("code", "")
            try:
                result = sandbox_exec(code, extra_vars=params.get("context_vars") or {})
                return result.summary() if result.ok else f"沙箱执行失败: {result.error}"
            except SandboxSecurityError as e:
                return f"安全检查未通过: {e}"

        if tool_name == "file_reader":
            from app.tools.file_reader import FileReader
            reader = FileReader()
            text = await reader.extract_text(params.get("file_path", ""), params.get("file_type", "txt"))
            return text or "无法读取文件内容"

        return f"工具 '{tool_name}' 暂未实现"

    async def _process_tool_calls(
        self, response: str, context: Dict[str, Any], callback: Optional[Callable]
    ) -> List[Dict[str, Any]]:
        tool_results: List[Dict[str, Any]] = []

        if "sandbox" in self.available_tools:
            for code in self._extract_code_blocks(response):
                if callback:
                    await callback({"type": "code_executing", "employee_id": self.employee_id, "code": code[:500]})
                output = await self._execute_tool("sandbox", {"code": code})
                if callback:
                    await callback({"type": "code_result", "employee_id": self.employee_id, "output": output[:1000]})
                tool_results.append({"tool": "sandbox", "code": code, "output": output})

        return tool_results

    def _extract_code_blocks(self, text: str) -> List[str]:
        return re.findall(r"```python\n(.*?)```", text, re.DOTALL)

    # ------------------------------------------------------------------
    # Message builder
    # ------------------------------------------------------------------

    def _build_messages(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        messages = [{"role": "system", "content": self._build_system_prompt(context)}]

        if context.get("files"):
            files_content = "\n\n".join(
                f"=== 文件: {f.get('name', '未知')} ===\n{f.get('content', '')}"
                for f in context["files"]
            )
            messages.append({"role": "user", "content": f"以下是相关文件内容：\n\n{files_content}"})
            messages.append({"role": "assistant", "content": "好的，我已阅读文件，请告诉我任务。"})

        if context.get("previous_results"):
            prev = "\n\n".join(
                f"[{eid}的工作成果]:\n{res}"
                for eid, res in context["previous_results"].items()
            )
            messages.append({"role": "user", "content": f"已有工作成果：\n\n{prev}"})
            messages.append({"role": "assistant", "content": "收到，我会参考已有成果。"})

        if context.get("evidence_context"):
            messages.append({"role": "user", "content": f"证据索引：\n\n{context['evidence_context']}"})
            messages.append({"role": "assistant", "content": "收到，我会基于证据索引进行可追溯分析。"})

        messages.append({"role": "user", "content": task})
        return messages

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        additions: List[str] = []
        if context.get("rules"):
            additions.append(f"\n\n## 特别要求\n{context['rules']}")
        if context.get("output_format"):
            additions.append(f"\n\n## 输出格式\n{context['output_format']}")
        if self.available_tools:
            tool_hints = []
            if "sandbox" in self.available_tools:
                tool_hints.append("- Python 沙箱：在回复中包含 ```python 代码块```，系统自动执行")
            if tool_hints:
                additions.append("\n\n## 可用工具\n" + "\n".join(tool_hints))
        return self.system_prompt + "".join(additions)
