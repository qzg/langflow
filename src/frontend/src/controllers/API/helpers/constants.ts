import { BASE_URL_API, BASE_URL_API_V2 } from "../../../constants/constants";

export const URLs = {
  TRANSACTIONS: `monitor/transactions`,
  API_KEY: `api_key`,
  FILES: `files`,
  FILE_MANAGEMENT: `files`,
  VERSION: `version`,
  MESSAGES: `monitor/messages`,
  BUILDS: `monitor/builds`,
  STORE: `store`,
  USERS: "users",
  LOGOUT: `logout`,
  LOGIN: `login`,
  AUTOLOGIN: "auto_login",
  REFRESH: "refresh",
  BUILD: `build`,
  CUSTOM_COMPONENT: `custom_component`,
  FLOWS: `flows`,
  FOLDERS: `projects`,
  PROJECTS: `projects`,
  VARIABLES: `variables`,
  VALIDATE: `validate`,
  CONFIG: `config`,
  STARTER_PROJECTS: `starter-projects`,
  SIDEBAR_CATEGORIES: `sidebar_categories`,
  ALL: `all`,
  VOICE: `voice`,
  PUBLIC_FLOW: `flows/public_flow`,
  MCP: `mcp/project`,
  MCP_SERVERS: `mcp/servers`,
  KNOWLEDGE_BASES: `knowledge_bases`,
  // wasmCloud runtime endpoints
  WASMCLOUD_SETTINGS: `wasmcloud/settings`,
  WASMCLOUD_TEST_CONNECTION: `wasmcloud/test_connection`,
  // wasm component endpoints
  WASM_CAPABILITIES: `wasm/capabilities`,
  WASM_PUBLISH: `wasm/publish`,
  WASM_PARITY: `wasm/parity`,
  WASM_SUGGEST_OCI: `wasm/suggest_oci_ref`,
  WASM_GENERATE_WIT: `wasm/generate_wit`,
  WASM_GENERATE_RUST: `wasm/generate_rust`,
  WASM_BUILD: `wasm/build`,
  WASM_BUILD_START: `wasm/build/start`,
  WASM_EXECUTE_FLOW: `wasm/execute_flow`,
  // AI codegen settings and SSE start
  AI_CODEGEN_SETTINGS: `ai_codegen/settings`,
  WASM_CODEGEN_START: `wasm/generate_rust/start`,
  AI_CODEGEN_WORKSPACES: `ai_codegen/workspaces`,
  COMPONENT_TWINS: `component_twins`,
} as const;

// IMPORTANT: FOLDERS endpoint now points to 'projects' for backward compatibility

export function getURL(
  key: keyof typeof URLs,
  params: any = {},
  v2: boolean = false,
) {
  let url = URLs[key];
  for (const paramKey of Object.keys(params)) {
    url += `/${params[paramKey]}`;
  }
  return `${v2 ? BASE_URL_API_V2 : BASE_URL_API}${url}`;
}

export type URLsType = typeof URLs;
