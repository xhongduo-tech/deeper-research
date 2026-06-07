import { useState } from "react";
import { X, Eye, EyeOff, Lock, User, Building2, Key, UserCircle } from "lucide-react";
import logoImg from "../../imports/deep-research.png";
import { ImageWithFallback } from "./figma/ImageWithFallback";

type Tab = "login" | "register" | "forgot";

const TAB_LABELS: { key: Tab; label: string }[] = [
  { key: "login", label: "登录" },
  { key: "register", label: "注册" },
  { key: "forgot", label: "找回密码" },
];

export function LoginModal({
  onClose,
  onLogin,
  onRegister,
  initialTab = "login",
}: {
  onClose: () => void;
  onLogin: (authId: string, password: string) => Promise<void>;
  onRegister: (payload: {
    auth_id: string;
    username: string;
    department: string;
    password: string;
  }) => Promise<void>;
  initialTab?: Tab;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [showPwd, setShowPwd] = useState(false);
  const [showPwd2, setShowPwd2] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submitLogin = async (authId: string, password: string) => {
    setError("");
    setBusy(true);
    try {
      await onLogin(authId, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setBusy(false);
    }
  };

  const submitRegister = async (payload: {
    auth_id: string;
    username: string;
    department: string;
    password: string;
    confirmPassword: string;
  }) => {
    const authId = payload.auth_id.trim();
    const username = payload.username.trim();
    const department = payload.department.trim();
    const password = payload.password;
    if (!username || !authId || !department || !password) {
      setError("请完整填写姓名、统一认证号、所属部门和密码");
      return;
    }
    if (password !== payload.confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await onRegister({ auth_id: authId, username, department, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className="relative rounded-2xl w-[400px] flex flex-col overflow-hidden"
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          boxShadow: "0 24px 72px rgba(0,0,0,0.18)",
          animation: "modal-in 0.2s cubic-bezier(0.34,1.56,0.64,1)",
        }}
      >
        <style>{`
          @keyframes modal-in {
            from { opacity: 0; transform: scale(0.96) translateY(6px); }
            to   { opacity: 1; transform: scale(1) translateY(0); }
          }
        `}</style>

        {/* Header */}
        <div className="flex items-center gap-3 px-6 pt-6 pb-5">
          <div
            className="h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: "#000" }}
          >
            <ImageWithFallback
              src={logoImg}
              alt="dataAgent"
              style={{ width: 24, height: 24, objectFit: "contain" }}
            />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "16px", color: "var(--ink-900)", letterSpacing: "-0.02em" }}>
              dataAgent
            </div>
            <div style={{ fontSize: "12px", color: "var(--ink-400)", marginTop: 1 }}>
              数据分析智能体助手
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-auto h-7 w-7 inline-flex items-center justify-center rounded-lg transition hover:bg-[var(--hover)]"
            style={{ color: "var(--ink-400)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div
          className="flex mx-6 mb-5 rounded-xl p-1 gap-0.5"
          style={{ background: "var(--bg-subtle)" }}
        >
          {TAB_LABELS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex-1 h-8 rounded-lg text-[13px] transition"
              style={{
                background: tab === t.key ? "var(--bg-elevated)" : "transparent",
                color: tab === t.key ? "var(--ink-900)" : "var(--ink-500)",
                fontWeight: tab === t.key ? 600 : 500,
                boxShadow: tab === t.key ? "var(--shadow-xs)" : "none",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Form content */}
        <div className="px-6 pb-6 flex flex-col gap-3">
          {tab === "login" && <LoginForm onLogin={submitLogin} showPwd={showPwd} setShowPwd={setShowPwd} busy={busy} />}
          {tab === "register" && <RegisterForm onRegister={submitRegister} showPwd={showPwd} setShowPwd={setShowPwd} showPwd2={showPwd2} setShowPwd2={setShowPwd2} busy={busy} />}
          {tab === "forgot" && <ForgotForm onLogin={submitLogin} busy={busy} />}

          {error && (
            <div className="rounded-xl px-3 py-2 text-[12.5px]" style={{ color: "#dc2626", background: "#fee2e2" }}>
              {error}
            </div>
          )}

          {/* ── 使用规范与免责声明 ── */}
          <div className="rounded-xl p-3 mt-1"
            style={{ background: "var(--bg-subtle, #f8fafc)", border: "1px solid var(--border)" }}>
            <p className="text-[11px] font-semibold mb-1.5" style={{ color: "var(--ink-600)" }}>
              使用规范与免责声明
            </p>
            <div className="flex flex-col gap-1 text-[10.5px] leading-[1.55]" style={{ color: "var(--ink-400)" }}>
              <p>📌 <strong style={{ color: "var(--ink-600)" }}>数据安全</strong>：本系统部署于内网环境，所有数据处理均在本地完成，不向外部网络传输任何用户数据或文件内容。</p>
              <p>📌 <strong style={{ color: "var(--ink-600)" }}>AI 生成内容</strong>：系统输出由人工智能生成，仅供参考，不构成法律、投资、医疗等专业建议。重要决策请结合专业人员判断。</p>
              <p>📌 <strong style={{ color: "var(--ink-600)" }}>文件上传限制</strong>：请勿上传含有个人隐私、国家秘密或加密保护的文件。上传即视为您确认拥有相应授权。</p>
              <p>📌 <strong style={{ color: "var(--ink-600)" }}>使用责任</strong>：用户须对通过本系统生成内容的使用结果承担责任，请遵守相关法律法规及组织内部规定。</p>
            </div>
            <p className="text-[10px] mt-1.5" style={{ color: "var(--ink-300)" }}>
              登录即表示您已阅读并同意以上使用规范
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Login ── */
function LoginForm({
  onLogin,
  showPwd,
  setShowPwd,
  busy,
}: {
  onLogin: (authId: string, password: string) => void;
  showPwd: boolean;
  setShowPwd: (v: boolean) => void;
  busy: boolean;
}) {
  const [authId, setAuthId] = useState("");
  const [password, setPassword] = useState("");
  return (
    <>
      <Field icon={<User className="h-4 w-4" />} placeholder="统一认证号" type="text" value={authId} onChange={setAuthId} />
      <div className="relative">
        <Field icon={<Lock className="h-4 w-4" />} placeholder="密码" type={showPwd ? "text" : "password"} value={password} onChange={setPassword} />
        <button
          type="button"
          onClick={() => setShowPwd(!showPwd)}
          className="absolute right-3 top-1/2 -translate-y-1/2"
          style={{ color: "var(--ink-400)" }}
        >
          {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: "13px", color: "var(--ink-500)" }}>
          <input type="checkbox" className="rounded" />
          记住登录
        </label>
      </div>
      <PrimaryBtn onClick={() => onLogin(authId, password)} disabled={busy || !authId || !password}>
        {busy ? "登录中..." : "登录"}
      </PrimaryBtn>
    </>
  );
}

/* ── Register ── */
function RegisterForm({ onRegister, showPwd, setShowPwd, showPwd2, setShowPwd2, busy }: {
  onRegister: (payload: {
    auth_id: string;
    username: string;
    department: string;
    password: string;
    confirmPassword: string;
  }) => void;
  showPwd: boolean; setShowPwd: (v: boolean) => void;
  showPwd2: boolean; setShowPwd2: (v: boolean) => void;
  busy: boolean;
}) {
  const [username, setUsername] = useState("");
  const [authId, setAuthId] = useState("");
  const [department, setDepartment] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  return (
    <>
      <Field icon={<UserCircle className="h-4 w-4" />} placeholder="姓名" type="text" value={username} onChange={setUsername} />
      <Field icon={<User className="h-4 w-4" />} placeholder="统一认证号" type="text" value={authId} onChange={setAuthId} />
      <Field icon={<Building2 className="h-4 w-4" />} placeholder="所属部门" type="text" value={department} onChange={setDepartment} />
      <div className="relative">
        <Field icon={<Lock className="h-4 w-4" />} placeholder="设置密码" type={showPwd ? "text" : "password"} value={password} onChange={setPassword} />
        <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--ink-400)" }}>
          {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      <div className="relative">
        <Field icon={<Lock className="h-4 w-4" />} placeholder="确认密码" type={showPwd2 ? "text" : "password"} value={confirmPassword} onChange={setConfirmPassword} />
        <button type="button" onClick={() => setShowPwd2(!showPwd2)} className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--ink-400)" }}>
          {showPwd2 ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      <PrimaryBtn
        onClick={() => onRegister({ auth_id: authId, username, department, password, confirmPassword })}
        disabled={busy || !username || !authId || !department || !password || !confirmPassword}
      >
        注册并登录
      </PrimaryBtn>
    </>
  );
}

/* ── Forgot ── */
function ForgotForm({ onLogin, busy }: { onLogin: (authId: string, password: string) => void; busy: boolean }) {
  const [showPwd, setShowPwd] = useState(false);
  const [authId, setAuthId] = useState("");
  const [password, setPassword] = useState("");
  return (
    <>
      <Field icon={<User className="h-4 w-4" />} placeholder="统一认证号" type="text" value={authId} onChange={setAuthId} />
      <Field icon={<Key className="h-4 w-4" />} placeholder="管理员提供的验证码" type="text" />
      <div className="relative">
        <Field icon={<Lock className="h-4 w-4" />} placeholder="新密码" type={showPwd ? "text" : "password"} value={password} onChange={setPassword} />
        <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--ink-400)" }}>
          {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      <PrimaryBtn onClick={() => onLogin(authId, password)} disabled={busy || !authId || !password}>重置密码</PrimaryBtn>
    </>
  );
}

/* ── Shared sub-components ── */
function Field({
  icon,
  placeholder,
  type,
  value,
  onChange,
}: {
  icon: React.ReactNode;
  placeholder: string;
  type: string;
  value?: string;
  onChange?: (value: string) => void;
}) {
  return (
    <div
      className="flex items-center gap-2.5 h-11 px-3.5 rounded-xl"
      style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
    >
      <span style={{ color: "var(--ink-400)", flexShrink: 0 }}>{icon}</span>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="flex-1 bg-transparent outline-none text-[13.5px]"
        style={{ color: "var(--ink-900)" }}
      />
    </div>
  );
}

function PrimaryBtn({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full h-11 rounded-xl flex items-center justify-center transition active:scale-[0.99]"
      style={{ background: "var(--ink-900)", color: "#fff", fontWeight: 600, fontSize: "14px", opacity: disabled ? 0.55 : 1 }}
    >
      {children}
    </button>
  );
}
