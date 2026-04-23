import { useEffect, useRef } from 'react';
import { API_BASE_URL, TOKEN_KEY } from '../utils/constants';

export type ReportStreamEvent =
  | { type: 'status'; payload: { status: string; phase: string; progress: number; error_message?: string | null } }
  | { type: 'message'; payload: any }
  | { type: 'clarification'; payload: any }
  | { type: 'timeline'; payload: any }
  | { type: 'section_output'; payload: { section_id: string; output: any } }
  | { type: 'heartbeat' };

/**
 * Subscribe to a report's SSE stream. Uses fetch + ReadableStream because
 * EventSource can't set Authorization headers in the browser.
 *
 * The callback is invoked for every parsed event until the component unmounts
 * or the report id changes.
 */
export function useReportStream(
  reportId: number | null,
  onEvent: (evt: ReportStreamEvent) => void,
) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!reportId) return;
    const controller = new AbortController();

    (async () => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) return;

      try {
        const resp = await fetch(`${API_BASE_URL}/reports/${reportId}/events`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (!resp.ok || !resp.body) {
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by double newlines
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() ?? '';
          for (const chunk of chunks) {
            const line = chunk.split('\n').find((l) => l.startsWith('data: '));
            if (!line) continue;
            const raw = line.slice(6);
            try {
              const evt = JSON.parse(raw) as ReportStreamEvent;
              onEventRef.current(evt);
            } catch {
              // swallow parse errors; server sometimes splits mid-chunk
            }
          }
        }
      } catch {
        // aborts and network hiccups are non-fatal
      }
    })();

    return () => controller.abort();
  }, [reportId]);
}
