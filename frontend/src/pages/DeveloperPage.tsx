import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Key,
  Copy,
  Trash2,
  Plus,
  Pause,
  Play,
  Check,
  Code2,
  Terminal,
  Eye,
  EyeOff,
} from 'lucide-react';
import toast from 'react-hot-toast';

import {
  Button,
  Dialog,
  Input,
  Badge,
  Skeleton,
  Tabs,
  cn,
} from '../design-system';
import {
  createApiKey,
  deleteApiKey,
  listMyApiKeys,
  revealApiKey,
  setApiKeyStatus,
} from '../api/developer';
import { formatDate } from '../utils/formatters';
import { getApiErrorMessage } from '../utils/errors';
import type { ApiKeyRecord } from '../types/report';

// =============================================================================
// Create key dialog
// =============================================================================

const CreateKeyDialog: React.FC<{
  open: boolean;
  onClose: () => void;
}> = ({ open, onClose }) => {
  const [name, setName] = useState('');
  const queryClient = useQueryClient();
  const createMut = useMutation({
    mutationFn: () => createApiKey({ name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', 'mine'] });
      toast.success('密钥已创建，可在列表里随时查看原文');
      setName('');
      onClose();
    },
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '创建失败')),
  });

  return (
    <Dialog open={open} onClose={onClose} title="创建 API Key">
      <div className="flex flex-col gap-4">
        <div>
          <label className="text-[12px] font-semibold text-ink-2">
            名称
          </label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：风险系统对接 / 本地脚本"
            autoFocus
            className="mt-1"
          />
          <p className="mt-1 text-[11.5px] text-ink-3">
            申请即通过。密钥用于调用 <code className="font-mono">/api/v1/reports</code> 等接口。
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button
            size="sm"
            variant="primary"
            loading={createMut.isPending}
            disabled={!name.trim()}
            onClick={() => createMut.mutate()}
          >
            创建
          </Button>
        </div>
      </div>
    </Dialog>
  );
};

// =============================================================================
// Key row — with inline reveal
// =============================================================================

const KeyRow: React.FC<{ k: ApiKeyRecord }> = ({ k }) => {
  const queryClient = useQueryClient();
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const statusMut = useMutation({
    mutationFn: (status: 'active' | 'suspended' | 'revoked') =>
      setApiKeyStatus(k.id, status),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['api-keys', 'mine'] }),
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteApiKey(k.id),
    onSuccess: () => {
      toast.success('已删除');
      queryClient.invalidateQueries({ queryKey: ['api-keys', 'mine'] });
    },
  });
  const revealMut = useMutation({
    mutationFn: () => revealApiKey(k.id),
    onSuccess: (res) => setRevealed(res.raw_key),
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '无法查看密钥原文')),
  });

  const active = k.status === 'active';
  const handleCopy = async (value: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div className="flex flex-col gap-2 px-4 py-3.5">
      <div className="flex items-center gap-4">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
          <Key size={13} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[13px] font-semibold text-ink-1">
              {k.name}
            </span>
            <Badge
              size="xs"
              tone={
                k.status === 'active'
                  ? 'success'
                  : k.status === 'suspended'
                    ? 'warning'
                    : 'neutral'
              }
              variant="soft"
            >
              {k.status === 'active' ? '生效' : k.status === 'suspended' ? '暂停' : '吊销'}
            </Badge>
          </div>
          <div className="mt-0.5 flex items-center gap-3 text-[11.5px] text-ink-3">
            <span className="font-mono">
              {revealed ? revealed : k.masked_key}
            </span>
            <span className="text-ink-4">·</span>
            <span>创建于 {formatDate(k.created_at)}</span>
            <span className="text-ink-4">·</span>
            <span>调用 {k.total_requests} 次</span>
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-1">
          {revealed ? (
            <>
              <Button
                size="xs"
                variant="ghost"
                leftIcon={copied ? <Check size={11} /> : <Copy size={11} />}
                onClick={() => handleCopy(revealed)}
              >
                {copied ? '已复制' : '复制'}
              </Button>
              <Button
                size="xs"
                variant="ghost"
                leftIcon={<EyeOff size={11} />}
                onClick={() => setRevealed(null)}
              >
                隐藏
              </Button>
            </>
          ) : (
            <Button
              size="xs"
              variant="ghost"
              leftIcon={<Eye size={11} />}
              loading={revealMut.isPending}
              onClick={() => revealMut.mutate()}
            >
              查看
            </Button>
          )}
          <Button
            size="xs"
            variant="ghost"
            leftIcon={active ? <Pause size={11} /> : <Play size={11} />}
            onClick={() =>
              statusMut.mutate(active ? 'suspended' : 'active')
            }
            loading={statusMut.isPending}
          >
            {active ? '暂停' : '恢复'}
          </Button>
          <Button
            size="xs"
            variant="danger"
            leftIcon={<Trash2 size={11} />}
            loading={deleteMut.isPending}
            onClick={() => {
              if (confirm(`确认删除密钥"${k.name}"？此操作不可撤销。`)) {
                deleteMut.mutate();
              }
            }}
          >
            删除
          </Button>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// VSCode Dark+ syntax highlighter (lightweight, no external deps)
// =============================================================================

// Token types mapped to VSCode Dark+ theme colors
const TK_COLOR: Record<string, string> = {
  comment:  '#6a9955',  // green
  string:   '#ce9178',  // orange
  keyword:  '#569cd6',  // blue
  number:   '#b5cea8',  // light green
  builtin:  '#4ec9b0',  // teal
  fn:       '#dcdcaa',  // yellow
  flag:     '#9cdcfe',  // light blue
  plain:    '#d4d4d4',  // default
  punct:    '#d4d4d4',
};

const PY_KW  = new Set(['import','from','def','if','else','elif','while','for','in','return','True','False','None','class','with','as','try','except','raise','and','or','not','pass','break','continue','lambda','yield','del','global','nonlocal','assert','async','await']);
const PY_BI  = new Set(['requests','os','time','open','print','range','len','str','int','float','list','dict','set','tuple','json','sys','Exception','KeyError','ValueError','TypeError']);
const JS_KW  = new Set(['import','export','from','const','let','var','async','await','function','if','else','while','for','of','in','return','true','false','null','undefined','new','class','this','try','catch','finally','throw','typeof','instanceof','switch','case','default','break','continue']);
const JS_BI  = new Set(['fs','axios','FormData','console','JSON','process','Buffer','Promise','setTimeout','clearTimeout','require','module','exports','Object','Array','String','Number','Math','Date','Error','Symbol','Map','Set','WeakMap','WeakRef']);

type TkType = keyof typeof TK_COLOR;

function tokenize(code: string, lang: string): Array<[TkType, string]> {
  const tokens: Array<[TkType, string]> = [];
  let i = 0;
  const isCurl = lang === 'curl';
  const isPy   = lang === 'python';
  const isJs   = lang === 'node';

  while (i < code.length) {
    const ch = code[i];
    const rest = code.slice(i);

    // --- line comment ---
    if ((isPy || isCurl) && ch === '#') {
      const nl = rest.indexOf('\n');
      const seg = nl === -1 ? rest : rest.slice(0, nl);
      tokens.push(['comment', seg]);
      i += seg.length;
      continue;
    }
    if (isJs && rest.startsWith('//')) {
      const nl = rest.indexOf('\n');
      const seg = nl === -1 ? rest : rest.slice(0, nl);
      tokens.push(['comment', seg]);
      i += seg.length;
      continue;
    }

    // --- double-quoted string ---
    if (ch === '"') {
      let j = 1;
      while (j < rest.length && rest[j] !== '"') {
        if (rest[j] === '\\') j++;
        j++;
      }
      tokens.push(['string', rest.slice(0, j + 1)]);
      i += j + 1;
      continue;
    }
    // --- single-quoted string ---
    if (ch === "'") {
      let j = 1;
      while (j < rest.length && rest[j] !== "'") {
        if (rest[j] === '\\') j++;
        j++;
      }
      tokens.push(['string', rest.slice(0, j + 1)]);
      i += j + 1;
      continue;
    }
    // --- template literal (JS) ---
    if (isJs && ch === '`') {
      let j = 1;
      while (j < rest.length && rest[j] !== '`') {
        if (rest[j] === '\\') j++;
        j++;
      }
      tokens.push(['string', rest.slice(0, j + 1)]);
      i += j + 1;
      continue;
    }

    // --- number ---
    if (/\d/.test(ch) && (i === 0 || !/\w/.test(code[i - 1]))) {
      const m = rest.match(/^\d+(\.\d+)?/);
      if (m) { tokens.push(['number', m[0]]); i += m[0].length; continue; }
    }

    // --- CLI flag (curl) ---
    if (isCurl && ch === '-') {
      const m = rest.match(/^-[a-zA-Z]+/);
      if (m) { tokens.push(['flag', m[0]]); i += m[0].length; continue; }
    }

    // --- identifier / keyword / builtin ---
    if (/[a-zA-Z_$]/.test(ch)) {
      const m = rest.match(/^[a-zA-Z_$][a-zA-Z0-9_$]*/);
      if (m) {
        const word = m[0];
        let type: TkType = 'plain';
        const nextNonSpace = code.slice(i + word.length).trimStart()[0];
        if (isPy) {
          if (PY_KW.has(word)) type = 'keyword';
          else if (PY_BI.has(word)) type = 'builtin';
          else if (nextNonSpace === '(') type = 'fn';
        } else if (isJs) {
          if (JS_KW.has(word)) type = 'keyword';
          else if (JS_BI.has(word)) type = 'builtin';
          else if (nextNonSpace === '(') type = 'fn';
        } else if (isCurl) {
          if (['curl'].includes(word)) type = 'builtin';
          else if (['Bearer','POST','GET','PUT','DELETE','PATCH','HEAD','OPTIONS'].includes(word)) type = 'keyword';
        }
        tokens.push([type, word]);
        i += word.length;
        continue;
      }
    }

    // --- backslash line-continuation (curl/shell) ---
    if (ch === '\\' && code[i + 1] === '\n') {
      tokens.push(['punct', '\\\n']);
      i += 2;
      continue;
    }

    // --- anything else (operators, whitespace, punctuation) ---
    tokens.push(['plain', ch]);
    i++;
  }
  return tokens;
}

function renderHighlighted(code: string, lang: string): React.ReactNode {
  const toks = tokenize(code, lang);
  return toks.map(([type, text], idx) => (
    <span key={idx} style={{ color: TK_COLOR[type] ?? TK_COLOR.plain }}>
      {text}
    </span>
  ));
}

// =============================================================================
// Docs
// =============================================================================

const CodeBlock: React.FC<{ children: string; lang?: string }> = ({
  children,
  lang,
}) => {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative rounded-md border border-[#3c3c3c] bg-[#1e1e1e] text-[12px] leading-relaxed">
      {lang && (
        <div className="flex items-center justify-between border-b border-[#3c3c3c] px-4 py-1.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#858585]">
            {lang === 'curl' ? 'bash / cURL' : lang === 'python' ? 'Python' : 'Node.js'}
          </span>
          <button
            onClick={async () => {
              await navigator.clipboard.writeText(children);
              setCopied(true);
              setTimeout(() => setCopied(false), 1400);
            }}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[#858585] transition-colors hover:bg-[#2d2d2d] hover:text-[#cccccc]"
            title="复制"
          >
            {copied ? <Check size={11} /> : <Copy size={11} />}
            <span className="text-[10px]">{copied ? '已复制' : '复制'}</span>
          </button>
        </div>
      )}
      <pre className="overflow-x-auto p-4 font-mono">
        <code>{renderHighlighted(children, lang ?? '')}</code>
      </pre>
    </div>
  );
};

type DocLang = 'curl' | 'python' | 'node';

const DOC_SAMPLES: Record<DocLang, string> = {
  curl: `curl -X POST http://your-host/api/v1/reports \\
  -H "Authorization: Bearer dr_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "brief": "针对 2026 Q1 零售业务的经营分析，重点是收入与不良率变化",
    "report_type": "ops_review",
    "file_ids": [12, 13],
    "auto_start": true,
    "skip_clarifications": true
  }'

# 可选：轮询状态直到 delivered
curl http://your-host/api/v1/reports/42 \\
  -H "Authorization: Bearer dr_your_api_key"

# 下载交付的 .docx
curl -OJ http://your-host/api/v1/reports/42/download \\
  -H "Authorization: Bearer dr_your_api_key"`,
  python: `import os, time, requests

API = "http://your-host/api/v1"
HEAD = {"Authorization": f"Bearer {os.environ['DATAAGENT_KEY']}"}

# 1) 先上传文件（可选）
def upload(path):
    with open(path, "rb") as fp:
        r = requests.post(f"{API}/files",
            headers=HEAD, files={"file": fp})
    r.raise_for_status()
    return r.json()["id"]

file_ids = [upload("Q1_retail.xlsx"), upload("policy.pdf")]

# 2) 创建报告 — auto_start 让系统直接开工，
#    skip_clarifications 让系统不再回来提问、全部采纳默认答案
r = requests.post(f"{API}/reports", headers=HEAD, json={
    "brief": "针对 2026 Q1 零售业务的经营分析",
    "report_type": "ops_review",
    "file_ids": file_ids,
    "auto_start": True,
    "skip_clarifications": True,
})
r.raise_for_status()
report = r.json()

# 3) 轮询直到 delivered
while True:
    info = requests.get(f"{API}/reports/{report['id']}", headers=HEAD).json()
    if info["status"] in ("delivered", "failed", "cancelled"):
        break
    time.sleep(3)

# 4) 下载 Word
if info["status"] == "delivered":
    doc = requests.get(
        f"{API}/reports/{report['id']}/download", headers=HEAD)
    open("report.docx", "wb").write(doc.content)
`,
  node: `import fs from 'node:fs';
import FormData from 'form-data';
import axios from 'axios';

const API = 'http://your-host/api/v1';
const headers = { Authorization: \`Bearer \${process.env.DATAAGENT_KEY}\` };

async function upload(path) {
  const form = new FormData();
  form.append('file', fs.createReadStream(path));
  const { data } = await axios.post(\`\${API}/files\`, form, {
    headers: { ...headers, ...form.getHeaders() },
  });
  return data.id;
}

const fileIds = [await upload('Q1_retail.xlsx'), await upload('policy.pdf')];

// 创建报告 —— auto_start 表示直接生产，
// skip_clarifications 表示不再回来提问（全部采纳默认答案）。
const { data: report } = await axios.post(\`\${API}/reports\`, {
  brief: '针对 2026 Q1 零售业务的经营分析',
  report_type: 'ops_review',
  file_ids: fileIds,
  auto_start: true,
  skip_clarifications: true,
}, { headers });

// 轮询
let info = report;
while (!['delivered', 'failed', 'cancelled'].includes(info.status)) {
  await new Promise(r => setTimeout(r, 3000));
  info = (await axios.get(\`\${API}/reports/\${report.id}\`, { headers })).data;
}

// 下载
if (info.status === 'delivered') {
  const { data } = await axios.get(
    \`\${API}/reports/\${report.id}/download\`,
    { headers, responseType: 'arraybuffer' },
  );
  fs.writeFileSync('report.docx', data);
}
`,
};

const DocsPanel: React.FC = () => {
  const [lang, setLang] = useState<DocLang>('curl');
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-[14px] font-semibold text-ink-1">
          核心用法：给几份文件 + 提示词，拿一份报告
        </h3>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-2">
          API 的典型闭环只有一步：<code className="rounded bg-sunken px-1 font-mono">POST /api/v1/reports</code>{' '}
          带上 <code className="rounded bg-sunken px-1 font-mono">brief</code>、<code className="rounded bg-sunken px-1 font-mono">report_type</code>、<code className="rounded bg-sunken px-1 font-mono">file_ids</code>，
          再加 <code className="rounded bg-sunken px-1 font-mono">auto_start: true</code> 与{' '}
          <code className="rounded bg-sunken px-1 font-mono">skip_clarifications: true</code>{' '}
          系统就会不再回来提问、直接生产，最终产出一份 Word 报告让你下载。
        </p>

        <div className="mt-3 flex gap-1.5">
          {(['curl', 'python', 'node'] as DocLang[]).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={cn(
                'rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors',
                lang === l
                  ? 'bg-[#141414] text-white'
                  : 'bg-sunken text-ink-2 hover:bg-sunken/80',
              )}
            >
              {l === 'curl' ? 'cURL' : l === 'python' ? 'Python' : 'Node.js'}
            </button>
          ))}
        </div>
        <div className="mt-2">
          <CodeBlock lang={lang}>{DOC_SAMPLES[lang]}</CodeBlock>
        </div>
      </section>

      <section>
        <h3 className="text-[14px] font-semibold text-ink-1">请求参数速查</h3>
        <div className="mt-2 overflow-hidden rounded-md border border-line-subtle">
          <table className="w-full border-collapse text-[12px]">
            <thead className="bg-sunken/60 text-ink-2">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">字段</th>
                <th className="px-3 py-2 text-left font-semibold">类型</th>
                <th className="px-3 py-2 text-left font-semibold">说明</th>
              </tr>
            </thead>
            <tbody className="text-ink-2">
              {[
                ['brief', 'string · 必填', '你的需求描述（越具体越好）'],
                ['report_type', 'string · 必填', '报告类型 id，见下方列表'],
                ['file_ids', 'number[] · 可选', '通过 POST /files 预先上传得到的文件 id'],
                ['title', 'string · 可选', '自定义标题，不传则取 brief 前 40 字'],
                ['auto_start', 'boolean · 可选', '创建后立刻进入生产阶段，等价于再调 POST /reports/{id}/start'],
                ['skip_clarifications', 'boolean · 可选', '不再回来提问，全部采纳默认答案 —— 适合纯 API/自动化场景'],
              ].map((row, i) => (
                <tr
                  key={row[0]}
                  className={i > 0 ? 'border-t border-line-subtle' : ''}
                >
                  <td className="px-3 py-2 font-mono text-[11.5px] text-brand">
                    {row[0]}
                  </td>
                  <td className="px-3 py-2 text-[11.5px] text-ink-3">{row[1]}</td>
                  <td className="px-3 py-2">{row[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="text-[14px] font-semibold text-ink-1">报告类型</h3>
        <ul className="mt-1.5 space-y-1 text-[12.5px] text-ink-2">
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              ops_review
            </code>{' '}
            — 经营分析报告
          </li>
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              internal_research
            </code>{' '}
            — 内部专题研究
          </li>
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              risk_assessment
            </code>{' '}
            — 风险评估报告
          </li>
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              regulatory_filing
            </code>{' '}
            — 合规 / 监管报送
          </li>
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              training_material
            </code>{' '}
            — 培训 / 学习材料
          </li>
          <li>
            <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11.5px]">
              custom:&lt;id&gt;
            </code>{' '}
            — 你在「自定义报告类型」里创建的模板
          </li>
        </ul>
      </section>

      <section>
        <h3 className="text-[14px] font-semibold text-ink-1">提示</h3>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12.5px] text-ink-2">
          <li>API 中所有路径都需要带 header <code className="font-mono">Authorization: Bearer dr_...</code>，即上方列表里创建的密钥。</li>
          <li>想实时看生产过程（比如哪个员工在做哪个章节）可以订阅 <code className="font-mono">GET /reports/&#123;id&#125;/events</code> SSE 流。</li>
          <li>想批量创建报告，循环调 <code className="font-mono">POST /reports</code> 即可；系统会并发调度。</li>
        </ul>
      </section>
    </div>
  );
};

// =============================================================================
// Page
// =============================================================================

export const DeveloperPage: React.FC = () => {
  const keysQ = useQuery({
    queryKey: ['api-keys', 'mine'],
    queryFn: listMyApiKeys,
    staleTime: 30 * 1000,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [tab, setTab] = useState<string>('keys');

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[960px] px-6 py-10">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex flex-col gap-2"
        >
          <span className="flex items-center gap-1.5 text-caption uppercase tracking-[0.2em] text-ink-3">
            <Code2 size={11} />
            开发者
          </span>
          <h1 className="font-serif text-[24px] font-semibold text-ink-1">
            用 API 调用 dataagent
          </h1>
          <p className="max-w-[620px] text-[13px] leading-relaxed text-ink-2">
            给几份文件 + 一段提示词，就能拿到一份 Word 报告。
            密钥由你自助创建，系统自动审批。
          </p>
        </motion.div>

        <div className="mb-5">
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { value: 'keys', label: 'API Keys', icon: <Key size={12} /> },
              { value: 'docs', label: '接入文档', icon: <Terminal size={12} /> },
            ]}
          />
        </div>

        {tab === 'keys' && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[12.5px] text-ink-3">
                你的密钥 · {keysQ.data?.items?.length ?? 0} 个
                <span className="ml-2 text-ink-4">
                  (点击「查看」随时显示原文)
                </span>
              </p>
              <Button
                size="sm"
                variant="primary"
                leftIcon={<Plus size={12} />}
                onClick={() => setCreateOpen(true)}
              >
                新建密钥
              </Button>
            </div>

            {keysQ.isLoading ? (
              <div className="flex flex-col gap-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-[64px] rounded-lg" />
                ))}
              </div>
            ) : keysQ.data && keysQ.data.items.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-line-subtle bg-surface">
                {keysQ.data.items.map((k, i) => (
                  <div
                    key={k.id}
                    className={i > 0 ? 'border-t border-line-subtle' : ''}
                  >
                    <KeyRow k={k} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line-subtle px-6 py-12 text-center">
                <Key size={20} className="text-ink-4" />
                <p className="text-[13px] text-ink-3">
                  还没有密钥 — 点右上角「新建密钥」试试。
                </p>
              </div>
            )}
          </>
        )}

        {tab === 'docs' && <DocsPanel />}
      </div>

      <CreateKeyDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  );
};

export default DeveloperPage;
