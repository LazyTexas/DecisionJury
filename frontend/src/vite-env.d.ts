/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 开发期置 true 时走纯前端 mock 数据（不依赖后端） */
  readonly VITE_USE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
