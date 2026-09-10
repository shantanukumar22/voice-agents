/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_STAFF_TOKEN?: string;
  readonly VITE_STAFF_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
