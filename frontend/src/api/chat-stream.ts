// ============================================================
// SSE 流式聊天客户端
// 后端通过 SSE (Server-Sent Events) 实时推送 LLM 思考过程。
// 当前为 Mock 模式，与真实 SSE 使用相同的回调接口。
// ============================================================

import { CaseStatus } from '../types';

export interface ChatStreamCallbacks {
  onStatusChange?: (status: StreamStatus) => void;
  onReply?: (reply: string) => void;
  onCaseStatusChange?: (status: CaseStatus) => void;
  onMissingFields?: (fields: string[]) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

export type StreamStatus = 'idle' | 'sending' | 'streaming' | 'completed' | 'error';

export function createMockChatStream(
  _caseId: string,
  _content: string,
  callbacks: ChatStreamCallbacks,
): { close: () => void } {
  let cancelled = false;
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const run = async () => {
    callbacks.onStatusChange?.('sending');
    await sleep(400);
    if (cancelled) return;

    callbacks.onStatusChange?.('streaming');
    callbacks.onReply?.('正在分析你的回答…');
    await sleep(600);
    if (cancelled) return;

    callbacks.onReply?.('谢谢，信息已更新。还有其他需要补充的吗？');
    await sleep(300);
    if (cancelled) return;

    callbacks.onDone?.();
    callbacks.onStatusChange?.('completed');
  };

  run();
  return { close: () => { cancelled = true; } };
}
