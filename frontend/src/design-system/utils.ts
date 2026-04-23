/**
 * 轻量 className 合并（不引入 clsx/tailwind-merge 依赖）
 */
export function cn(
  ...inputs: Array<string | number | false | null | undefined>
): string {
  return inputs.filter(Boolean).join(' ');
}
