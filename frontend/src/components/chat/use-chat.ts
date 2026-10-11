import { useCallback, useRef, useState } from 'react';
import { streamChat } from '@/lib/chat-stream';
import type { ChatMessage } from '@/lib/types';

export function useChat(projectId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const threadId = useRef<string | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
        citations: [],
        cards: [],
        grounded: null,
      };
      const assistantId = crypto.randomUUID();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        citations: [],
        cards: [],
        grounded: null,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);
      setStage('routing');

      const controller = new AbortController();
      abortRef.current = controller;

      const patchAssistant = (patch: Partial<ChatMessage> | ((m: ChatMessage) => ChatMessage)) => {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantId) return m;
            return typeof patch === 'function' ? patch(m) : { ...m, ...patch };
          }),
        );
      };

      try {
        for await (const frame of streamChat(projectId, { message: text, thread_id: threadId.current }, controller.signal)) {
          switch (frame.type) {
            case 'thread':
              threadId.current = frame.thread_id;
              break;
            case 'status':
              setStage(frame.stage);
              break;
            case 'token':
              patchAssistant((m) => ({ ...m, content: m.content + frame.text }));
              break;
            case 'replace':
              patchAssistant({ content: frame.text });
              break;
            case 'card':
              patchAssistant((m) => ({ ...m, cards: [...m.cards, frame.card] }));
              break;
            case 'citations':
              patchAssistant({ citations: frame.citations, grounded: frame.grounded });
              break;
            case 'error':
              patchAssistant((m) => ({ ...m, cards: [...m.cards, { type: 'error', message: frame.message }] }));
              break;
            case 'done':
              patchAssistant((m) => ({ ...m, grounded: frame.grounded }));
              break;
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          patchAssistant((m) => ({ ...m, cards: [...m.cards, { type: 'error', message: 'Connection to the chat stream was lost.' }] }));
        }
      } finally {
        setIsStreaming(false);
        setStage(null);
      }
    },
    [projectId],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, stage, isStreaming, sendMessage, stop };
}
