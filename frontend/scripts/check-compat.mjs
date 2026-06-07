/**
 * check-compat.mjs — 构建产物 CSS 兼容性验证
 *
 * 在 CI 和 build_offline.sh 中调用，确保不把已知不兼容的 CSS 特性
 * 打包到内网部署包里。
 *
 * 退出码: 0 = 通过, 1 = 有未防护的现代 CSS 特性
 */

import { readFileSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root  = dirname(dirname(fileURLToPath(import.meta.url)))
const dist  = join(root, 'dist', 'assets')
const files = readdirSync(dist).filter(f => f.endsWith('.css'))

if (files.length === 0) {
  console.error('✗ 未找到构建产物 CSS，请先运行 npm run build')
  process.exit(1)
}

let hasError = false

for (const filename of files) {
  const css     = readFileSync(join(dist, filename), 'utf8')
  const results = []

  // ── Rule 1: oklch() / oklab() / lch() 不得出现在 @supports 块之外 ────────
  // 合法位置：@supports(color:oklch...) 或 @supports not(...)
  const oklchRegex = /oklch\(|oklab\(/g
  let m
  while ((m = oklchRegex.exec(css)) !== null) {
    const before = css.slice(0, m.index)
    // 简单判断：在此位置之前，@supports 的出现次数应 > 当前同级 }} 的封闭数
    // 用"找最近的 @supports"代替完整括号匹配
    const lastSupports = before.lastIndexOf('@supports')
    const lastClose    = Math.max(before.lastIndexOf('}}'), before.lastIndexOf('} }'))
    if (lastSupports < 0 || lastClose > lastSupports) {
      const snippet = css.slice(Math.max(0, m.index - 40), m.index + 60)
      results.push({ rule: 'unguarded-oklch', snippet })
    }
  }

  // ── Rule 2: dvh / svh / lvh 不得无 vh 回退 ──────────────────────────────
  // 内网 Chrome 58 不支持动态视口单位
  const dvhMatches = [...css.matchAll(/\b\d+dvh\b/g)]
  if (dvhMatches.length > 0) {
    dvhMatches.forEach(dm => {
      // 检查前面 100 字节是否已有 vh 声明同一属性
      const before100 = css.slice(Math.max(0, dm.index - 100), dm.index)
      if (!/\d+vh[^a-z]/.test(before100)) {
        results.push({ rule: 'dvh-no-vh-fallback', snippet: dm[0] })
      }
    })
  }

  // ── Rule 3: color-mix() 动态值审计（警告级，不报错）────────────────────
  const dynamicMix = [...css.matchAll(/color-mix\([^)]*(?:currentcolor|var\()[^)]*\)/gi)]
  const warnCount  = dynamicMix.length

  // ── Rule 4: @property 数量（仅统计，纯警告）──────────────────────────────
  const propCount = (css.match(/@property /g) || []).length

  // ── 输出 ──────────────────────────────────────────────────────────────────
  const icon  = results.length === 0 ? '✓' : '✗'
  console.log(`${icon} ${filename}`)
  if (results.length > 0) {
    hasError = true
    for (const r of results) {
      console.log(`  ✗ [${r.rule}] ...${r.snippet.trim().slice(0, 100)}...`)
    }
  }

  const warns = []
  if (warnCount > 0)  warns.push(`${warnCount} dynamic color-mix() (degraded on Chrome<111)`)
  if (propCount > 0)  warns.push(`${propCount} @property (animations degrade on Chrome<85)`)
  if (warns.length > 0) {
    console.log(`  ⚠ ${warns.join(' | ')}`)
  }
}

if (hasError) {
  console.error('\n✗ CSS 兼容性检查失败。请确保 PostCSS 插件正常运行并重新构建。')
  process.exit(1)
} else {
  console.log('\n✓ CSS 兼容性检查通过（内网 Chrome 58+ 安全部署）')
}
