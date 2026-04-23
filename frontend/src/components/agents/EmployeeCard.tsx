import React, { useMemo, useState } from 'react';
import { Check, RotateCw } from 'lucide-react';
import type { Employee, AgentStatus } from '../../types';
import { EMPLOYEE_CATEGORIES } from '../../utils/constants';
import { truncateText } from '../../utils/formatters';

interface EmployeeCardProps {
  employee: Employee;
  status?: AgentStatus;
  compact?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  index?: number;
  /** 是否渲染挂绳（在 Grid 顶部会有大量重复挂绳，建议仅在 hero/焦点展示处 true） */
  showLanyard?: boolean;
}

/* ============================================================================
 * 员工身份牌（dataagent）
 *
 * - 正面：名牌条 + 艺术化头像 + 英文 Role + tagline + 品牌 + 角色说明按钮
 * - 点击「角色说明」后，整张卡片沿 Y 轴翻转 180°，背面展示完整描述、技能、模型等
 * - 背面有「返回」按钮，再次翻回正面
 *
 * 头像不再是 1×1 像素点阵，改为彩色渐变底 + 几何卡通头像（头发/脸/面部特征），
 * 风格接近现代 Notion 头像表情（flat + soft gradient），按 seed 生成稳定但多样。
 * ==========================================================================*/

// ---- 稳定 hash ----
function hash(seed: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function pickFrom<T>(arr: T[], h: number, salt: number): T {
  // JS `%` preserves the sign, so `(h ^ salt) % len` can be negative.
  // Normalize it to a valid array index; otherwise avatar specs can end up
  // with `undefined` fields and crash in older/minified builds.
  const raw = (h ^ salt) >>> 0;
  return arr[raw % arr.length];
}

/* ============================================================================
 * 新头像：彩色渐变底 + 几何卡通人物
 * ==========================================================================*/

const BG_GRADIENTS: [string, string][] = [
  ['#ffd6a5', '#ff8fab'],
  ['#bde0fe', '#a2d2ff'],
  ['#caffbf', '#9bf6ff'],
  ['#fdffb6', '#ffc6ff'],
  ['#e0c3fc', '#8ec5fc'],
  ['#f9c6c9', '#f3e8ff'],
  ['#ffadad', '#ffd6a5'],
  ['#b5ead7', '#c7ceea'],
  ['#ffc8dd', '#bde0fe'],
  ['#fec89a', '#ffb5a7'],
  ['#dec0f1', '#b3cde0'],
  ['#fbb4a5', '#fdf0d5'],
];

const SKIN_TONES = [
  '#f5d0a9', // light
  '#ecc091', // peach
  '#d5a377', // tan
  '#b07d56', // medium
  '#8d5524', // deep
  '#6b3e1f', // dark
];

const HAIR_COLORS = [
  '#0f0f0f',
  '#2b1d14',
  '#4a2e1a',
  '#6b4226',
  '#8a5a2a',
  '#b27a3c',
  '#c89a57',
  '#d9a96e',
  '#7d5a3a',
  '#e6b86a', // blonde
  '#b94f3f', // auburn
  '#5a2e2e', // burgundy
];

const ACCENT_COLORS = [
  '#e63946',
  '#ff6b6b',
  '#ffb703',
  '#fb8500',
  '#06a77d',
  '#118ab2',
  '#7209b7',
  '#3a86ff',
  '#ef476f',
  '#06d6a0',
];

type HairStyle =
  | 'short'
  | 'longStraight'
  | 'curly'
  | 'bun'
  | 'afro'
  | 'buzz'
  | 'ponytail'
  | 'sideSwept'
  | 'pixie';

type Accessory = 'none' | 'glasses' | 'headphones' | 'earrings' | 'beret';

interface AvatarSpec {
  bg: [string, string];
  skin: string;
  hairColor: string;
  hairStyle: HairStyle;
  accessory: Accessory;
  accent: string;
  hasBeard: boolean;
  smile: 'small' | 'grin' | 'neutral';
  browTilt: number; // -2..2
}

function generateSpec(seed: string): AvatarSpec {
  const h = hash(seed);
  return {
    bg: pickFrom(BG_GRADIENTS, h, 0x9e37),
    skin: pickFrom(SKIN_TONES, h, 0x12ab),
    hairColor: pickFrom(HAIR_COLORS, h, 0x71c3),
    hairStyle: pickFrom<HairStyle>(
      [
        'short',
        'longStraight',
        'curly',
        'bun',
        'afro',
        'buzz',
        'ponytail',
        'sideSwept',
        'pixie',
      ],
      h,
      0x4413,
    ),
    accessory: pickFrom<Accessory>(
      ['none', 'none', 'glasses', 'headphones', 'earrings', 'beret'],
      h,
      0x8810,
    ),
    accent: pickFrom(ACCENT_COLORS, h, 0x55aa),
    hasBeard: ((h >> 17) & 7) === 0, // ~1/8
    smile: pickFrom<'small' | 'grin' | 'neutral'>(
      ['small', 'grin', 'neutral', 'small', 'grin'],
      h,
      0x1f1f,
    ),
    browTilt: (((h >> 13) & 3) as number) - 1,
  };
}

/** 根据 hair style 返回一组 SVG path / shape 的描述（相对 100x100 viewBox） */
function renderHair(style: HairStyle, hairColor: string) {
  switch (style) {
    case 'short':
      return (
        <path
          d="M25 45 Q25 20 50 18 Q75 20 75 45 L75 40 Q70 30 50 28 Q30 30 25 40 Z"
          fill={hairColor}
        />
      );
    case 'longStraight':
      return (
        <>
          <path
            d="M22 48 Q22 18 50 16 Q78 18 78 48 L78 78 Q75 80 73 78 L73 50 Q70 40 50 38 Q30 40 27 50 L27 78 Q25 80 22 78 Z"
            fill={hairColor}
          />
        </>
      );
    case 'curly':
      return (
        <>
          <circle cx="32" cy="32" r="10" fill={hairColor} />
          <circle cx="45" cy="22" r="11" fill={hairColor} />
          <circle cx="60" cy="24" r="10" fill={hairColor} />
          <circle cx="70" cy="35" r="9" fill={hairColor} />
          <circle cx="28" cy="44" r="8" fill={hairColor} />
          <circle cx="72" cy="46" r="8" fill={hairColor} />
        </>
      );
    case 'bun':
      return (
        <>
          <circle cx="50" cy="12" r="8" fill={hairColor} />
          <path d="M27 42 Q27 22 50 20 Q73 22 73 42 Z" fill={hairColor} />
        </>
      );
    case 'afro':
      return (
        <ellipse
          cx="50"
          cy="30"
          rx="30"
          ry="22"
          fill={hairColor}
        />
      );
    case 'buzz':
      return (
        <path
          d="M28 42 Q28 26 50 24 Q72 26 72 42 Q72 36 50 34 Q28 36 28 42 Z"
          fill={hairColor}
          opacity="0.82"
        />
      );
    case 'ponytail':
      return (
        <>
          <path
            d="M27 45 Q27 20 50 18 Q73 20 73 45 L73 40 Q70 30 50 28 Q30 30 27 40 Z"
            fill={hairColor}
          />
          <path
            d="M73 38 Q85 42 84 58 Q82 64 76 60 L76 48 Q75 42 73 40 Z"
            fill={hairColor}
          />
        </>
      );
    case 'sideSwept':
      return (
        <path
          d="M24 44 Q22 22 45 18 Q68 16 78 34 Q66 28 44 32 Q30 34 27 44 Z"
          fill={hairColor}
        />
      );
    case 'pixie':
      return (
        <>
          <path
            d="M27 42 Q27 22 50 20 Q73 22 73 42 L70 44 Q68 32 50 32 Q32 32 30 44 Z"
            fill={hairColor}
          />
          <path
            d="M32 28 Q42 20 55 24"
            stroke={hairColor}
            strokeWidth="3"
            fill="none"
            strokeLinecap="round"
          />
        </>
      );
  }
}

function renderAccessory(acc: Accessory, accent: string) {
  switch (acc) {
    case 'glasses':
      return (
        <g stroke="#1a1a1a" strokeWidth="1.4" fill="none">
          <circle cx="40" cy="54" r="6" fill="rgba(255,255,255,0.25)" />
          <circle cx="60" cy="54" r="6" fill="rgba(255,255,255,0.25)" />
          <path d="M46 54 L54 54" />
        </g>
      );
    case 'headphones':
      return (
        <g fill={accent}>
          <path
            d="M23 40 Q23 20 50 18 Q77 20 77 40"
            stroke={accent}
            strokeWidth="4"
            fill="none"
            strokeLinecap="round"
          />
          <rect x="19" y="38" width="8" height="14" rx="3" />
          <rect x="73" y="38" width="8" height="14" rx="3" />
        </g>
      );
    case 'earrings':
      return (
        <>
          <circle cx="24" cy="62" r="2.4" fill={accent} />
          <circle cx="76" cy="62" r="2.4" fill={accent} />
        </>
      );
    case 'beret':
      return (
        <g>
          <ellipse cx="50" cy="22" rx="26" ry="9" fill={accent} />
          <circle cx="66" cy="17" r="4" fill={accent} />
        </g>
      );
    default:
      return null;
  }
}

function renderMouth(
  smile: 'small' | 'grin' | 'neutral',
  accent: string,
) {
  if (smile === 'grin') {
    return (
      <path
        d="M42 68 Q50 76 58 68"
        stroke="#1a1a1a"
        strokeWidth="1.8"
        fill={accent}
        fillOpacity="0.35"
        strokeLinecap="round"
      />
    );
  }
  if (smile === 'small') {
    return (
      <path
        d="M44 68 Q50 72 56 68"
        stroke="#1a1a1a"
        strokeWidth="1.7"
        fill="none"
        strokeLinecap="round"
      />
    );
  }
  return (
    <line
      x1="45"
      y1="69"
      x2="55"
      y2="69"
      stroke="#1a1a1a"
      strokeWidth="1.7"
      strokeLinecap="round"
    />
  );
}

const Avatar: React.FC<{ seed: string; size?: number }> = ({
  seed,
  size = 96,
}) => {
  const spec = useMemo(() => generateSpec(seed), [seed]);
  const gradId = useMemo(() => `g-${Math.abs(hash(seed))}`, [seed]);

  return (
    <div
      className="relative overflow-hidden rounded-[14px]"
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={spec.bg[0]} />
            <stop offset="100%" stopColor={spec.bg[1]} />
          </linearGradient>
        </defs>

        {/* Background */}
        <rect width="100" height="100" fill={`url(#${gradId})`} />
        {/* Soft highlight */}
        <ellipse
          cx="30"
          cy="20"
          rx="28"
          ry="14"
          fill="rgba(255,255,255,0.22)"
        />

        {/* Shoulders / body base */}
        <path
          d="M10 100 Q10 78 30 74 Q50 80 70 74 Q90 78 90 100 Z"
          fill={spec.accent}
          opacity="0.88"
        />
        {/* Neck */}
        <rect x="44" y="68" width="12" height="10" fill={spec.skin} />

        {/* Face */}
        <ellipse cx="50" cy="52" rx="20" ry="22" fill={spec.skin} />

        {/* Ears */}
        <ellipse cx="28" cy="54" rx="3" ry="5" fill={spec.skin} />
        <ellipse cx="72" cy="54" rx="3" ry="5" fill={spec.skin} />

        {/* Hair */}
        {renderHair(spec.hairStyle, spec.hairColor)}

        {/* Brows */}
        <path
          d={`M38 45 L46 ${45 + spec.browTilt}`}
          stroke="#1a1a1a"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d={`M54 ${45 + spec.browTilt} L62 45`}
          stroke="#1a1a1a"
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* Eyes */}
        <circle cx="42" cy="54" r="2" fill="#1a1a1a" />
        <circle cx="58" cy="54" r="2" fill="#1a1a1a" />
        <circle cx="42.8" cy="53.2" r="0.6" fill="#fff" />
        <circle cx="58.8" cy="53.2" r="0.6" fill="#fff" />

        {/* Cheeks */}
        <circle cx="38" cy="62" r="3" fill="#ff8a93" opacity="0.35" />
        <circle cx="62" cy="62" r="3" fill="#ff8a93" opacity="0.35" />

        {/* Mouth */}
        {renderMouth(spec.smile, spec.accent)}

        {/* Beard (optional) */}
        {spec.hasBeard && (
          <path
            d="M38 68 Q50 78 62 68 Q60 74 50 76 Q40 74 38 68 Z"
            fill={spec.hairColor}
            opacity="0.85"
          />
        )}

        {/* Accessory on top */}
        {renderAccessory(spec.accessory, spec.accent)}
      </svg>
    </div>
  );
};

/* ============================================================================
 * 派生英文名 / role / tagline
 * ==========================================================================*/

const NAME_POOL = [
  'Allen', 'Reid', 'Quinne', 'Searle', 'Fayer', 'Adam', 'Stigler', 'Nash',
  'Kai', 'Eno', 'Luca', 'Orin', 'Remi', 'Silas', 'Vera', 'Wren', 'Yuki',
  'Zane', 'Cyrus', 'Dara', 'Elio', 'Ford', 'Gale', 'Hart', 'Ivo', 'Joss',
  'Knox', 'Lior', 'Milo', 'Niko',
];

function deriveFirstName(employee: Employee): string {
  const en = (employee.name_en || '').trim();
  if (en) {
    const jobWords = /researcher|writer|analyst|engineer|designer|strategist|expert|specialist|lead|manager/i;
    if (!jobWords.test(en)) {
      const first = en.split(/\s+/)[0];
      if (/^[A-Za-z]{2,}$/.test(first)) {
        return first;
      }
    }
  }
  const idx = hash(employee.id) % NAME_POOL.length;
  return NAME_POOL[idx];
}

const CATEGORY_TO_ROLE: Record<string, string> = {
  research: 'Researcher',
  writing: 'Writer',
  data: 'Data Analyst',
  code: 'Engineer',
  design: 'Designer',
  strategy: 'Strategist',
  legal: 'Counsel',
  finance: 'Analyst',
  marketing: 'Marketer',
  hr: 'People Ops',
  operations: 'Operator',
  tech: 'Engineer',
};

function deriveRoleTitle(employee: Employee): string {
  const en = (employee.name_en || '').trim();
  const jobWords = /researcher|writer|analyst|engineer|designer|strategist|expert|specialist|lead|manager|counsel|operator|marketer/i;
  if (en && jobWords.test(en)) return en;
  const role = CATEGORY_TO_ROLE[employee.category] || 'Specialist';
  const surname = employee.name || en || '';
  return surname ? `${role} ${surname}` : role;
}

function deriveTagline(employee: Employee): string {
  const d = (employee.description || '').trim();
  if (d) {
    const clean = d
      .replace(/[。\.]+$/, '')
      .replace(/^["「『]|["」』]$/g, '');
    return truncateText(clean, 64);
  }
  const cat = EMPLOYEE_CATEGORIES[employee.category] || 'Specialist';
  return `Professional ${cat}`;
}

/* ============================================================================
 * 挂绳
 * ==========================================================================*/

const Lanyard: React.FC = () => (
  <div className="pointer-events-none mx-auto flex h-16 w-[70px] flex-col items-center">
    <div
      className="relative h-10 w-6 bg-[#111]"
      style={{
        backgroundImage:
          'repeating-linear-gradient(90deg, transparent 0 2px, rgba(255,255,255,0.12) 2px 3px, transparent 3px 6px)',
      }}
    />
    <div className="flex h-5 w-9 items-center justify-center">
      <div className="h-4 w-8 rounded-full border-[2px] border-[#111] bg-[#f3f1ec]" />
    </div>
    <div className="h-2 w-3 bg-[#111]" />
    <div className="h-[3px] w-6 rounded-b-sm bg-white shadow" />
  </div>
);

/* ============================================================================
 * 主组件 —— 支持翻转动画
 * ==========================================================================*/

const CARD_SHADOW = 'var(--id-card-shadow)';
const CARD_BG     = 'var(--id-card-bg)';

/**
 * Some enterprise browsers (IE11, older Android WebView, Edge Legacy)
 * mis-render 3D flips. Detect `preserve-3d` support once; if unavailable we
 * fall back to a simple cross-fade between the two faces, which looks fine
 * and crucially never leaves the user staring at the back-of-card.
 */
function supportsPreserve3D(): boolean {
  if (typeof window === 'undefined' || typeof CSS === 'undefined' || !CSS.supports) {
    return false;
  }
  try {
    return (
      CSS.supports('transform-style', 'preserve-3d') ||
      CSS.supports('-webkit-transform-style', 'preserve-3d')
    );
  } catch {
    return false;
  }
}

export const EmployeeCard: React.FC<EmployeeCardProps> = ({
  employee,
  status,
  compact = false,
  selectable = false,
  selected = false,
  onSelect,
  index: _index,
  showLanyard = false,
}) => {
  const [flipped, setFlipped] = useState(false);
  const canFlip = useMemo(() => supportsPreserve3D(), []);

  const agentStatus = status?.status || 'idle';
  const isActive = agentStatus === 'running';
  const isCompleted = agentStatus === 'completed';
  const isFailed = agentStatus === 'failed';

  const firstName = deriveFirstName(employee);
  const roleTitle = deriveRoleTitle(employee);
  const tagline = deriveTagline(employee);
  const portraitSeed = employee.id + ':' + firstName;

  /* ============================== compact 版 ============================== */
  if (compact) {
    return (
      <button
        type="button"
        onClick={selectable ? onSelect : undefined}
        className={[
          'group flex w-full items-center gap-3 rounded-xl border bg-elevated px-3 py-2.5 text-left transition-all',
          selectable ? 'cursor-pointer hover:border-line-strong' : '',
          selected
            ? 'border-brand shadow-[0_0_0_3px_var(--color-brand-ring)]'
            : 'border-line-subtle',
        ].join(' ')}
      >
        <div className="flex-shrink-0">
          <Avatar seed={portraitSeed} size={36} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[13.5px] font-semibold text-ink-1">
              {roleTitle}
            </span>
            <span className="rounded bg-[#141414] px-1.5 py-0.5 font-mono text-[10px] text-white">
              {firstName}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px]">
            <span
              className={[
                'h-1.5 w-1.5 flex-shrink-0 rounded-full',
                isActive && 'bg-[#22c55e] animate-pulse',
                isCompleted && 'bg-success',
                isFailed && 'bg-danger',
                !isActive && !isCompleted && !isFailed && 'bg-ink-4',
              ]
                .filter(Boolean)
                .join(' ')}
            />
            <span className="truncate text-ink-3">
              {isActive && status?.last_message
                ? truncateText(status.last_message, 42)
                : tagline}
            </span>
          </div>
        </div>
        {selectable && (
          <span
            className={[
              'flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md border transition-colors',
              selected
                ? 'border-brand bg-brand text-ink-inverse'
                : 'border-line group-hover:border-line-strong',
            ].join(' ')}
          >
            {selected && <Check size={12} />}
          </span>
        )}
      </button>
    );
  }

  /* ============================== 完整身份牌（带翻转） ============================== */
  return (
    <div
      className={selectable ? 'cursor-pointer' : undefined}
      onClick={selectable ? onSelect : undefined}
      style={{ perspective: 1400 }}
    >
      {showLanyard && <Lanyard />}

      <div
        className="relative aspect-[3/4] w-full"
        style={
          canFlip
            ? ({
                minHeight: '380px',
                transformStyle: 'preserve-3d',
                WebkitTransformStyle: 'preserve-3d',
                transform: `rotateY(${flipped ? 180 : 0}deg)`,
                WebkitTransform: `rotateY(${flipped ? 180 : 0}deg)`,
                transition:
                  'transform 0.55s cubic-bezier(0.2, 0.85, 0.3, 1.05)',
                WebkitTransition:
                  '-webkit-transform 0.55s cubic-bezier(0.2, 0.85, 0.3, 1.05)',
              } as React.CSSProperties)
            : { minHeight: '380px' }
        }
      >
        {/* -------- FRONT -------- */}
        <div
          className={[
            'absolute inset-0 flex flex-col overflow-hidden rounded-[22px] transition-shadow',
            selected ? 'ring-2 ring-brand ring-offset-2 ring-offset-canvas' : '',
          ].join(' ')}
          style={{
            background: CARD_BG,
            boxShadow: selected ? undefined : CARD_SHADOW,
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            // Fallback for browsers without preserve-3d: cross-fade by opacity.
            opacity: canFlip ? 1 : flipped ? 0 : 1,
            visibility: canFlip ? 'visible' : flipped ? 'hidden' : 'visible',
            transition: canFlip ? undefined : 'opacity 0.35s ease',
          }}
        >
          {/* 顶部名牌条 */}
          <div className="px-5 pt-5">
            <div
              className="flex h-9 items-center rounded-lg px-3.5"
              style={{ background: 'var(--id-card-name-bg)' }}
            >
              <span
                className="truncate text-[14px] font-semibold tracking-[0.01em]"
                style={{ color: 'var(--id-card-name-text)' }}
              >
                {firstName}
              </span>
            </div>
          </div>

          {/* 状态胶囊 */}
          {(isActive || isCompleted || isFailed) && (
            <span
              className="absolute right-4 top-[68px] flex items-center gap-1 rounded-full bg-white px-2 py-[3px] text-[10px] font-medium shadow-sm"
              style={{ zIndex: 2 }}
            >
              <span
                className={[
                  'h-1.5 w-1.5 rounded-full',
                  isActive && 'bg-[#22c55e] animate-pulse',
                  isCompleted && 'bg-success',
                  isFailed && 'bg-danger',
                ]
                  .filter(Boolean)
                  .join(' ')}
              />
              <span
                className={[
                  isActive ? 'text-ink-1' : '',
                  isCompleted ? 'text-success' : '',
                  isFailed ? 'text-danger' : '',
                ].join(' ')}
              >
                {isActive ? 'Running' : isCompleted ? 'Done' : 'Failed'}
              </span>
            </span>
          )}

          {/* 头像 */}
          <div className="mt-5 px-5">
            <Avatar seed={portraitSeed} size={96} />
          </div>

          {/* role title + tagline */}
          <div className="mt-4 px-5">
            <h3
              className="text-[17px] font-semibold leading-snug"
              style={{ color: 'var(--id-card-text)' }}
            >
              {roleTitle}
            </h3>
            <p
              className="mt-1.5 line-clamp-2 min-h-[38px] text-[13px] leading-[1.45]"
              style={{ color: 'var(--id-card-sub)' }}
            >
              {tagline}
            </p>
          </div>

          {/* 进度条 */}
          {isActive && typeof status?.progress === 'number' && (
            <div className="mx-5 mt-2">
              <div className="h-[2px] overflow-hidden rounded-full bg-black/10">
                <div
                  className="h-full rounded-full bg-[#22c55e] transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max(0, status.progress))}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* 底部 */}
          <div className="mt-auto px-5 pb-5">
            <div
              className="mb-4 h-px w-full"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(90deg, #b9b6ae 0 4px, transparent 4px 8px)',
              }}
            />
            <div className="flex items-center justify-between">
              <span
                className="font-sans text-[13px] font-bold tracking-[0.08em]"
                style={{ color: 'var(--id-card-text)' }}
              >
                data<span className="text-brand">agent</span>
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFlipped(true);
                }}
                className="rounded-full px-3.5 py-1.5 text-[11.5px] font-medium transition-all active:scale-95"
                style={{
                  background: 'var(--id-card-name-bg)',
                  color: 'var(--id-card-name-text)',
                }}
              >
                角色说明
              </button>
            </div>
          </div>

          {selectable && selected && (
            <span className="absolute left-4 top-[68px] flex h-6 w-6 items-center justify-center rounded-full bg-brand text-ink-inverse shadow-md">
              <Check size={14} strokeWidth={3} />
            </span>
          )}
        </div>

        {/* -------- BACK -------- */}
        <div
          className="absolute inset-0 flex flex-col overflow-hidden rounded-[22px]"
          style={{
            background: CARD_BG,
            boxShadow: CARD_SHADOW,
            transform: canFlip ? 'rotateY(180deg)' : undefined,
            WebkitTransform: canFlip ? 'rotateY(180deg)' : undefined,
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            opacity: canFlip ? 1 : flipped ? 1 : 0,
            visibility: canFlip ? 'visible' : flipped ? 'visible' : 'hidden',
            transition: canFlip ? undefined : 'opacity 0.35s ease',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between border-b border-line-subtle/60 px-5 pb-3 pt-5">
            <div className="min-w-0">
              <p className="text-[10.5px] font-medium uppercase tracking-wider text-ink-4">
                Role · {firstName}
              </p>
              <h4
                className="truncate text-[15px] font-semibold"
                style={{ color: 'var(--id-card-text)' }}
              >
                {roleTitle}
              </h4>
              <p className="mt-0.5 text-[11.5px] text-ink-3">
                {employee.name}
                {employee.category
                  ? ` · ${EMPLOYEE_CATEGORIES[employee.category] || employee.category}`
                  : ''}
              </p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setFlipped(false);
              }}
              aria-label="返回"
              title="返回"
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full transition-all active:scale-95"
              style={{
                background: 'var(--id-card-name-bg)',
                color: 'var(--id-card-name-text)',
              }}
            >
              <RotateCw size={14} />
            </button>
          </div>

          <div className="custom-scrollbar flex-1 overflow-y-auto px-5 py-3">
            <p
              className="whitespace-pre-wrap text-[12.5px] leading-relaxed"
              style={{ color: 'var(--id-card-sub)' }}
            >
              {employee.description || tagline}
            </p>

            {employee.skills && employee.skills.length > 0 && (
              <div className="mt-4">
                <p className="mb-1.5 text-[10.5px] font-medium uppercase tracking-wider text-ink-4">
                  Skills
                </p>
                <div className="flex flex-wrap gap-1">
                  {employee.skills.slice(0, 12).map((skill) => (
                    <span
                      key={skill}
                      className="rounded border border-line-subtle px-1.5 py-0.5 text-[10.5px]"
                      style={{
                        background: 'var(--id-card-skill-bg)',
                        color: 'var(--id-card-sub)',
                      }}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {employee.default_model && (
              <div
                className="mt-4 flex items-center gap-1.5 text-[10.5px]"
                style={{ color: 'var(--id-card-sub)' }}
              >
                <span>Model:</span>
                <code
                  className="rounded px-1.5 py-0.5 font-mono"
                  style={{
                    background: 'var(--id-card-skill-bg)',
                    color: 'var(--id-card-sub)',
                  }}
                >
                  {employee.default_model}
                </code>
              </div>
            )}
          </div>

          <div className="border-t border-line-subtle/60 px-5 py-3">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setFlipped(false);
              }}
              className="w-full rounded-full py-1.5 text-[11.5px] font-medium transition-all active:scale-95"
              style={{
                background: 'var(--id-card-name-bg)',
                color: 'var(--id-card-name-text)',
              }}
            >
              返回
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmployeeCard;
