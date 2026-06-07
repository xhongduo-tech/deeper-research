/**
 * PostCSS — 内网兼容性降级流水线
 *
 * 目标浏览器: Chrome 58+, Edge 18+, Firefox 57+, Safari 11+, iOS 11+
 *
 * 处理顺序（Vite 先跑 Tailwind v4，PostCSS 再处理输出 CSS）：
 *   1. postcss-logical          — CSS 逻辑属性 → 物理属性回退（关键！）
 *                                 Tailwind v4 把间距工具类编译为 padding-inline/
 *                                 margin-inline-start 等逻辑属性（91 处）
 *                                 Chrome 87 以下完全不认识，导致全局间距消失
 *   2. postcss-oklab-function   — oklch()/oklab()/lch()/lab() → sRGB 回退
 *   3. postcss-color-mix-function — color-mix() 静态计算 → sRGB 回退
 *   4. autoprefixer             — 补全 -webkit-/-ms- 厂商前缀
 *
 * preserve:true 策略：同时保留现代语法（@supports 包裹），
 * 新浏览器仍用精准值，旧浏览器回退到物理属性/sRGB 近似值。
 */

// postcss-logical 用 CJS 构建加载，避免 Vite jiti 不支持字符串导出名的问题
import { createRequire } from 'module'
const _require = createRequire(import.meta.url)
const postcssLogical = _require('postcss-logical')

import postcssOklabFunction from '@csstools/postcss-oklab-function'
import postcssColorMixFunction from '@csstools/postcss-color-mix-function'
import autoprefixer from 'autoprefixer'

const browserTargets = [
  'Chrome >= 58',
  'Edge >= 18',
  'Firefox >= 57',
  'Safari >= 11',
  'iOS >= 11',
]

export default {
  plugins: [
    // Step 1: CSS 逻辑属性 → 物理属性（LTR 布局，内网中文平台）
    // Tailwind v4 将 px-N/pl-N/mx-N/ml-N 等编译为 padding-inline/margin-inline-start
    // Chrome 87 以下不支持这些逻辑属性，导致全局间距消失（91 处）
    // postcss-logical 将其还原为 padding-left/margin-left 等物理属性
    postcssLogical({ dir: 'ltr' }),

    // Step 2: oklch()/oklab() → rgb() fallback
    postcssOklabFunction({ preserve: true }),

    // Step 3: color-mix() 静态值 → rgb() fallback
    postcssColorMixFunction({ preserve: true }),

    // Step 4: vendor prefixes
    autoprefixer({ overrideBrowserslist: browserTargets }),
  ],
}
