import type { ChatCard, ChatCitation } from './types';

export type ChatStreamFrame =
  | { type: 'thread'; thread_id: string; user_message_id: string }
  | { type: 'status'; stage: string; retrieval_mode?: string }
  | { type: 'token'; text: string }
  | { type: 'replace'; text: string }
  | { type: 'card'; card: ChatCard }
  | { type: 'citations'; citations: ChatCitation[]; grounded: boolean }
  | { type: 'error'; message: string }
  | { type: 'done'; message_id: string; grounded: boolean };

export async function* streamChat(
  projectId: string,
  body: { message: string; thread_id?: string },
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamFrame> {
  const res = await fetch(`/api/projects/${projectId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawFrame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const dataLine = rawFrame.split('\n').find((line) => line.startsWith('data:'));
      if (dataLine) {
        const json = dataLine.slice(5).trim();
        if (json) {
          try {
            yield JSON.parse(json) as ChatStreamFrame;
          } catch {
            // ignore malformed frame
          }
        }
      }

      boundary = buffer.indexOf('\n\n');
    }
  }
}
