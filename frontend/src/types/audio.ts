// 定义音频队列项的接口
export interface AudioQueueItem {
  data: string;
  onComplete: (value: void | PromiseLike<void>) => void;
}

export interface AudioContextType {
  queueAndPlayAudio: (audioBase64: string) => Promise<void>
  resetAudioState: () => Promise<void>
}