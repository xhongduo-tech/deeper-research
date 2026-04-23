import React from 'react';

interface State {
  hasError: boolean;
  error?: Error;
}

interface Props {
  children: React.ReactNode;
  /** Optional custom renderer for the error state. */
  fallback?: (err: Error, reset: () => void) => React.ReactNode;
  /** Section name for the default fallback heading. */
  label?: string;
}

/**
 * Generic error boundary. We ship it at the page level so a crash in one
 * screen (e.g. a map/filter over undefined on an older browser) never leaves
 * the user staring at a blank panel.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', this.props.label || '', error, info);
  }

  reset = () => this.setState({ hasError: false, error: undefined });

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return (
        <div className="mx-auto my-10 max-w-xl rounded-lg border border-line-subtle bg-elevated p-6 text-sm">
          <p className="mb-2 text-base font-semibold text-ink-1">
            {this.props.label || '页面'}加载失败
          </p>
          <p className="mb-3 text-ink-2">
            系统在渲染该页面时遇到了错误。你可以点击下方按钮重试，如果问题持续，
            请刷新整个页面或切换到较新版本的浏览器（Chrome / Edge / Safari）。
          </p>
          <pre className="mb-3 max-h-40 overflow-auto rounded bg-sunken p-2 text-[11px] text-ink-3">
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={this.reset}
            className="rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-ink-inverse hover:opacity-90"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
