import React from "react";
import ReactDOM from "react-dom/client";
import { createPortal } from "react-dom";
import { LANGUAGE_OPTIONS, type LanguageOption } from "./languageOptions";
import { getMenuLibrary, type MenuLibraryItem } from "./menuLibrary";
import {
  Activity,
  AlertTriangle,
  Archive,
  BellRing,
  Bot,
  BookOpen,
  Brain,
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CheckCircle2,
  CircleAlert,
  Copy,
  CornerDownRight,
  Database,
  Edit3,
  Eye,
  ExternalLink,
  FilePlus2,
  FileText,
  FolderKanban,
  Globe2,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LoaderCircle,
  LogOut,
  Medal,
  Menu,
  MonitorCog,
  Moon,
  Pause,
  Play,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  SquareCheckBig,
  Star,
  Sun,
  Trash2,
  UserPlus,
  Users,
  X
} from "lucide-react";
import "./styles/global.css";

type Stats = {
  total_tasks: number;
  generated: number;
  awaiting_approve: number;
  scheduled: number;
  published: number;
  errors: number;
  next_publication_at: string | null;
};

type Task = {
  id: string;
  title: string;
  created_by_user_id: string | null;
  created_by_username: string | null;
  site_id: string | null;
  section_id: string | null;
  ai_provider_id: string | null;
  geo: string;
  language: string;
  payload_mode: string;
  topics_count: number;
  target_words: number | null;
  status: string;
  include_toc: boolean;
  include_faq: boolean;
  collect_competitors: boolean;
  include_casino_rating: boolean;
  archived_at: string | null;
  archived_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  prompt_template_name: string | null;
  prompt_template: string | null;
};

type ContentItem = {
  id: string;
  task_id: string;
  site_id: string | null;
  publication_campaign_id: string | null;
  section_id: string | null;
  section_content_mode: "nested" | "menu_page";
  topic: string;
  slug: string;
  status: string;
  word_count: number;
  include_casino_rating: boolean;
  scheduled_at: string | null;
  published_at: string | null;
  published_url: string | null;
  generated_json: Record<string, unknown>;
  generation_prompt_name: string | null;
  generated_at: string | null;
  generation_progress: number;
  generation_error: string | null;
  competitor_research_status: string;
  competitor_research_progress: number;
  competitor_research_error: string | null;
  competitor_brief: CompetitorBrief | null;
  created_at: string;
  updated_at: string;
};

type ProjectPagePreview = {
  title: string;
  slug: string;
  description: string;
  page: Record<string, unknown>;
};

type CompetitorBrief = {
  generated_at?: string;
  search_queries?: string[];
  competitor_urls?: string[];
  competitor_summary?: Array<Record<string, unknown>>;
  common_headings?: string[];
  content_gaps?: string[];
  topics_to_cover?: string[];
  missing_blocks_to_cover?: string[];
  notes?: string[];
};

type CompetitorQuery = {
  id: string;
  content_item_id: string;
  query: string;
  position: number;
  status: string;
  result_count: number;
};

type CompetitorResult = {
  id: string;
  content_item_id: string;
  query_id: string | null;
  query_text: string;
  position: number;
  url: string;
  normalized_url: string;
  title: string | null;
  snippet: string | null;
  source_provider: string;
  status: string;
};

type CompetitorPage = {
  id: string;
  content_item_id: string;
  competitor_result_id: string;
  url: string;
  http_status: number | null;
  title: string | null;
  h1: string | null;
  meta_description: string | null;
  headings: Array<Record<string, unknown>>;
  text_content: string | null;
  tables: unknown[];
  lists: unknown[];
  faq: unknown[];
  word_count: number;
  error_message: string | null;
  fetched_at: string | null;
};

type CompetitorResearch = {
  content_item_id: string;
  status: string;
  progress: number;
  error: string | null;
  brief: CompetitorBrief | null;
  queries: CompetitorQuery[];
  results: CompetitorResult[];
  pages: CompetitorPage[];
};

type Site = {
  id: string;
  name: string;
  base_url: string;
  publication_endpoint: string;
  payload_mode: "simple_page" | "full_site";
  editor_version: string;
  default_menu: Record<string, unknown>;
  menu_library: MenuLibraryItem[];
  default_banners: string[];
  showcase_payload: Record<string, unknown> | null;
  external_project_id: string | null;
  cache_canon: string | null;
  cache_language: string | null;
  cache_geo: string | null;
  homepage_title: string | null;
  internal_pages_count: number;
  domains_count: number;
  cache_domains: string[];
  cache_server_ip: string | null;
  cache_server_host: string | null;
  project_status: "test" | "working" | "not_in_focus" | "duplicate";
  is_test_project: boolean;
  has_menu: boolean;
  cache_synced_at: string | null;
  menu_capabilities_checked_at: string | null;
  header_menu_template_rendered: boolean | null;
  header_menu_rendered: boolean | null;
  header_menu_nested: boolean | null;
  footer_menu_template_rendered: boolean | null;
  footer_menu_rendered: boolean | null;
  footer_menu_nested: boolean | null;
};

type MenuCapabilities = {
  checked_at: string | null;
  header_menu_template_rendered: boolean | null;
  header_menu_rendered: boolean | null;
  header_menu_nested: boolean | null;
  footer_menu_template_rendered: boolean | null;
  footer_menu_rendered: boolean | null;
  footer_menu_nested: boolean | null;
  check_id: string | null;
  check_status: "not_checked" | "queued" | "running" | "completed" | "failed" | string;
  check_error_code: string | null;
  check_error_message: string | null;
};

type MenuVisibilityCheck = {
  id: string;
  site_id: string;
  site_name: string;
  requested_by_username: string | null;
  status: string;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

type MenuTemplate = {
  id: string;
  language: string;
  name: string;
  description: string;
  max_depth: number;
  items: MenuLibraryItem[];
};

type MenuTemplateApplyResult = {
  template_id: string;
  total_count: number;
  created_count: number;
  skipped_count: number;
  updated_count: number;
  sections: Section[];
};

type ProjectCacheItem = {
  external_project_id: string;
  name: string;
  canon: string | null;
  language: string | null;
  geo: string | null;
  homepage_title: string | null;
  internal_pages_count: number;
  domains_count: number;
  domains: string[];
  has_menu: boolean;
  is_working_project: boolean;
};

type ProjectCacheSyncResult = {
  cache_count: number;
  matched_count: number;
  created_count: number;
  updated_count: number;
  confirmed_sections_count: number;
  projects: ProjectCacheItem[];
};

type ProjectChangesSyncResult = {
  success: boolean;
  status_codes: number[];
  last_status_code: number | null;
  results: Array<{ type: "header" | "footer"; status_code: number | null; success: boolean; error?: string }>;
};

type DuplicateSitesDeleteResult = {
  deleted_count: number;
  skipped_count: number;
};

type Section = {
  id: string;
  site_id: string;
  external_id: string;
  name: string;
  path: string;
  menu_type: "header" | "footer";
  parent_id: string | null;
  is_temporary_parent: boolean;
  sync_status: "pending" | "synced" | "external_deleted";
  synced_at: string | null;
  updated_at: string;
};

type AiProvider = {
  id: string;
  name: string;
  provider_type: "custom" | "gemini" | "dataforseo";
  endpoint_url: string;
  model: string;
  prompt_tokens_used: number;
  completion_tokens_used: number;
  total_tokens_used: number;
  last_used_at: string | null;
  validation_status: "unchecked" | "valid" | "invalid" | string;
  validation_message: string | null;
  validated_at: string | null;
  created_at: string;
  is_active: boolean;
};

type PromptTemplate = {
  id: string;
  site_id: string | null;
  name: string;
  content: string;
  is_default: boolean;
  used_by_projects: number;
  generated_texts_count: number;
  created_at: string;
  updated_at: string;
};

type PromptGeneratedContent = {
  id: string;
  task_id: string;
  site_id: string | null;
  site_name: string | null;
  topic: string;
  slug: string;
  status: string;
  word_count: number;
  generation_prompt_name: string | null;
  include_casino_rating: boolean;
  generated_at: string | null;
  updated_at: string;
};

type PublicationContentItem = {
  id: string;
  task_id: string;
  site_id: string;
  topic: string;
  slug: string;
  status: string;
  word_count: number;
  include_casino_rating: boolean;
  generated_at: string | null;
  published_at: string | null;
  updated_at: string;
};

type TaskDetails = {
  task: Task;
  items: ContentItem[];
};

type TopicSuggestionsResponse = {
  topics: string[];
};

type TaskRegenerateAllOptions = {
  prompt_template_name: string;
  prompt_template: string;
  include_toc: boolean;
  include_faq: boolean;
  collect_competitors: boolean;
  include_casino_rating: boolean;
};

type User = {
  id: string;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
};

type Dashboard = {
  stats: Stats;
  active_tasks: Task[];
  publication_queue: ContentItem[];
  recent_errors: Array<{ id: string; error_message: string; endpoint_url: string; created_at: string }>;
};

type SiteOverview = {
  site: {
    id: string;
    name: string;
    base_url: string;
    payload_mode: string;
    publication_endpoint: string;
  };
  stats: {
    tasks: number;
    menu_items: number;
    generated: number;
    approved: number;
    scheduled: number;
    published: number;
    failed: number;
    next_publication_at: string | null;
  };
  recent_content: ContentItem[];
};

type PublicationLog = {
  id: string;
  content_item_id: string | null;
  endpoint_url: string;
  response_status: number | null;
  error_message: string | null;
  created_at: string;
};

type AdminRequestLog = {
  id: string;
  created_at: string;
  project_name: string;
  actor_username: string | null;
  action: string;
  item_name: string | null;
  method: string;
  destination: string;
  result: "Успешно" | "Ошибка" | "Ожидает ответа";
  status_code: number | null;
  can_retry: boolean;
};

type PublicationCampaign = {
  id: string;
  name: string;
  site_id: string;
  status: "active" | "paused" | "stopped" | "completed" | string;
  interval_minutes: number;
  items_per_run: number;
  start_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

type PublicationQueueItem = {
  id: string;
  topic: string;
  slug: string;
  section_id: string | null;
  section_name: string | null;
  status: string;
  word_count: number;
  include_casino_rating: boolean;
  scheduled_at: string | null;
  published_at: string | null;
};

type PublicationCampaignQueue = {
  campaign: PublicationCampaign;
  items: PublicationQueueItem[];
};

type ThemeMode = "light" | "dark";
type InputStyle = "balanced" | "classic" | "soft" | "inset" | "underline" | "emerald" | "graphite" | "rounded" | "contrast" | "glass";
type AppView = "dashboard" | "workspace" | "prompts" | "tasks" | "taskArchive" | "content" | "publications" | "providers" | "sites" | "favorites" | "guide" | "settings";
type WorkspaceTab = "overview" | "topics" | "content" | "publication" | "menu";

type WorkspaceAccordionContextValue = {
  storagePrefix: string;
  allowPanelCollapse: boolean;
};

const WorkspaceAccordionContext = React.createContext<WorkspaceAccordionContextValue | null>(null);

function usePersistentWorkspacePanelState(panelKey: string, defaultExpanded = true) {
  const accordionContext = React.useContext(WorkspaceAccordionContext);
  const storageKey = accordionContext ? `workspace_accordion:${accordionContext.storagePrefix}:${panelKey}` : "";
  const readStoredState = React.useCallback(() => {
    if (!storageKey) return defaultExpanded;
    const stored = localStorage.getItem(storageKey);
    return stored === null ? defaultExpanded : stored === "expanded";
  }, [defaultExpanded, storageKey]);
  const [expanded, setExpandedState] = React.useState(readStoredState);

  React.useEffect(() => {
    setExpandedState(readStoredState());
  }, [readStoredState]);

  const setExpanded = React.useCallback((next: React.SetStateAction<boolean>) => {
    setExpandedState((current) => {
      const value = typeof next === "function" ? next(current) : next;
      if (storageKey) localStorage.setItem(storageKey, value ? "expanded" : "collapsed");
      return value;
    });
  }, [storageKey]);

  return [expanded, setExpanded] as const;
}

type AppRoute = {
  view: AppView;
  workspaceTab: WorkspaceTab;
};

const API_BASE = "/api";

type ApiRequestError = Error & { statusCode?: number; code?: string };

function requestErrorCode(error: unknown): string {
  if (error instanceof Error) {
    const requestError = error as ApiRequestError;
    if (requestError.statusCode) return `HTTP ${requestError.statusCode}`;
    if (requestError.code) return requestError.code.toUpperCase();
    if (error.name === "TypeError" || /failed to fetch|network/i.test(error.message)) return "NETWORK";
  }
  return "UNKNOWN";
}
const ACTIVE_RESEARCH_STATUSES = ["queued", "collecting_serp", "serp_collected", "serp_empty", "fetching_pages", "pages_fetched"];
const ACTIVE_GENERATION_STATUSES = ["generation_queued", "generating"];
const DEFAULT_TARGET_WORDS = 2000;
const DEFAULT_WORKSPACE_TAB: WorkspaceTab = "overview";
const DEFAULT_ROUTE: AppRoute = { view: "dashboard", workspaceTab: DEFAULT_WORKSPACE_TAB };
const DEFAULT_INPUT_STYLE: InputStyle = "emerald";
const INPUT_STYLE_STORAGE_VERSION = "emerald-default-v1";
const INPUT_STYLE_OPTIONS: Array<{ id: InputStyle; name: string; description: string }> = [
  { id: "balanced", name: "Сбалансированный", description: "Чёткая рамка и аккуратная мягкая тень." },
  { id: "classic", name: "Классический", description: "Строгая форма без декоративной тени." },
  { id: "soft", name: "Мягкое заполнение", description: "Спокойный фон и деликатный объём." },
  { id: "inset", name: "Внутренняя глубина", description: "Лёгкая внутренняя тень подчёркивает ввод." },
  { id: "underline", name: "Нижняя линия", description: "Минималистичное поле только с акцентом снизу." },
  { id: "emerald", name: "Изумрудный", description: "Фирменный зелёный акцент и мягкое свечение." },
  { id: "graphite", name: "Графитовый", description: "Насыщенный нейтральный фон и контрастная рамка." },
  { id: "rounded", name: "Скруглённый", description: "Выраженное скругление и воздушная тень." },
  { id: "contrast", name: "Высокий контраст", description: "Усиленная рамка для максимальной заметности." },
  { id: "glass", name: "Стекло", description: "Полупрозрачная поверхность с лёгким бликом." }
];

function storedInputStyle(): InputStyle {
  if (localStorage.getItem("input_style_version") !== INPUT_STYLE_STORAGE_VERSION) return DEFAULT_INPUT_STYLE;
  const stored = localStorage.getItem("input_style");
  return INPUT_STYLE_OPTIONS.some((option) => option.id === stored) ? stored as InputStyle : DEFAULT_INPUT_STYLE;
}

async function copyTextToClipboard(text: string) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!copied) throw new Error("Clipboard copy failed");
}

function secureRandomIndex(max: number): number {
  if (!Number.isInteger(max) || max < 1 || max > 256) throw new Error("Invalid random range");
  const randomByte = new Uint8Array(1);
  const unbiasedLimit = Math.floor(256 / max) * max;
  do {
    window.crypto.getRandomValues(randomByte);
  } while (randomByte[0] >= unbiasedLimit);
  return randomByte[0] % max;
}

function generateSecurePassword(length = 10): string {
  const groups = [
    "abcdefghijkmnopqrstuvwxyz",
    "ABCDEFGHJKLMNPQRSTUVWXYZ",
    "23456789",
    "!@#$%^&*_-+="
  ];
  const allCharacters = groups.join("");
  const characters = groups.map((group) => group[secureRandomIndex(group.length)]);
  while (characters.length < Math.max(length, groups.length)) {
    characters.push(allCharacters[secureRandomIndex(allCharacters.length)]);
  }
  for (let index = characters.length - 1; index > 0; index -= 1) {
    const swapIndex = secureRandomIndex(index + 1);
    [characters[index], characters[swapIndex]] = [characters[swapIndex], characters[index]];
  }
  return characters.join("");
}

const MAIN_VIEW_PATHS: Record<Exclude<AppView, "workspace">, string> = {
  dashboard: "/dashboard",
  prompts: "/prompts",
  tasks: "/tasks",
  taskArchive: "/task-archive",
  content: "/content",
  publications: "/publications",
  providers: "/ai-providers",
  sites: "/sites",
  favorites: "/favorites",
  guide: "/guide",
  settings: "/settings"
};

const WORKSPACE_TAB_PATHS: Record<WorkspaceTab, string> = {
  overview: "/project-overview",
  topics: "/project-generation",
  content: "/project-content",
  publication: "/project-publication",
  menu: "/project-menu"
};

function routeFromPath(pathname: string): AppRoute {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/project-prompts") {
    return { view: "prompts", workspaceTab: DEFAULT_WORKSPACE_TAB };
  }
  if (path === "/project-topics") {
    return { view: "workspace", workspaceTab: "topics" };
  }
  if (path === "/tasks") {
    return { view: "workspace", workspaceTab: "topics" };
  }
  if (path === "/project-tasks" || path.startsWith("/project-tasks/")) {
    return { view: "workspace", workspaceTab: "topics" };
  }
  const workspaceEntry = Object.entries(WORKSPACE_TAB_PATHS).find(([, routePath]) => path === routePath || path.startsWith(`${routePath}/`));
  if (workspaceEntry) {
    return { view: "workspace", workspaceTab: workspaceEntry[0] as WorkspaceTab };
  }

  const mainEntry = Object.entries(MAIN_VIEW_PATHS).find(([, routePath]) => routePath === path);
  if (mainEntry) {
    return { view: mainEntry[0] as Exclude<AppView, "workspace">, workspaceTab: DEFAULT_WORKSPACE_TAB };
  }

  if (path === "/workspace" || path === "/project") {
    return { view: "workspace", workspaceTab: DEFAULT_WORKSPACE_TAB };
  }

  return DEFAULT_ROUTE;
}

function workspaceProjectNameFromPath(pathname: string): string | null {
  const path = pathname.replace(/\/+$/, "") || "/";
  const routePath = [...Object.values(WORKSPACE_TAB_PATHS), "/project-tasks"].find((candidate) => path.startsWith(`${candidate}/`));
  if (!routePath) return null;
  const encodedName = path.slice(routePath.length + 1).split("/")[0];
  if (!encodedName) return null;
  try {
    return decodeURIComponent(encodedName);
  } catch {
    return encodedName;
  }
}

function pathForRoute(view: AppView, workspaceTab: WorkspaceTab = DEFAULT_WORKSPACE_TAB, projectName?: string | null) {
  if (view === "workspace") {
    const basePath = WORKSPACE_TAB_PATHS[workspaceTab];
    return projectName ? `${basePath}/${encodeURIComponent(projectName)}/` : basePath;
  }
  return MAIN_VIEW_PATHS[view];
}

function isAdminOnlyView(view: AppView) {
  return ["dashboard", "providers"].includes(view);
}

const DEFAULT_PROMPT_DRAFT = `Рабочий промпт для конкретной задачи.

Базовые требования качества, юридической осторожности и формата ответа применяются отдельно через "Базовый промпт".
Здесь описывай только нишу, интент, структуру и специальные требования к странице.

Роль:
Ты — senior SEO-редактор и content strategist для gambling/betting тем.

Задача:
Сгенерировать готовую SEO-страницу для сайта {{SITE_NAME}}.

Переменные:
- Тема страницы: {{TOPIC}}
- Slug страницы: {{SLUG}}
- Гео/страна: {{GEO}}
- Язык страницы: {{LANGUAGE}}
- Желаемый объем: около {{TARGET_WORDS}} слов
- Текущий год: {{CURRENT_YEAR}}
- Shortcode context: {{SHORTCODE}}
- Поисковые запросы: {{SEARCH_QUERIES}}
- URL конкурентов: {{COMPETITOR_URLS}}
- Анализ конкурентов: {{COMPETITOR_SUMMARY}}
- Content gaps: {{CONTENT_GAPS}}
- Частые заголовки конкурентов: {{COMMON_HEADINGS}}
- Темы, подтвержденные анализом нескольких конкурентов: {{MISSING_BLOCKS_TO_COVER}}

Контекст ниши:
Онлайн-казино, ставки, casino providers, легальные Anbieter, лицензии, Spielerschutz, Zahlungen, Auszahlungen, KYC, Datenschutz, Limits, sichere Online Casinos.

Главная цель:
Создать полезную, структурированную, юридически аккуратную страницу, которая полно отвечает на поисковый интент пользователя и пригодна для редакторской проверки перед публикацией.

Если передан анализ конкурентов:
- Используй его только как исследовательский контекст.
- Не копируй конкурентов и не делай близкий перефраз.
- Делай оригинальную структуру и закрывай intent полнее.
- Не утверждай в публичном тексте, что ты изучил Google или конкретных конкурентов.

Внутренняя SEO-логика, НЕ выводить в текст:
1. Главный интент.
2. 8-12 подинтентов.
3. Главный ключ.
4. Вторичные ключи.
5. FAQ-запросы.
6. Legal/Safety/Payment кластеры.
7. Гипотетические content gaps.
8. Риски фактов, которые нужно проверить редактору.

Правила локализации и анализа:
- Структуру и набор смысловых блоков определяй динамически по теме, выбранному гео, языку и фактически собранным материалам конкурентов.
- Не добавляй обязательный блок только потому, что он обычно встречается в нише или был нужен для другой страны.
- Не добавляй раздел о проверке лицензии, если эта тема не подтверждена анализом нескольких конкурентов для текущего гео.

Если тема рейтинговая:
- Если нет проверенного списка брендов, делай таблицу критериев выбора.
- Для мест под реальные бренды используй только placeholder:
  [Anbieter 1 - muss geprüft werden]
  [Anbieter 2 - muss geprüft werden]
  [Anbieter 3 - muss geprüft werden]

Шаблон ответа:
Title:
Meta Description:
H1:

H2: Intro
1-2 коротких абзаца. Сразу отвечай на основной запрос, без длинного вступления.

H2: Quick Answer
3-5 предложений с практическим ответом.

H2: Überblick / schneller Vergleich
2-4 абзаца. Если уместно, добавь таблицу:
| Kriterium | Worauf achten | Warum wichtig |
|---|---|---|

H2: Methodik: Wie wir Anbieter bewerten
Объясни критерии оценки без фейковых баллов и без неподтвержденного рейтинга.

H2: Lizenz und rechtlicher Rahmen
Объясни лицензии, локальные ограничения, что должен проверить пользователь и что должен проверить редактор.

H2: Sicherheit: Lizenz, Zahlungen, Datenschutz und KYC
Раскрой безопасность без обещаний абсолютной защиты.

H2: Zahlungen und Auszahlungen
Объясни различие между Einzahlung и Auszahlung, KYC, возможные задержки и что проверить до депозита.

H2: Spielerschutz und Limits
Раскрой лимиты, самоисключение, признаки проблемной игры.

H2: Für wen geeignet / nicht geeignet
Дай честное разделение аудиторий, без рекламного давления.

H2: Häufige Fehler vor der Registrierung
Дай практический список ошибок.

H2: FAQ
Сгенерируй 8-10 вопросов. Каждый вопрос и ответ пиши отдельными строками:
Q: ...
A: ...

H2: Responsible Gambling Hinweis
Добавь аккуратный блок на языке {{LANGUAGE}}:
- Glücksspiel ist mit Risiken verbunden.
- Nur mit Geld spielen, dessen Verlust verkraftbar ist.
- Limits nutzen.
- Bei Kontrollverlust Hilfe suchen.
- [Muss geprüft werden: lokale Hilfsangebote in {{GEO}}].

Editor Check:
- Suchintention: OK / Risiko
- Fakten: OK / Muss geprüft werden
- Legal-Risiko: OK / Risiko
- Keyword-Stuffing: OK / Risiko
- E-E-A-T: OK / Muss gestärkt werden
- Thin Content: OK / Risiko
- Struktur: OK / Risiko
- Nächste Prüfung vor Veröffentlichung: ...`;

const COUNTRY_CODES = [
  "AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ",
  "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR",
  "IO", "BN", "BG", "BF", "BI", "CV", "KH", "CM", "CA", "KY", "CF", "TD", "CL", "CN", "CX", "CC",
  "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO",
  "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF",
  "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY",
  "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM",
  "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY",
  "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX",
  "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI",
  "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH",
  "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC",
  "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS",
  "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK",
  "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU",
  "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW"
] as const;

const regionNames = new Intl.DisplayNames(["ru"], { type: "region" });
const COUNTRIES = COUNTRY_CODES.map((code) => ({
  code,
  name: regionNames.of(code) || code,
  flag: countryFlag(code)
})).sort((first, second) => first.name.localeCompare(second.name, "ru"));

function projectLanguageCode(site?: Site): string {
  const supportedLanguages = new Set(LANGUAGE_OPTIONS.map((option) => option.code));
  for (const value of [site?.cache_language, site?.cache_geo]) {
    const languageCode = (value || "").trim().toLowerCase().split(/[-_]/)[0];
    if (supportedLanguages.has(languageCode)) return languageCode;
  }
  return "en";
}

function projectGeoCode(site?: Site): string {
  const supportedCountries = new Set<string>(COUNTRY_CODES);
  for (const value of [site?.cache_geo, site?.cache_language]) {
    const countryCode = localeCountryCode(value || "");
    if (countryCode && supportedCountries.has(countryCode)) return countryCode;
  }
  const domainZone = (site?.cache_canon || "").split(".").pop()?.toUpperCase() || "";
  return supportedCountries.has(domainZone) ? domainZone : "DE";
}

function App() {
  const initialRoute = React.useMemo(() => routeFromPath(window.location.pathname), []);
  const [token, setToken] = React.useState(() => localStorage.getItem("admin_token") || "");
  const [theme, setTheme] = React.useState<ThemeMode>(() => (localStorage.getItem("theme_mode") === "dark" ? "dark" : "light"));
  const [inputStyle, setInputStyle] = React.useState<InputStyle>(storedInputStyle);
  const [activeView, setActiveView] = React.useState<AppView>(initialRoute.view);
  const [workspaceTab, setWorkspaceTab] = React.useState<WorkspaceTab>(initialRoute.workspaceTab);
  const [, setRouteVersion] = React.useState(0);
  const [dashboard, setDashboard] = React.useState<Dashboard | null>(null);
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [archivedTasks, setArchivedTasks] = React.useState<Task[]>([]);
  const [content, setContent] = React.useState<ContentItem[]>([]);
  const [sites, setSites] = React.useState<Site[]>([]);
  const [providers, setProviders] = React.useState<AiProvider[]>([]);
  const [currentUser, setCurrentUser] = React.useState<User | null>(null);
  const [users, setUsers] = React.useState<User[]>([]);
  const [message, setMessage] = React.useState("");
  const [notificationPromptVisible, setNotificationPromptVisible] = React.useState(false);
  const [viewAsUser, setViewAsUser] = React.useState(false);
  const isAdmin = Boolean(currentUser?.is_admin && !viewAsUser);

  const navigateTo = React.useCallback((view: AppView, nextWorkspaceTab: WorkspaceTab = workspaceTab, replace = false, projectName?: string | null) => {
    const normalizedWorkspaceTab = view === "workspace" ? nextWorkspaceTab : workspaceTab;
    const nextPath = pathForRoute(view, normalizedWorkspaceTab, projectName);
    setActiveView(view);
    if (view === "workspace") {
      setWorkspaceTab(normalizedWorkspaceTab);
    }
    if (window.location.pathname !== nextPath) {
      const method = replace ? "replaceState" : "pushState";
      window.history[method](null, "", nextPath);
    }
  }, [workspaceTab]);

  const api = React.useCallback(
    async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
      const method = (options.method || "GET").toUpperCase();
      const attempts = method === "GET" ? 3 : 1;
      let response: Response | null = null;
      let networkError: unknown = null;
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        try {
          response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              ...(options.headers || {})
            }
          });
          if (![502, 503, 504].includes(response.status) || attempt === attempts - 1) break;
        } catch (error) {
          networkError = error;
          if (attempt === attempts - 1) throw error;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 250 * (attempt + 1)));
      }
      if (!response) throw networkError instanceof Error ? networkError : new Error("Failed to fetch");
      if (response.status === 401) {
        localStorage.removeItem("admin_token");
        setToken("");
        setCurrentUser(null);
        setUsers([]);
        setArchivedTasks([]);
        const authError = new Error("Нужно войти заново") as ApiRequestError;
        authError.statusCode = response.status;
        throw authError;
      }
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Request failed" }));
        const requestError = new Error(error.detail || "Request failed") as ApiRequestError;
        requestError.statusCode = response.status;
        throw requestError;
      }
      return response.json();
    },
    [token]
  );

  const loadAll = React.useCallback(async () => {
    if (!token) return;
    const nextUser = await api<User>("/auth/me");
    const [nextSites, nextProviders] = await Promise.all([
      api<Site[]>("/sites"),
      api<AiProvider[]>("/ai-providers")
    ]);
    const [nextTasks, nextArchivedTasks, nextContent] = await Promise.all([
      api<Task[]>("/tasks"),
      api<Task[]>("/tasks-archive"),
      api<ContentItem[]>("/content")
    ]);
    const nextDashboard = nextUser.is_admin ? await api<Dashboard>("/dashboard") : null;
    const nextUsers = nextUser.is_admin ? await api<User[]>("/users") : [];
    setCurrentUser(nextUser);
    setDashboard(nextDashboard);
    setTasks(nextTasks);
    setArchivedTasks(nextArchivedTasks);
    setContent(nextContent);
    setSites(nextSites);
    setProviders(nextProviders);
    setUsers(nextUsers);
  }, [api, token]);

  async function requestPopupPermission() {
    if (!window.isSecureContext) {
      setNotificationPromptVisible(false);
      setMessage("Браузерное разрешение на всплывающие уведомления доступно только по HTTPS или localhost.");
      sessionStorage.setItem("popup_permission_prompt_closed", "true");
      return;
    }

    if (!("Notification" in window)) {
      setNotificationPromptVisible(false);
      setMessage("Браузер не поддерживает всплывающие уведомления.");
      sessionStorage.setItem("popup_permission_prompt_closed", "true");
      return;
    }

    const permission = await Notification.requestPermission();
    setNotificationPromptVisible(false);
    sessionStorage.setItem("popup_permission_prompt_closed", "true");

    if (permission === "granted") {
      setMessage("Разрешение на всплывающие уведомления включено.");
    } else if (permission === "denied") {
      setMessage("Всплывающие уведомления заблокированы в настройках браузера.");
    }
  }

  function closePopupPermissionPrompt() {
    sessionStorage.setItem("popup_permission_prompt_closed", "true");
    setNotificationPromptVisible(false);
  }

  React.useEffect(() => {
    loadAll().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Не удалось загрузить данные"));
  }, [loadAll]);

  React.useEffect(() => {
    if (!currentUser?.is_admin) {
      setViewAsUser(false);
      return;
    }
    setViewAsUser(localStorage.getItem(`admin_view_mode:${currentUser.username}`) === "user");
  }, [currentUser?.id, currentUser?.is_admin, currentUser?.username]);

  React.useEffect(() => {
    const handlePopState = () => {
      const nextRoute = routeFromPath(window.location.pathname);
      setActiveView(nextRoute.view);
      setWorkspaceTab(nextRoute.workspaceTab);
      setRouteVersion((version) => version + 1);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme_mode", theme);
  }, [theme]);

  React.useEffect(() => {
    document.documentElement.dataset.inputStyle = inputStyle;
    localStorage.setItem("input_style", inputStyle);
    localStorage.setItem("input_style_version", INPUT_STYLE_STORAGE_VERSION);
  }, [inputStyle]);

  React.useEffect(() => {
    if (!currentUser) {
      setNotificationPromptVisible(false);
      return;
    }
    const promptWasClosed = sessionStorage.getItem("popup_permission_prompt_closed") === "true";
    const canAskBrowserPermission = "Notification" in window && Notification.permission === "default";
    if (!promptWasClosed && (!window.isSecureContext || canAskBrowserPermission)) {
      setNotificationPromptVisible(true);
    }
  }, [currentUser]);

  React.useEffect(() => {
    if (!currentUser) return;
    if (!isAdmin && isAdminOnlyView(activeView)) {
      navigateTo("workspace", DEFAULT_WORKSPACE_TAB, true);
      return;
    }
    const projectName = activeView === "workspace" ? workspaceProjectNameFromPath(window.location.pathname) : null;
    const nextPath = pathForRoute(activeView, activeView === "workspace" ? workspaceTab : DEFAULT_WORKSPACE_TAB, projectName);
    if (window.location.pathname !== nextPath) {
      window.history.replaceState(null, "", nextPath);
    }
  }, [activeView, currentUser, isAdmin, navigateTo, workspaceTab]);

  if (!token) {
    return <LoginScreen onLogin={setToken} />;
  }

  if (!currentUser) {
    return (
      <AuthScreen>
        <div className="loginPanel">
          <div className="brandMark large logoMark"><BrandLogo /></div>
          <h1>Загрузка панели</h1>
          <p>{message || "Проверяем сессию и права пользователя."}</p>
          <div className="loginLoadingBar" aria-hidden="true"><span /></div>
        </div>
      </AuthScreen>
    );
  }

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="sidebarDigitalRain" aria-hidden="true">
          {Array.from({ length: 12 }, (_, index) => (
            <span key={index} style={{ "--rain-column": index, "--rain-delay": `${-(index * 0.73) % 7}s` } as React.CSSProperties}>
              {index % 3 === 0 ? "01011010 101001 11001" : index % 3 === 1 ? "1011001 001011 01010" : "001101 110010 10101"}
            </span>
          ))}
        </div>
        <div className="brand">
          <div className="brandMark logoMark"><BrandLogo /></div>
          <div>
            <strong>Content Admin</strong>
            <span>AI publishing control</span>
          </div>
        </div>
        <nav className="nav">
          {isAdmin ? (
            <>
              <NavButton href={pathForRoute("dashboard")} icon={<LayoutDashboard />} label="Dashboard" active={activeView === "dashboard"} onClick={() => navigateTo("dashboard")} />
              <NavButton href={pathForRoute("workspace", DEFAULT_WORKSPACE_TAB)} icon={<FolderKanban />} label="Рабочий экран" active={activeView === "workspace"} onClick={() => navigateTo("workspace", DEFAULT_WORKSPACE_TAB)} />
              <NavButton href={pathForRoute("prompts")} icon={<Edit3 />} label="Промпты" active={activeView === "prompts"} onClick={() => navigateTo("prompts")} />
              <NavButton href={pathForRoute("taskArchive")} icon={<Archive />} label="Архив" active={activeView === "taskArchive"} onClick={() => navigateTo("taskArchive")} />
              <NavButton href={pathForRoute("publications")} icon={<Send />} label="Контент и публикации" active={activeView === "publications"} onClick={() => navigateTo("publications")} />
              <NavButton href={pathForRoute("providers")} icon={<Bot />} label="API Providers" active={activeView === "providers"} onClick={() => navigateTo("providers")} />
              <NavButton href={pathForRoute("sites")} icon={<Globe2 />} label="Сайты" active={activeView === "sites"} onClick={() => navigateTo("sites")} />
              <NavButton href={pathForRoute("favorites")} icon={<Star className="favoriteNavIcon" fill="currentColor" />} label="Избранное" active={activeView === "favorites"} onClick={() => navigateTo("favorites")} />
            </>
          ) : (
            <>
              <NavButton href={pathForRoute("workspace", DEFAULT_WORKSPACE_TAB)} icon={<FolderKanban />} label="Рабочий экран" active={activeView === "workspace"} onClick={() => navigateTo("workspace", DEFAULT_WORKSPACE_TAB)} />
              <NavButton href={pathForRoute("prompts")} icon={<Edit3 />} label="Промпты" active={activeView === "prompts"} onClick={() => navigateTo("prompts")} />
              <NavButton href={pathForRoute("taskArchive")} icon={<Archive />} label="Архив" active={activeView === "taskArchive"} onClick={() => navigateTo("taskArchive")} />
              <NavButton href={pathForRoute("publications")} icon={<Send />} label="Контент и публикации" active={activeView === "publications"} onClick={() => navigateTo("publications")} />
              <NavButton href={pathForRoute("sites")} icon={<Globe2 />} label="Сайты" active={activeView === "sites"} onClick={() => navigateTo("sites")} />
              <NavButton href={pathForRoute("favorites")} icon={<Star className="favoriteNavIcon" fill="currentColor" />} label="Избранное" active={activeView === "favorites"} onClick={() => navigateTo("favorites")} />
            </>
          )}
          <NavButton href={pathForRoute("guide")} icon={<BookOpen />} label="Инструкция" active={activeView === "guide"} onClick={() => navigateTo("guide")} />
          <NavButton href={pathForRoute("settings")} icon={<Settings />} label="Настройки" active={activeView === "settings"} onClick={() => navigateTo("settings")} />
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">Рабочая панель</p>
            <h1>{viewTitle(activeView, workspaceTab)}</h1>
          </div>
          <div className="topbarActions">
            {currentUser.is_admin ? (
              <button
                className={`button secondary adminViewModeButton ${viewAsUser ? "active" : ""}`}
                type="button"
                onClick={() => {
                  const nextValue = !viewAsUser;
                  setViewAsUser(nextValue);
                  localStorage.setItem(`admin_view_mode:${currentUser.username}`, nextValue ? "user" : "admin");
                  if (nextValue && isAdminOnlyView(activeView)) navigateTo("workspace", DEFAULT_WORKSPACE_TAB);
                }}
                title={viewAsUser ? "Вернуться к полному интерфейсу администратора" : "Показать интерфейс обычного пользователя"}
              >
                {viewAsUser ? <ShieldCheck size={17} /> : <Eye size={17} />}
                {viewAsUser ? "Режим администратора" : "Посмотреть как пользователь"}
              </button>
            ) : null}
            {currentUser ? (
              <div className="userPill">
                <span>{viewAsUser ? "Просмотр как пользователь" : currentUser.is_admin ? "Администратор" : "Пользователь"}</span>
                <strong>{currentUser.username}</strong>
              </div>
            ) : null}
            <button className="button secondary" onClick={() => loadAll()} title="Обновить данные">
              <RefreshCcw size={18} />
              Обновить
            </button>
            <button
              className="iconButton"
              onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              title={theme === "dark" ? "Включить светлую тему" : "Включить темную тему"}
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              className="iconButton"
              onClick={() => {
                localStorage.removeItem("admin_token");
                setToken("");
                setCurrentUser(null);
                setUsers([]);
                setArchivedTasks([]);
              }}
              title="Выйти"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {message ? <div className="notice">{message}</div> : null}

        {activeView === "workspace" && <ProjectWorkspaceView api={api} sites={sites} providers={providers} currentUsername={currentUser.username} activeTab={workspaceTab} onTabChange={(tab, projectName) => navigateTo("workspace", tab, false, projectName)} onChanged={loadAll} />}
        {activeView === "prompts" && <PromptsView api={api} sites={sites} isAdmin={isAdmin} onChanged={loadAll} />}
        {isAdmin && activeView === "dashboard" && dashboard && <DashboardView api={api} dashboard={dashboard} tasks={tasks} content={content} sites={sites} onOpenTask={(task) => {
          const site = sites.find((candidate) => candidate.id === task.site_id);
          if (!site) {
            setMessage("Для этой задачи проект не назначен.");
            return;
          }
          sessionStorage.setItem("workspace_open_task_id", task.id);
          localStorage.setItem(`workspace_site_id:${currentUser.username}`, site.id);
          navigateTo("workspace", "topics", false, site.name);
        }} onChanged={loadAll} />}
        {activeView === "tasks" && <TasksView api={api} sites={sites} providers={providers} tasks={tasks} onChanged={loadAll} />}
        {activeView === "taskArchive" && <TaskArchiveView api={api} tasks={archivedTasks} onChanged={loadAll} />}
        {activeView === "content" && <ContentView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {activeView === "publications" && <PublicationsView api={api} sites={sites} content={content} onOpenProject={(site) => {
          localStorage.setItem(`workspace_site_id:${currentUser.username}`, site.id);
          navigateTo("workspace", "content", false, site.name);
        }} onChanged={loadAll} />}
        {isAdmin && activeView === "providers" && <ProvidersView api={api} providers={providers} onChanged={loadAll} />}
        {activeView === "sites" && <SitesView api={api} sites={sites} currentUsername={currentUser.username} readOnly={!isAdmin} onChanged={loadAll} />}
        {activeView === "favorites" && <SitesView api={api} sites={sites} currentUsername={currentUser.username} favoritesOnly readOnly={!isAdmin} onChanged={loadAll} />}
        {activeView === "guide" && <UserGuideView />}
        {activeView === "settings" && <SettingsView api={api} currentUser={currentUser} users={users} inputStyle={inputStyle} onInputStyleChange={setInputStyle} onChanged={loadAll} />}
      </main>
      {notificationPromptVisible ? (
        <div className="permissionOverlay" role="dialog" aria-modal="true" aria-labelledby="popup-permission-title">
          <div className="permissionDialog">
            <div className="permissionIcon"><BellRing size={22} /></div>
            <div>
              <h2 id="popup-permission-title">Разрешить всплывающие уведомления?</h2>
              <p>Сервис сможет показывать уведомления о генерации, публикациях и ошибках, даже если вкладка открыта в фоне.</p>
            </div>
            <div className="permissionActions">
              <button className="button secondary" type="button" onClick={closePopupPermissionPrompt}>Не сейчас</button>
              <button className="button primary" type="button" onClick={requestPopupPermission}>Разрешить</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AuthDashboardBackdrop() {
  const navigation = [
    { icon: <LayoutDashboard size={18} />, label: "Dashboard", active: true },
    { icon: <FolderKanban size={18} />, label: "Рабочий экран" },
    { icon: <Edit3 size={18} />, label: "Промпты" },
    { icon: <Archive size={18} />, label: "Архив" },
    { icon: <Send size={18} />, label: "Контент и публикации" },
    { icon: <Globe2 size={18} />, label: "Сайты" },
    { icon: <Settings size={18} />, label: "Настройки" }
  ];
  const metrics = [
    { icon: <Database size={20} />, label: "Всего задач" },
    { icon: <CheckCircle2 size={20} />, label: "Сгенерировано" },
    { icon: <FileText size={20} />, label: "Ждет approve" },
    { icon: <Send size={20} />, label: "В очереди" },
    { icon: <Activity size={20} />, label: "Опубликовано" },
    { icon: <AlertTriangle size={20} />, label: "Ошибки" }
  ];

  return (
    <div className="authDashboardBackdrop" aria-hidden="true">
      <aside className="authPreviewSidebar">
        <div className="authPreviewBrand">
          <div className="brandMark logoMark"><BrandLogo /></div>
          <div><strong>Content Admin</strong><span>AI publishing control</span></div>
        </div>
        <div className="authPreviewNav">
          {navigation.map((item) => (
            <div className={`authPreviewNavItem${item.active ? " active" : ""}`} key={item.label}>
              {item.icon}<span>{item.label}</span>
            </div>
          ))}
        </div>
      </aside>
      <main className="authPreviewMain">
        <div className="authPreviewTopbar">
          <div><span>Рабочая панель</span><strong>Dashboard</strong></div>
          <div className="authPreviewControls"><i /><i /><i /></div>
        </div>
        <div className="authPreviewKpis">
          {metrics.map((metric) => (
            <div className="authPreviewKpi" key={metric.label}>
              {metric.icon}<span>{metric.label}</span><strong>—</strong>
            </div>
          ))}
        </div>
        <div className="authPreviewPanels">
          <div className="authPreviewPanel">
            <strong>Активные задачи</strong>
            <div className="authPreviewTableHead"><span>Задача</span><span>Гео</span><span>Тем</span><span>Статус</span></div>
            {[0, 1, 2, 3].map((row) => <div className="authPreviewTableRow" key={row}><i /><i /><i /><i /></div>)}
          </div>
          <div className="authPreviewPanel">
            <strong>Очередь публикаций</strong>
            <div className="authPreviewEmpty">Данных пока нет.</div>
          </div>
        </div>
        <div className="authPreviewPanel authPreviewErrors">
          <strong>Последние ошибки</strong>
          <div className="authPreviewEmpty">Ошибок пока нет.</div>
        </div>
      </main>
    </div>
  );
}

function BrandLogo() {
  return (
    <svg className="brandLogo" viewBox="0 0 128 128" role="img" aria-label="AI Content panel">
      <defs>
        <linearGradient id="brand-logo-background" x1="20" y1="12" x2="110" y2="118" gradientUnits="userSpaceOnUse">
          <stop stopColor="#35BE73" />
          <stop offset="1" stopColor="#178149" />
        </linearGradient>
        <linearGradient id="brand-logo-spark" x1="78" y1="15" x2="104" y2="49" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" />
          <stop offset="0.48" stopColor="#D8FFE7" />
          <stop offset="1" stopColor="#91EDB6" />
        </linearGradient>
      </defs>
      <rect className="brandLogoTile" x="7" y="7" width="114" height="114" rx="27" fill="url(#brand-logo-background)" />
      <g className="brandLogoDocument" fill="none" stroke="#fff" strokeLinecap="round" strokeLinejoin="round">
        <path d="M39 42h29l15 15v39a6 6 0 0 1-6 6H39a6 6 0 0 1-6-6V48a6 6 0 0 1 6-6Z" strokeWidth="7" />
        <path d="M68 43v16h14M47 72h23M47 85h17" strokeWidth="6" />
      </g>
      <g className="brandLogoSpark">
        <path d="M93 11c1.8 9.1 4.3 14.7 8 18 3.3 3.2 8.5 5.2 15.7 6.3-7.7 1.8-13 4.2-16.2 7.5-3.1 3.2-5.6 8.2-7.5 15.2-1.9-7.3-4.5-12.4-7.8-15.6-3.2-3.1-8.3-5.5-15.2-7.1 7.3-1.4 12.5-3.6 15.6-6.8 3.2-3.3 5.7-9.1 7.4-17.5Z" fill="url(#brand-logo-spark)" />
        <path d="M93 19c1.1 5.8 2.8 9.5 5.1 11.6 2.1 2 5.4 3.4 9.9 4.4-4.8 1.2-8.2 2.8-10.2 4.9-2 2-3.6 5.2-4.8 9.6-1.2-4.6-2.9-7.9-5-10-2.1-2.1-5.3-3.6-9.8-4.5 4.6-.9 7.9-2.4 10-4.4 2-2.2 3.6-6 4.8-11.6Z" fill="#fff" fillOpacity="0.5" />
        <circle cx="111" cy="17" r="3.5" fill="#D8FFE7" />
      </g>
    </svg>
  );
}

function AuthScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="loginPage">
      <AuthDashboardBackdrop />
      <div className="authBackdropShade" aria-hidden="true" />
      {children}
    </div>
  );
}

function LoginScreen({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      if (!response.ok) {
        setError("Неверный логин или пароль");
        return;
      }
      const data = await response.json();
      localStorage.setItem("admin_token", data.access_token);
      onLogin(data.access_token);
    } catch {
      setError("Не удалось подключиться к серверу");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthScreen>
      <form className="loginPanel" onSubmit={submit} aria-busy={submitting}>
        <div className="loginBrandRow">
          <div className="brandMark large logoMark loginBrandLogo"><BrandLogo /></div>
          <h1>AI Content panel</h1>
        </div>
        <p>Вход в панель генерации и публикации контента.</p>
        <label>
          Логин
          <input value={username} onChange={(event) => setUsername(event.target.value)} disabled={submitting} />
        </label>
        <label>
          Пароль
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus disabled={submitting} />
        </label>
        {error ? <span className="formError">{error}</span> : null}
        <button className="button primary" type="submit" disabled={submitting}>
          {submitting ? <><LoaderCircle className="spin" size={18} /> Входим…</> : "Войти"}
        </button>
      </form>
    </AuthScreen>
  );
}

function DashboardView({ api, dashboard, tasks, content, sites, onOpenTask, onChanged }: ViewProps & { dashboard: Dashboard; tasks: Task[]; content: ContentItem[]; sites: Site[]; onOpenTask: (task: Task) => void }) {
  const [reviewExpanded, setReviewExpanded] = React.useState(false);
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [selectedReviewIds, setSelectedReviewIds] = React.useState<string[]>([]);
  const [actionId, setActionId] = React.useState("");
  const [reviewError, setReviewError] = React.useState("");
  const [sectionsBySite, setSectionsBySite] = React.useState<Record<string, Section[]>>({});
  const awaitingItems = content.filter((item) => item.status === "generated");
  const awaitingItemIds = awaitingItems.map((item) => item.id);
  const selectedReviewItems = awaitingItems.filter((item) => selectedReviewIds.includes(item.id));
  const selectedReadyItems = selectedReviewItems.filter((item) => Boolean(item.site_id && item.section_id));
  const allReviewSelected = awaitingItemIds.length > 0 && awaitingItemIds.every((id) => selectedReviewIds.includes(id));
  const bulkReviewBusy = actionId.startsWith("bulk:");

  React.useEffect(() => {
    setSelectedReviewIds((current) => {
      const next = current.filter((id) => awaitingItemIds.includes(id));
      return next.length === current.length ? current : next;
    });
  }, [content]);

  React.useEffect(() => {
    if (!selectedPreview || !ACTIVE_GENERATION_STATUSES.includes(selectedPreview.status)) return;
    let cancelled = false;
    const contentId = selectedPreview.id;
    const pollGeneration = async () => {
      try {
        const updated = await api<ContentItem>(`/content/${contentId}`);
        if (cancelled) return;
        setSelectedPreview(updated);
        if (!ACTIVE_GENERATION_STATUSES.includes(updated.status)) await onChanged();
      } catch (error) {
        if (!cancelled) setReviewError(error instanceof Error ? error.message : "Не удалось обновить прогресс генерации.");
      }
    };
    const intervalId = window.setInterval(pollGeneration, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [api, onChanged, selectedPreview?.id, selectedPreview?.status]);

  function toggleReviewSelected(id: string) {
    setSelectedReviewIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  }

  function toggleAllReviewItems() {
    setSelectedReviewIds(allReviewSelected ? [] : awaitingItemIds);
  }

  async function toggleReview() {
    const nextExpanded = !reviewExpanded;
    setReviewExpanded(nextExpanded);
    setReviewError("");
    if (!nextExpanded) return;
    const siteIds = Array.from(new Set(awaitingItems.map((item) => item.site_id).filter((siteId): siteId is string => Boolean(siteId))));
    const missingSiteIds = siteIds.filter((siteId) => !sectionsBySite[siteId]);
    if (!missingSiteIds.length) return;
    try {
      const loaded = await Promise.all(missingSiteIds.map(async (siteId) => [siteId, await api<Section[]>(`/sites/${siteId}/sections`)] as const));
      setSectionsBySite((current) => ({ ...current, ...Object.fromEntries(loaded) }));
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось загрузить пункты меню.");
    }
  }

  async function selectSection(item: ContentItem, sectionId: string) {
    setActionId(`${item.id}:section`);
    setReviewError("");
    try {
      await api(`/content/${item.id}`, { method: "PATCH", body: JSON.stringify({ section_id: sectionId || null }) });
      await onChanged();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось выбрать раздел.");
    } finally {
      setActionId("");
    }
  }

  async function approveItem(item: ContentItem) {
    setActionId(`${item.id}:approve`);
    setReviewError("");
    try {
      await api(`/content/${item.id}/approve`, { method: "POST" });
      setSelectedPreview((current) => current?.id === item.id ? null : current);
      await onChanged();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось согласовать текст.");
    } finally {
      setActionId("");
    }
  }

  async function deleteItem(item: ContentItem) {
    if (!window.confirm(`Удалить сгенерированный контент по теме "${item.topic}"?`)) return;
    setActionId(`${item.id}:delete`);
    setReviewError("");
    try {
      await api(`/content/${item.id}`, { method: "DELETE" });
      setSelectedPreview((current) => current?.id === item.id ? null : current);
      await onChanged();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось удалить текст.");
    } finally {
      setActionId("");
    }
  }

  async function sendToPublication(item: ContentItem) {
    if (!item.site_id || !item.section_id) {
      setReviewError("Перед публикацией выберите проект и раздел.");
      return;
    }
    setActionId(`${item.id}:publish`);
    setReviewError("");
    try {
      await api(`/content/${item.id}/publish-now`, { method: "POST" });
      setSelectedPreview((current) => current?.id === item.id ? null : current);
      await onChanged();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось отправить текст в публикацию.");
    } finally {
      setActionId("");
    }
  }

  async function regenerateReviewItem(item: ContentItem) {
    setActionId(`${item.id}:generate`);
    setReviewError("");
    try {
      const updated = await api<ContentItem>(`/content/${item.id}/generate`, { method: "POST" });
      setSelectedPreview(updated);
      await onChanged();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось запустить повторную генерацию.");
    } finally {
      setActionId("");
    }
  }

  async function bulkApproveReviewItems() {
    if (!selectedReadyItems.length) return;
    setActionId("bulk:approve");
    setReviewError("");
    try {
      const results = await Promise.allSettled(selectedReadyItems.map((item) => api(`/content/${item.id}/approve`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedReviewIds([]);
      setSelectedPreview((current) => current && selectedReadyItems.some((item) => item.id === current.id) ? null : current);
      await onChanged();
      if (failed) setReviewError(`Не удалось согласовать часть текстов: ${failed}.`);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось согласовать выбранные тексты.");
    } finally {
      setActionId("");
    }
  }

  async function bulkPublishReviewItems() {
    if (!selectedReadyItems.length) return;
    setActionId("bulk:publish");
    setReviewError("");
    try {
      const results = await Promise.allSettled(selectedReadyItems.map((item) => api(`/content/${item.id}/publish-now`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedReviewIds([]);
      setSelectedPreview((current) => current && selectedReadyItems.some((item) => item.id === current.id) ? null : current);
      await onChanged();
      if (failed) setReviewError(`Не удалось отправить в публикацию часть текстов: ${failed}.`);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось отправить выбранные тексты в публикацию.");
    } finally {
      setActionId("");
    }
  }

  async function bulkDeleteReviewItems() {
    if (!selectedReviewItems.length) return;
    if (!window.confirm(`Удалить выбранные тексты: ${selectedReviewItems.length}?`)) return;
    setActionId("bulk:delete");
    setReviewError("");
    try {
      const results = await Promise.allSettled(selectedReviewItems.map((item) => api(`/content/${item.id}`, { method: "DELETE" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedReviewIds([]);
      setSelectedPreview((current) => current && selectedReviewItems.some((item) => item.id === current.id) ? null : current);
      await onChanged();
      if (failed) setReviewError(`Не удалось удалить часть текстов: ${failed}.`);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось удалить выбранные тексты.");
    } finally {
      setActionId("");
    }
  }

  return (
    <section className="viewStack">
      <div className="kpiGrid">
        <KpiCard icon={<Database />} label="Всего задач" value={dashboard.stats.total_tasks} />
        <KpiCard icon={<CheckCircle2 />} label="Сгенерировано" value={dashboard.stats.generated} />
        <KpiCard icon={<FileText />} label="Ждет approve" value={dashboard.stats.awaiting_approve} onClick={toggleReview} active={reviewExpanded} />
        <KpiCard icon={<Send />} label="В очереди" value={dashboard.stats.scheduled} />
        <KpiCard icon={<Activity />} label="Опубликовано" value={dashboard.stats.published} />
        <KpiCard icon={<AlertTriangle />} label="Ошибки" value={dashboard.stats.errors} danger />
      </div>
      {reviewExpanded ? (
        <DataPanel title={`Тексты на согласование · ${awaitingItems.length}`}>
          <div className="bulkToolbar">
            <label className="checkboxRow bulkSelectAll">
              <input type="checkbox" checked={allReviewSelected} onChange={toggleAllReviewItems} disabled={!awaitingItems.length || bulkReviewBusy} />
              Выбрать все
            </label>
            <span className="fieldHint">Выбрано: {selectedReviewItems.length}</span>
            <button className="button compact approve" type="button" onClick={bulkApproveReviewItems} disabled={!selectedReadyItems.length || bulkReviewBusy} title={selectedReviewItems.length && !selectedReadyItems.length ? "Для выбранных текстов сначала назначьте проект и раздел" : undefined}>
              <CheckCircle2 size={15} /> {actionId === "bulk:approve" ? "Согласовываю" : `Согласовать (${selectedReadyItems.length})`}
            </button>
            <button className="button compact primary" type="button" onClick={bulkPublishReviewItems} disabled={!selectedReadyItems.length || bulkReviewBusy} title={selectedReviewItems.length && !selectedReadyItems.length ? "Для выбранных текстов сначала назначьте проект и раздел" : undefined}>
              <Send size={15} /> {actionId === "bulk:publish" ? "Отправляю" : `В публикацию (${selectedReadyItems.length})`}
            </button>
            <button className="button compact danger" type="button" onClick={bulkDeleteReviewItems} disabled={!selectedReviewItems.length || bulkReviewBusy}>
              <Trash2 size={15} /> {actionId === "bulk:delete" ? "Удаляю" : `Удалить (${selectedReviewItems.length})`}
            </button>
          </div>
          <ResponsiveTable
            columns={["Выбор", "Тема", "Проект", "Раздел", "Слова", "Статус", "Действия"]}
            rows={awaitingItems.map((item) => {
              const itemBusy = actionId.startsWith(item.id) || bulkReviewBusy;
              const sections = item.site_id ? sectionsBySite[item.site_id] || [] : [];
              const publicationReady = Boolean(item.site_id && item.section_id);
              return [
                <input className="rowCheckbox" type="checkbox" checked={selectedReviewIds.includes(item.id)} onChange={() => toggleReviewSelected(item.id)} disabled={bulkReviewBusy} aria-label={`Выбрать ${item.topic}`} />,
                <TopicMetaCell item={item} />,
                sites.find((site) => site.id === item.site_id)?.name || "Не назначен",
                item.site_id ? (
                  <SearchableSelect
                    value={item.section_id || ""}
                    onChange={(value) => selectSection(item, value)}
                    options={[{ value: "", label: "Выберите раздел" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
                    disabled={itemBusy}
                    ariaLabel={`Раздел для ${item.topic}`}
                    searchPlaceholder="Найти раздел"
                  />
                ) : "Сначала назначьте проект",
                item.word_count,
                <StatusBadge status={item.status} />,
                <div className="userActions dashboardReviewActions">
                  <button className="button compact" type="button" onClick={() => setSelectedPreview(item)} disabled={itemBusy}><Eye size={15} /> Просмотр</button>
                  <button className="button compact danger" type="button" onClick={() => deleteItem(item)} disabled={itemBusy}><Trash2 size={15} /> Удалить</button>
                  <button className="button compact approve" type="button" onClick={() => approveItem(item)} disabled={itemBusy || !publicationReady} title={publicationReady ? undefined : "Сначала выберите раздел"}><CheckCircle2 size={15} /> Согласовать</button>
                  <button className="button compact primary" type="button" onClick={() => sendToPublication(item)} disabled={itemBusy || !publicationReady} title={publicationReady ? "Согласовать и поставить в очередь публикации" : "Сначала выберите раздел"}><Send size={15} /> В публикацию</button>
                </div>
              ];
            })}
          />
          {reviewError ? <span className="formError">{reviewError}</span> : null}
        </DataPanel>
      ) : null}
      <div className="gridTwo">
        <DataPanel title="Активные задачи">
          <ResponsiveTable
            columns={["Задача", "Гео", "Язык", "Тем", "Статус"]}
            rows={tasks.slice(0, 8).map((task) => [<button className="dashboardTaskLink" type="button" onClick={() => onOpenTask(task)} disabled={!task.site_id} title={task.site_id ? "Открыть задачу в проекте" : "Проект не назначен"}>{task.title}</button>, countryLabel(task.geo), languageLabel(task.language), task.topics_count, <StatusBadge status={task.status} />])}
          />
        </DataPanel>
        <DataPanel title="Очередь публикаций">
          <ResponsiveTable
            columns={["Тема", "Статус", "Время"]}
            rows={content
              .filter((item) => ["scheduled", "retry_scheduled", "publishing"].includes(item.status))
              .slice(0, 8)
              .map((item) => [<ContentTopicLabel item={item} />, <StatusBadge status={item.status} />, item.scheduled_at ? formatDate(item.scheduled_at) : "-"])}
          />
        </DataPanel>
      </div>
      <DataPanel title="Последние ошибки">
        {dashboard.recent_errors.length ? (
          <ResponsiveTable
            columns={["Время", "Endpoint", "Ошибка"]}
            rows={dashboard.recent_errors.map((error) => [formatDate(error.created_at), error.endpoint_url, error.error_message])}
          />
        ) : (
          <EmptyState text="Ошибок пока нет." />
        )}
      </DataPanel>
      {selectedPreview ? (
        <ContentPreviewModal
          item={selectedPreview}
          promptName={selectedPreview.generation_prompt_name}
          onClose={() => setSelectedPreview(null)}
          actions={
            <>
              <button className="button compact" type="button" onClick={() => regenerateReviewItem(selectedPreview)} disabled={actionId.startsWith(selectedPreview.id) || ACTIVE_GENERATION_STATUSES.includes(selectedPreview.status)} title={selectedPreview.competitor_brief ? "Текст будет создан заново с сохранённым анализом конкурентов" : "Текст будет создан заново без анализа конкурентов"}>
                <RefreshCcw size={15} /> {actionId === `${selectedPreview.id}:generate` ? "Запускаю…" : "Сгенерировать заново"}
              </button>
              <button className="button compact danger" type="button" onClick={() => deleteItem(selectedPreview)} disabled={actionId.startsWith(selectedPreview.id)}><Trash2 size={15} /> Удалить</button>
              <button className="button compact approve" type="button" onClick={() => approveItem(selectedPreview)} disabled={actionId.startsWith(selectedPreview.id) || !selectedPreview.section_id}><CheckCircle2 size={15} /> Согласовать</button>
              <button className="button compact primary" type="button" onClick={() => sendToPublication(selectedPreview)} disabled={actionId.startsWith(selectedPreview.id) || !selectedPreview.site_id || !selectedPreview.section_id}><Send size={15} /> В публикацию</button>
            </>
          }
        />
      ) : null}
    </section>
  );
}

const FastProjectOverviewPanel = React.memo(ProjectOverviewPanel);
const FastTasksView = React.memo(TasksView);
const FastProjectContentPanel = React.memo(ProjectContentPanel);
const FastProjectPublicationPanel = React.memo(ProjectPublicationPanel);
const FastProjectMenuPanel = React.memo(ProjectMenuPanel);

function ProjectWorkspaceView({
  api,
  sites,
  providers,
  currentUsername,
  activeTab,
  onTabChange,
  onChanged
}: ViewProps & {
  sites: Site[];
  providers: AiProvider[];
  currentUsername: string;
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab, projectName?: string) => void;
}) {
  const workspaceSiteStorageKey = `workspace_site_id:${currentUsername}`;
  const [selectedSiteId, setSelectedSiteId] = React.useState(() => localStorage.getItem(workspaceSiteStorageKey) || localStorage.getItem("workspace_site_id") || "");
  const [overview, setOverview] = React.useState<SiteOverview | null>(null);
  const [siteTasks, setSiteTasks] = React.useState<Task[]>([]);
  const [siteContent, setSiteContent] = React.useState<ContentItem[]>([]);
  const [sections, setSections] = React.useState<Section[]>([]);
  const [promptTemplates, setPromptTemplates] = React.useState<PromptTemplate[]>([]);
  const [logs, setLogs] = React.useState<PublicationLog[]>([]);
  const [campaigns, setCampaigns] = React.useState<PublicationCampaign[]>([]);
  const [workspaceError, setWorkspaceError] = React.useState("");
  const [canonCopied, setCanonCopied] = React.useState(false);
  const [favoriteSiteIds, setFavoriteSiteIds] = React.useState<string[]>([]);
  const [favoritesOnly, setFavoritesOnly] = React.useState(false);
  const [menuCapabilities, setMenuCapabilities] = React.useState<MenuCapabilities | null>(null);
  const [menuCapabilitiesLoading, setMenuCapabilitiesLoading] = React.useState(false);
  const [menuCapabilitiesError, setMenuCapabilitiesError] = React.useState("");
  const [projectRefreshStatus, setProjectRefreshStatus] = React.useState<"idle" | "loading" | "success" | "error">("idle");
  const [projectRefreshResponseCode, setProjectRefreshResponseCode] = React.useState("");
  const [publicationWorkflowSection, setPublicationWorkflowSection] = React.useState<PublicationWorkspaceSection>("campaigns");
  const projectLoadRequestRef = React.useRef(0);
  const selectedSite = sites.find((site) => site.id === selectedSiteId) || null;
  const routeProjectName = workspaceProjectNameFromPath(window.location.pathname);
  const pendingSectionsCount = sections.filter((section) => section.sync_status === "pending").length;
  const unpublishedGeneratedContentCount = siteContent.filter((item) => Boolean(item.generated_at) && item.status !== "published").length;
  const selectedProjectMedalStatus = menuCapabilities?.checked_at
    ? menuMedalStatus(menuCapabilities.checked_at, menuCapabilities.header_menu_rendered, menuCapabilities.footer_menu_rendered)
    : selectedSite ? projectMenuMedalStatus(selectedSite) : "unchecked";
  const menuCheckPending = menuCapabilities?.check_status === "queued" || menuCapabilities?.check_status === "running";
  const menuCheckError = menuCapabilities?.check_status === "failed"
    ? [menuCapabilities.check_error_code, menuCapabilities.check_error_message].filter(Boolean).join(": ")
    : "";

  React.useLayoutEffect(() => {
    if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, []);

  React.useEffect(() => {
    if (!selectedSiteId) return;
    const saved = window.localStorage.getItem(`publication_workspace_section:${currentUsername}:${selectedSiteId}`) as PublicationWorkspaceSection | null;
    if (saved && ["content", "campaigns", "process", "queue", "backlog"].includes(saved)) setPublicationWorkflowSection(saved);
    else setPublicationWorkflowSection("campaigns");
  }, [currentUsername, selectedSiteId]);

  const openPublicationSection = React.useCallback((section: PublicationWorkspaceSection) => {
    setPublicationWorkflowSection(section);
    if (selectedSiteId) window.localStorage.setItem(`publication_workspace_section:${currentUsername}:${selectedSiteId}`, section);
  }, [currentUsername, selectedSiteId]);

  const loadProject = React.useCallback(async (refreshCapabilities = false) => {
    if (!selectedSiteId) return { success: false, errorCode: "NO_PROJECT" };
    const requestId = projectLoadRequestRef.current + 1;
    projectLoadRequestRef.current = requestId;
    setWorkspaceError("");
    setMenuCapabilitiesLoading(true);
    setMenuCapabilitiesError("");
    const requestResource = async <T,>(path: string): Promise<{ value: T | null; error: string; errorCode: string }> => {
      try {
        return { value: await api<T>(path), error: "", errorCode: "" };
      } catch (error) {
        return {
          value: null,
          error: error instanceof Error ? error.message : "Не удалось загрузить данные",
          errorCode: requestErrorCode(error)
        };
      }
    };
    const [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextLogs, nextCampaigns, nextMenuCapabilities] = await Promise.all([
      requestResource<SiteOverview>(`/sites/${selectedSiteId}/overview`),
      requestResource<Task[]>(`/sites/${selectedSiteId}/tasks`),
      requestResource<ContentItem[]>(`/sites/${selectedSiteId}/content`),
      requestResource<Section[]>(`/sites/${selectedSiteId}/sections`),
      requestResource<PromptTemplate[]>(`/sites/${selectedSiteId}/prompt-templates`),
      requestResource<PublicationLog[]>(`/sites/${selectedSiteId}/publication-logs`),
      requestResource<PublicationCampaign[]>(`/sites/${selectedSiteId}/publication-campaigns`),
      requestResource<MenuCapabilities>(`/sites/${selectedSiteId}/menu-capabilities${refreshCapabilities ? "?refresh=true" : ""}`)
    ]);
    if (requestId !== projectLoadRequestRef.current) return { success: false, errorCode: "CANCELLED" };
    if (nextOverview.value) setOverview(nextOverview.value);
    if (nextTasks.value) setSiteTasks(nextTasks.value);
    if (nextContent.value) setSiteContent(nextContent.value);
    if (nextSections.value) setSections(nextSections.value);
    if (nextPrompts.value) setPromptTemplates(nextPrompts.value);
    if (nextLogs.value) setLogs(nextLogs.value);
    if (nextCampaigns.value) setCampaigns(nextCampaigns.value);
    setMenuCapabilities(nextMenuCapabilities.value);
    setMenuCapabilitiesError(nextMenuCapabilities.error);
    setMenuCapabilitiesLoading(false);
    const dataErrors = [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextLogs, nextCampaigns]
      .map((result) => result.error)
      .filter(Boolean);
    setWorkspaceError(dataErrors.length ? "Не удалось загрузить часть данных проекта. Повторите попытку через несколько секунд." : "");
    const failedResource = [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextLogs, nextCampaigns, nextMenuCapabilities]
      .find((result) => Boolean(result.error));
    return {
      success: !failedResource,
      errorCode: failedResource?.errorCode || ""
    };
  }, [api, selectedSiteId]);

  const openProject = React.useCallback(async () => {
    if (!selectedSiteId) return;
    let cacheError = "";
    try {
      await api<ProjectCacheSyncResult>(`/sites/${selectedSiteId}/cache/refresh`, { method: "POST" });
      await onChanged();
    } catch (error) {
      cacheError = error instanceof Error ? `Не удалось получить свежий кеш проекта: ${error.message}` : "Не удалось получить свежий кеш проекта";
    }
    await loadProject();
    if (cacheError) setWorkspaceError(cacheError);
  }, [api, loadProject, onChanged, selectedSiteId]);

  React.useEffect(() => {
    api<{ site_ids: string[] }>("/me/favorite-sites")
      .then((result) => setFavoriteSiteIds(result.site_ids))
      .catch((error: unknown) => setWorkspaceError(error instanceof Error ? error.message : "Не удалось загрузить избранное"));
  }, [api]);

  React.useEffect(() => {
    if (!selectedSite || !menuCheckPending) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const result = await api<MenuCapabilities>(`/sites/${selectedSite.id}/menu-capabilities`);
        if (cancelled) return;
        setMenuCapabilities(result);
        if (result.check_status === "completed" || result.check_status === "failed") await onChanged();
      } catch (error) {
        if (!cancelled) setMenuCapabilitiesError(error instanceof Error ? error.message : "Не удалось обновить очередь проверки меню");
      }
    };
    const intervalId = window.setInterval(() => void poll(), 2500);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [api, menuCheckPending, onChanged, selectedSite]);

  React.useEffect(() => {
    const routeSite = routeProjectName ? sites.find((site) => site.name === routeProjectName) : null;
    if (routeSite && routeSite.id !== selectedSiteId) {
      setSelectedSiteId(routeSite.id);
      return;
    }
    if (routeProjectName && !routeSite) {
      setSelectedSiteId("");
      return;
    }
    if (selectedSiteId && !sites.some((site) => site.id === selectedSiteId)) {
      localStorage.removeItem(workspaceSiteStorageKey);
      setSelectedSiteId("");
    }
  }, [routeProjectName, selectedSiteId, sites, workspaceSiteStorageKey]);

  React.useEffect(() => {
    if (!selectedSite) return;
    const projectPath = pathForRoute("workspace", activeTab, selectedSite.name);
    if (window.location.pathname !== projectPath) window.history.replaceState(null, "", projectPath);
  }, [activeTab, selectedSite]);

  React.useEffect(() => {
    if (selectedSiteId) {
      localStorage.setItem(workspaceSiteStorageKey, selectedSiteId);
      localStorage.removeItem("workspace_site_id");
      setOverview(null);
      setSiteTasks([]);
      setSiteContent([]);
      setSections([]);
      setPromptTemplates([]);
      setLogs([]);
      setCampaigns([]);
      setMenuCapabilities(null);
      setMenuCapabilitiesLoading(false);
      setMenuCapabilitiesError("");
      setProjectRefreshStatus("idle");
      setProjectRefreshResponseCode("");
      setWorkspaceError("");
      void openProject();
    }
  }, [openProject, selectedSiteId, workspaceSiteStorageKey]);

  const openContentForMenuSection = React.useCallback((section: Section) => {
    if (!selectedSite) return;
    window.sessionStorage.setItem(`workspace_add_content_section:${selectedSite.id}`, section.id);
    onTabChange("topics", selectedSite.name);
  }, [onTabChange, selectedSite]);

  const refreshProject = React.useCallback(async (syncExternal = false) => {
    let changesResult: ProjectChangesSyncResult | null = null;
    if (syncExternal && selectedSite) {
      await api<ProjectCacheSyncResult>("/sites/cache/sync", {
        method: "POST",
        body: JSON.stringify({ names: [selectedSite.name] })
      });
      changesResult = await api<ProjectChangesSyncResult>(`/sites/${selectedSite.id}/sync-changes`, { method: "POST" });
      const refreshedCapabilities = await api<MenuCapabilities>(`/sites/${selectedSite.id}/menu-capabilities`);
      setMenuCapabilities(refreshedCapabilities);
    }
    await onChanged();
    const loaded = await loadProject();
    return {
      success: loaded.success && (!changesResult || changesResult.success),
      errorCode: loaded.errorCode || (changesResult && !changesResult.success ? "TARGET" : ""),
      statusCode: changesResult?.last_status_code ?? null
    };
  }, [api, loadProject, onChanged, selectedSite]);

  const handleProjectRefresh = React.useCallback(async () => {
    if (!selectedSite || projectRefreshStatus === "loading") return;
    setProjectRefreshStatus("loading");
    setProjectRefreshResponseCode("");
    setWorkspaceError("");
    try {
      const result = await refreshProject(true);
      setProjectRefreshStatus(result.success ? "success" : "error");
      setProjectRefreshResponseCode(result.statusCode ? String(result.statusCode) : result.errorCode.replace(/^HTTP\s+/, ""));
    } catch (error) {
      setProjectRefreshStatus("error");
      setProjectRefreshResponseCode(requestErrorCode(error).replace(/^HTTP\s+/, ""));
      setWorkspaceError(error instanceof Error ? error.message : "Не удалось обновить проект");
    }
  }, [projectRefreshStatus, refreshProject, selectedSite]);

  async function retryMenuCapabilities() {
    if (!selectedSite || menuCapabilitiesLoading) return;
    setMenuCapabilitiesLoading(true);
    setMenuCapabilitiesError("");
    try {
      const refreshedCapabilities = await api<MenuCapabilities>(`/sites/${selectedSite.id}/menu-capabilities/check`, { method: "POST" });
      setMenuCapabilities(refreshedCapabilities);
      await onChanged();
    } catch (error) {
      setMenuCapabilitiesError(error instanceof Error ? error.message : "Не удалось проверить меню");
    } finally {
      setMenuCapabilitiesLoading(false);
    }
  }

  async function copyCanon() {
    if (!selectedSite) return;
    await copyTextToClipboard(selectedSite.cache_canon || selectedSite.base_url);
    setCanonCopied(true);
    window.setTimeout(() => setCanonCopied(false), 1600);
  }

  function selectWorkspaceSite(siteId: string) {
    const site = sites.find((candidate) => candidate.id === siteId);
    if (site) {
      const projectPath = pathForRoute("workspace", activeTab, site.name);
      if (window.location.pathname !== projectPath) window.history.pushState(null, "", projectPath);
    }
    setSelectedSiteId(siteId);
  }

  async function toggleSiteFavorite(siteId: string) {
    try {
      const result = await api<{ site_ids: string[] }>(`/me/favorite-sites/${siteId}`, {
        method: favoriteSiteIds.includes(siteId) ? "DELETE" : "PUT"
      });
      setFavoriteSiteIds(result.site_ids);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "Не удалось изменить избранное");
    }
  }

  async function toggleWorkspaceFavorite() {
    if (selectedSite) await toggleSiteFavorite(selectedSite.id);
  }

  if (!sites.length) {
    return <EmptyState text="Сначала добавьте сайт в админском разделе Сайты." />;
  }

  const accordionContextValue = {
    storagePrefix: `${currentUsername}:${selectedSiteId || "no-project"}:${activeTab}`,
    allowPanelCollapse: false
  };

  return (
    <WorkspaceAccordionContext.Provider value={accordionContextValue}>
    <section className="viewStack projectWorkspaceView">
      <DataPanel title={(
        <span className="workspaceProjectTitle">
          {selectedSite ? (
            <button
              className={`workspaceFavoriteButton ${favoriteSiteIds.includes(selectedSite.id) ? "active" : ""}`}
              type="button"
              onClick={toggleWorkspaceFavorite}
              title={favoriteSiteIds.includes(selectedSite.id) ? "Убрать из избранного" : "Добавить в избранное"}
              aria-label={favoriteSiteIds.includes(selectedSite.id) ? "Убрать проект из избранного" : "Добавить проект в избранное"}
            >
              <Star size={22} />
            </button>
          ) : null}
          <strong>{selectedSite?.name || "Выберите проект"}</strong>
          {selectedSite ? <ProjectVerificationMedal status={selectedProjectMedalStatus} /> : null}
          {selectedSite ? (
            <button
              className="workspaceMenuCheckButton"
              type="button"
              onClick={() => void retryMenuCapabilities()}
              disabled={menuCapabilitiesLoading || menuCheckPending}
              title="Точная проверка отображения меню на сайте — Desktop 1440×1000"
              aria-label={`Запустить точную desktop-проверку меню проекта ${selectedSite.name}`}
            >
              <RefreshCcw className={menuCapabilitiesLoading || menuCheckPending ? "spin" : ""} size={15} />
            </button>
          ) : null}
        </span>
      )}>
        <div className="projectHeader">
          <div className="projectPicker">
            <SearchableSelect
              value={selectedSiteId}
              onChange={selectWorkspaceSite}
              options={sites.map((site) => {
                const headerCount = Array.isArray(site.default_menu.header) ? site.default_menu.header.length : 0;
                const footerCount = Array.isArray(site.default_menu.footer) ? site.default_menu.footer.length : 0;
                const menuCount = headerCount + footerCount;
                const searchOption = projectSearchOption(site);
                return {
                  ...searchOption,
                  keywords: `${searchOption.keywords || ""} ${site.is_test_project ? "тестовый проект" : ""}`,
                  description: menuCount
                    ? `Пунктов меню: ${menuCount} · Header: ${headerCount} · Footer: ${footerCount}`
                    : "Пункты меню отсутствуют",
                  badge: site.is_test_project ? "Тестовый проект" : undefined,
                  tone: site.is_test_project ? "test" as const : site.has_menu ? "menu" as const : undefined
                };
              })}
              showSelectedIndicator={false}
              searchPlaceholder="Найти проект"
              optionPredicate={(option) => !favoritesOnly || favoriteSiteIds.includes(option.value)}
              dropdownToolbar={(
                <button
                  className={`searchableSelectFavoritesFilter ${favoritesOnly ? "active" : ""}`}
                  type="button"
                  onClick={() => setFavoritesOnly((current) => !current)}
                  aria-pressed={favoritesOnly}
                >
                  <Star size={16} fill={favoritesOnly ? "currentColor" : "none"} />
                  {favoritesOnly ? "Показаны избранные" : "Только избранные"}
                  <span>{favoriteSiteIds.length}</span>
                </button>
              )}
              renderOptionAction={(option) => {
                const favorite = favoriteSiteIds.includes(option.value);
                return (
                  <button
                    className={`searchableSelectFavoriteButton ${favorite ? "active" : ""}`}
                    type="button"
                    onClick={() => toggleSiteFavorite(option.value)}
                    title={favorite ? "Убрать из избранного" : "Добавить в избранное"}
                    aria-label={favorite ? `Убрать ${option.label} из избранного` : `Добавить ${option.label} в избранное`}
                  >
                    <Star size={17} fill={favorite ? "currentColor" : "none"} />
                  </button>
                );
              }}
            />
          </div>
          <div className="projectMeta">
            {selectedSite ? (
              <>
                <div className="projectTopDetails">
                  <span>
                    <small>Main</small>
                    <span className="projectCanonValue">
                      <AutoFitDomain value={selectedSite.cache_canon || selectedSite.base_url} />
                      <span className="projectCanonActions">
                        <a className="projectCanonOpenButton" href={selectedSite.base_url} target="_blank" rel="noreferrer" title="Перейти на сайт" aria-label={`Перейти на сайт ${selectedSite.cache_canon || selectedSite.base_url}`}>
                          <ExternalLink size={14} />
                        </a>
                        <button className="projectCanonCopyButton" type="button" onClick={copyCanon} title={canonCopied ? "Скопировано" : "Копировать"} aria-label="Копировать адрес MAIN">
                          {canonCopied ? <CheckCircle2 size={14} /> : <Copy size={14} />}
                        </button>
                        <a
                          className="projectUniversalAdminButton"
                          href={`https://johnny.g4fj2fhghgwg.top/projects/${encodeURIComponent(selectedSite.name)}`}
                          target="_blank"
                          rel="noreferrer"
                          title="Универсальная админка"
                          aria-label={`Открыть универсальную админку проекта ${selectedSite.name}`}
                        >
                          <MonitorCog size={14} />
                        </a>
                      </span>
                    </span>
                  </span>
                  <span className="projectTitleCard"><small>Title</small><b title={selectedSite.homepage_title || "Title не указан"}>{selectedSite.homepage_title || "—"}</b></span>
                  <span className="projectMetricCard"><small>Доменов в сетке</small><b>{formatNumber(selectedSite.domains_count)}</b></span>
                  <span className="projectMetricCard"><small>Страниц</small><b>{formatNumber(selectedSite.internal_pages_count)}</b></span>
                  <MenuCapabilityCard label="Header" templateRendered={menuCapabilities?.header_menu_template_rendered} rendered={menuCapabilities?.header_menu_rendered} nested={menuCapabilities?.header_menu_nested} icon="header" loading={menuCapabilitiesLoading || menuCheckPending} error={menuCapabilitiesError || menuCheckError} />
                  <MenuCapabilityCard label="Footer" templateRendered={menuCapabilities?.footer_menu_template_rendered} rendered={menuCapabilities?.footer_menu_rendered} nested={menuCapabilities?.footer_menu_nested} icon="footer" loading={menuCapabilitiesLoading || menuCheckPending} error={menuCapabilitiesError || menuCheckError} />
                </div>
              </>
            ) : null}
          </div>
          <button className={`button secondary projectRefreshButton ${projectRefreshStatus === "success" ? "isSuccess" : projectRefreshStatus === "error" ? "isError" : ""}`} type="button" onClick={() => void handleProjectRefresh()} disabled={!selectedSite || projectRefreshStatus === "loading"}>
            <span className="projectRefreshButtonLabel">
              <span className={`buttonRefreshIcon ${projectRefreshStatus === "loading" ? "isLoading" : projectRefreshStatus === "error" ? "isError" : ""}`}>
                {projectRefreshStatus === "success" ? <SquareCheckBig size={15} /> : projectRefreshStatus === "error" ? <CircleAlert size={15} /> : <RefreshCcw size={15} />}
              </span>
              {projectRefreshStatus === "loading" ? "Обновление" : projectRefreshStatus === "success" ? "Готово" : projectRefreshStatus === "error" ? "Ошибка" : "Обновить проект"}
            </span>
            {selectedSite ? <span className="projectRefreshMeta"><small title={selectedSite.cache_server_host || "Сервер не указан"}>{selectedSite.cache_server_host || "—"}</small>{projectRefreshStatus === "success" || projectRefreshStatus === "error" ? <em className={projectRefreshStatus === "success" ? "success" : ""}>Status Code: {projectRefreshResponseCode || "UNKNOWN"}</em> : null}</span> : null}
          </button>
        </div>
        {selectedSite ? (
          <div className="projectUpdatedAt">
            <CalendarClock size={20} />
            <span>Последнее обновление</span>
            <strong>{selectedSite.cache_synced_at ? formatDate(selectedSite.cache_synced_at) : "не выполнялось"}</strong>
            <b className={pendingSectionsCount ? "pending" : "synced"}>
              {pendingSectionsCount ? `Не синхронизировано: ${pendingSectionsCount}` : "Синхронизировано"}
            </b>
          </div>
        ) : null}
        {selectedSite && selectedProjectMedalStatus === "missing" ? (
          <div className="projectMenuImplementationWarning" role="status">
            <AlertTriangle size={20} />
            <div>
              <strong>Рендеринг меню не реализован на сайте</strong>
              <span>Необходимо обратиться к веб-разработчику для добавления рендеринга меню на сайт.</span>
            </div>
          </div>
        ) : null}
        <div className="workspaceTabs">
          <TabButton
            href={pathForRoute("workspace", "overview", selectedSite?.name)}
            icon={<span className="tabButtonIcon overview" aria-hidden="true"><Search size={15} /></span>}
            label="Обзор"
            active={activeTab === "overview"}
            onClick={() => onTabChange("overview", selectedSite?.name)}
          />
          <TabButton
            href={pathForRoute("workspace", "topics", selectedSite?.name)}
            icon={<span className="tabButtonIcon ai" aria-hidden="true"><Brain size={17} /></span>}
            label="Генерация"
            active={activeTab === "topics"}
            onClick={() => onTabChange("topics", selectedSite?.name)}
          />
          <TabButton
            href={pathForRoute("workspace", "content", selectedSite?.name)}
            icon={<span className="tabButtonIcon document" aria-hidden="true"><FileText size={15} /></span>}
            label={unpublishedGeneratedContentCount ? `Контент и публикация (${unpublishedGeneratedContentCount})` : "Контент и публикация"}
            active={activeTab === "content" || activeTab === "publication"}
            onClick={() => onTabChange("content", selectedSite?.name)}
          />
          <TabButton
            href={pathForRoute("workspace", "menu", selectedSite?.name)}
            icon={<span className="tabButtonIcon menu" aria-hidden="true"><Menu size={16} /></span>}
            label={pendingSectionsCount ? `Меню (${pendingSectionsCount})` : "Меню"}
            active={activeTab === "menu"}
            attention={pendingSectionsCount > 0}
            onClick={() => onTabChange("menu", selectedSite?.name)}
          />
        </div>
        {workspaceError ? <div className="notice">{workspaceError}</div> : null}
      </DataPanel>

      {selectedSite && (activeTab === "content" || activeTab === "publication") ? (
        <PublicationWorkflowNav
          content={siteContent}
          campaigns={campaigns}
          activeSection={publicationWorkflowSection}
          onSectionChange={openPublicationSection}
        />
      ) : null}

      {!selectedSite ? (
        <div className="workspaceProjectEmpty">
          <span className="workspaceProjectEmptyIcon"><FolderKanban size={34} /></span>
          <div>
            <h2>Выберите проект</h2>
            <p>Выберите проект в поле выше, чтобы открыть рабочий экран. Последний активный проект сохранится для вашего пользователя.</p>
          </div>
        </div>
      ) : null}

      {selectedSite ? (
        <>
          <WorkspaceTabPane active={activeTab === "overview"} storagePrefix={`${currentUsername}:${selectedSite.id}:overview`}>
            {overview ? <FastProjectOverviewPanel key={selectedSite.id} overview={overview} content={siteContent} sections={sections} logs={logs} /> : null}
          </WorkspaceTabPane>
          <WorkspaceTabPane active={activeTab === "topics"} storagePrefix={`${currentUsername}:${selectedSite.id}:topics`}>
            <FastTasksView
              key={selectedSite.id}
              api={api}
              sites={sites}
              providers={providers}
              tasks={siteTasks}
              fixedSite={selectedSite}
              onProjectChange={setSelectedSiteId}
              sections={sections}
              promptTemplates={promptTemplates}
              onChanged={refreshProject}
            />
          </WorkspaceTabPane>
          <WorkspaceTabPane active={activeTab === "content" || activeTab === "publication"} storagePrefix={`${currentUsername}:${selectedSite.id}:content`}>
            {publicationWorkflowSection === "campaigns" ? <>
              <FastProjectPublicationPanel key={`${selectedSite.id}:publication-launch`} mode="launch" api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} logs={logs} onChanged={refreshProject} />
              <FastProjectPublicationPanel key={`${selectedSite.id}:publication-campaigns`} mode="campaigns" api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} logs={logs} onChanged={refreshProject} />
            </> : null}
            {publicationWorkflowSection === "content" ? <FastProjectContentPanel key={`${selectedSite.id}:content`} api={api} site={selectedSite} content={siteContent} sections={sections} onChanged={refreshProject} /> : null}
            {publicationWorkflowSection !== "content" && publicationWorkflowSection !== "campaigns" ? (
              <FastProjectPublicationPanel key={`${selectedSite.id}:publication-workflow`} mode="workflow" workflowSection={publicationWorkflowSection} api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} logs={logs} onChanged={refreshProject} />
            ) : null}
          </WorkspaceTabPane>
          <WorkspaceTabPane active={activeTab === "menu"} storagePrefix={`${currentUsername}:${selectedSite.id}:menu`}>
            <FastProjectMenuPanel api={api} site={selectedSite} sections={sections} content={siteContent} menuCapabilities={menuCapabilities} onAddContent={openContentForMenuSection} onChanged={refreshProject} />
          </WorkspaceTabPane>
        </>
      ) : null}
    </section>
    </WorkspaceAccordionContext.Provider>
  );
}

function WorkspaceTabPane({ active, storagePrefix, children }: { active: boolean; storagePrefix: string; children: React.ReactNode }) {
  const accordionContextValue = React.useMemo(() => ({ storagePrefix, allowPanelCollapse: false }), [storagePrefix]);
  if (!active) return null;
  return (
    <WorkspaceAccordionContext.Provider value={accordionContextValue}>
      <div className="workspaceTabPane">{children}</div>
    </WorkspaceAccordionContext.Provider>
  );
}

function AutoFitDomain({ value }: { value: string }) {
  const domainRef = React.useRef<HTMLElement>(null);

  React.useLayoutEffect(() => {
    const domain = domainRef.current;
    if (!domain) return;
    const fit = () => {
      let fontSize = 13;
      domain.style.fontSize = `${fontSize}px`;
      while ((domain.scrollHeight > domain.clientHeight + 1 || domain.scrollWidth > domain.clientWidth + 1) && fontSize > 9) {
        fontSize -= 0.5;
        domain.style.fontSize = `${fontSize}px`;
      }
    };
    fit();
    const observer = new ResizeObserver(fit);
    if (domain.parentElement) observer.observe(domain.parentElement);
    return () => observer.disconnect();
  }, [value]);

  return <b ref={domainRef} className="projectCanonDomain" title={value}>{value}</b>;
}

function MenuCapabilityCard({ label, templateRendered, rendered, nested, icon, loading, error }: { label: string; templateRendered: boolean | null | undefined; rendered: boolean | null | undefined; nested: boolean | null | undefined; icon: "header" | "footer"; loading: boolean; error: string }) {
  const statusText = loading ? "Проверяем" : error ? "Ошибка сервера" : rendered == null ? "Не проверено" : rendered ? "Меню реализовано" : "Меню не реализовано";
  const renderingDetails = rendered === false
    ? templateRendered ? "Шаблон поддерживает меню, но на сайте оно не отображается" : "В шаблоне и на сайте меню не отображается"
    : rendered ? nested ? "Вложенность поддерживается" : "Только один уровень" : "";
  return (
    <span className={`projectMenuCapability ${error ? "isError" : rendered === true ? "isReady" : rendered === false ? "isMissing" : "isChecking"}`} title={error || `${label}: ${statusText}${renderingDetails ? `. ${renderingDetails}` : ""}`}>
      <span className="projectMenuCapabilityHeader">
        <small>{label}</small>
      </span>
      <span className="projectMenuCapabilityValue">
        {rendered === true ? <MenuReadyMedal /> : rendered === false ? <MenuReadyMedal tone="red" /> : icon === "header" ? <HeaderMenuIcon /> : <FooterMenuIcon />}
        <b>{statusText}</b>
      </span>
      {error ? <em className="projectMenuCapabilityError">{error}</em> : rendered ? <em>{nested ? "Есть вложенность" : "Один уровень"}</em> : rendered === false ? <em>Не отображается на сайте</em> : null}
    </span>
  );
}

function MenuReadyMedal({ tone = "green" }: { tone?: "green" | "red" | "gold" }) {
  return (
    <svg className={`menuReadyMedal ${tone === "red" ? "isRed" : tone === "gold" ? "isGold" : ""}`} viewBox="0 0 48 52" aria-hidden="true">
      <defs>
        <linearGradient id="menuReadyRibbon" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#2eaa61" /><stop offset="1" stopColor="#09612e" /></linearGradient>
        <linearGradient id="menuReadyFace" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f2fff6" /><stop offset="1" stopColor="#aee9c4" /></linearGradient>
        <filter id="menuReadyShadow" x="-40%" y="-40%" width="180%" height="200%"><feDropShadow dx="0" dy="3" stdDeviation="2.5" floodColor="#063d21" floodOpacity=".28" /></filter>
      </defs>
      <path d="m13 31-3 18 14-8V30zM35 31l3 18-14-8V30z" fill="url(#menuReadyRibbon)" />
      <g filter="url(#menuReadyShadow)"><circle cx="24" cy="22" r="18" fill="#15713b" /><circle cx="24" cy="22" r="14" fill="url(#menuReadyFace)" stroke="#63bd82" /><path d="m16 22 5 5 11-12" fill="none" stroke="#126d38" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" /></g>
    </svg>
  );
}

function ProjectOverviewPanel({ overview, content, sections, logs }: { overview: SiteOverview; content: ContentItem[]; sections: Section[]; logs: PublicationLog[] }) {
  return (
    <section className="viewStack">
      <div className="kpiGrid projectKpis">
        <KpiCard icon={<ListChecks />} label="Задачи" value={overview.stats.tasks} />
        <KpiCard icon={<FileText />} label="Generated" value={overview.stats.generated} />
        <KpiCard icon={<CheckCircle2 />} label="Approved" value={overview.stats.approved} />
        <KpiCard icon={<CalendarClock />} label="Scheduled" value={overview.stats.scheduled} />
        <KpiCard icon={<Activity />} label="Published" value={overview.stats.published} />
        <KpiCard icon={<AlertTriangle />} label="Ошибки" value={overview.stats.failed} danger />
      </div>
      <div className="gridTwo">
        <DataPanel title="Последний контент">
          <ResponsiveTable
            columns={["Тема", "Меню", "Статус", "Дата"]}
            rows={content.slice(0, 8).map((item) => [
              <TopicMetaCell item={item} />,
              sectionLabel(item.section_id, sections),
              <StatusBadge status={item.status} />,
              item.published_at ? formatDate(item.published_at) : formatDate(item.updated_at)
            ])}
          />
        </DataPanel>
        <DataPanel title="Публикационные логи">
          <ResponsiveTable
            columns={["Время", "Статус", "Endpoint"]}
            rows={logs.slice(0, 8).map((log) => [
              formatDate(log.created_at),
              log.error_message || log.response_status || "-",
              log.endpoint_url
            ])}
          />
        </DataPanel>
      </div>
    </section>
  );
}

function useSimulatedOperationProgress(active: boolean) {
  const [progress, setProgress] = React.useState(0);
  React.useEffect(() => {
    if (!active) return;
    const intervalId = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 94) return 94;
        const increment = current < 30 ? 4 : current < 65 ? 2 : 1;
        return Math.min(94, current + increment);
      });
    }, 420);
    return () => window.clearInterval(intervalId);
  }, [active]);
  return [progress, setProgress] as const;
}

function CircularOperationProgress({ value }: { value: number }) {
  const normalizedValue = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <span
      className={`circularOperationProgress ${normalizedValue === 100 ? "complete" : ""}`}
      style={{ "--operation-progress": `${normalizedValue * 3.6}deg` } as React.CSSProperties}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={normalizedValue}
    >
      <i>{normalizedValue}</i>
    </span>
  );
}

function ProjectTopicsPanel({ api, site, providers, sections, promptTemplates, tasks, onChanged }: ViewProps & { site: Site; providers: AiProvider[]; sections: Section[]; promptTemplates: PromptTemplate[]; tasks: Task[] }) {
  const [title, setTitle] = React.useState("");
  const [geo, setGeo] = React.useState(() => projectGeoCode(site));
  const [language, setLanguage] = React.useState(() => projectLanguageCode(site));
  const [targetWords, setTargetWords] = React.useState(DEFAULT_TARGET_WORDS);
  const [topics, setTopics] = React.useState("");
  const [providerId, setProviderId] = React.useState("");
  const [promptTemplateId, setPromptTemplateId] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [shortcode, setShortcode] = React.useState("");
  const [collectCompetitors, setCollectCompetitors] = React.useState(false);
  const [includeCasinoRating, setIncludeCasinoRating] = React.useState(false);
  const [generatingTopics, setGeneratingTopics] = React.useState(false);
  const [topicGenerationProgress, setTopicGenerationProgress] = useSimulatedOperationProgress(generatingTopics);
  const [formError, setFormError] = React.useState("");
  const [taskDetails, setTaskDetails] = React.useState<TaskDetails | null>(null);
  const [taskResearch, setTaskResearch] = React.useState<CompetitorResearch[]>([]);
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [detailsError, setDetailsError] = React.useState("");
  const [detailsLoadingId, setDetailsLoadingId] = React.useState("");
  const [researchAction, setResearchAction] = React.useState("");
  const topicCount = topics.split("\n").map((line) => line.trim()).filter(Boolean).length;
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === promptTemplateId) || defaultPromptTemplate(promptTemplates);

  React.useEffect(() => {
    setGeo(projectGeoCode(site));
    setLanguage(projectLanguageCode(site));
  }, [site.id, site.cache_geo, site.cache_language, site.cache_canon]);

  React.useEffect(() => {
    const generationProviders = providers.filter(isGenerationProvider);
    if (!providerId || !generationProviders.some((provider) => provider.id === providerId)) {
      const geminiProvider = generationProviders.find((provider) => provider.provider_type === "gemini" && provider.is_active);
      setProviderId(geminiProvider?.id || "");
    }
  }, [providerId, providers]);

  React.useEffect(() => {
    if (!promptTemplateId && promptTemplates.length) {
      setPromptTemplateId(defaultPromptTemplate(promptTemplates)?.id || "");
    }
  }, [promptTemplateId, promptTemplates]);

  async function generateTopicsWithGemini() {
    setFormError("");
    if (topicCount > 20) {
      setFormError("Чтобы добавить ещё 10 тем, оставьте в форме не более 20 тем.");
      return;
    }
    const provider = providers.find((item) => item.id === providerId);
    if (!provider || provider.provider_type !== "gemini" || !provider.is_active) {
      setFormError("Для генерации тем выберите активный Gemini provider.");
      return;
    }
    setTopicGenerationProgress(3);
    setGeneratingTopics(true);
    try {
      const response = await api<TopicSuggestionsResponse>(`/sites/${site.id}/topic-suggestions`, {
        method: "POST",
        body: JSON.stringify({
          geo,
          language,
          ai_provider_id: provider.id,
          section_id: sectionId || null,
          current_topics: topics.split("\n").map((line) => line.trim()).filter(Boolean)
        })
      });
      const currentTopics = topics.split("\n").map((line) => line.trim()).filter(Boolean);
      setTopics([...currentTopics, ...response.topics].join("\n"));
      setTopicGenerationProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    } catch (error) {
      setTopicGenerationProgress(0);
      setFormError(error instanceof Error ? error.message : "Gemini не смог сгенерировать уникальные темы.");
    } finally {
      setGeneratingTopics(false);
      window.setTimeout(() => setTopicGenerationProgress(0), 120);
    }
  }

  async function createTask(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    const cleanTopics = topics.split("\n").map((line) => line.trim()).filter(Boolean);
    if (!cleanTopics.length) {
      setFormError("Добавьте хотя бы одну тему.");
      return;
    }
    if (cleanTopics.length > 30) {
      setFormError("За одну генерацию можно отправить от 1 до 30 тем.");
      return;
    }
    const task = await api<Task>(`/sites/${site.id}/tasks`, {
      method: "POST",
      body: JSON.stringify({
        title: title.trim() || `${site.name}: генерация ${new Date().toLocaleDateString("ru-RU")}`,
        geo,
        language,
        target_words: targetWords || null,
        section_id: sectionId || null,
        ai_provider_id: providerId || null,
        payload_mode: "site_default",
        prompt_template_name: selectedPrompt?.name || null,
        prompt_template: selectedPrompt?.content || null,
        shortcode: shortcode.trim() || null,
        include_toc: true,
        include_faq: true,
        collect_competitors: collectCompetitors,
        include_casino_rating: includeCasinoRating,
        topics: cleanTopics
      })
    });
    if (!collectCompetitors) {
      await api(`/tasks/${task.id}/generate`, { method: "POST" });
    }
    await openTaskDetails(task.id);
    setTitle("");
    setTopics("");
    setShortcode("");
    await onChanged();
  }

  async function openTaskDetails(taskId: string) {
    setDetailsError("");
    setDetailsLoadingId(taskId);
    try {
      const details = await api<TaskDetails>(`/tasks/${taskId}`);
      setTaskDetails(details);
      setSelectedPreview(details.items[0] || null);
      await refreshTaskResearch(taskId);
    } catch (error) {
      setDetailsError(error instanceof Error ? error.message : "Не удалось открыть задачу.");
    } finally {
      setDetailsLoadingId("");
    }
  }

  async function refreshTaskResearch(taskId = taskDetails?.task.id) {
    if (!taskId) return;
    const research = await api<CompetitorResearch[]>(`/tasks/${taskId}/competitor-research`);
    setTaskResearch(research);
  }

  async function runResearchAction(contentItemId: string, action: "save" | "serp" | "pages" | "brief" | "generate", queries?: string[]) {
    setDetailsError("");
    setResearchAction(`${contentItemId}:${action}`);
    try {
      if (action === "save") {
        await api(`/content/${contentItemId}/competitor-queries`, {
          method: "PUT",
          body: JSON.stringify({ queries: (queries || []).map((query) => query.trim()).filter(Boolean) })
        });
      } else if (action === "serp") {
        await api(`/content/${contentItemId}/competitor-serp`, { method: "POST" });
      } else if (action === "pages") {
        await api(`/content/${contentItemId}/competitor-pages`, { method: "POST" });
      } else if (action === "brief") {
        await api(`/content/${contentItemId}/competitor-brief`, { method: "POST" });
      } else {
        await api(`/content/${contentItemId}/generate`, { method: "POST" });
      }
      await refreshTaskResearch();
      if (taskDetails) {
        const updated = await api<TaskDetails>(`/tasks/${taskDetails.task.id}`);
        setTaskDetails(updated);
      }
    } catch (error) {
      setDetailsError(error instanceof Error ? error.message : "Не удалось выполнить действие с конкурентами.");
    } finally {
      setResearchAction("");
    }
  }

  async function generateOpenedTask() {
    if (!taskDetails) return;
    setDetailsError("");
    setResearchAction(`${taskDetails.task.id}:generate`);
    try {
      await api(`/tasks/${taskDetails.task.id}/generate`, { method: "POST" });
      await openTaskDetails(taskDetails.task.id);
      await onChanged();
    } catch (error) {
      setDetailsError(error instanceof Error ? error.message : "Не удалось запустить генерацию.");
    } finally {
      setResearchAction("");
    }
  }

  return (
    <section className="viewStack">
      <DataPanel title="Загрузить темы и сгенерировать">
        <form className="formGrid" onSubmit={createTask}>
          <label>
            Название задачи
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={`${site.name}: batch`} />
          </label>
          <label>
            Пункт меню
            <SearchableSelect
              value={sectionId}
              onChange={setSectionId}
              options={[{ value: "", label: "Выбрать позже" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
              searchPlaceholder="Найти пункт меню"
            />
          </label>
          <label>
            Страна
            <SearchableSelect
              value={geo}
              onChange={setGeo}
              options={COUNTRIES.map((country) => ({ value: country.code, label: `${country.flag} ${country.name} (${country.code})` }))}
              searchPlaceholder="Введите страну или код"
            />
          </label>
          <label>
            Язык
            <SearchableSelect
              value={language}
              onChange={setLanguage}
              options={LANGUAGE_OPTIONS.map((option) => ({ value: option.code, label: `${option.flag} ${option.nativeName} (${option.code.toUpperCase()})`, keywords: option.name }))}
              searchPlaceholder="Введите язык или код"
            />
          </label>
          <label>
            Количество слов
            <input value={targetWords} onChange={(event) => setTargetWords(Number(event.target.value))} type="number" min={300} max={8000} step={100} required />
          </label>
          <label>
            AI Provider
            <SearchableSelect
              value={providerId}
              onChange={setProviderId}
              options={[{ value: "", label: "Stub generator" }, ...providers.filter(isGenerationProvider).map((provider) => ({ value: provider.id, label: provider.name }))]}
              searchPlaceholder="Найти AI Provider"
            />
          </label>
          <label>
            Промпт генерации
            <SearchableSelect
              value={promptTemplateId}
              onChange={setPromptTemplateId}
              options={promptTemplates.map((prompt) => ({ value: prompt.id, label: `${prompt.is_default ? "Default · " : ""}${prompt.name}` }))}
              searchPlaceholder="Найти промпт"
            />
          </label>
          <label>
            Shortcode
            <input value={shortcode} onChange={(event) => setShortcode(event.target.value)} placeholder="showcase-redesign" />
          </label>
          <label className="checkboxRow wide">
            <input checked={collectCompetitors} onChange={(event) => setCollectCompetitors(event.target.checked)} type="checkbox" />
            Собрать конкурентов
          </label>
          <label className="checkboxRow wide casinoRatingOption">
            <input checked={includeCasinoRating} onChange={(event) => setIncludeCasinoRating(event.target.checked)} type="checkbox" />
            <span><b>Собрать рейтинг казино</b><small>Добавит в промпт тематический рейтинг из 5–10 казино с оценками и обоснованием мест.</small></span>
          </label>
          <label className="wide">
            <span className="topicFieldHeader">
              <span>Темы, каждая с новой строки</span>
              <button
                className="button compact topicGenerateButton"
                type="button"
                onClick={generateTopicsWithGemini}
                disabled={generatingTopics || topicCount > 20}
                title={topicCount > 20 ? "Для добавления 10 тем в форме должно быть не более 20 тем" : "Добавить 10 уникальных тем через Gemini"}
              >
                {generatingTopics ? <CircularOperationProgress value={topicGenerationProgress} /> : <Sparkles size={15} />}
                {generatingTopics ? "Генерация тем" : "Сгенерировать 10 тем"}
              </button>
            </span>
            <textarea
              value={topics}
              onChange={(event) => setTopics(event.target.value)}
              rows={10}
              required
              placeholder={"Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich\nLegale Online Casinos in Deutschland: Anbieter mit GGL-Lizenz\nBeste Online Spielotheken in Deutschland: Sichere Slots mit Lizenz"}
            />
            <span className={topicCount > 30 ? "fieldHint danger" : "fieldHint"}>{topicCount}/30 тем</span>
          </label>
          {formError ? <span className="formError wide">{formError}</span> : null}
          <div className="formActions wide">
            <button className="button primary" type="submit">
              <span className="buttonPlusIcon"><Plus size={15} /></span> {collectCompetitors ? "Создать и перейти к запросам" : "Создать и сгенерировать"}
            </button>
          </div>
        </form>
      </DataPanel>
      <DataPanel title="Задачи проекта">
        <ResponsiveTable
          columns={["Задача", "Тем", "Страна", "Язык", "Слова", "Промпт", "Статус", "Действие"]}
          rows={tasks.map((task) => [
            task.title,
            task.topics_count,
            countryLabel(task.geo),
            languageLabel(task.language),
            task.target_words || "-",
            <PromptBadge name={task.prompt_template_name} />,
            <StatusBadge status={task.status} />,
            <button className="button compact" type="button" onClick={() => openTaskDetails(task.id)} disabled={detailsLoadingId === task.id}>
              <FileText size={15} />
              {detailsLoadingId === task.id ? "Открываю" : "Открыть"}
            </button>
          ])}
        />
        {detailsError ? <span className="formError">{detailsError}</span> : null}
      </DataPanel>
      {taskDetails ? (
        <DataPanel title={`Заявка на генерацию: ${taskDetails.task.title}`}>
          <div className="taskDetailGrid">
            <div><span>Статус</span><StatusBadge status={taskDetails.task.status} /></div>
            <div><span>Страна</span><strong>{countryLabel(taskDetails.task.geo)}</strong></div>
            <div><span>Язык</span><strong>{languageLabel(taskDetails.task.language)}</strong></div>
            <div><span>Слов</span><strong>{taskDetails.task.target_words || "-"}</strong></div>
            <div><span>Тем</span><strong>{taskDetails.task.topics_count}</strong></div>
            <div><span>Промпт</span><PromptBadge name={taskDetails.task.prompt_template_name} /></div>
          </div>
          {taskDetails.task.collect_competitors ? (
            <CompetitorResearchWorkflow
              items={taskDetails.items}
              research={taskResearch}
              actionId={researchAction}
              onAction={runResearchAction}
              onGenerateAll={generateOpenedTask}
            />
          ) : null}
          <div className="gridTwo">
            <div className="subPanel">
              <h3 className="subPanelTitle"><ListChecks size={18} /> Темы и результаты</h3>
              <ResponsiveTable
                columns={["Тема", "Slug", "Слова", "Статус", "Просмотр"]}
                rows={taskDetails.items.map((item) => [
                  <TopicMetaCell item={item} promptName={taskDetails.task.prompt_template_name} />,
                  item.slug,
                  item.word_count,
                  <StatusBadge status={item.status} />,
                  <button className="button compact" type="button" onClick={() => setSelectedPreview(item)}><FileText size={15} /> Текст</button>
                ])}
              />
            </div>
            <div className="subPanel">
              <h3 className="subPanelTitle"><Edit3 size={18} /> Промпт задачи</h3>
              <textarea className="promptSnapshot" value={taskDetails.task.prompt_template || ""} readOnly rows={16} />
            </div>
          </div>
        </DataPanel>
      ) : null}
      {selectedPreview ? (
        <ContentPreviewModal
          item={selectedPreview}
          promptName={taskDetails?.task.prompt_template_name}
          onClose={() => setSelectedPreview(null)}
        />
      ) : null}
    </section>
  );
}

function CompetitorResearchWorkflow({
  items,
  research,
  actionId,
  onAction,
  onGenerateAll
}: {
  items: ContentItem[];
  research: CompetitorResearch[];
  actionId: string;
  onAction: (contentItemId: string, action: "save" | "serp" | "pages" | "brief" | "generate", queries?: string[]) => Promise<void>;
  onGenerateAll: () => Promise<void>;
}) {
  const byItem = new Map(research.map((item) => [item.content_item_id, item]));
  const allBriefReady = items.length > 0 && items.every((item) => byItem.get(item.id)?.brief);
  const generatingAll = actionId.endsWith(":generate") && !items.some((item) => actionId.startsWith(item.id));
  return (
    <div className="competitorWorkflow">
      <div className="workflowSteps">
        {["Темы", "Запросы", "Конкуренты", "Анализ", "Генерация", "Просмотр и approve"].map((step, index) => (
          <span key={step} className="workflowStep">{index + 1}. {step}</span>
        ))}
      </div>
      <div className="promptHelp">
        Перед генерацией проверь запросы, собери TOP-5 URL, спарси страницы и собери brief. В Gemini уйдет brief, а не сырой HTML.
      </div>
      <div className="competitorCards">
        {items.map((item) => (
          <CompetitorResearchCard
            key={item.id}
            item={item}
            research={byItem.get(item.id)}
            actionId={actionId}
            onAction={onAction}
          />
        ))}
      </div>
      <div className="formActions">
        <button className="button primary" type="button" onClick={onGenerateAll} disabled={!allBriefReady || generatingAll}>
          <Play size={18} /> {generatingAll ? "Генерация" : "Сгенерировать все тексты"}
        </button>
        {!allBriefReady ? <span className="fieldHint">Кнопка станет доступна, когда brief будет готов по каждой теме.</span> : null}
      </div>
    </div>
  );
}

function CompetitorResearchCard({
  item,
  research,
  actionId,
  onAction
}: {
  item: ContentItem;
  research?: CompetitorResearch;
  actionId: string;
  onAction: (contentItemId: string, action: "save" | "serp" | "pages" | "brief" | "generate", queries?: string[]) => Promise<void>;
}) {
  const [queryDraft, setQueryDraft] = React.useState("");
  React.useEffect(() => {
    setQueryDraft((research?.queries || []).map((query) => query.query).join("\n"));
  }, [research?.queries]);

  const busy = actionId.startsWith(item.id);
  const activeAction = busy ? actionId.split(":")[1] : "";
  const pagesOk = (research?.pages || []).filter((page) => (page.http_status || 0) >= 200 && (page.http_status || 0) < 400 && page.word_count > 0).length;
  const brief = research?.brief || item.competitor_brief;
  const queryLines = queryDraft.split("\n").map((line) => line.trim()).filter(Boolean);
  return (
    <article className="competitorCard">
      <div className="competitorCardHeader">
        <div>
          <span className="fieldHint">Тема</span>
          <strong><ContentTopicLabel item={item} /></strong>
          <div className="topicMeta">
            <StatusBadge status={research?.status || item.competitor_research_status || "not_requested"} />
            <span>{research?.results.length || 0} URL</span>
            <span>{pagesOk}/{research?.pages.length || 0} страниц</span>
          </div>
        </div>
        <button className="button compact" type="button" onClick={() => onAction(item.id, "generate")} disabled={!brief || busy}>
          <Play size={15} /> {activeAction === "generate" ? "Генерация" : "Сгенерировать текст"}
        </button>
      </div>
      <div className="researchGrid">
        <label>
          Запросы для Google
          <textarea value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} rows={4} placeholder="2-3 запроса, каждый с новой строки" />
          <span className={queryLines.length > 5 ? "fieldHint danger" : "fieldHint"}>{queryLines.length}/5 запросов</span>
        </label>
        <div className="researchActions">
          <button className="button compact" type="button" onClick={() => onAction(item.id, "save", queryLines)} disabled={busy || !queryLines.length}>
            <Edit3 size={15} /> {activeAction === "save" ? "Сохраняю" : "Сохранить запросы"}
          </button>
          <button className="button compact" type="button" onClick={() => onAction(item.id, "serp")} disabled={busy || !queryLines.length}>
            <Globe2 size={15} /> {activeAction === "serp" ? "Собираю" : "Собрать выдачу"}
          </button>
          <button className="button compact" type="button" onClick={() => onAction(item.id, "pages")} disabled={busy || !(research?.results.length)}>
            <Database size={15} /> {activeAction === "pages" ? "Парсинг" : "Спарсить URL"}
          </button>
          <button className="button compact" type="button" onClick={() => onAction(item.id, "brief")} disabled={busy || !research?.pages.length}>
            <ListChecks size={15} /> {activeAction === "brief" ? "Анализ" : "Собрать анализ"}
          </button>
        </div>
      </div>
      {research?.results.length ? (
        <div className="competitorList">
          <strong>Найденные конкуренты</strong>
          {research.results.slice(0, 15).map((result) => (
            <div className="competitorResult" key={result.id}>
              <span>{result.query_text} · #{result.position}</span>
              <a href={result.url} target="_blank" rel="noreferrer">{result.title || result.url}</a>
              {result.snippet ? <p>{result.snippet}</p> : null}
            </div>
          ))}
        </div>
      ) : null}
      {research?.pages.length ? (
        <div className="pageParseList">
          <strong>Парсинг страниц</strong>
          {research.pages.slice(0, 15).map((page) => (
            <div className="pageParseItem" key={page.id}>
              <span>HTTP {page.http_status || "-"} · {page.word_count} слов</span>
              <a href={page.url} target="_blank" rel="noreferrer">{page.title || page.h1 || page.url}</a>
              {page.error_message ? <p>{page.error_message}</p> : null}
            </div>
          ))}
        </div>
      ) : null}
      {brief ? (
        <div className="briefPreview">
          <strong>Краткий анализ конкурентов</strong>
          <BriefList title="Content gaps" items={brief.content_gaps || []} />
          <BriefList title="Частые заголовки" items={brief.common_headings || []} />
          <BriefList title="Темы, подтвержденные конкурентами" items={brief.topics_to_cover || []} />
        </div>
      ) : null}
    </article>
  );
}

function BriefList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="briefList">
      <span>{title}</span>
      <ul>
        {items.slice(0, 8).map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function PromptsView({ api, sites, isAdmin, onChanged }: ViewProps & { sites: Site[]; isAdmin: boolean }) {
  const [selectedSiteId, setSelectedSiteId] = React.useState(() => localStorage.getItem("workspace_site_id") || "");
  const [promptTemplates, setPromptTemplates] = React.useState<PromptTemplate[]>([]);
  const [basePrompt, setBasePrompt] = React.useState<PromptTemplate | null>(null);
  const [promptsError, setPromptsError] = React.useState("");
  const selectedSite = sites.find((site) => site.id === selectedSiteId) || null;

  const loadPrompts = React.useCallback(async () => {
    if (!selectedSiteId) return;
    setPromptsError("");
    const [nextPrompts, nextBasePrompt] = await Promise.all([
      api<PromptTemplate[]>(`/sites/${selectedSiteId}/prompt-templates`),
      api<PromptTemplate>("/prompt-templates/base")
    ]);
    setPromptTemplates(nextPrompts);
    setBasePrompt(nextBasePrompt);
  }, [api, selectedSiteId]);

  React.useEffect(() => {
    if (sites.length && (!selectedSiteId || !sites.some((site) => site.id === selectedSiteId))) {
      setSelectedSiteId(sites[0].id);
    }
  }, [selectedSiteId, sites]);

  React.useEffect(() => {
    if (!selectedSiteId) return;
    localStorage.setItem("workspace_site_id", selectedSiteId);
    setPromptTemplates([]);
    setBasePrompt(null);
    loadPrompts().catch((error: unknown) => setPromptsError(error instanceof Error ? error.message : "Не удалось загрузить промпты"));
  }, [loadPrompts, selectedSiteId]);

  async function refreshPrompts() {
    await loadPrompts();
    await onChanged();
  }

  if (!sites.length) {
    return <EmptyState text="Сначала добавьте сайт в разделе Сайты." />;
  }

  return (
    <section className="viewStack">
      <DataPanel title="Проект для промптов">
        <div className="projectHeader">
          <label>
            Проект
            <SearchableSelect
              value={selectedSiteId}
              onChange={setSelectedSiteId}
              options={sites.map(projectSearchOption)}
              searchPlaceholder="Найти проект"
            />
          </label>
          <div className="projectMeta">
            <strong>{selectedSite?.base_url || "..."}</strong>
            <span>{selectedSite ? humanPayloadMode(selectedSite.payload_mode) : ""}</span>
          </div>
          <button className="button secondary" type="button" onClick={() => refreshPrompts()}><RefreshCcw size={18} /> Обновить промпты</button>
        </div>
        {promptsError ? <div className="notice">{promptsError}</div> : null}
      </DataPanel>

      {selectedSite ? (
        <ProjectPromptsPanel
          key={selectedSite.id}
          api={api}
          site={selectedSite}
          promptTemplates={promptTemplates}
          basePrompt={basePrompt}
          isAdmin={isAdmin}
          onChanged={refreshPrompts}
        />
      ) : null}
    </section>
  );
}

function ProjectPromptsPanel({ api, site, promptTemplates, basePrompt, isAdmin, onChanged }: ViewProps & { site: Site; promptTemplates: PromptTemplate[]; basePrompt: PromptTemplate | null; isAdmin: boolean }) {
  const [selectedId, setSelectedId] = React.useState("");
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === selectedId) || defaultPromptTemplate(promptTemplates);
  const [name, setName] = React.useState("");
  const [content, setContent] = React.useState("");
  const [isDefault, setIsDefault] = React.useState(true);
  const [editorError, setEditorError] = React.useState("");
  const [editorSuccess, setEditorSuccess] = React.useState("");
  const [baseContent, setBaseContent] = React.useState("");
  const [baseError, setBaseError] = React.useState("");
  const [baseSuccess, setBaseSuccess] = React.useState("");
  const [newPromptSeed, setNewPromptSeed] = React.useState<{ name: string; content: string } | null>(null);
  const [generatedTexts, setGeneratedTexts] = React.useState<PromptGeneratedContent[] | null>(null);
  const [generatedTextsPromptId, setGeneratedTextsPromptId] = React.useState("");
  const [generatedTextsLoading, setGeneratedTextsLoading] = React.useState(false);
  const [generatedTextsError, setGeneratedTextsError] = React.useState("");
  const [previewItem, setPreviewItem] = React.useState<ContentItem | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = React.useState("");
  const isNewPrompt = selectedId === "__new__";

  React.useEffect(() => {
    setBaseContent(basePrompt?.content || "");
    setBaseError("");
    setBaseSuccess("");
  }, [basePrompt]);

  React.useEffect(() => {
    if (!selectedId && promptTemplates.length) {
      setSelectedId(defaultPromptTemplate(promptTemplates)?.id || "");
    }
  }, [promptTemplates, selectedId]);

  React.useEffect(() => {
    if (isNewPrompt) {
      setName(newPromptSeed?.name || "");
      setContent(newPromptSeed?.content || "");
      setIsDefault(false);
      setEditorError("");
      setEditorSuccess("");
      return;
    }
    if (selectedPrompt) {
      setName(selectedPrompt.name);
      setContent(selectedPrompt.content);
      setIsDefault(selectedPrompt.is_default);
      setEditorError("");
      setEditorSuccess("");
    }
  }, [isNewPrompt, newPromptSeed, selectedPrompt]);

  async function savePrompt(event: React.FormEvent) {
    event.preventDefault();
    setEditorError("");
    setEditorSuccess("");
    if (content.trim().length < 20) {
      setEditorError("Промпт слишком короткий.");
      return;
    }
    if (isNewPrompt) {
      const created = await api<PromptTemplate>(`/sites/${site.id}/prompt-templates`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), content: content.trim(), is_default: isDefault })
      });
      setSelectedId(created.id);
    } else if (selectedPrompt) {
      await api<PromptTemplate>(`/prompt-templates/${selectedPrompt.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: name.trim(), content: content.trim(), is_default: isDefault, site_id: site.id })
      });
    }
    setEditorSuccess("Промпт сохранен.");
    await onChanged();
  }

  async function saveBasePrompt(event: React.FormEvent) {
    event.preventDefault();
    setBaseError("");
    setBaseSuccess("");
    if (!isAdmin) {
      setBaseError("Редактировать базовый промпт может только администратор.");
      return;
    }
    if (baseContent.trim().length < 20) {
      setBaseError("Базовый промпт слишком короткий.");
      return;
    }
    await api<PromptTemplate>("/prompt-templates/base", {
      method: "PATCH",
      body: JSON.stringify({ content: baseContent.trim() })
    });
    setBaseSuccess("Базовый промпт сохранен.");
    await onChanged();
  }

  function createEmptyPrompt() {
    setNewPromptSeed(null);
    setSelectedId("__new__");
  }

  function createPromptFromSelected() {
    if (!selectedPrompt || isNewPrompt) return;
    setNewPromptSeed({ name: `${selectedPrompt.name} копия`, content: selectedPrompt.content });
    setSelectedId("__new__");
  }

  async function deletePrompt() {
    if (!selectedPrompt || isNewPrompt) return;
    if (selectedPrompt.used_by_projects > 0) {
      setEditorError(`Промпт используется в проектах: ${selectedPrompt.used_by_projects}. Сначала выберите другой промпт в этих проектах.`);
      return;
    }
    const confirmed = window.confirm(`Удалить промпт "${selectedPrompt.name}"? Это действие доступно только администратору.`);
    if (!confirmed) return;
    setEditorError("");
    setEditorSuccess("");
    await api(`/prompt-templates/${selectedPrompt.id}`, { method: "DELETE" });
    setSelectedId("");
    setEditorSuccess("Промпт удален.");
    await onChanged();
  }

  async function showGeneratedTexts() {
    if (!selectedPrompt || isNewPrompt) return;
    setGeneratedTextsPromptId(selectedPrompt.id);
    setGeneratedTexts(null);
    setGeneratedTextsError("");
    setGeneratedTextsLoading(true);
    try {
      const rows = await api<PromptGeneratedContent[]>(`/prompt-templates/${selectedPrompt.id}/generated-content`);
      setGeneratedTexts(rows);
    } catch (error) {
      setGeneratedTextsError(error instanceof Error ? error.message : "Не удалось загрузить тексты.");
    } finally {
      setGeneratedTextsLoading(false);
    }
  }

  async function previewGeneratedText(contentId: string) {
    setGeneratedTextsError("");
    setPreviewLoadingId(contentId);
    try {
      setPreviewItem(await api<ContentItem>(`/content/${contentId}`));
    } catch (error) {
      setGeneratedTextsError(error instanceof Error ? error.message : "Не удалось открыть текст.");
    } finally {
      setPreviewLoadingId("");
    }
  }

  const generatedTextsPrompt = promptTemplates.find((prompt) => prompt.id === generatedTextsPromptId) || null;

  return (
    <section className="viewStack">
      <DataPanel title="Базовый промпт">
        <form className="promptEditorForm" onSubmit={saveBasePrompt}>
          <div className="promptHelp">
            Эти требования автоматически добавляются к любому выбранному рабочему промпту при генерации. Здесь держим общие правила качества, фактов, юридической осторожности и формата для парсера.
          </div>
          <label className="wide">
            Общие требования для всех генераций
            <textarea
              className="promptTextarea basePromptTextarea"
              value={baseContent}
              onChange={(event) => setBaseContent(event.target.value)}
              rows={18}
              readOnly={!isAdmin}
              placeholder="Базовые правила будут созданы системой автоматически."
            />
          </label>
          {basePrompt ? (
            <div className="promptHelp">
              Обновлен: {formatDate(basePrompt.updated_at)}. Обычные пользователи видят базовый промпт, но не могут менять его.
            </div>
          ) : null}
          {baseError ? <span className="formError">{baseError}</span> : null}
          {baseSuccess ? <span className="formSuccess">{baseSuccess}</span> : null}
          <div className="formActions">
            <button className="button primary" type="submit" disabled={!isAdmin}>
              <Edit3 size={18} /> Сохранить базовый промпт
            </button>
          </div>
        </form>
      </DataPanel>
      <DataPanel title="Глобальные промпты">
        <div className="promptEditorLayout">
          <aside className="promptList">
            {promptTemplates.map((prompt) => (
              <button key={prompt.id} className={`promptListButton ${selectedId === prompt.id ? "active" : ""}`} type="button" onClick={() => setSelectedId(prompt.id)}>
                <strong>{prompt.name}</strong>
                <span>{prompt.is_default ? "По умолчанию для проекта" : formatDate(prompt.updated_at)}</span>
                <span>Используется: {prompt.used_by_projects}</span>
                <span>Сгенерировано текстов: {prompt.generated_texts_count}</span>
              </button>
            ))}
            <button className={`promptListButton ${isNewPrompt ? "active" : ""}`} type="button" onClick={createEmptyPrompt}>
              <strong>Создать новый промпт</strong>
              <span>Поля будут пустыми</span>
            </button>
          </aside>
          <form className="promptEditorForm" onSubmit={savePrompt}>
            <div className="formGrid">
              <label>
                Название
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Например: Промпт тест 1 v3" required />
              </label>
              <label className="checkboxRow promptDefaultRow">
                <input checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} type="checkbox" />
                Использовать по умолчанию для проекта
              </label>
              <label className="wide">
                Текст промпта
                <textarea className="promptTextarea" value={content} onChange={(event) => setContent(event.target.value)} rows={22} placeholder={DEFAULT_PROMPT_DRAFT} />
              </label>
            </div>
            <div className="promptHelp">
              Это общий список промптов для всех проектов. При генерации система автоматически подставляет значения из формы и анализа: <code>{"{{TOPIC}}"}</code>, <code>{"{{GEO}}"}</code>, <code>{"{{LANGUAGE}}"}</code>, <code>{"{{TARGET_WORDS}}"}</code>, <code>{"{{SITE_NAME}}"}</code>, <code>{"{{SLUG}}"}</code>, <code>{"{{CURRENT_YEAR}}"}</code>, <code>{"{{SHORTCODE}}"}</code>, <code>{"{{SEARCH_QUERIES}}"}</code>, <code>{"{{COMPETITOR_URLS}}"}</code>, <code>{"{{COMPETITOR_SUMMARY}}"}</code>, <code>{"{{CONTENT_GAPS}}"}</code>, <code>{"{{COMMON_HEADINGS}}"}</code>, <code>{"{{MISSING_BLOCKS_TO_COVER}}"}</code>.
            </div>
            {editorError ? <span className="formError">{editorError}</span> : null}
            {editorSuccess ? <span className="formSuccess">{editorSuccess}</span> : null}
            <div className="formActions">
              {selectedPrompt && !isNewPrompt ? (
                <button className="button secondary" type="button" onClick={() => void showGeneratedTexts()}>
                  <FileText size={18} /> Тексты ({selectedPrompt.generated_texts_count})
                </button>
              ) : null}
              {selectedPrompt && !isNewPrompt ? (
                <button className="button secondary" type="button" onClick={createPromptFromSelected}>
                  <span className="buttonPlusIcon"><Plus size={15} /></span> Создать на основе
                </button>
              ) : null}
              {isAdmin && selectedPrompt && !isNewPrompt ? (
                <button className="button danger" type="button" onClick={() => deletePrompt()} disabled={selectedPrompt.used_by_projects > 0}>
                  Удалить промпт
                </button>
              ) : null}
              <button className="button primary" type="submit"><Edit3 size={18} /> Сохранить промпт</button>
            </div>
          </form>
        </div>
      </DataPanel>
      {generatedTextsPromptId ? (
        <Modal
          title={`Тексты по промпту: ${generatedTextsPrompt?.name || "Промпт"}`}
          subtitle={`Сгенерировано: ${generatedTextsPrompt?.generated_texts_count ?? generatedTexts?.length ?? 0}`}
          onClose={() => setGeneratedTextsPromptId("")}
          wide
          className="promptGeneratedTextsModal"
        >
          {generatedTextsLoading ? <EmptyState text="Загружаем список текстов…" /> : null}
          {generatedTextsError ? <span className="formError">{generatedTextsError}</span> : null}
          {!generatedTextsLoading && generatedTexts ? (
            <ResponsiveTable
              columns={["Тема", "Проект", "URL", "Сгенерировано", "Слов", "Статус", "Действия"]}
              rows={generatedTexts.map((item) => [
                <strong><ContentTopicLabel item={item} /></strong>,
                item.site_name || "—",
                <code>{item.slug}</code>,
                item.generated_at ? formatDate(item.generated_at) : "—",
                item.word_count,
                <StatusBadge status={item.status} />,
                <button className="button compact" type="button" disabled={previewLoadingId === item.id} onClick={() => void previewGeneratedText(item.id)}>
                  <Eye size={15} /> {previewLoadingId === item.id ? "Открываем…" : "Просмотр"}
                </button>
              ])}
              wrapperClassName="promptGeneratedTextsTable"
            />
          ) : null}
        </Modal>
      ) : null}
      {previewItem ? <ContentPreviewModal item={previewItem} promptName={generatedTextsPrompt?.name} onClose={() => setPreviewItem(null)} /> : null}
    </section>
  );
}

function ProjectContentPanel({ api, site, content, sections, onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[] }) {
  const [selectedItem, setSelectedItem] = React.useState<ContentItem | null>(null);
  const [previewItem, setPreviewItem] = React.useState<ContentItem | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [bulkSectionId, setBulkSectionId] = React.useState("");
  const [bulkSectionContentMode, setBulkSectionContentMode] = React.useState<"nested" | "menu_page">("nested");
  const [bulkBusy, setBulkBusy] = React.useState(false);
  const [publishingItemId, setPublishingItemId] = React.useState("");
  const [createMenuVisible, setCreateMenuVisible] = React.useState(false);
  const [menuName, setMenuName] = React.useState("");
  const [menuExternalId, setMenuExternalId] = React.useState("");
  const [menuPath, setMenuPath] = React.useState("");
  const [menuType, setMenuType] = React.useState<"header" | "footer">("header");
  const [jsonDraft, setJsonDraft] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [sectionContentMode, setSectionContentMode] = React.useState<"nested" | "menu_page">("nested");
  const [editorError, setEditorError] = React.useState("");
  const [contentSort, setContentSort] = React.useState<{ columnIndex: number; direction: "asc" | "desc" } | null>(null);
  const selectableIds = React.useMemo(() => content.filter((item) => !isPublicationLocked(item)).map((item) => item.id), [content]);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const selectedItems = content.filter((item) => selectedIds.includes(item.id));
  const bulkApproveItems = selectedItems.filter((item) => Boolean(item.section_id) && canApproveContent(item));
  const bulkPublishItems = selectedItems.filter(canPublishContentImmediately);
  const awaitingPublicationCount = content.filter((item) => Boolean(item.generated_at) && item.status !== "published").length;
  const sectionContentCounts = React.useMemo(() => {
    const counts = new Map<string, number>();
    content.forEach((item) => {
      if (item.section_id && item.generated_at) counts.set(item.section_id, (counts.get(item.section_id) || 0) + 1);
    });
    return counts;
  }, [content]);
  const cachedContentTargets = React.useMemo(() => {
    const targets = new Map<string, { externalId: string; name: string; path: string; menuType: "header" | "footer" }>();
    const collect = (items: unknown[], menuType: "header" | "footer") => {
      items.forEach((rawItem, index) => {
        const item = menuPreviewItem(rawItem, index);
        const normalizedPath = normalizedTreePath(item.path);
        if (!normalizedPath) {
          collect(nestedPreviewItems(rawItem), menuType);
          return;
        }
        const existing = sections.find((section) => section.menu_type === menuType && (
          section.external_id.toLocaleLowerCase() === item.externalId.toLocaleLowerCase()
          || Boolean(normalizedPath && normalizedTreePath(section.path) === normalizedPath)
        ));
        if (!existing) {
          const key = `cached:${menuType}:${item.externalId}:${normalizedPath}`;
          targets.set(key, { externalId: item.externalId, name: item.title, path: normalizedPath, menuType });
        }
        collect(nestedPreviewItems(rawItem), menuType);
      });
    };
    collect(Array.isArray(site.default_menu.header) ? site.default_menu.header : [], "header");
    collect(Array.isArray(site.default_menu.footer) ? site.default_menu.footer : [], "footer");
    return targets;
  }, [sections, site.default_menu]);
  const contentTargetOptions = React.useMemo(() => [
    { value: "", label: "Выберите пункт меню" },
    ...sections.filter((section) => section.sync_status !== "external_deleted").map((section) => ({
      value: section.id,
      label: `${section.name} · ${section.path}`,
      badge: String(sectionContentCounts.get(section.id) || 0),
      badgeTone: "neutral" as const
    })),
    ...Array.from(cachedContentTargets.entries()).map(([value, target]) => ({
      value,
      label: `${target.name} · ${target.path}`,
      description: `Существующий ${target.menuType === "header" ? "Header" : "Footer"}`
    }))
  ], [cachedContentTargets, sectionContentCounts, sections]);
  const sortedContent = React.useMemo(() => {
    if (!contentSort) return content;
    const direction = contentSort.direction === "asc" ? 1 : -1;
    return content
      .map((item, originalIndex) => ({ item, originalIndex }))
      .sort((left, right) => {
        let comparison = 0;
        if (contentSort.columnIndex === 1) comparison = left.item.topic.localeCompare(right.item.topic, undefined, { sensitivity: "base" });
        if (contentSort.columnIndex === 2) comparison = sectionLabel(left.item.section_id, sections).localeCompare(sectionLabel(right.item.section_id, sections), undefined, { sensitivity: "base" });
        if (contentSort.columnIndex === 3) comparison = left.item.word_count - right.item.word_count;
        if (contentSort.columnIndex === 4) comparison = left.item.status.localeCompare(right.item.status, undefined, { sensitivity: "base" });
        if (contentSort.columnIndex === 5) comparison = new Date(left.item.published_at || 0).getTime() - new Date(right.item.published_at || 0).getTime();
        return comparison ? comparison * direction : left.originalIndex - right.originalIndex;
      })
      .map(({ item }) => item);
  }, [content, contentSort, sections]);

  function sortContentByColumn(columnIndex: number) {
    setContentSort((current) => current?.columnIndex === columnIndex
      ? { columnIndex, direction: current.direction === "asc" ? "desc" : "asc" }
      : { columnIndex, direction: "asc" });
  }

  function contentSiteUrl(item: ContentItem): string {
    if (item.published_url) return item.published_url;
    const projectBaseUrl = site.base_url || `https://${site.cache_canon || site.name}`;
    try {
      return new URL(item.slug.replace(/^\/+/, ""), `${projectBaseUrl.replace(/\/+$/, "")}/`).toString();
    } catch {
      return `${projectBaseUrl.replace(/\/+$/, "")}/${item.slug.replace(/^\/+/, "")}`;
    }
  }

  React.useEffect(() => {
    setSelectedIds((current) => current.filter((id) => selectableIds.includes(id)));
  }, [selectableIds]);

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? [] : selectableIds);
  }

  async function resolveContentSectionId(value: string): Promise<string> {
    if (sections.some((section) => section.id === value)) return value;
    const target = cachedContentTargets.get(value);
    if (!target) throw new Error("Выбранный пункт меню не найден в актуальном меню проекта");
    const result = await api<{ section: Section; created: boolean }>(`/sites/${site.id}/sections/content-target`, {
      method: "POST",
      body: JSON.stringify({
        external_id: target.externalId,
        name: target.name,
        path: target.path,
        menu_type: target.menuType,
        parent_id: null
      })
    });
    return result.section.id;
  }

  async function applyBulkSection() {
    if (!selectedIds.length || !bulkSectionId) {
      setEditorError(!selectedIds.length ? "Выберите хотя бы один текст." : "Выберите пункт меню.");
      return;
    }
    setEditorError("");
    setBulkBusy(true);
    try {
      const resolvedSectionId = await resolveContentSectionId(bulkSectionId);
      const results = await Promise.allSettled(selectedIds.map((id) => api(`/content/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ section_id: resolvedSectionId, section_content_mode: bulkSectionContentMode })
      })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await onChanged();
      if (failed) setEditorError(`Не удалось изменить пункт меню у ${failed} текстов.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось применить пункт меню.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function approveSelected() {
    if (!bulkApproveItems.length) return;
    setEditorError("");
    setBulkBusy(true);
    try {
      const results = await Promise.allSettled(bulkApproveItems.map((item) => api(`/content/${item.id}/approve`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await onChanged();
      if (failed) setEditorError(`Не удалось принять ${failed} текстов.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось принять выбранные тексты.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function publishSelected() {
    if (!bulkPublishItems.length) return;
    setEditorError("");
    setBulkBusy(true);
    try {
      const results = await Promise.allSettled(bulkPublishItems.map((item) => api(`/content/${item.id}/publish-immediately`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedIds([]);
      await onChanged();
      if (failed) setEditorError(`Не удалось опубликовать ${failed} текстов.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось опубликовать выбранные тексты.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function createMenuItem(event: React.FormEvent) {
    event.preventDefault();
    setEditorError("");
    setBulkBusy(true);
    try {
      const created = await api<Section>(`/sites/${site.id}/sections`, {
        method: "POST",
        body: JSON.stringify({
          name: menuName.trim(),
          external_id: menuExternalId.trim() || slugFromText(menuName),
          path: menuPath.trim() || `/${slugFromText(menuName)}/`,
          menu_type: menuType
        })
      });
      setMenuName("");
      setMenuExternalId("");
      setMenuPath("");
      setMenuType("header");
      setBulkSectionId(created.id);
      setCreateMenuVisible(false);
      await onChanged();
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось создать пункт меню.");
    } finally {
      setBulkBusy(false);
    }
  }

  function openEditor(item: ContentItem) {
    setSelectedItem(item);
    setJsonDraft(JSON.stringify(item.generated_json, null, 2));
    setSectionId(item.section_id || "");
    setSectionContentMode(item.section_content_mode || "nested");
    setEditorError("");
  }

  async function saveContent(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedItem) return;
    setEditorError("");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonDraft);
    } catch {
      setEditorError("JSON невалидный.");
      return;
    }
    try {
      const resolvedSectionId = sectionId ? await resolveContentSectionId(sectionId) : null;
      await api(`/content/${selectedItem.id}`, {
        method: "PATCH",
        body: JSON.stringify({ generated_json: parsed, section_id: resolvedSectionId, section_content_mode: sectionContentMode })
      });
      setSelectedItem(null);
      await onChanged();
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось сохранить контент.");
    }
  }

  async function approve(item: ContentItem) {
    setEditorError("");
    if (!item.section_id) {
      setEditorError("Перед принятием выберите пункт меню.");
      openEditor(item);
      return;
    }
    await api(`/content/${item.id}/approve`, { method: "POST" });
    await onChanged();
  }

  async function publishImmediately(item: ContentItem) {
    if (!canPublishContentImmediately(item)) {
      setEditorError("Перед публикацией выберите пункт меню и убедитесь, что текст готов.");
      return;
    }
    setEditorError("");
    setPublishingItemId(item.id);
    try {
      await api(`/content/${item.id}/publish-immediately`, { method: "POST" });
      await onChanged();
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось опубликовать текст.");
    } finally {
      setPublishingItemId("");
    }
  }

  return (
    <section className="viewStack">
      <DataPanel id="workspace-section-content" className="projectContentPanel" collapseKey="project-content" title={(
        <span className="workspacePanelTitleWithStats">
          <span>Контент проекта</span>
          <span className="workspacePanelStats">
            <span>Контента: <b>{content.length}</b></span>
            <span className="positive">Ожидает публикации: <b>{awaitingPublicationCount}</b></span>
          </span>
        </span>
      )}>
        <div className="bulkToolbar projectContentBulkToolbar">
          <label className="checkboxRow bulkSelectAll">
            <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} disabled={!selectableIds.length || bulkBusy} />
            Выбрать все
          </label>
          <span className="fieldHint">Выбрано: {selectedIds.length}</span>
          <div className="bulkMenuSelect">
            <SearchableSelect
              value={bulkSectionId}
              onChange={setBulkSectionId}
              options={contentTargetOptions}
              searchPlaceholder="Найти пункт меню"
              disabled={bulkBusy}
            />
          </div>
          <select className="contentPlacementSelect" value={bulkSectionContentMode} onChange={(event) => setBulkSectionContentMode(event.target.value as "nested" | "menu_page")} disabled={bulkBusy} title="Способ размещения контента">
            <option value="nested">Вложенная страница</option>
            <option value="menu_page">Контент пункта меню</option>
          </select>
          <button className="button compact primary" type="button" onClick={applyBulkSection} disabled={!selectedIds.length || !bulkSectionId || bulkBusy}>
            <CheckCircle2 size={15} /> {bulkBusy ? "Сохраняю" : `Назначить выбранным (${selectedIds.length})`}
          </button>
          <button className="button compact approve" type="button" onClick={approveSelected} disabled={!bulkApproveItems.length || bulkBusy} title={selectedIds.length && !bulkApproveItems.length ? "Сначала назначьте пункт меню текстам со статусом generated" : undefined}>
            <CheckCircle2 size={15} /> Принять ({bulkApproveItems.length})
          </button>
          <button className="button compact primary" type="button" onClick={publishSelected} disabled={!bulkPublishItems.length || bulkBusy} title={selectedIds.length && !bulkPublishItems.length ? "Сначала назначьте пункт меню" : "Сразу отправить JSON выбранных текстов на сервер проекта"}>
            <Send size={15} /> Опубликовать ({bulkPublishItems.length})
          </button>
          <button className="button compact secondary createMenuButton" type="button" onClick={() => setCreateMenuVisible((current) => !current)} disabled={bulkBusy}>
            <span className="buttonPlusIcon"><Plus size={15} /></span> Новый пункт меню
          </button>
        </div>
        {createMenuVisible ? (
          <form className="inlineMenuCreate" onSubmit={createMenuItem}>
            <label>
              Название пункта
              <input value={menuName} onChange={(event) => setMenuName(event.target.value)} placeholder="Casino bonus" required />
            </label>
            <label>
              External ID
              <input value={menuExternalId} onChange={(event) => setMenuExternalId(event.target.value)} placeholder="Сформируется автоматически" />
            </label>
            <label>
              Path
              <input value={menuPath} onChange={(event) => setMenuPath(event.target.value)} placeholder="/casino-bonus/" />
            </label>
            <label>
              Тип меню
              <select value={menuType} onChange={(event) => setMenuType(event.target.value as "header" | "footer")}>
                <option value="header">Header</option>
                <option value="footer">Footer</option>
              </select>
            </label>
            <div className="formActions alignEnd">
              <button className="button compact secondary" type="button" onClick={() => setCreateMenuVisible(false)}>Отмена</button>
              <button className="button compact primary" type="submit" disabled={bulkBusy}><span className="buttonPlusIcon"><Plus size={15} /></span> Создать</button>
            </div>
          </form>
        ) : null}
        <ResponsiveTable
          columns={["Выбор", "Тема", "Меню", "Слова", "Статус", "Опубликовано", "Действия"]}
          columnKeys={["select", "topic", "menu", "words", "status", "published", "actions"]}
          wrapperClassName="projectContentTable"
          sortableColumnIndexes={[1, 2, 3, 4, 5]}
          sortColumnIndex={contentSort?.columnIndex ?? null}
          sortDirection={contentSort?.direction}
          onSortColumn={sortContentByColumn}
          rows={sortedContent.map((item) => [
            <input
              className="rowCheckbox"
              type="checkbox"
              checked={selectedIds.includes(item.id)}
              onChange={() => toggleSelected(item.id)}
              disabled={isPublicationLocked(item) || bulkBusy}
              aria-label={`Выбрать ${item.topic}`}
              title={isPublicationLocked(item) ? "Пункт меню опубликованного или запланированного текста изменять нельзя" : undefined}
            />,
            <span className="campaignTopicWithPreview">
              <span className="compactContentTopic" title={item.topic}><ContentTopicLabel item={item} /></span>
              <button className="contentPreviewIconButton" type="button" onClick={() => setPreviewItem(item)} title="Просмотреть текст и метаданные" aria-label={`Просмотреть текст: ${item.topic}`}><Eye size={14} /></button>
            </span>,
            <span className="contentSectionPlacement">
              <span>{sectionLabel(item.section_id, sections)}</span>
              {item.section_id ? <small>{item.section_content_mode === "menu_page" ? "Контент пункта меню" : "Вложенная страница"}</small> : null}
            </span>,
            item.word_count,
            <StatusBadge status={item.status} />,
            item.published_url ? <a href={item.published_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> URL</a> : item.published_at ? formatDate(item.published_at) : "-",
            <div className="userActions projectContentActions">
              <button className="button compact" type="button" onClick={() => openEditor(item)} disabled={isPublicationLocked(item)} title="Открыть и редактировать JSON payload"><Database size={15} /> JSON</button>
              <button className="button compact approve" type="button" onClick={() => approve(item)} disabled={!canApproveContent(item)} title="Принять текст"><CheckCircle2 size={15} /> Принять</button>
              <button className="button compact primary" type="button" onClick={() => void publishImmediately(item)} disabled={!canPublishContentImmediately(item) || publishingItemId === item.id} title="Сразу отправить JSON текста на сервер проекта"><Send size={15} /> {publishingItemId === item.id ? "Публикуем…" : "Опубликовать"}</button>
              {item.status === "published" ? <a className="viewOnSiteIconButton" href={contentSiteUrl(item)} target="_blank" rel="noreferrer" title="Посмотреть на сайте" aria-label={`Посмотреть на сайте: ${item.topic}`}><ExternalLink size={16} /></a> : null}
            </div>
          ])}
        />
        {editorError ? <span className="formError">{editorError}</span> : null}
      </DataPanel>

      {selectedItem ? (
        <Modal title={`JSON: ${selectedItem.topic}`} subtitle="Редактирование полного JSON payload" onClose={() => setSelectedItem(null)} wide>
          <form className="formGrid modalForm" onSubmit={saveContent}>
            <label>
              Пункт меню
              <SearchableSelect
                value={sectionId}
                onChange={setSectionId}
                options={[{ value: "", label: "Не выбран" }, ...contentTargetOptions.filter((option) => option.value)]}
                searchPlaceholder="Найти пункт меню"
              />
            </label>
            <label>
              Размещение
              <select value={sectionContentMode} onChange={(event) => setSectionContentMode(event.target.value as "nested" | "menu_page")}>
                <option value="nested">Вложенная страница</option>
                <option value="menu_page">Контент самого пункта меню</option>
              </select>
            </label>
            <label>
              Slug
              <input value={selectedItem.slug} disabled />
            </label>
            <label className="wide">
              JSON payload
              <textarea className="jsonEditor" value={jsonDraft} onChange={(event) => setJsonDraft(event.target.value)} rows={18} />
            </label>
            <div className="formActions wide">
              <button className="button secondary" type="button" onClick={() => setSelectedItem(null)}>Закрыть</button>
              <button className="button primary" type="submit">Сохранить</button>
            </div>
          </form>
        </Modal>
      ) : null}
      {previewItem ? (
        <ContentPreviewModal item={previewItem} onClose={() => setPreviewItem(null)} />
      ) : null}
    </section>
  );
}

type PublicationWorkflowSection = "process" | "queue" | "backlog";
type PublicationWorkspaceSection = "content" | "campaigns" | PublicationWorkflowSection;

function PublicationWorkflowNav({ content, campaigns, activeSection, onSectionChange }: { content: ContentItem[]; campaigns: PublicationCampaign[]; activeSection: PublicationWorkspaceSection; onSectionChange: (section: PublicationWorkspaceSection) => void }) {
  const awaitingPublicationCount = content.filter((item) => Boolean(item.generated_at) && item.status !== "published").length;
  const activeCampaignCount = campaigns.filter((campaign) => ["active", "paused", "created", "publishing_all"].includes(campaign.status)).length;
  const completedCampaignCount = campaigns.filter((campaign) => ["completed", "completed_with_errors"].includes(campaign.status)).length;
  const processReadyCount = content.filter((item) => Boolean(item.site_id && item.section_id) && ["generated", "rejected", "approved"].includes(item.status)).length;
  const processPublishedCount = content.filter((item) => item.status === "published").length;
  const processCount = processReadyCount + processPublishedCount;
  const queueCount = content.filter((item) => ["scheduled", "retry_scheduled", "publication_paused", "publishing"].includes(item.status)).length;
  const errorCount = content.filter((item) => item.status === "publication_failed").length;
  return (
    <nav className="publicationWorkflowNav publicationWorkflowNavTop" aria-label="Разделы публикации">
      <button className={activeSection === "campaigns" ? "active" : ""} type="button" onClick={() => onSectionChange("campaigns")} title="Запустить публикацию" aria-label="Кампании — запустить публикацию">
        <FolderKanban size={17} /> <span className="publicationWorkflowLabel"><strong>Кампании</strong><small>{activeCampaignCount} в работе · {completedCampaignCount} завершено</small></span><span>{campaigns.length}</span>
      </button>
      <button className={activeSection === "content" ? "active" : ""} type="button" onClick={() => onSectionChange("content")}>
        <FileText size={17} /> <span className="publicationWorkflowLabel"><strong>Контент</strong><small>{awaitingPublicationCount} ожидает публикации</small></span><span>{content.length}</span>
      </button>
      <button className={activeSection === "process" ? "active" : ""} type="button" onClick={() => onSectionChange("process")}>
        <Activity size={17} /> <span className="publicationWorkflowLabel"><strong>Процесс</strong><small>Готовы к запуску: {processReadyCount} · Опубликовано: {processPublishedCount}</small></span><span>{processCount}</span>
      </button>
      <button className={activeSection === "queue" ? "active" : ""} type="button" onClick={() => onSectionChange("queue")}>
        <ListChecks size={17} /> <span className="publicationWorkflowLabel"><strong>Очередь</strong><small>ожидают публикации</small></span><span>{queueCount}</span>
      </button>
      <button className={`${activeSection === "backlog" ? "active" : ""} ${errorCount ? "danger" : ""}`} type="button" onClick={() => onSectionChange("backlog")}>
        <AlertTriangle size={17} /> <span className="publicationWorkflowLabel"><strong>Ошибки</strong><small>нужна проверка</small></span><span>{errorCount}</span>
      </button>
    </nav>
  );
}

function ProjectPublicationPanel({ api, site, content, sections, campaigns, logs, mode, workflowSection = "process", onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[]; campaigns: PublicationCampaign[]; logs: PublicationLog[]; mode: "launch" | "campaigns" | "workflow"; workflowSection?: PublicationWorkflowSection }) {
  const [launchExpanded, setLaunchExpanded] = usePersistentWorkspacePanelState("publication-launch", false);
  const [name, setName] = React.useState("Daily publication");
  const [itemsPerDay, setItemsPerDay] = React.useState(1);
  const [selectedPublicationSectionIds, setSelectedPublicationSectionIds] = React.useState<string[]>([]);
  const [startAt, setStartAt] = React.useState(() => toDateTimeInputValue(new Date()));
  const [formError, setFormError] = React.useState("");
  const [publishingNowId, setPublishingNowId] = React.useState("");
  const [selectedProcessIds, setSelectedProcessIds] = React.useState<string[]>([]);
  const [publishingProcessSelection, setPublishingProcessSelection] = React.useState(false);
  const [publishingAllCampaignId, setPublishingAllCampaignId] = React.useState("");
  const [reschedulingCampaignId, setReschedulingCampaignId] = React.useState("");
  const [previewItem, setPreviewItem] = React.useState<ContentItem | null>(null);
  const publicationReady = content.filter((item) => Boolean(item.site_id && item.section_id)
    && ["generated", "rejected", "approved"].includes(item.status)
    && (!selectedPublicationSectionIds.length || (item.section_id && selectedPublicationSectionIds.includes(item.section_id))));
  const publishedContent = content
    .filter((item) => item.status === "published")
    .sort((left, right) => new Date(left.published_at || 0).getTime() - new Date(right.published_at || 0).getTime());
  const publicationProcessItems = [...publicationReady, ...publishedContent];
  const processSelectableIds = publicationProcessItems.filter(canPublishContentImmediately).map((item) => item.id);
  const allProcessItemsSelected = processSelectableIds.length > 0 && processSelectableIds.every((id) => selectedProcessIds.includes(id));
  const selectedProcessItems = publicationProcessItems.filter((item) => selectedProcessIds.includes(item.id) && canPublishContentImmediately(item));
  const publicationSections = sections
    .map((section) => ({ section, count: content.filter((item) => ["generated", "rejected", "approved"].includes(item.status) && item.section_id === section.id).length }))
    .filter(({ count }) => count > 0);
  const publicationQueue = content
    .filter((item) => ["scheduled", "retry_scheduled", "publication_paused", "publishing"].includes(item.status))
    .sort((left, right) => new Date(left.scheduled_at || 0).getTime() - new Date(right.scheduled_at || 0).getTime());
  const publicationBacklog = content
    .filter((item) => item.status === "publication_failed")
    .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime());
  const activeCampaignCount = campaigns.filter((campaign) => ["active", "paused", "created", "publishing_all"].includes(campaign.status)).length;
  const completedCampaignCount = campaigns.filter((campaign) => ["completed", "completed_with_errors"].includes(campaign.status)).length;
  const latestErrorByContentId = React.useMemo(() => {
    const result = new Map<string, PublicationLog>();
    logs.forEach((log) => {
      if (log.content_item_id && !result.has(log.content_item_id)) result.set(log.content_item_id, log);
    });
    return result;
  }, [logs]);

  async function createCampaign(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!publicationReady.length) {
      setFormError("Нет принятых текстов, ожидающих публикации, для выбранного фильтра.");
      return;
    }
    try {
      await api(`/sites/${site.id}/publication-campaigns`, {
        method: "POST",
        body: JSON.stringify({
          name,
          content_item_ids: publicationReady.map((item) => item.id),
          start_at: new Date(startAt).toISOString(),
          items_per_day: itemsPerDay
        })
      });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось создать кампанию.");
    }
  }

  async function changeCampaign(campaign: PublicationCampaign, action: "pause" | "resume" | "stop") {
    setFormError("");
    try {
      await api(`/publication-campaigns/${campaign.id}`, {
        method: "PATCH",
        body: JSON.stringify({ action })
      });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось изменить кампанию.");
    }
  }

  async function publishImmediately(item: ContentItem) {
    if (!window.confirm(`Опубликовать текст «${item.topic}» сейчас, без ожидания очереди?`)) return;
    setPublishingNowId(item.id);
    setFormError("");
    try {
      await api<ContentItem>(`/content/${item.id}/publish-immediately`, { method: "POST" });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось опубликовать текст.");
    } finally {
      setPublishingNowId("");
    }
  }

  function toggleProcessItem(itemId: string) {
    setSelectedProcessIds((current) => current.includes(itemId)
      ? current.filter((id) => id !== itemId)
      : [...current, itemId]);
  }

  function toggleAllProcessItems() {
    setSelectedProcessIds(allProcessItemsSelected ? [] : processSelectableIds);
  }

  async function publishSelectedProcessItems() {
    if (!selectedProcessItems.length) return;
    if (!window.confirm(`Опубликовать выбранные тексты (${selectedProcessItems.length}) сейчас, без ожидания очереди?`)) return;
    setPublishingProcessSelection(true);
    setFormError("");
    try {
      const results = await Promise.allSettled(selectedProcessItems.map((item) => api(`/content/${item.id}/publish-immediately`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedProcessIds([]);
      await onChanged();
      if (failed) setFormError(`Не удалось опубликовать часть выбранных текстов: ${failed}.`);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось опубликовать выбранные тексты.");
    } finally {
      setPublishingProcessSelection(false);
    }
  }

  React.useEffect(() => {
    setSelectedProcessIds((current) => current.filter((id) => processSelectableIds.includes(id)));
  }, [content, selectedPublicationSectionIds, site.id]);

  async function publishAll(campaign: PublicationCampaign) {
    const count = content.filter((item) => item.publication_campaign_id === campaign.id && item.status !== "published").length;
    if (!count || !window.confirm(`Опубликовать все тексты кампании «${campaign.name}» (${count}) одним пакетным запросом?`)) return;
    setPublishingAllCampaignId(campaign.id);
    setFormError("");
    try {
      await api(`/publication-campaigns/${campaign.id}/publish-all`, { method: "POST" });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось запустить пакетную публикацию.");
      setPublishingAllCampaignId("");
    }
  }

  async function rescheduleCampaign(campaign: PublicationCampaign, nextItemsPerDay: number) {
    if (!window.confirm(`Изменить режим кампании «${campaign.name}» и заново рассчитать оставшуюся очередь?`)) return;
    setReschedulingCampaignId(campaign.id);
    setFormError("");
    try {
      await api(`/publication-campaigns/${campaign.id}/reschedule`, {
        method: "POST",
        body: JSON.stringify({ items_per_day: nextItemsPerDay, timezone_offset_minutes: new Date().getTimezoneOffset() })
      });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось пересчитать очередь публикации.");
    } finally {
      setReschedulingCampaignId("");
    }
  }

  React.useEffect(() => {
    const inProgress = campaigns.some((campaign) => campaign.status === "publishing_all");
    if (!inProgress) {
      if (publishingAllCampaignId) setPublishingAllCampaignId("");
      return;
    }
    const timer = window.setInterval(() => void onChanged(), 4000);
    return () => window.clearInterval(timer);
  }, [campaigns, onChanged, publishingAllCampaignId]);

  function togglePublicationSection(sectionId: string) {
    setSelectedPublicationSectionIds((current) => current.includes(sectionId)
      ? current.filter((id) => id !== sectionId)
      : [...current, sectionId]);
  }

  return (
    <section className="viewStack">
      {mode === "launch" ? <section className={`dataPanel publicationLaunchPanel ${launchExpanded ? "expanded" : ""}`}>
        <button className="publicationLaunchToggle" type="button" onClick={() => setLaunchExpanded((current) => !current)} aria-expanded={launchExpanded}>
          <span className="publicationLaunchIcon"><Send size={20} /></span>
          <span className="publicationLaunchText">
            <strong>Запустить публикацию</strong>
            <small>{launchExpanded ? "Нажмите, чтобы свернуть настройки" : `Нажмите, чтобы настроить кампанию · приняты и ожидают публикации: ${publicationReady.length}`}</small>
          </span>
          {launchExpanded ? <ChevronUp size={22} /> : <ChevronDown size={22} />}
        </button>
        {launchExpanded ? (
          <form className="formGrid publicationLaunchForm" onSubmit={createCampaign}>
            <label>
              Название кампании
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            <label>
              Пункты меню
              <span className="publicationSectionPicker">
                <button className={!selectedPublicationSectionIds.length ? "active" : ""} type="button" onClick={() => setSelectedPublicationSectionIds([])}>
                  Приняты и ожидают публикации <small>{content.filter((item) => Boolean(item.site_id && item.section_id) && ["generated", "rejected", "approved"].includes(item.status)).length}</small>
                </button>
                {publicationSections.map(({ section, count }) => (
                  <button className={selectedPublicationSectionIds.includes(section.id) ? "active" : ""} type="button" key={section.id} onClick={() => togglePublicationSection(section.id)}>
                    <span>{section.name}</span><small>{count}</small>
                  </button>
                ))}
              </span>
            </label>
            <label>
              Режим публикации
              <select value={itemsPerDay} onChange={(event) => setItemsPerDay(Number(event.target.value))}>
                <option value={1}>1 текст в день · каждые 24 часа</option>
                <option value={2}>2 текста в день · каждые 12 часов</option>
                <option value={3}>3 текста в день · каждые 7 часов</option>
              </select>
            </label>
            <label>
              Старт
              <input type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} required />
            </label>
            {formError ? <span className="formError wide">{formError}</span> : null}
            <div className="formActions wide">
              <button className="button primary" type="submit" disabled={!publicationReady.length}><Play size={18} /> Запланировать ({publicationReady.length})</button>
            </div>
          </form>
        ) : null}
      </section> : null}
      {mode === "campaigns" ? <DataPanel id="workspace-section-campaigns" collapseKey="project-campaigns" title={(
        <span className="workspacePanelTitleWithStats">
          <span>Кампании проекта</span>
          <span className="workspacePanelStats">
            <span>Всего: <b>{campaigns.length}</b></span>
            <span className="positive">В работе: <b>{activeCampaignCount}</b></span>
            <span className="muted">Завершено: <b>{completedCampaignCount}</b></span>
          </span>
        </span>
      )}>
        <div className="projectCampaignTree">
          {campaigns.map((campaign, index) => (
            <ProjectCampaignTreeItem
              key={campaign.id}
              campaign={campaign}
              items={content.filter((item) => item.publication_campaign_id === campaign.id)}
              sections={sections}
              defaultExpanded={index === 0}
              publishingNowId={publishingNowId}
              publishingAllCampaignId={publishingAllCampaignId}
              reschedulingCampaignId={reschedulingCampaignId}
              onPreview={setPreviewItem}
              onPublishImmediately={publishImmediately}
              onPublishAll={publishAll}
              onRescheduleCampaign={rescheduleCampaign}
              onChangeCampaign={changeCampaign}
            />
          ))}
          {!campaigns.length ? <div className="projectCampaignEmpty">Кампании для проекта пока не созданы.</div> : null}
        </div>
        {formError ? <span className="formError">{formError}</span> : null}
      </DataPanel> : null}
      {mode === "workflow" && workflowSection === "process" ? <DataPanel id="workspace-section-process" collapseKey="publication-process" title={`Процесс публикации · ${publicationProcessItems.length}`}>
        <div className="publicationProcessBulkToolbar">
          <span>Выбрано: <strong>{selectedProcessItems.length}</strong></span>
          <button className="button compact primary" type="button" onClick={() => void publishSelectedProcessItems()} disabled={!selectedProcessItems.length || publishingProcessSelection}>
            <Send size={15} /> {publishingProcessSelection ? "Публикуем…" : `Опубликовать (${selectedProcessItems.length})`}
          </button>
        </div>
        <ResponsiveTable
          columns={["", "Тема", "Меню", "Slug", "Действия"]}
          columnKeys={["select", "topic", "menu", "slug", "actions"]}
          columnHeaders={{
            0: (
              <label className={`tableSelectAllButton ${processSelectableIds.length ? "" : "disabled"}`} title="Выбрать все неопубликованные тексты">
                <input type="checkbox" checked={allProcessItemsSelected} disabled={!processSelectableIds.length || publishingProcessSelection} onChange={toggleAllProcessItems} aria-label="Выбрать все неопубликованные тексты" />
              </label>
            )
          }}
          rows={publicationProcessItems.map((item) => [
            <input
              className="rowCheckbox"
              type="checkbox"
              checked={selectedProcessIds.includes(item.id)}
              onChange={() => toggleProcessItem(item.id)}
              disabled={!canPublishContentImmediately(item) || publishingProcessSelection}
              aria-label={`Выбрать ${item.topic}`}
              title={item.status === "published" ? "Текст уже опубликован" : undefined}
            />,
            <div className="compactContentTopic" title={item.topic}><ContentTopicLabel item={item} /></div>,
            sectionLabel(item.section_id, sections),
            item.slug,
            item.status === "published" ? (
              <span className="publishedProcessState" title={item.published_at ? `Опубликовано ${formatDate(item.published_at)}` : "Опубликовано"}>
                <CheckCircle2 size={14} /> <strong>Опубликовано</strong><span>·</span><time>{item.published_at ? formatDate(item.published_at) : "—"}</time>
              </span>
            ) : (
              <button className="button compact primary publishImmediatelyButton" type="button" onClick={() => void publishImmediately(item)} disabled={publishingNowId === item.id}>
                <Send size={14} /> {publishingNowId === item.id ? "Публикуем…" : "Опубликовать сейчас"}
              </button>
            )
          ])}
          wrapperClassName="projectPublicationProcessTable"
        />
        {formError ? <span className="formError">{formError}</span> : null}
      </DataPanel> : null}
      {mode === "workflow" && workflowSection === "queue" ? <DataPanel id="workspace-section-queue" collapseKey="publication-queue" title={`Очередь публикации · ${publicationQueue.length}`}>
        <div className="publicationQueueHint">Очередь чередуется по пунктам меню и сохраняет исходный порядок добавления тем.</div>
        <ResponsiveTable
          columns={["№", "Тема", "Меню", "Публикация", "Статус", "Действия"]}
          rows={publicationQueue.map((item, index) => [
            index + 1,
            <div className="compactContentTopic" title={item.topic}><ContentTopicLabel item={item} /></div>,
            sectionLabel(item.section_id, sections),
            item.scheduled_at ? formatDate(item.scheduled_at) : "—",
            <StatusBadge status={item.status} />,
            <button className="button compact primary publishImmediatelyButton" type="button" onClick={() => void publishImmediately(item)} disabled={publishingNowId === item.id || item.status === "publishing"}>
              <Send size={14} /> {publishingNowId === item.id ? "Отправляем…" : "Отправить"}
            </button>
          ])}
          wrapperClassName="projectPublicationQueueTable"
        />
        {formError ? <span className="formError">{formError}</span> : null}
      </DataPanel> : null}
      {mode === "workflow" && workflowSection === "backlog" ? <DataPanel id="workspace-section-backlog" className="publicationBacklogPanel" collapseKey="publication-backlog" title={<span className="publicationBacklogTitle"><AlertTriangle size={18} /> Ошибки публикации · {publicationBacklog.length}</span>}>
        <div className="publicationBacklogHint">Сюда автоматически переносятся тексты, которые не удалось опубликовать из-за ошибки.</div>
        <ResponsiveTable
          columns={["Тема", "Меню", "Ошибка", "Время", "Статус"]}
          rows={publicationBacklog.map((item) => {
            const errorLog = latestErrorByContentId.get(item.id);
            return [
              <div className="compactContentTopic" title={item.topic}><ContentTopicLabel item={item} /></div>,
              sectionLabel(item.section_id, sections),
              <span className="publicationBacklogError">{errorLog?.error_message || (errorLog?.response_status ? `HTTP ${errorLog.response_status}` : "Ошибка публикации")}</span>,
              errorLog ? formatDate(errorLog.created_at) : formatDate(item.updated_at),
              <StatusBadge status={item.status} />
            ];
          })}
          rowClassNames={publicationBacklog.map(() => "publicationBacklogRow")}
          wrapperClassName="publicationBacklogTable"
        />
      </DataPanel> : null}
      {previewItem ? <ContentPreviewModal item={previewItem} onClose={() => setPreviewItem(null)} /> : null}
    </section>
  );
}

function ProjectCampaignTreeItem({
  campaign,
  items,
  sections,
  defaultExpanded,
  publishingNowId,
  publishingAllCampaignId,
  reschedulingCampaignId,
  onPreview,
  onPublishImmediately,
  onPublishAll,
  onRescheduleCampaign,
  onChangeCampaign
}: {
  campaign: PublicationCampaign;
  items: ContentItem[];
  sections: Section[];
  defaultExpanded: boolean;
  publishingNowId: string;
  publishingAllCampaignId: string;
  reschedulingCampaignId: string;
  onPreview: (item: ContentItem) => void;
  onPublishImmediately: (item: ContentItem) => Promise<void>;
  onPublishAll: (campaign: PublicationCampaign) => Promise<void>;
  onRescheduleCampaign: (campaign: PublicationCampaign, itemsPerDay: number) => Promise<void>;
  onChangeCampaign: (campaign: PublicationCampaign, action: "pause" | "resume" | "stop") => Promise<void>;
}) {
  const [expanded, setExpanded] = usePersistentWorkspacePanelState(`campaign:${campaign.id}`, defaultExpanded);
  const currentItemsPerDay = campaign.interval_minutes === 420 ? 3 : campaign.interval_minutes === 720 ? 2 : 1;
  const [itemsPerDayDraft, setItemsPerDayDraft] = React.useState(currentItemsPerDay);
  React.useEffect(() => setItemsPerDayDraft(currentItemsPerDay), [currentItemsPerDay]);
  const orderedItems = React.useMemo(() => [...items].sort((left, right) => {
    const leftDate = new Date(left.scheduled_at || left.published_at || left.created_at).getTime();
    const rightDate = new Date(right.scheduled_at || right.published_at || right.created_at).getTime();
    return leftDate - rightDate;
  }), [items]);
  const queuedCount = items.filter((item) => ["scheduled", "retry_scheduled", "publication_paused", "publishing"].includes(item.status)).length;
  const publishedCount = items.filter((item) => item.status === "published").length;
  const failedCount = items.filter((item) => item.status === "publication_failed").length;
  const campaignTone = campaign.status === "completed_with_errors" ? "error" : campaign.status === "completed" ? "success" : "working";
  const isPublishingAll = campaign.status === "publishing_all" || publishingAllCampaignId === campaign.id;
  const isRescheduling = reschedulingCampaignId === campaign.id;
  const publicationModeChanged = itemsPerDayDraft !== currentItemsPerDay;
  const unpublishedCount = items.length - publishedCount;

  return (
    <article className={`projectCampaignItem campaign-${campaignTone} ${expanded ? "expanded" : ""}`}>
      <div className="projectCampaignHeader">
        <button className="projectCampaignToggle" type="button" onClick={() => setExpanded((current) => !current)} aria-expanded={expanded}>
          <span className="projectCampaignChevron">{expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
          <span className="projectCampaignIdentity">
            <strong>{campaign.name}</strong>
            <small>{campaign.completed_at ? `Завершена: ${formatDate(campaign.completed_at)}` : `Старт: ${formatDate(campaign.start_at)}`} · {publicationIntervalLabel(campaign.interval_minutes)}</small>
          </span>
          <CampaignStatusBadge status={campaign.status} />
          <span className="projectCampaignCounters">
            <span>Текстов <b>{items.length}</b></span>
            <span>В очереди <b>{queuedCount}</b></span>
            <span className="published">Опубликовано <b>{publishedCount}</b></span>
            <span className={failedCount ? "failed" : ""}>Ошибки <b>{failedCount}</b></span>
          </span>
        </button>
        <div className="projectCampaignActions">
          {["active", "paused"].includes(campaign.status) ? (
            <span className="projectCampaignModeControls">
              <select value={itemsPerDayDraft} onChange={(event) => setItemsPerDayDraft(Number(event.target.value))} disabled={isRescheduling || isPublishingAll} aria-label="Режим публикации кампании" title="Режим публикации">
                <option value={1}>1 текст в сутки · 24 ч</option>
                <option value={2}>2 текста в сутки · 12 ч</option>
                <option value={3}>3 текста в сутки · 7 ч</option>
              </select>
              <button className="button compact applyCampaignModeButton" type="button" onClick={() => void onRescheduleCampaign(campaign, itemsPerDayDraft)} disabled={!publicationModeChanged || isRescheduling || isPublishingAll}>
                {isRescheduling ? "Пересчёт…" : "Применить"}
              </button>
            </span>
          ) : null}
          {unpublishedCount > 0 ? (
            <button className="button compact primary publishAllCampaignButton" type="button" onClick={() => void onPublishAll(campaign)} disabled={isPublishingAll} title="Сформировать единый JSON и отправить все тексты кампании">
              <Send size={15} /> {isPublishingAll ? "Публикуем…" : "Опубликовать все"}
            </button>
          ) : null}
          {campaign.status === "active" ? (
            <button className="button compact campaignActionIconButton" type="button" onClick={() => void onChangeCampaign(campaign, "pause")} title="Приостановить" aria-label="Приостановить кампанию"><Pause size={15} /></button>
          ) : null}
          {campaign.status === "paused" ? (
            <button className="button compact campaignActionIconButton" type="button" onClick={() => void onChangeCampaign(campaign, "resume")} title="Продолжить" aria-label="Продолжить кампанию"><Play size={15} /></button>
          ) : null}
          {["active", "paused"].includes(campaign.status) ? (
            <button className="button compact danger campaignActionIconButton" type="button" onClick={() => void onChangeCampaign(campaign, "stop")} title="Остановить" aria-label="Остановить кампанию"><X size={15} /></button>
          ) : null}
        </div>
      </div>
      {expanded ? (
        <div className="projectCampaignBody">
          <ResponsiveTable
            columns={["№", "Тема", "Пункт меню", "Публикация", "Статус", "Действия"]}
            rows={orderedItems.map((item, index) => [
              index + 1,
              <span className="campaignTopicWithPreview">
                <span className="compactContentTopic" title={item.topic}><ContentTopicLabel item={item} /></span>
                <button className="contentPreviewIconButton" type="button" onClick={() => onPreview(item)} title="Просмотреть текст и метаданные" aria-label={`Просмотреть текст: ${item.topic}`}><Eye size={14} /></button>
              </span>,
              sectionLabel(item.section_id, sections),
              item.published_at ? formatDate(item.published_at) : item.scheduled_at ? formatDate(item.scheduled_at) : "—",
              <StatusBadge status={item.status} />,
              <span className="projectCampaignRowActions">
                {item.status !== "published" ? (
                  <button className="button compact primary publishImmediatelyButton" type="button" onClick={() => void onPublishImmediately(item)} disabled={publishingNowId === item.id || item.status === "publishing"}>
                    <Send size={14} /> {publishingNowId === item.id ? "Отправляем…" : "Отправить"}
                  </button>
                ) : item.published_url ? <a href={item.published_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Открыть</a> : "—"}
              </span>
            ])}
            wrapperClassName="projectCampaignContentTable"
          />
          {!orderedItems.length ? <div className="projectCampaignEmpty">В этой кампании пока нет текстов.</div> : null}
        </div>
      ) : null}
    </article>
  );
}

function ProjectMenuPanel({ api, site, sections, content, menuCapabilities, onAddContent, onChanged }: ViewProps & { site: Site; sections: Section[]; content: ContentItem[]; menuCapabilities: MenuCapabilities | null; onAddContent: (section: Section) => void }) {
  const [name, setName] = React.useState("");
  const [path, setPath] = React.useState("");
  const [menuType, setMenuType] = React.useState<"header" | "footer">("header");
  const [parentId, setParentId] = React.useState("");
  const [parentName, setParentName] = React.useState("");
  const [parentTreeKey, setParentTreeKey] = React.useState("");
  const [formError, setFormError] = React.useState("");
  const [addExpanded, setAddExpanded] = usePersistentWorkspacePanelState("menu-add-item", false);
  const [inlineMenuType, setInlineMenuType] = React.useState<"header" | "footer" | null>(null);
  const [addingMenuItemId, setAddingMenuItemId] = React.useState<string | null>(null);
  const [libraryFormExpanded, setLibraryFormExpanded] = React.useState(false);
  const [libraryName, setLibraryName] = React.useState("");
  const [libraryPath, setLibraryPath] = React.useState("");
  const [savingLibraryItem, setSavingLibraryItem] = React.useState(false);
  const [editingLibraryItem, setEditingLibraryItem] = React.useState<MenuLibraryItem | null>(null);
  const [editingLibraryName, setEditingLibraryName] = React.useState("");
  const [editingLibraryPath, setEditingLibraryPath] = React.useState("");
  const [editingLibraryRussianName, setEditingLibraryRussianName] = React.useState("");
  const [savingLibraryEdit, setSavingLibraryEdit] = React.useState(false);
  const [menuTemplates, setMenuTemplates] = React.useState<MenuTemplate[]>([]);
  const [applyingTemplateId, setApplyingTemplateId] = React.useState<string | null>(null);
  const [templateApplyMessage, setTemplateApplyMessage] = React.useState("");
  const [updatedAt, setUpdatedAt] = React.useState<string | null>(null);
  const [editingSectionId, setEditingSectionId] = React.useState<string | null>(null);
  const [editingSectionName, setEditingSectionName] = React.useState("");
  const [editingSectionPath, setEditingSectionPath] = React.useState("");
  const [savingSectionEdit, setSavingSectionEdit] = React.useState(false);
  const [deletingSectionId, setDeletingSectionId] = React.useState<string | null>(null);
  const [restoringSectionId, setRestoringSectionId] = React.useState<string | null>(null);
  const [menuNestingNotice, setMenuNestingNotice] = React.useState("");
  const [adoptingParentKey, setAdoptingParentKey] = React.useState<string | null>(null);
  const [temporaryParentId, setTemporaryParentId] = React.useState<string | null>(null);
  const [releasingTemporaryParent, setReleasingTemporaryParent] = React.useState(false);
  const [pagePreview, setPagePreview] = React.useState<ProjectPagePreview | null>(null);
  const [pagePreviewError, setPagePreviewError] = React.useState<{ title: string; slug: string; message: string } | null>(null);
  const [pagePreviewLoadingKey, setPagePreviewLoadingKey] = React.useState<string | null>(null);
  const cachedHeader = Array.isArray(site.default_menu.header) ? site.default_menu.header : [];
  const cachedFooter = Array.isArray(site.default_menu.footer) ? site.default_menu.footer : [];
  const menuLibrary = React.useMemo(() => {
    const itemsById = new Map(getMenuLibrary(site.cache_language).map((item) => [item.external_id, item]));
    for (const template of menuTemplates) {
      for (const item of template.items) itemsById.set(item.external_id, item);
    }
    for (const item of Array.isArray(site.menu_library) ? site.menu_library : []) itemsById.set(item.external_id, item);
    return Array.from(itemsById.values());
  }, [menuTemplates, site.cache_language, site.menu_library]);
  const existingSectionIds = React.useMemo(() => new Set(sections.map((section) => section.external_id)), [sections]);
  const existingHeaderSectionPaths = React.useMemo(
    () => new Set(
      sections
        .filter((section) => section.menu_type === "header")
        .map((section) => {
          const pathWithoutEdgeSlashes = section.path.trim().replace(/^\/+|\/+$/g, "");
          return pathWithoutEdgeSlashes ? `/${pathWithoutEdgeSlashes}/` : "/";
        })
    ),
    [sections]
  );
  const persistedSections = React.useMemo(() => sections.filter((section) => !section.is_temporary_parent), [sections]);
  const pendingSections = React.useMemo(() => sections.filter((section) => section.sync_status === "pending"), [sections]);
  const menuLibraryListId = React.useId();

  React.useEffect(() => {
    setName("");
    setPath("");
    setParentId("");
    setParentName("");
    setParentTreeKey("");
    setTemporaryParentId(null);
    setInlineMenuType(null);
    setLibraryFormExpanded(false);
    setLibraryName("");
    setLibraryPath("");
    setEditingLibraryItem(null);
    setMenuTemplates([]);
    setTemplateApplyMessage("");
    setUpdatedAt(null);
    setPagePreview(null);
    setPagePreviewError(null);
    setPagePreviewLoadingKey(null);
    setMenuNestingNotice("");
  }, [site.id]);

  async function openPagePreview(item: MenuPreviewItem, treeKey: string) {
    const slug = normalizedTreePath(item.path);
    setPagePreviewLoadingKey(treeKey);
    setPagePreviewError(null);
    try {
      const preview = await api<ProjectPagePreview>(`/sites/${site.id}/pages/preview?slug=${encodeURIComponent(slug || item.path || "#")}`);
      setPagePreview(preview);
    } catch (error) {
      setPagePreviewError({
        title: item.title,
        slug: item.path,
        message: error instanceof Error ? error.message : "Не удалось загрузить текст страницы"
      });
    } finally {
      setPagePreviewLoadingKey(null);
    }
  }

  React.useEffect(() => {
    let cancelled = false;
    void api<MenuTemplate[]>(`/menu-templates?language=${encodeURIComponent(site.cache_language || "")}`)
      .then((templates) => {
        if (!cancelled) setMenuTemplates(templates);
      })
      .catch((error) => {
        if (!cancelled) setFormError(error instanceof Error ? error.message : "Не удалось загрузить шаблоны меню");
      });
    return () => { cancelled = true; };
  }, [api, site.cache_language, site.id]);

  function updateMenuName(value: string) {
    setName(value);
    const libraryItem = menuLibrary.find((item) => item.name === value);
    if (libraryItem) setPath(libraryItem.path);
  }

  function openInlineForm(targetMenuType: "header" | "footer") {
    setName("");
    setPath("");
    setMenuType(targetMenuType);
    setParentId("");
    setParentName("");
    setParentTreeKey("");
    setInlineMenuType((current) => current === targetMenuType ? null : targetMenuType);
    setAddExpanded(false);
    setFormError("");
  }

  async function openChildForm(targetMenuType: "header" | "footer", item: MenuPreviewItem, existingParent?: Section, treeKey = "") {
    const nestingSupported = targetMenuType === "header" ? menuCapabilities?.header_menu_nested : menuCapabilities?.footer_menu_nested;
    if (nestingSupported === false) {
      setMenuNestingNotice(
        `${targetMenuType === "header" ? "Header" : "Footer"}: шаблон проекта поддерживает только один уровень меню. `
        + "Обратитесь к веб-разработчику, чтобы добавить выпадающее меню, затем повторите добавление вложенного пункта."
      );
      return;
    }
    const itemPath = normalizedTreePath(item.path) || normalizedTreePath(existingParent?.path || "");
    if (!itemPath) {
      setFormError(`У пункта «${item.title}» отсутствует корректный URL. Обновите проект и повторите попытку.`);
      return;
    }
    setMenuNestingNotice("");
    const parentKey = `${targetMenuType}:${item.externalId}`;
    setAdoptingParentKey(parentKey);
    setFormError("");
    try {
      const adopted = existingParent
        ? { section: existingParent, created: false }
        : await api<{ section: Section; created: boolean }>(`/sites/${site.id}/sections/adopt`, {
            method: "POST",
            body: JSON.stringify({
              external_id: item.externalId,
              name: item.title,
              path: itemPath,
              menu_type: targetMenuType,
              parent_id: null
            })
          });
      setName("");
      setPath("");
      setMenuType(targetMenuType);
      setParentId(adopted.section.id);
      setParentName(item.title);
      setParentTreeKey(treeKey);
      setTemporaryParentId(adopted.created || adopted.section.is_temporary_parent ? adopted.section.id : null);
      setInlineMenuType(targetMenuType);
      setAddExpanded(false);
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось выбрать родительский пункт");
    } finally {
      setAdoptingParentKey(null);
    }
  }

  async function addContentToMenuItem(targetMenuType: "header" | "footer", item: MenuPreviewItem, existingSection?: Section) {
    setFormError("");
    const itemPath = normalizedTreePath(item.path) || normalizedTreePath(existingSection?.path || "");
    if (!itemPath) {
      setFormError(`У пункта «${item.title}» отсутствует корректный URL. Обновите проект и повторите попытку.`);
      return;
    }
    try {
      const result = existingSection
        ? { section: existingSection, created: false }
        : await api<{ section: Section; created: boolean }>(`/sites/${site.id}/sections/content-target`, {
            method: "POST",
            body: JSON.stringify({
              external_id: item.externalId,
              name: item.title,
              path: itemPath,
              menu_type: targetMenuType,
              parent_id: null
            })
          });
      if (result.created) await onChanged();
      onAddContent(result.section);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось выбрать пункт меню для контента");
    }
  }

  async function cancelInlineMenuForm() {
    const sectionId = temporaryParentId;
    setInlineMenuType(null);
    setName("");
    setPath("");
    setParentId("");
    setParentName("");
    setParentTreeKey("");
    setTemporaryParentId(null);
    if (!sectionId) return;
    setReleasingTemporaryParent(true);
    setFormError("");
    try {
      await api(`/sites/${site.id}/sections/${sectionId}/adopt`, { method: "DELETE" });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось удалить временный родительский пункт");
    } finally {
      setReleasingTemporaryParent(false);
    }
  }

  function startSectionEdit(section: Section) {
    setEditingSectionId(section.id);
    setEditingSectionName(section.name);
    setEditingSectionPath(section.path);
    setFormError("");
  }

  function cancelSectionEdit() {
    setEditingSectionId(null);
    setEditingSectionName("");
    setEditingSectionPath("");
  }

  async function saveSectionEdit(section: Section) {
    if (!editingSectionName.trim() || !editingSectionPath.trim()) return;
    setSavingSectionEdit(true);
    setFormError("");
    try {
      const updated = await api<Section>(`/sites/${site.id}/sections/${section.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: editingSectionName.trim(), path: editingSectionPath.trim() })
      });
      setUpdatedAt(updated.updated_at);
      cancelSectionEdit();
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось изменить пункт меню");
    } finally {
      setSavingSectionEdit(false);
    }
  }

  async function deleteSection(section: Section) {
    if (!window.confirm(`Удалить пункт меню «${section.name}» из нашей системы?`)) return;
    setDeletingSectionId(section.id);
    setFormError("");
    try {
      await api(`/sites/${site.id}/sections/${section.id}`, { method: "DELETE" });
      if (editingSectionId === section.id) cancelSectionEdit();
      setUpdatedAt(new Date().toISOString());
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось удалить пункт меню");
    } finally {
      setDeletingSectionId(null);
    }
  }

  async function restoreSection(section: Section) {
    setRestoringSectionId(section.id);
    setFormError("");
    setMenuNestingNotice("");
    try {
      await api<Section>(`/sites/${site.id}/sections/${section.id}/restore`, { method: "POST" });
      const syncResult = await api<ProjectChangesSyncResult>(`/sites/${site.id}/sync-changes`, { method: "POST" });
      if (!syncResult.success) {
        const failure = syncResult.results.find((result) => !result.success);
        throw new Error(failure?.error || "Не удалось восстановить пункт меню на проекте");
      }
      setUpdatedAt(new Date().toISOString());
      await onChanged();
    } catch (error) {
      setMenuNestingNotice(error instanceof Error ? error.message : "Не удалось восстановить пункт меню");
      await onChanged();
    } finally {
      setRestoringSectionId(null);
    }
  }

  async function saveMenuItem(targetMenuType: "header" | "footer", item?: MenuLibraryItem) {
    const itemName = (item?.name || name).trim();
    const itemPath = (item?.path || path).trim();
    if (!itemName || !itemPath) return;
    setFormError("");
    const pathWithoutEdgeSlashes = itemPath.replace(/^\/+|\/+$/g, "");
    const normalizedPath = pathWithoutEdgeSlashes ? `/${pathWithoutEdgeSlashes}/` : "/";
    const libraryItem = item || menuLibrary.find((candidate) => candidate.name === itemName);
    const actionId = `${libraryItem?.external_id || slugFromText(itemName)}:${targetMenuType}`;
    setAddingMenuItemId(actionId);
    try {
      const created = await api<Section>(`/sites/${site.id}/sections`, {
        method: "POST",
        body: JSON.stringify({
          name: itemName,
          external_id: libraryItem?.external_id || slugFromText(itemName),
          path: normalizedPath,
          menu_type: targetMenuType,
          parent_id: parentId || null
        })
      });
      setName("");
      setPath("");
      setParentId("");
      setParentName("");
      setParentTreeKey("");
      setTemporaryParentId(null);
      setInlineMenuType(null);
      setUpdatedAt(created.updated_at || new Date().toISOString());
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось добавить пункт меню");
    } finally {
      setAddingMenuItemId(null);
    }
  }

  async function createSection(event: React.FormEvent, targetMenuType = menuType) {
    event.preventDefault();
    await saveMenuItem(targetMenuType);
  }

  async function addLibraryItem(event: React.FormEvent) {
    event.preventDefault();
    const itemName = libraryName.trim();
    const rawPath = libraryPath.trim();
    if (!itemName || !rawPath) return;
    const pathWithoutEdgeSlashes = rawPath.replace(/^\/+|\/+$/g, "");
    const normalizedPath = pathWithoutEdgeSlashes ? `/${pathWithoutEdgeSlashes}/` : "/";
    setSavingLibraryItem(true);
    setFormError("");
    try {
      await api<MenuLibraryItem>(`/sites/${site.id}/menu-library`, {
        method: "POST",
        body: JSON.stringify({
          name: itemName,
          path: normalizedPath,
          external_id: slugFromText(itemName),
          russian_name: ""
        })
      });
      setLibraryName("");
      setLibraryPath("");
      setLibraryFormExpanded(false);
      setUpdatedAt(new Date().toISOString());
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось добавить пункт в библиотеку");
    } finally {
      setSavingLibraryItem(false);
    }
  }

  async function applyMenuTemplate(template: MenuTemplate) {
    setApplyingTemplateId(template.id);
    setTemplateApplyMessage("");
    setFormError("");
    try {
      const result = await api<MenuTemplateApplyResult>(`/sites/${site.id}/menu-templates/${encodeURIComponent(template.id)}/apply`, {
        method: "POST"
      });
      setTemplateApplyMessage(
        `Структура добавлена: новых пунктов — ${result.created_count}, уже существовало — ${result.skipped_count}, обновлена вложенность — ${result.updated_count}.`
      );
      setUpdatedAt(new Date().toISOString());
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось добавить готовую структуру меню");
    } finally {
      setApplyingTemplateId(null);
    }
  }

  function openLibraryEdit(item: MenuLibraryItem) {
    setEditingLibraryItem(item);
    setEditingLibraryName(item.name);
    setEditingLibraryPath(item.path);
    setEditingLibraryRussianName(item.russian_name || "");
    setFormError("");
  }

  async function saveLibraryEdit(event: React.FormEvent) {
    event.preventDefault();
    if (!editingLibraryItem || !editingLibraryName.trim() || !editingLibraryPath.trim()) return;
    setSavingLibraryEdit(true);
    setFormError("");
    try {
      await api<MenuLibraryItem>(`/sites/${site.id}/menu-library/${encodeURIComponent(editingLibraryItem.external_id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editingLibraryName.trim(),
          path: editingLibraryPath.trim(),
          russian_name: editingLibraryRussianName.trim()
        })
      });
      setEditingLibraryItem(null);
      setUpdatedAt(new Date().toISOString());
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось изменить пункт библиотеки");
    } finally {
      setSavingLibraryEdit(false);
    }
  }

  function menuFields(targetMenuType?: "header" | "footer") {
    const effectiveMenuType = targetMenuType || menuType;
    const nestingSupported = effectiveMenuType === "header" ? menuCapabilities?.header_menu_nested : menuCapabilities?.footer_menu_nested;
    const possibleParents = sections.filter((section) => section.menu_type === effectiveMenuType);
    const sectionById = new Map(sections.map((section) => [section.id, section]));
    const parentLabel = (section: Section) => {
      const names = [section.name];
      const visited = new Set([section.id]);
      let current = section.parent_id ? sectionById.get(section.parent_id) : undefined;
      while (current && !visited.has(current.id)) {
        names.unshift(current.name);
        visited.add(current.id);
        current = current.parent_id ? sectionById.get(current.parent_id) : undefined;
      }
      return names.join(" → ");
    };
    return (
      <>
        {targetMenuType && parentId ? <div className="siteMenuSelectedParent"><CornerDownRight size={17} /><span>Дочерний пункт для:</span><strong>{parentName || sections.find((section) => section.id === parentId)?.name}</strong></div> : null}
        <label>
          Пункт меню
          <input list={menuLibraryListId} value={name} onChange={(event) => updateMenuName(event.target.value)} placeholder="Выберите или введите свой" required />
          <datalist id={menuLibraryListId}>
            {menuLibrary.map((item) => <option value={item.name} label={item.russian_name ? `* ${item.russian_name} · ${item.path}` : item.path} key={item.external_id} />)}
          </datalist>
        </label>
        <label>
          URL
          <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="casino-bonuses" required />
        </label>
        {!targetMenuType && nestingSupported && possibleParents.length ? <label>
          Родительский пункт
          <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
            <option value="">Без вложенности</option>
            {possibleParents.map((section) => <option value={section.id} key={section.id}>{parentLabel(section)}</option>)}
          </select>
        </label> : null}
        {targetMenuType ? (
          <div className="siteMenuInlineActions">
            <button className="button siteMenuCancelButton" type="button" onClick={cancelInlineMenuForm} disabled={Boolean(addingMenuItemId) || releasingTemporaryParent}>{releasingTemporaryParent ? "Отменяем" : "Отменить"}</button>
            <button className="button primary" type="submit" disabled={Boolean(addingMenuItemId)}>{addingMenuItemId ? "Сохраняем" : "Сохранить"}</button>
          </div>
        ) : <button className="button primary" type="submit" disabled={Boolean(addingMenuItemId)}>{addingMenuItemId ? "Сохраняем" : "Сохранить"}</button>}
      </>
    );
  }

  return (
    <section className="viewStack">
      <DataPanel title="Структура меню проекта" allowCollapse={false}>
        {menuNestingNotice ? <div className="notice menuNestingNotice" role="note"><AlertTriangle size={17} /><span>{menuNestingNotice}</span></div> : null}
        <section className={`menuAddPanel embeddedMenuAddPanel ${addExpanded ? "expanded" : ""}`}>
          <button className="menuAddToggle" type="button" onClick={() => { setInlineMenuType(null); setAddExpanded((current) => !current); }} aria-expanded={addExpanded}>
            <span className="menuAddToggleIcon"><Plus size={18} /></span>
            <span><strong>Добавить пункт меню</strong><small>{addExpanded ? "Нажмите, чтобы свернуть" : "Добавить новый пункт в существующую структуру"}</small></span>
            {addExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
          {addExpanded ? <form className="menuAddForm simplifiedMenuForm" onSubmit={createSection}>
            <label>
              Тип меню
              <select value={menuType} onChange={(event) => setMenuType(event.target.value as "header" | "footer")}>
                <option value="header">Header</option>
                <option value="footer">Footer</option>
              </select>
            </label>
            {menuFields()}
            {formError ? <span className="formError simplifiedMenuFormError">{formError}</span> : null}
            {updatedAt ? <span className="formSuccess simplifiedMenuFormError">Информация обновлена: {formatDate(updatedAt)}</span> : null}
          </form> : null}
        </section>
        <div className="projectMenuStructureGrid">
          <SiteMenuPreviewSection key={`${site.id}:header`} title="Меню Header" icon={<HeaderMenuIcon />} items={cachedHeader} sections={sections.filter((section) => section.menu_type === "header" && section.sync_status !== "external_deleted")} content={content} adoptingParentKey={adoptingParentKey} activeParentTreeKey={inlineMenuType === "header" ? parentTreeKey : ""} pagePreviewLoadingKey={pagePreviewLoadingKey} onPreviewPage={(item, treeKey) => void openPagePreview(item, treeKey)} onAddContent={(item, section) => void addContentToMenuItem("header", item, section)} onAddChild={(item, section, treeKey) => openChildForm("header", item, section, treeKey)} action={<button className="siteMenuInlineAddButton" type="button" onClick={() => openInlineForm("header")}><span className="buttonPlusIcon"><Plus size={15} /></span> Добавить пункт в Header</button>}>
            {inlineMenuType === "header" ? <form className="siteMenuInlineForm" onSubmit={(event) => createSection(event, "header")}>{menuFields("header")}{formError ? <span className="formError">{formError}</span> : null}</form> : null}
          </SiteMenuPreviewSection>
          <SiteMenuPreviewSection key={`${site.id}:footer`} title="Меню Footer" icon={<FooterMenuIcon />} items={cachedFooter} sections={sections.filter((section) => section.menu_type === "footer" && section.sync_status !== "external_deleted")} content={content} adoptingParentKey={adoptingParentKey} activeParentTreeKey={inlineMenuType === "footer" ? parentTreeKey : ""} pagePreviewLoadingKey={pagePreviewLoadingKey} onPreviewPage={(item, treeKey) => void openPagePreview(item, treeKey)} onAddContent={(item, section) => void addContentToMenuItem("footer", item, section)} onAddChild={(item, section, treeKey) => openChildForm("footer", item, section, treeKey)} action={<button className="siteMenuInlineAddButton" type="button" onClick={() => openInlineForm("footer")}><span className="buttonPlusIcon"><Plus size={15} /></span> Добавить пункт в Footer</button>}>
            {inlineMenuType === "footer" ? <form className="siteMenuInlineForm" onSubmit={(event) => createSection(event, "footer")}>{menuFields("footer")}{formError ? <span className="formError">{formError}</span> : null}</form> : null}
          </SiteMenuPreviewSection>
        </div>
        {persistedSections.length ? <ResponsiveTable
          wrapperClassName="pendingMenuChangesTable"
          columns={["Название", "Тип меню", "URL", "Изменено", "Состояние", "Действия"]}
          rows={persistedSections.map((section) => {
            const editing = editingSectionId === section.id;
            return [
              editing ? <input className="menuSectionEditInput" value={editingSectionName} onChange={(event) => setEditingSectionName(event.target.value)} aria-label="Название пункта меню" /> : section.name,
              section.menu_type === "footer" ? "Footer" : "Header",
              editing ? <input className="menuSectionEditInput" value={editingSectionPath} onChange={(event) => setEditingSectionPath(event.target.value)} aria-label="URL пункта меню" /> : section.path,
              formatDate(section.synced_at || section.updated_at),
              section.sync_status === "synced"
                ? <span className="syncedBadge">Синхронизировано</span>
                : section.sync_status === "external_deleted"
                  ? <span className="pendingSyncBadge">Удалено на проекте</span>
                  : <span className="pendingSyncBadge">Не синхронизировано</span>,
              editing ? <div className="menuSectionEditActions"><button className="button compact secondary" type="button" onClick={cancelSectionEdit} disabled={savingSectionEdit}>Отменить</button><button className="button compact primary" type="button" onClick={() => saveSectionEdit(section)} disabled={savingSectionEdit}>Сохранить</button></div> : <div className="menuSectionEditActions">{section.sync_status === "external_deleted" ? <button className="button compact primary" type="button" onClick={() => restoreSection(section)} disabled={restoringSectionId === section.id}><RefreshCcw size={14} /> {restoringSectionId === section.id ? "Восстанавливаем" : "Восстановить"}</button> : <button className="button compact secondary" type="button" onClick={() => startSectionEdit(section)} disabled={deletingSectionId === section.id}><Edit3 size={14} /> Изменить</button>}<button className="button compact danger" type="button" onClick={() => deleteSection(section)} disabled={deletingSectionId === section.id || restoringSectionId === section.id}><Trash2 size={14} /> {deletingSectionId === section.id ? "Удаляем" : "Удалить"}</button></div>
            ];
          })}
        /> : null}
        {pagePreview ? <ProjectPagePreviewModal preview={pagePreview} onClose={() => setPagePreview(null)} /> : null}
        {pagePreviewError ? <Modal title={`Просмотр страницы: ${pagePreviewError.title}`} subtitle={pagePreviewError.slug || "URL не указан"} onClose={() => setPagePreviewError(null)}><div className="emptyState">{pagePreviewError.message}</div></Modal> : null}
      </DataPanel>
      <DataPanel
        title={`Библиотека пунктов меню · ${menuLibrary.length}`}
        allowCollapse={false}
        actions={<button className="button secondary compact" type="button" onClick={() => setLibraryFormExpanded((current) => !current)}><span className="buttonPlusIcon"><Plus size={15} /></span> Новый пункт</button>}
      >
          {menuTemplates.map((template) => {
            const existingCount = template.items.filter((item) => existingSectionIds.has(item.external_id) || existingHeaderSectionPaths.has(item.path)).length;
            const missingCount = template.items.length - existingCount;
            const rootCount = template.items.filter((item) => !item.parent_external_id).length;
            const applying = applyingTemplateId === template.id;
            return (
              <article className="menuTemplateCard" key={template.id}>
                <span className="menuTemplateIcon"><ListChecks size={23} /></span>
                <div className="menuTemplateCopy">
                  <strong>{template.name}</strong>
                  <span>{template.description}</span>
                  <small>{rootCount} основных разделов · {template.items.length} пунктов · до {template.max_depth} уровней · только Header</small>
                </div>
                <div className="menuTemplateProgress">
                  <b>{existingCount}/{template.items.length}</b>
                  <span>уже добавлено</span>
                </div>
                <button className="button primary menuTemplateApplyButton" type="button" onClick={() => void applyMenuTemplate(template)} disabled={applying || missingCount === 0}>
                  <span className="buttonPlusIcon"><Plus size={15} /></span>
                  {applying ? "Добавляем…" : missingCount ? `Добавить всю структуру (${missingCount})` : "Структура добавлена"}
                </button>
              </article>
            );
          })}
          {templateApplyMessage ? <div className="formSuccess menuTemplateResult">{templateApplyMessage}</div> : null}
          {libraryFormExpanded ? (
            <form className="menuLibraryCreateForm" onSubmit={addLibraryItem}>
              <label>Название<input value={libraryName} onChange={(event) => setLibraryName(event.target.value)} placeholder="Введите название" required /></label>
              <label>URL<input value={libraryPath} onChange={(event) => setLibraryPath(event.target.value)} placeholder="new-section" required /></label>
              <button className="button primary compact" type="submit" disabled={savingLibraryItem}><span className="buttonPlusIcon"><Plus size={15} /></span> {savingLibraryItem ? "Сохраняем" : "Добавить в библиотеку"}</button>
            </form>
          ) : null}
          <div className="menuItemLibraryHeader">
            <div>
              <strong>Выберите отдельный пункт</strong>
              <span>Быстрое добавление в Header или Footer</span>
            </div>
            <b>{site.cache_language}</b>
          </div>
          {updatedAt ? <div className="formSuccess">Информация обновлена: {formatDate(updatedAt)}</div> : null}
          {formError ? <div className="formError">{formError}</div> : null}
          <div className="menuItemLibraryGrid">
            {menuLibrary.map((item) => {
              const alreadyAdded = existingSectionIds.has(item.external_id);
              const addingToHeader = addingMenuItemId === `${item.external_id}:header`;
              const addingToFooter = addingMenuItemId === `${item.external_id}:footer`;
              return (
                <article className={`menuItemLibraryCard ${alreadyAdded ? "isAdded" : ""}`} key={item.external_id}>
                  <div className="menuItemLibraryText">
                    <strong>{item.name}</strong>
                    <code>{item.path}</code>
                    {item.russian_name ? <small>* {item.russian_name}</small> : null}
                  </div>
                  <div className="menuItemLibraryActions">
                    <button className="button compact menuLibraryEditButton" type="button" data-tooltip="Редактировать" aria-label={`Редактировать ${item.name}`} onClick={() => openLibraryEdit(item)}>
                      <Edit3 size={14} />
                    </button>
                    {alreadyAdded ? <span>Уже добавлен</span> : (
                      <>
                        <button className="button compact menuPlacementButton" type="button" data-tooltip="Добавить в Header" aria-label={`Добавить ${item.name} в Header`} onClick={() => saveMenuItem("header", item)} disabled={Boolean(addingMenuItemId)}>
                          <HeaderMenuIcon /> {addingToHeader ? "Добавляем" : "Header"}
                        </button>
                        <button className="button compact menuPlacementButton" type="button" data-tooltip="Добавить в Footer" aria-label={`Добавить ${item.name} в Footer`} onClick={() => saveMenuItem("footer", item)} disabled={Boolean(addingMenuItemId)}>
                          <FooterMenuIcon /> {addingToFooter ? "Добавляем" : "Footer"}
                        </button>
                      </>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
      </DataPanel>
      {editingLibraryItem ? (
        <Modal title="Редактировать пункт библиотеки" subtitle="Изменения сохранятся только для выбранного проекта" onClose={() => setEditingLibraryItem(null)}>
          <form className="menuLibraryEditForm" onSubmit={saveLibraryEdit}>
            <label>Название<input value={editingLibraryName} onChange={(event) => setEditingLibraryName(event.target.value)} required autoFocus /></label>
            <label>URL<input value={editingLibraryPath} onChange={(event) => setEditingLibraryPath(event.target.value)} required /></label>
            <label>Перевод на русский<input value={editingLibraryRussianName} onChange={(event) => setEditingLibraryRussianName(event.target.value)} /></label>
            {formError ? <span className="formError">{formError}</span> : null}
            <div className="modalActions">
              <button className="button secondary" type="button" onClick={() => setEditingLibraryItem(null)} disabled={savingLibraryEdit}>Отменить</button>
              <button className="button primary" type="submit" disabled={savingLibraryEdit}>{savingLibraryEdit ? "Сохраняем" : "Сохранить"}</button>
            </div>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}

function HeaderMenuIcon() {
  return (
    <svg className="menuPlacementIcon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2.5" y="3.5" width="19" height="17" rx="3" />
      <path className="menuPlacementIconAccent" d="M3 7.5h18" />
      <path d="M6.5 5.6h3M11 5.6h2" />
    </svg>
  );
}

function FooterMenuIcon() {
  return (
    <svg className="menuPlacementIcon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2.5" y="3.5" width="19" height="17" rx="3" />
      <path className="menuPlacementIconAccent" d="M3 16.5h18" />
      <path d="M6.5 18.4h3M11 18.4h2" />
    </svg>
  );
}

function TasksView({
  api,
  sites,
  providers,
  tasks,
  fixedSite,
  onProjectChange,
  sections = [],
  promptTemplates = [],
  onChanged
}: ViewProps & {
  sites: Site[];
  providers: AiProvider[];
  tasks: Task[];
  fixedSite?: Site;
  onProjectChange?: (siteId: string) => void;
  sections?: Section[];
  promptTemplates?: PromptTemplate[];
}) {
  const [geo, setGeo] = React.useState(() => projectGeoCode(fixedSite));
  const [language, setLanguage] = React.useState(() => projectLanguageCode(fixedSite));
  const [topics, setTopics] = React.useState("");
  const [siteId, setSiteId] = React.useState(fixedSite?.id || "");
  const [providerId, setProviderId] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [promptTemplateId, setPromptTemplateId] = React.useState("");
  const [targetWords, setTargetWords] = React.useState(DEFAULT_TARGET_WORDS);
  const taskCheckboxPreferences = React.useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("task_create_checkbox_preferences") || "{}") as Partial<Record<"includeToc" | "includeFaq" | "collectCompetitors" | "includeCasinoRating", boolean>>;
    } catch {
      return {};
    }
  }, []);
  const [includeToc, setIncludeToc] = React.useState(taskCheckboxPreferences.includeToc ?? true);
  const [includeFaq, setIncludeFaq] = React.useState(taskCheckboxPreferences.includeFaq ?? true);
  const [collectCompetitors, setCollectCompetitors] = React.useState(taskCheckboxPreferences.collectCompetitors ?? false);
  const [includeCasinoRating, setIncludeCasinoRating] = React.useState(taskCheckboxPreferences.includeCasinoRating ?? false);
  const [createFormExpanded, setCreateFormExpanded] = React.useState(false);
  const [creatingTaskAction, setCreatingTaskAction] = React.useState<"draft" | "start" | "">("");
  const [generatingTopics, setGeneratingTopics] = React.useState(false);
  const [topicGenerationProgress, setTopicGenerationProgress] = useSimulatedOperationProgress(generatingTopics);
  const [expandedTaskId, setExpandedTaskId] = React.useState("");
  const [expandedDetails, setExpandedDetails] = React.useState<TaskDetails | null>(null);
  const [expandedResearch, setExpandedResearch] = React.useState<CompetitorResearch[]>([]);
  const [detailsLoadingId, setDetailsLoadingId] = React.useState("");
  const [taskActionId, setTaskActionId] = React.useState("");
  const [taskError, setTaskError] = React.useState("");
  const [queryModal, setQueryModal] = React.useState<{ item: ContentItem } | null>(null);
  const [queryDraft, setQueryDraft] = React.useState("");
  const [promptModalTask, setPromptModalTask] = React.useState<Task | null>(null);
  const [previewItem, setPreviewItem] = React.useState<ContentItem | null>(null);
  const hasResearchInProgress = expandedResearch.some((entry) => ACTIVE_RESEARCH_STATUSES.includes(entry.status));
  const hasGenerationInProgress = (expandedDetails?.items || []).some((item) => ACTIVE_GENERATION_STATUSES.includes(item.status));
  const cleanTopics = topics.split("\n").map((line) => line.trim()).filter(Boolean);
  const selectedSite = sites.find((site) => site.id === siteId);
  const automaticTaskTitle = selectedSite
    ? `${selectedSite.name} · ${cleanTopics.length} тем · ${language.toUpperCase()}-${geo.toUpperCase()}`
    : "Выберите проект — название сформируется автоматически";
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === promptTemplateId)
    || defaultPromptTemplate(promptTemplates);

  React.useEffect(() => {
    if (fixedSite && siteId !== fixedSite.id) {
      setSiteId(fixedSite.id);
    }
  }, [fixedSite, siteId]);

  React.useEffect(() => {
    if (!selectedSite) return;
    const storageKey = `workspace_add_content_section:${selectedSite.id}`;
    const requestedSectionId = window.sessionStorage.getItem(storageKey);
    if (!requestedSectionId || !sections.some((section) => section.id === requestedSectionId)) return;
    window.sessionStorage.removeItem(storageKey);
    setSectionId(requestedSectionId);
    setCreateFormExpanded(true);
  }, [sections, selectedSite]);

  React.useEffect(() => {
    if (!selectedSite) return;
    setGeo(projectGeoCode(selectedSite));
    setLanguage(projectLanguageCode(selectedSite));
  }, [selectedSite?.id, selectedSite?.cache_geo, selectedSite?.cache_language, selectedSite?.cache_canon]);

  React.useEffect(() => {
    const generationProviders = providers.filter(isGenerationProvider);
    if (!providerId || !generationProviders.some((provider) => provider.id === providerId)) {
      const geminiProvider = generationProviders.find((provider) => provider.provider_type === "gemini" && provider.is_active);
      setProviderId(geminiProvider?.id || "");
    }
  }, [providerId, providers]);

  React.useEffect(() => {
    if (!promptTemplateId && promptTemplates.length) {
      setPromptTemplateId(defaultPromptTemplate(promptTemplates)?.id || "");
    }
  }, [promptTemplateId, promptTemplates]);

  async function generateTopicsWithGemini() {
    setTaskError("");
    if (!selectedSite) {
      setTaskError("Выберите проект для генерации тем.");
      return;
    }
    if (cleanTopics.length > 20) {
      setTaskError("Чтобы добавить ещё 10 тем, оставьте в форме не более 20 тем.");
      return;
    }
    const provider = providers.find((item) => item.id === providerId);
    if (!provider || provider.provider_type !== "gemini" || !provider.is_active) {
      setTaskError("Для генерации тем выберите активный Gemini provider.");
      return;
    }
    setTopicGenerationProgress(3);
    setGeneratingTopics(true);
    try {
      const response = await api<TopicSuggestionsResponse>(`/sites/${selectedSite.id}/topic-suggestions`, {
        method: "POST",
        body: JSON.stringify({
          geo,
          language,
          ai_provider_id: provider.id,
          section_id: sectionId || null,
          current_topics: cleanTopics
        })
      });
      setTopics([...cleanTopics, ...response.topics].join("\n"));
      setTopicGenerationProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    } catch (error) {
      setTopicGenerationProgress(0);
      setTaskError(error instanceof Error ? error.message : "Gemini не смог сгенерировать уникальные темы.");
    } finally {
      setGeneratingTopics(false);
      window.setTimeout(() => setTopicGenerationProgress(0), 120);
    }
  }

  React.useEffect(() => {
    const taskId = sessionStorage.getItem("workspace_open_task_id");
    if (!taskId || !tasks.some((task) => task.id === taskId)) return;
    sessionStorage.removeItem("workspace_open_task_id");
    void loadTaskDetails(taskId);
  }, [fixedSite?.id, tasks]);

  React.useEffect(() => {
    localStorage.setItem("task_create_checkbox_preferences", JSON.stringify({ includeToc, includeFaq, collectCompetitors, includeCasinoRating }));
  }, [includeToc, includeFaq, collectCompetitors, includeCasinoRating]);

  React.useEffect(() => {
    if (!expandedTaskId || (!hasResearchInProgress && !hasGenerationInProgress)) return;
    let cancelled = false;
    const pollResearch = async () => {
      try {
        const [details, research] = await Promise.all([
          api<TaskDetails>(`/tasks/${expandedTaskId}`),
          api<CompetitorResearch[]>(`/tasks/${expandedTaskId}/competitor-research`)
        ]);
        if (cancelled) return;
        setExpandedDetails(details);
        setExpandedResearch(research);
        const researchFinished = !research.some((entry) => ACTIVE_RESEARCH_STATUSES.includes(entry.status));
        const generationFinished = !details.items.some((item) => ACTIVE_GENERATION_STATUSES.includes(item.status));
        if (researchFinished && generationFinished) {
          await onChanged();
        }
      } catch (pollError) {
        if (!cancelled) setTaskError(pollError instanceof Error ? pollError.message : "Не удалось обновить прогресс сбора конкурентов.");
      }
    };
    const intervalId = window.setInterval(pollResearch, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [api, expandedTaskId, hasGenerationInProgress, hasResearchInProgress, onChanged]);

  async function createTask(event: React.FormEvent) {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const action = submitter?.value === "draft" ? "draft" : "start";
    setTaskError("");
    if (!siteId) {
      setTaskError("Выберите проект для создания задачи.");
      return;
    }
    const payload = {
      geo,
      language,
      site_id: siteId || null,
      section_id: sectionId || null,
      ai_provider_id: providerId || null,
      payload_mode: "site_default",
      target_words: targetWords || null,
      prompt_template_name: selectedPrompt?.name || null,
      prompt_template: selectedPrompt?.content || null,
      shortcode: null,
      include_toc: includeToc,
      include_faq: includeFaq,
      collect_competitors: collectCompetitors,
      include_casino_rating: includeCasinoRating,
      save_as_draft: action === "draft",
      topics: cleanTopics
    };
    setCreatingTaskAction(action);
    try {
      const task = await api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) });
      if (action === "start") {
        await api(`/tasks/${task.id}/start`, { method: "POST" });
      }
      setTopics("");
      setCreateFormExpanded(false);
      await onChanged();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось создать задачу.");
    } finally {
      setCreatingTaskAction("");
    }
  }

  async function loadTaskDetails(taskId: string) {
    setTaskError("");
    setDetailsLoadingId(taskId);
    try {
      const [details, research] = await Promise.all([
        api<TaskDetails>(`/tasks/${taskId}`),
        api<CompetitorResearch[]>(`/tasks/${taskId}/competitor-research`)
      ]);
      setExpandedTaskId(taskId);
      setExpandedDetails(details);
      setExpandedResearch(research);
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось открыть задачу.");
    } finally {
      setDetailsLoadingId("");
    }
  }

  async function toggleTask(task: Task) {
    if (detailsLoadingId) return;
    if (expandedTaskId === task.id) {
      setExpandedTaskId("");
      setExpandedDetails(null);
      setExpandedResearch([]);
      return;
    }
    await loadTaskDetails(task.id);
  }

  async function refreshExpandedTask() {
    if (!expandedTaskId) return;
    await loadTaskDetails(expandedTaskId);
    await onChanged();
  }

  async function archiveTask(task: Task) {
    const confirmed = window.confirm(`Удалить задачу "${task.title}"? Она будет перемещена в архив и её можно будет восстановить.`);
    if (!confirmed) return;
    setTaskError("");
    setTaskActionId(`${task.id}:archive`);
    try {
      await api(`/tasks/${task.id}`, { method: "DELETE" });
      if (expandedTaskId === task.id) {
        setExpandedTaskId("");
        setExpandedDetails(null);
        setExpandedResearch([]);
      }
      await onChanged();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось переместить задачу в архив.");
    } finally {
      setTaskActionId("");
    }
  }

  async function startTaskPipeline(task: Task) {
    setTaskError("");
    setTaskActionId(`${task.id}:start`);
    try {
      await api(`/tasks/${task.id}/start`, { method: "POST" });
      if (expandedTaskId === task.id) await loadTaskDetails(task.id);
      await onChanged();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось запустить задачу.");
    } finally {
      setTaskActionId("");
    }
  }

  async function changeTaskSection(task: Task, nextSectionId: string) {
    setTaskError("");
    setTaskActionId(`${task.id}:section`);
    try {
      await api<Task>(`/tasks/${task.id}/section`, {
        method: "PATCH",
        body: JSON.stringify({ section_id: nextSectionId || null })
      });
      if (expandedTaskId === task.id) await loadTaskDetails(task.id);
      await onChanged();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось выбрать пункт меню.");
    } finally {
      setTaskActionId("");
    }
  }

  async function openQueryEditor(item: ContentItem) {
    setTaskError("");
    setTaskActionId(`${item.id}:queries`);
    try {
      const research = await api<CompetitorResearch>(`/content/${item.id}/competitor-research`);
      setQueryModal({ item });
      setQueryDraft(research.queries.map((query) => query.query).join("\n"));
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось открыть запросы.");
    } finally {
      setTaskActionId("");
    }
  }

  async function saveQueryEditor(event: React.FormEvent) {
    event.preventDefault();
    if (!queryModal) return;
    const cleanQueries = queryDraft.split("\n").map((line) => line.trim()).filter(Boolean);
    setTaskError("");
    setTaskActionId(`${queryModal.item.id}:save-queries`);
    try {
      await api(`/content/${queryModal.item.id}/competitor-queries`, {
        method: "PUT",
        body: JSON.stringify({ queries: cleanQueries })
      });
      setQueryModal(null);
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось сохранить запросы.");
    } finally {
      setTaskActionId("");
    }
  }

  async function regenerateCompetitorQueries(item: ContentItem) {
    setTaskError("");
    setTaskActionId(`${item.id}:regenerate-queries`);
    try {
      await api(`/content/${item.id}/competitor-queries/regenerate`, { method: "POST" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось пересоздать запросы.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkRegenerateCompetitorQueries(items: ContentItem[]) {
    if (!items.length) return;
    setTaskError("");
    setTaskActionId("bulk:regenerate-queries");
    let failed = 0;
    try {
      for (const item of items) {
        try {
          await api(`/content/${item.id}/competitor-queries/regenerate`, { method: "POST" });
        } catch {
          failed += 1;
        }
      }
      await refreshExpandedTask();
      if (failed) {
        setTaskError(`Не удалось сгенерировать запросы для части тем: ${failed}.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось сгенерировать запросы для задачи.");
    } finally {
      setTaskActionId("");
    }
  }

  async function collectItemCompetitors(item: ContentItem) {
    setTaskError("");
    setTaskActionId(`${item.id}:collect-competitors`);
    try {
      await api(`/content/${item.id}/competitor-collect`, { method: "POST" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось собрать конкурентов.");
    } finally {
      setTaskActionId("");
    }
  }

  async function regenerateContent(item: ContentItem) {
    setTaskError("");
    setTaskActionId(`${item.id}:generate`);
    try {
      await api(`/content/${item.id}/generate`, { method: "POST" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось запустить генерацию.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkApproveTaskContent(items: ContentItem[]) {
    const actionable = items.filter(canApproveContent);
    if (!actionable.length) return;
    setTaskError("");
    setTaskActionId("bulk:approve");
    try {
      const results = await Promise.allSettled(actionable.map((item) => api(`/content/${item.id}/approve`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await refreshExpandedTask();
      if (failed) {
        setTaskError(`Не удалось принять часть текстов: ${failed}. Проверьте, выбран ли пункт меню.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось принять выбранные тексты.");
    } finally {
      setTaskActionId("");
    }
  }

  async function approveTaskContent(item: ContentItem) {
    setTaskError("");
    setTaskActionId(`${item.id}:approve`);
    try {
      await api(`/content/${item.id}/approve`, { method: "POST" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось принять текст.");
    } finally {
      setTaskActionId("");
    }
  }

  async function publishTaskContent(item: ContentItem) {
    if (!canPublishContentImmediately(item)) {
      setTaskError("Перед публикацией выберите проект и пункт меню.");
      return;
    }
    setTaskError("");
    setTaskActionId(`${item.id}:publish`);
    try {
      await api(`/content/${item.id}/publish-immediately`, { method: "POST" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось опубликовать текст.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkPublishTaskContent(items: ContentItem[]) {
    const actionable = items.filter(canPublishContentImmediately);
    if (!actionable.length) return;
    setTaskError("");
    setTaskActionId("bulk:publish");
    try {
      const results = await Promise.allSettled(actionable.map((item) => api(`/content/${item.id}/publish-immediately`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await refreshExpandedTask();
      if (failed) setTaskError(`Не удалось опубликовать часть текстов: ${failed}.`);
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось опубликовать выбранные тексты.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkRegenerateTaskContent(items: ContentItem[]) {
    const actionable = items.filter((item) => !isPublicationLocked(item));
    if (!actionable.length) return;
    setTaskError("");
    setTaskActionId("bulk:generate");
    try {
      const results = await Promise.allSettled(actionable.map((item) => api(`/content/${item.id}/generate`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await refreshExpandedTask();
      if (failed) {
        setTaskError(`Не удалось перегенерировать часть текстов: ${failed}.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось запустить повторную генерацию.");
    } finally {
      setTaskActionId("");
    }
  }

  async function regenerateAllTaskContent(task: Task, options: TaskRegenerateAllOptions) {
    const mutableCount = (expandedDetails?.items || []).filter((item) => !isPublicationLocked(item)).length;
    if (!mutableCount) return;
    const confirmed = window.confirm(
      `Перегенерировать все доступные тексты задачи (${mutableCount}) по промпту «${options.prompt_template_name}»? Запланированные и опубликованные тексты останутся без изменений.`
    );
    if (!confirmed) return;
    setTaskError("");
    setTaskActionId(`${task.id}:regenerate-all`);
    try {
      await api(`/tasks/${task.id}/regenerate-all`, {
        method: "POST",
        body: JSON.stringify(options)
      });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось запустить генерацию всех текстов задачи.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkCollectTaskCompetitors(items: ContentItem[]) {
    if (!items.length) return;
    setTaskError("");
    setTaskActionId("bulk:collect-competitors");
    let failed = 0;
    try {
      for (const item of items) {
        try {
          await api(`/content/${item.id}/competitor-collect`, { method: "POST" });
        } catch {
          failed += 1;
        }
      }
      await refreshExpandedTask();
      if (failed) {
        setTaskError(`Не удалось собрать конкурентов для части текстов: ${failed}.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось собрать конкурентов для выбранных текстов.");
    } finally {
      setTaskActionId("");
    }
  }

  async function deleteContentItem(item: ContentItem) {
    const confirmed = window.confirm(`Удалить сгенерированный контент по теме "${item.topic}"?`);
    if (!confirmed) return;
    setTaskError("");
    setTaskActionId(`${item.id}:delete`);
    try {
      await api(`/content/${item.id}`, { method: "DELETE" });
      await refreshExpandedTask();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось удалить контент.");
    } finally {
      setTaskActionId("");
    }
  }

  async function bulkDeleteTaskContent(items: ContentItem[]) {
    const deletable = items.filter((item) => !isPublicationLocked(item));
    if (!deletable.length) return;
    const confirmed = window.confirm(`Удалить выбранные тексты: ${deletable.length}?`);
    if (!confirmed) return;
    setTaskError("");
    setTaskActionId("bulk:delete");
    try {
      const results = await Promise.allSettled(deletable.map((item) => api(`/content/${item.id}`, { method: "DELETE" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      await refreshExpandedTask();
      if (failed) {
        setTaskError(`Не удалось удалить часть текстов: ${failed}. Scheduled/published контент не удаляется.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось удалить выбранные тексты.");
    } finally {
      setTaskActionId("");
    }
  }

  function toggleCreateForm() {
    setCreateFormExpanded((current) => !current);
  }

  return (
    <section className="viewStack">
      <div className="taskCreateToolbar">
        <button
          className="newGenerationTaskButton"
          type="button"
          onClick={toggleCreateForm}
          aria-haspopup="dialog"
        >
          <span className="newGenerationTaskIcon" aria-hidden="true">
            <Brain size={25} strokeWidth={2.1} />
            <Plus className="newGenerationTaskIconPlus" size={13} strokeWidth={3} />
          </span>
          <span className="newGenerationTaskCopy">
            <strong>Новая задача на генерацию</strong>
            <small>Добавить темы для генерации текстов</small>
          </span>
        </button>
      </div>
      {createFormExpanded ? (
        <Modal
          title="Создать задачу генерации"
          subtitle="Настройте параметры и добавьте темы для новой задачи"
          onClose={() => setCreateFormExpanded(false)}
          wide
          className="createGenerationTaskModal"
          headerActions={(
            <div className="generationModalHeaderActions">
              <button
                className="button secondary compact"
                type="submit"
                form="create-generation-task-form"
                name="taskAction"
                value="draft"
                disabled={Boolean(creatingTaskAction)}
              >
                <FileText size={16} /> {creatingTaskAction === "draft" ? "Сохраняем" : "Сохранить как черновик"}
              </button>
              <button
                className="button primary compact"
                type="submit"
                form="create-generation-task-form"
                name="taskAction"
                value="start"
                disabled={Boolean(creatingTaskAction)}
              >
                <Play size={16} /> {creatingTaskAction === "start" ? "Запускаем" : "Запустить"}
              </button>
            </div>
          )}
        >
        <form id="create-generation-task-form" className="formGrid createTaskForm" onSubmit={createTask}>
          <label>
            {fixedSite ? "Проект" : "Выберите проект"}
            <SearchableSelect
              value={siteId}
              onChange={(nextSiteId) => {
                setSiteId(nextSiteId);
                onProjectChange?.(nextSiteId);
              }}
              options={[
                ...(fixedSite ? [] : [{ value: "", label: "Проект не выбран" }]),
                ...sites.map(projectSearchOption)
              ]}
              searchPlaceholder="Введите название проекта"
            />
          </label>
          <label>
            Гео
            <SearchableSelect
              value={geo}
              onChange={setGeo}
              options={COUNTRIES.map((country) => ({ value: country.code, label: `${country.flag} ${country.name} (${country.code})` }))}
              searchPlaceholder="Введите страну или код"
            />
          </label>
          <label className="automaticTaskTitleField">
            Название задачи
            <input value={automaticTaskTitle} readOnly aria-readonly="true" />
            <span className="fieldHint">Формируется автоматически: проект · количество тем · язык-гео</span>
          </label>
          <label>
            Язык
            <SearchableSelect
              value={language}
              onChange={setLanguage}
              options={LANGUAGE_OPTIONS.map((option) => ({ value: option.code, label: `${option.flag} ${option.nativeName} (${option.code.toUpperCase()})`, keywords: option.name }))}
              searchPlaceholder="Введите язык или код"
            />
          </label>
          <label>
            AI Provider
            <SearchableSelect
              value={providerId}
              onChange={setProviderId}
              options={[{ value: "", label: "Stub generator" }, ...providers.filter(isGenerationProvider).map((provider) => ({ value: provider.id, label: provider.name }))]}
              searchPlaceholder="Найти AI Provider"
            />
          </label>
          <label>
            Количество слов
            <input value={targetWords} onChange={(event) => setTargetWords(Number(event.target.value))} type="number" min={300} max={8000} step={100} required />
          </label>
          {promptTemplates.length ? (
            <label>
              Промпт генерации
              <SearchableSelect
                value={promptTemplateId}
                onChange={setPromptTemplateId}
                options={promptTemplates.map((prompt) => ({ value: prompt.id, label: `${prompt.is_default ? "Default · " : ""}${prompt.name}` }))}
                searchPlaceholder="Найти промпт"
              />
            </label>
          ) : null}
          {sections.length ? (
            <label>
              Пункт меню
              <SearchableSelect
                value={sectionId}
                onChange={setSectionId}
                options={[{ value: "", label: "Выбрать позже" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
                searchPlaceholder="Найти пункт меню"
              />
            </label>
          ) : null}
          <fieldset className="generationOptionsGroup wide">
            <legend>Параметры генерации</legend>
            <div className="generationOptionsGrid">
              <label className="checkboxRow">
                <input type="checkbox" checked={includeToc} onChange={(event) => setIncludeToc(event.target.checked)} />
                Добавить содержание
              </label>
              <label className="checkboxRow">
                <input type="checkbox" checked={includeFaq} onChange={(event) => setIncludeFaq(event.target.checked)} />
                Создавать FAQ
              </label>
              <label className="checkboxRow">
                <input type="checkbox" checked={collectCompetitors} onChange={(event) => setCollectCompetitors(event.target.checked)} />
                Собрать конкурентов
              </label>
              <label className="checkboxRow casinoRatingOption">
                <input type="checkbox" checked={includeCasinoRating} onChange={(event) => setIncludeCasinoRating(event.target.checked)} />
                <span><b>Собрать рейтинг казино</b><small>Рейтинг из 5–10 казино с оценками и обоснованием мест.</small></span>
              </label>
            </div>
          </fieldset>
          <label className="wide">
            <span className="topicFieldHeader">
              <span>Темы, каждая с новой строки</span>
              <button
                className="button compact topicGenerateButton"
                type="button"
                onClick={generateTopicsWithGemini}
                disabled={generatingTopics || !selectedSite || cleanTopics.length > 20}
                title={cleanTopics.length > 20 ? "Для добавления 10 тем в форме должно быть не более 20 тем" : "Добавить 10 уникальных тем через Gemini"}
              >
                {generatingTopics ? <CircularOperationProgress value={topicGenerationProgress} /> : <Sparkles size={15} />}
                {generatingTopics ? "Генерация тем" : "Сгенерировать 10 тем"}
              </button>
            </span>
            <textarea value={topics} onChange={(event) => setTopics(event.target.value)} required rows={5} placeholder="best online casinos in Germany" />
            <span className="fieldHint">Тем в задаче: {cleanTopics.length}</span>
          </label>
          {taskError ? <span className="formError wide">{taskError}</span> : null}
          <div className="formActions wide">
            <button className="button secondary" type="submit" name="taskAction" value="draft" disabled={Boolean(creatingTaskAction)}>
              <FileText size={18} /> {creatingTaskAction === "draft" ? "Сохраняем" : "Сохранить как черновик"}
            </button>
            <button className="button primary" type="submit" name="taskAction" value="start" disabled={Boolean(creatingTaskAction)}>
              <Play size={18} /> {creatingTaskAction === "start" ? "Запускаем" : "Запустить"}
            </button>
          </div>
        </form>
        </Modal>
      ) : null}
      <DataPanel title="Все задачи" allowCollapse={false}>
        <AdminTasksAccordion
          tasks={tasks}
          sections={sections}
          promptTemplates={promptTemplates}
          expandedTaskId={expandedTaskId}
          expandedDetails={expandedDetails}
          research={expandedResearch}
          loadingId={detailsLoadingId}
          actionId={taskActionId}
          onToggle={toggleTask}
          onStart={startTaskPipeline}
          onSectionChange={changeTaskSection}
          onArchive={archiveTask}
          onEditQueries={openQueryEditor}
          onRegenerateQueries={regenerateCompetitorQueries}
          onCollectCompetitors={collectItemCompetitors}
          onPreview={setPreviewItem}
          onRegenerate={regenerateContent}
          onDelete={deleteContentItem}
          onApprove={approveTaskContent}
          onPublish={publishTaskContent}
          onBulkApprove={bulkApproveTaskContent}
          onBulkPublish={bulkPublishTaskContent}
          onBulkRegenerateQueries={bulkRegenerateCompetitorQueries}
          onBulkCollectCompetitors={bulkCollectTaskCompetitors}
          onBulkRegenerate={bulkRegenerateTaskContent}
          onRegenerateAll={regenerateAllTaskContent}
          onBulkDelete={bulkDeleteTaskContent}
          onShowPrompt={(task) => setPromptModalTask(task)}
        />
        {taskError ? <span className="formError">{taskError}</span> : null}
      </DataPanel>
      {queryModal ? (
        <Modal title={`Запросы конкурентов: ${queryModal.item.topic}`} onClose={() => setQueryModal(null)} wide>
          <form className="modalForm" onSubmit={saveQueryEditor}>
            <label>
              Список запросов, каждый с новой строки
              <textarea value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} rows={8} placeholder="beste online casinos deutschland" />
              <span className={queryDraft.split("\n").map((line) => line.trim()).filter(Boolean).length > 5 ? "fieldHint danger" : "fieldHint"}>
                {queryDraft.split("\n").map((line) => line.trim()).filter(Boolean).length}/5 запросов
              </span>
            </label>
            <div className="formActions">
              <button className="button secondary" type="button" onClick={() => setQueryModal(null)}>Отмена</button>
              <button className="button primary" type="submit" disabled={taskActionId.endsWith(":save-queries") || queryDraft.split("\n").map((line) => line.trim()).filter(Boolean).length < 1 || queryDraft.split("\n").map((line) => line.trim()).filter(Boolean).length > 5}>
                <Edit3 size={16} /> {taskActionId.endsWith(":save-queries") ? "Сохраняю" : "Сохранить"}
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
      {promptModalTask ? (
        <Modal title={`Промпт задачи: ${promptModalTask.title}`} onClose={() => setPromptModalTask(null)} wide>
          <textarea className="promptTextarea modalPrompt" value={promptModalTask.prompt_template || "Промпт не сохранен в задаче."} readOnly rows={22} />
        </Modal>
      ) : null}
      {previewItem ? (
        <ContentPreviewModal
          item={previewItem}
          promptName={previewItem.generation_prompt_name || expandedDetails?.task.prompt_template_name}
          onClose={() => setPreviewItem(null)}
          actions={(
            <>
              <button className="button compact approve" type="button" onClick={() => void approveTaskContent(previewItem)} disabled={!canApproveContent(previewItem) || taskActionId.startsWith(previewItem.id)}><CheckCircle2 size={15} /> Принять</button>
              <button className="button compact primary" type="button" onClick={() => void publishTaskContent(previewItem)} disabled={!canPublishContentImmediately(previewItem) || taskActionId.startsWith(previewItem.id)}><Send size={15} /> {taskActionId === `${previewItem.id}:publish` ? "Публикуем…" : "Опубликовать"}</button>
            </>
          )}
        />
      ) : null}
    </section>
  );
}

function TaskArchiveView({ api, tasks, onChanged }: ViewProps & { tasks: Task[] }) {
  const [actionId, setActionId] = React.useState("");
  const [error, setError] = React.useState("");

  async function restoreTask(task: Task) {
    setError("");
    setActionId(task.id);
    try {
      await api(`/tasks/${task.id}/restore`, { method: "POST" });
      await onChanged();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Не удалось восстановить задачу.");
    } finally {
      setActionId("");
    }
  }

  return (
    <section className="viewStack">
      <DataPanel title="Архив задач">
        {tasks.length ? (
          <ResponsiveTable
            columns={["Задача", "Гео", "Язык", "Тем", "Создана", "Перемещена в архив", "Действия"]}
            rows={tasks.map((task) => [
              <strong>{task.title}</strong>,
              countryLabel(task.geo),
              languageLabel(task.language),
              task.topics_count,
              formatDate(task.created_at),
              task.archived_at ? formatDate(task.archived_at) : "-",
              <button className="button compact" type="button" onClick={() => restoreTask(task)} disabled={actionId === task.id}>
                <RefreshCcw size={15} /> {actionId === task.id ? "Восстанавливаю" : "Восстановить"}
              </button>
            ])}
          />
        ) : <EmptyState text="В архиве пока нет задач." />}
        {error ? <span className="formError">{error}</span> : null}
      </DataPanel>
    </section>
  );
}

function AdminTasksAccordion({
  tasks,
  sections,
  promptTemplates,
  expandedTaskId,
  expandedDetails,
  research,
  loadingId,
  actionId,
  onToggle,
  onStart,
  onSectionChange,
  onArchive,
  onEditQueries,
  onRegenerateQueries,
  onCollectCompetitors,
  onPreview,
  onRegenerate,
  onDelete,
  onApprove,
  onPublish,
  onBulkApprove,
  onBulkPublish,
  onBulkRegenerateQueries,
  onBulkCollectCompetitors,
  onBulkRegenerate,
  onRegenerateAll,
  onBulkDelete,
  onShowPrompt
}: {
  tasks: Task[];
  sections: Section[];
  promptTemplates: PromptTemplate[];
  expandedTaskId: string;
  expandedDetails: TaskDetails | null;
  research: CompetitorResearch[];
  loadingId: string;
  actionId: string;
  onToggle: (task: Task) => Promise<void>;
  onStart: (task: Task) => Promise<void>;
  onSectionChange: (task: Task, sectionId: string) => Promise<void>;
  onArchive: (task: Task) => Promise<void>;
  onEditQueries: (item: ContentItem) => Promise<void>;
  onRegenerateQueries: (item: ContentItem) => Promise<void>;
  onCollectCompetitors: (item: ContentItem) => Promise<void>;
  onPreview: (item: ContentItem) => void;
  onRegenerate: (item: ContentItem) => Promise<void>;
  onDelete: (item: ContentItem) => Promise<void>;
  onApprove: (item: ContentItem) => Promise<void>;
  onPublish: (item: ContentItem) => Promise<void>;
  onBulkApprove: (items: ContentItem[]) => Promise<void>;
  onBulkPublish: (items: ContentItem[]) => Promise<void>;
  onBulkRegenerateQueries: (items: ContentItem[]) => Promise<void>;
  onBulkCollectCompetitors: (items: ContentItem[]) => Promise<void>;
  onBulkRegenerate: (items: ContentItem[]) => Promise<void>;
  onRegenerateAll: (task: Task, options: TaskRegenerateAllOptions) => Promise<void>;
  onBulkDelete: (items: ContentItem[]) => Promise<void>;
  onShowPrompt: (task: Task) => void;
}) {
  const expandedTask = expandedDetails?.task;
  const expandedItems = React.useMemo(() => expandedDetails?.items || [], [expandedDetails?.items]);
  const expandedItemIds = React.useMemo(() => expandedItems.map((item) => item.id), [expandedItems]);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [copyState, setCopyState] = React.useState("");
  const [regeneratePromptId, setRegeneratePromptId] = React.useState("");
  const [regenerateIncludeToc, setRegenerateIncludeToc] = React.useState(true);
  const [regenerateIncludeFaq, setRegenerateIncludeFaq] = React.useState(true);
  const [regenerateCollectCompetitors, setRegenerateCollectCompetitors] = React.useState(false);
  const [regenerateIncludeCasinoRating, setRegenerateIncludeCasinoRating] = React.useState(false);
  const [summaryDialog, setSummaryDialog] = React.useState<"queries" | "competitors" | null>(null);
  const selectedItems = expandedItems.filter((item) => selectedIds.includes(item.id));
  const allSelected = expandedItemIds.length > 0 && expandedItemIds.every((id) => selectedIds.includes(id));
  const bulkApproveItems = selectedItems.filter(canApproveContent);
  const bulkPublishItems = selectedItems.filter(canPublishContentImmediately);
  const bulkDeleteItems = selectedItems.filter((item) => !isPublicationLocked(item));
  const bulkRegenerateItems = selectedItems.filter((item) => !isPublicationLocked(item));
  const bulkCollectItems = selectedItems;
  const bulkBusy = actionId.startsWith("bulk:");
  const researchByItem = new Map(research.map((entry) => [entry.content_item_id, entry]));
  const totalQueries = research.reduce((sum, entry) => sum + entry.queries.length, 0);
  const competitorBriefs = expandedItems.filter((item) => item.competitor_brief || researchByItem.get(item.id)?.brief).length;
  const competitorRequestItems = expandedItems.filter((item) => !(item.competitor_brief || researchByItem.get(item.id)?.brief));
  const taskQueryGroups = expandedItems.map((item) => ({
    topic: item.topic,
    queries: researchByItem.get(item.id)?.queries || []
  })).filter((group) => group.queries.length > 0);
  const generatedDates = expandedItems.map((item) => item.generated_at).filter(Boolean) as string[];
  const sortedGeneratedDates = generatedDates.sort();
  const latestGeneration = sortedGeneratedDates.length ? sortedGeneratedDates[sortedGeneratedDates.length - 1] : null;

  React.useEffect(() => {
    setSelectedIds([]);
    setCopyState("");
    setSummaryDialog(null);
  }, [expandedTaskId]);

  React.useEffect(() => {
    if (!expandedTask) return;
    const matchingPrompt = promptTemplates.find((prompt) => prompt.name === expandedTask.prompt_template_name);
    setRegeneratePromptId(matchingPrompt?.id || defaultPromptTemplate(promptTemplates)?.id || "");
    setRegenerateIncludeToc(expandedTask.include_toc ?? true);
    setRegenerateIncludeFaq(expandedTask.include_faq ?? true);
    setRegenerateCollectCompetitors(expandedTask.collect_competitors ?? false);
    setRegenerateIncludeCasinoRating(expandedTask.include_casino_rating ?? false);
  }, [expandedTask?.id, promptTemplates]);

  React.useEffect(() => {
    setSelectedIds((current) => {
      const next = current.filter((id) => expandedItemIds.includes(id));
      return next.length === current.length ? current : next;
    });
  }, [expandedItemIds]);

  if (!tasks.length) return <EmptyState text="Данных пока нет." />;

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? [] : expandedItemIds);
  }

  async function handleBulkApprove() {
    await onBulkApprove(bulkApproveItems);
    setSelectedIds([]);
  }

  async function handleBulkRegenerate() {
    await onBulkRegenerate(bulkRegenerateItems);
    setSelectedIds([]);
  }

  async function handleRegenerateAll() {
    if (!expandedTask) return;
    const selectedPrompt = promptTemplates.find((prompt) => prompt.id === regeneratePromptId);
    if (!selectedPrompt) return;
    await onRegenerateAll(expandedTask, {
      prompt_template_name: selectedPrompt.name,
      prompt_template: selectedPrompt.content,
      include_toc: regenerateIncludeToc,
      include_faq: regenerateIncludeFaq,
      collect_competitors: regenerateCollectCompetitors,
      include_casino_rating: regenerateIncludeCasinoRating
    });
  }

  async function handleBulkCollectCompetitors() {
    await onBulkCollectCompetitors(bulkCollectItems);
    setSelectedIds([]);
  }

  async function handleRequestCompetitors() {
    await onBulkCollectCompetitors(competitorRequestItems);
  }

  async function handleGenerateQueries() {
    const hasCollectedResearch = research.some((entry) => entry.results.length || entry.pages.length || entry.brief);
    if (hasCollectedResearch) {
      const confirmed = window.confirm("Сгенерировать запросы заново? Старые результаты сбора конкурентов и competitor brief для тем этой задачи будут удалены.");
      if (!confirmed) return;
    }
    await onBulkRegenerateQueries(expandedItems);
  }

  async function handleBulkDelete() {
    await onBulkDelete(bulkDeleteItems);
    setSelectedIds([]);
  }

  async function handleBulkPublish() {
    await onBulkPublish(bulkPublishItems);
    setSelectedIds([]);
  }

  async function copyTopicNames() {
    const topicNames = expandedItems.map((item) => item.topic).join("\n");
    if (!topicNames) return;
    setCopyState("");
    try {
      await copyTextToClipboard(topicNames);
      setCopyState("Скопировано");
      window.setTimeout(() => setCopyState(""), 2400);
    } catch {
      setCopyState("Не удалось скопировать");
    }
  }

  return (
    <>
    <div className="tasksTableWrap">
      <table className="expandableTable">
        <thead>
          <tr>
            <th>Задача</th>
            <th>Создана</th>
            <th>Гео</th>
            <th>Язык</th>
            <th>Пункт меню</th>
            <th>Промпт</th>
            <th>Тем</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => {
            const expanded = expandedTaskId === task.id;
            const loading = loadingId === task.id;
            return (
              <React.Fragment key={task.id}>
                <tr
                  className={`clickableRow ${expanded ? "isExpanded" : ""} ${loading ? "isLoading" : ""}`}
                  onClick={() => {
                    if (!loadingId) onToggle(task);
                  }}
                  aria-busy={loading}
                >
                  <td data-label="Задача">
                    <span className="taskTitleCell">
                      {loading ? <LoaderCircle className="taskRowSpinner" size={17} /> : expanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                      <strong>{task.title}</strong>
                      {loading ? <span className="taskRowLoadingText">Загружаем темы…</span> : null}
                      {expanded && !loading ? <span className="taskRowCollapseHint">Нажмите строку, чтобы свернуть</span> : null}
                    </span>
                  </td>
                  <td data-label="Создана">{formatDate(task.created_at)}</td>
                  <td data-label="Гео">{countryLabel(task.geo)}</td>
                  <td data-label="Язык">{languageLabel(task.language)}</td>
                  <td data-label="Пункт меню" onClick={(event) => event.stopPropagation()}>
                    <select
                      className={`taskMenuSectionSelect ${task.section_id ? "hasValue" : ""}`}
                      value={task.section_id || ""}
                      onChange={(event) => onSectionChange(task, event.target.value)}
                      disabled={actionId === `${task.id}:section` || !sections.length}
                      aria-label={`Пункт меню задачи ${task.title}`}
                    >
                      <option value="">Не выбран</option>
                      {sections.map((section) => <option value={section.id} key={section.id}>{section.name} · {section.path}</option>)}
                    </select>
                  </td>
                  <td data-label="Промпт" onClick={(event) => event.stopPropagation()}>
                    <span className="taskPromptSummary">
                      <PromptBadge name={task.prompt_template_name} />
                      <button className="taskPromptPreviewButton" type="button" onClick={() => onShowPrompt(task)} title="Посмотреть промпт" aria-label={`Посмотреть промпт задачи ${task.title}`}><Eye size={14} /></button>
                    </span>
                  </td>
                  <td data-label="Тем">{task.topics_count}</td>
                  <td data-label="Статус"><StatusBadge status={task.status} /></td>
                  <td data-label="Действия">
                    <span className="taskRowActions">
                      <button
                        className="button compact primary"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onStart(task);
                        }}
                        disabled={loading || actionId === `${task.id}:start` || ["generation_queued", "generating"].includes(task.status)}
                        title="Собрать или повторно собрать конкурентов и запустить генерацию всех незавершённых тем"
                      >
                        <Play size={15} /> {actionId === `${task.id}:start` ? "Запускаю" : "Запустить"}
                      </button>
                      <button
                        className="button compact danger"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onArchive(task);
                        }}
                        disabled={loading || actionId === `${task.id}:archive`}
                      >
                        <Archive size={15} /> {actionId === `${task.id}:archive` ? "Переношу" : "Удалить"}
                      </button>
                    </span>
                  </td>
                </tr>
                {expanded ? (
                  <tr className="expandedRow">
                    <td colSpan={9}>
                      {loadingId === task.id && !expandedDetails ? (
                        <EmptyState text="Загружаю детали задачи." />
                      ) : expandedTask ? (
                        <div className="taskAccordionBody">
                          <div className="taskAccordionControls">
                            <strong>Управление темами</strong>
                            <button
                              className="button compact taskAccordionCollapseButton"
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onToggle(task);
                              }}
                            >
                              <ChevronUp size={16} /> Свернуть задачу
                            </button>
                          </div>
                          <div className="taskSummaryPanel">
                            <div className="taskSummaryMetrics">
                              <button className="taskSummaryMetricButton" type="button" onClick={() => setSummaryDialog("queries")}>
                                <span>Запросы для сбора конкурентов</span>
                                <strong>{totalQueries}</strong>
                                <span className="taskSummaryListIcon" title="Посмотреть запросы"><ListChecks size={16} /></span>
                              </button>
                              <button className="taskSummaryMetricButton" type="button" onClick={() => setSummaryDialog("competitors")}>
                                <span>Конкуренты для генерации</span>
                                <strong>{competitorBriefs}/{expandedItems.length}</strong>
                                <span className="taskSummaryListIcon" title="Посмотреть конкурентов"><ListChecks size={16} /></span>
                              </button>
                            </div>
                            <div className="taskSummaryPlainInfo">
                              <span>Последняя генерация <b>{latestGeneration ? formatDate(latestGeneration) : "не запускалась"}</b></span>
                              <span>Автор задачи <b>{expandedTask.created_by_username || "—"}</b></span>
                            </div>
                          </div>
                          <div className="taskRegenerateAllPanel">
                            <div className="taskRegenerateAllHeading">
                              <div>
                                <strong>Перегенерировать задачу</strong>
                                <small>Настройки применятся к доступным текстам. Материалы в публикации не изменятся.</small>
                              </div>
                            </div>
                            <div className="taskRegeneratePrimaryRow">
                              <label className="taskRegeneratePromptField">
                                Промпт
                                <SearchableSelect
                                  value={regeneratePromptId}
                                  onChange={setRegeneratePromptId}
                                  options={promptTemplates.map((prompt) => ({ value: prompt.id, label: `${latestPromptTemplate(promptTemplates)?.id === prompt.id ? "Последняя версия · " : ""}${prompt.name}` }))}
                                  searchPlaceholder="Найти промпт"
                                  disabled={actionId === `${expandedTask.id}:regenerate-all`}
                                />
                              </label>
                              <button
                                className="button compact primary taskRegenerateAllButton"
                                type="button"
                                onClick={handleRegenerateAll}
                                disabled={!regeneratePromptId || actionId === `${expandedTask.id}:regenerate-all` || !bulkRegenerateItems.length && !expandedItems.some((item) => !isPublicationLocked(item))}
                              >
                                <Play size={15} /> {actionId === `${expandedTask.id}:regenerate-all` ? "Запускаю" : "Сгенерировать все"}
                              </button>
                            </div>
                            <div className="taskRegenerateOptions">
                              <label className="checkboxRow">
                                <input type="checkbox" checked={regenerateIncludeToc} onChange={(event) => setRegenerateIncludeToc(event.target.checked)} />
                                Добавить содержание
                              </label>
                              <label className="checkboxRow">
                                <input type="checkbox" checked={regenerateIncludeFaq} onChange={(event) => setRegenerateIncludeFaq(event.target.checked)} />
                                Создавать FAQ
                              </label>
                              <label className="checkboxRow">
                                <input type="checkbox" checked={regenerateCollectCompetitors} onChange={(event) => setRegenerateCollectCompetitors(event.target.checked)} />
                                Собрать конкурентов
                              </label>
                              <label className="checkboxRow">
                                <input type="checkbox" checked={regenerateIncludeCasinoRating} onChange={(event) => setRegenerateIncludeCasinoRating(event.target.checked)} />
                                Собрать рейтинг казино
                              </label>
                            </div>
                          </div>
                          <div className="bulkToolbar">
                            <button className="button compact" type="button" onClick={copyTopicNames} disabled={!expandedItems.length}>
                              <Copy size={15} /> Копировать темы
                            </button>
                            {copyState ? <span className="fieldHint">{copyState}</span> : null}
                            <label className="checkboxRow bulkSelectAll">
                              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} disabled={!expandedItems.length || bulkBusy} />
                              Выбрать все
                            </label>
                            <span className="fieldHint">Выбрано: {selectedIds.length}</span>
                            <button className="button compact approve" type="button" onClick={handleBulkApprove} disabled={!bulkApproveItems.length || actionId === "bulk:approve"}>
                              <CheckCircle2 size={15} /> {actionId === "bulk:approve" ? "Принимаю" : `Принять (${bulkApproveItems.length})`}
                            </button>
                            <button className="button compact primary" type="button" onClick={handleBulkPublish} disabled={!bulkPublishItems.length || actionId === "bulk:publish"} title="Сразу отправить JSON выбранных текстов на сервер проекта">
                              <Send size={15} /> {actionId === "bulk:publish" ? "Публикуем…" : `Опубликовать (${bulkPublishItems.length})`}
                            </button>
                            <button className="button compact" type="button" onClick={handleBulkCollectCompetitors} disabled={!bulkCollectItems.length || actionId === "bulk:collect-competitors"}>
                              <Globe2 size={15} /> {actionId === "bulk:collect-competitors" ? "Сбор конкурентов" : `Собрать конкурентов (${bulkCollectItems.length})`}
                            </button>
                            <button className="button compact" type="button" onClick={handleBulkRegenerate} disabled={!bulkRegenerateItems.length || actionId === "bulk:generate"}>
                              <Play size={15} /> {actionId === "bulk:generate" ? "Генерация" : `Перегенерировать (${bulkRegenerateItems.length})`}
                            </button>
                            <button className="button compact danger" type="button" onClick={handleBulkDelete} disabled={!bulkDeleteItems.length || actionId === "bulk:delete"}>
                              <Trash2 size={15} /> {actionId === "bulk:delete" ? "Удаляю" : `Удалить выбранные (${bulkDeleteItems.length})`}
                            </button>
                          </div>
                          <ResponsiveTable
                            wrapperClassName="taskTopicsTableWrap"
                            columns={["Выбор", "Тема", "Запросы", "Загружена", "Генерация", "Конкуренты", "Статус", "Действия"]}
                            rows={expandedItems.map((item) => {
                              const itemResearch = researchByItem.get(item.id);
                              const busy = actionId.startsWith(item.id) || bulkBusy || ACTIVE_GENERATION_STATUSES.includes(item.status);
                              const deleteDisabled = isPublicationLocked(item);
                              return [
                                <input className="rowCheckbox" type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelected(item.id)} disabled={bulkBusy} aria-label={`Выбрать ${item.topic}`} />,
                                <TopicMetaCell item={item} promptName={expandedTask.prompt_template_name} />,
                                <QueryCell
                                  queries={itemResearch?.queries || []}
                                  activeAction={actionId.startsWith(item.id) ? actionId.split(":")[1] : ""}
                                  busy={busy}
                                  onEdit={() => onEditQueries(item)}
                                  onRegenerate={() => onRegenerateQueries(item)}
                                />,
                                formatDate(item.created_at),
                                <GenerationProgressCell item={item} />,
                                <CompetitorCell item={item} research={itemResearch} />,
                                <StatusBadge status={item.status} />,
                                <div className="userActions">
                                  <button className="button compact" type="button" onClick={() => onCollectCompetitors(item)} disabled={busy} title="Собрать SERP, спарсить страницы и подготовить brief для генерации.">
                                    <Globe2 size={15} /> {actionId === `${item.id}:collect-competitors` ? "Сбор" : "Собрать конкурентов"}
                                  </button>
                                  <button className="button compact" type="button" onClick={() => onPreview(item)}>
                                    <FileText size={15} /> Просмотр
                                  </button>
                                  <button className="button compact" type="button" onClick={() => onRegenerate(item)} disabled={busy || isPublicationLocked(item)}>
                                    <Play size={15} /> {actionId === `${item.id}:generate` ? "Генерация" : "Сгенерировать заново"}
                                  </button>
                                  <button className="button compact approve" type="button" onClick={() => void onApprove(item)} disabled={busy || !canApproveContent(item)} title="Принять текст">
                                    <CheckCircle2 size={15} /> {actionId === `${item.id}:approve` ? "Принимаю" : "Принять"}
                                  </button>
                                  <button className="button compact primary" type="button" onClick={() => void onPublish(item)} disabled={busy || !canPublishContentImmediately(item)} title="Сразу отправить JSON текста на сервер проекта">
                                    <Send size={15} /> {actionId === `${item.id}:publish` ? "Публикуем…" : "Опубликовать"}
                                  </button>
                                  <button className="button compact danger" type="button" onClick={() => onDelete(item)} disabled={busy || deleteDisabled} title={deleteDisabled ? "Нельзя удалить scheduled/published контент" : undefined}>
                                    <Trash2 size={15} /> {actionId === `${item.id}:delete` ? "Удаляю" : "Удалить"}
                                  </button>
                                </div>
                              ];
                            })}
                            rowClassNames={expandedItems.map(contentRowClassName)}
                          />
                        </div>
                      ) : (
                        <EmptyState text="Детали задачи не загружены." />
                      )}
                    </td>
                  </tr>
                ) : null}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
    {summaryDialog === "queries" && expandedTask ? (
      <Modal title="Запросы для сбора конкурентов" subtitle={`Всего запросов: ${totalQueries}`} onClose={() => setSummaryDialog(null)} wide className="taskSummaryDetailsModal">
        <div className="taskSummaryModalToolbar">
          <span>Запросы сгруппированы по темам задачи.</span>
          <button className="button compact" type="button" onClick={handleGenerateQueries} disabled={actionId === "bulk:regenerate-queries"}>
            <RefreshCcw size={15} /> {actionId === "bulk:regenerate-queries" ? "Генерирую" : "Сгенерировать запросы"}
          </button>
        </div>
        <div className="taskSummaryDetailsList">
          {taskQueryGroups.length ? taskQueryGroups.map((group) => (
            <section className="taskSummaryDetailGroup" key={group.topic}>
              <strong>{group.topic}</strong>
              <ol>
                {group.queries.map((query) => (
                  <li key={query.id}>
                    <span>{query.query}</span>
                    <small>{query.status === "serp_collected" ? `Сбор выполнен · результатов: ${query.result_count}` : query.status === "collecting" ? "Сбор выполняется" : "Запрос подготовлен"}</small>
                  </li>
                ))}
              </ol>
            </section>
          )) : <EmptyState text="Запросы пока не подготовлены." />}
        </div>
      </Modal>
    ) : null}
    {summaryDialog === "competitors" && expandedTask ? (
      <Modal title="Конкуренты для генерации" subtitle={`Анализ готов для ${competitorBriefs} из ${expandedItems.length} тем`} onClose={() => setSummaryDialog(null)} wide className="taskSummaryDetailsModal">
        <div className="taskSummaryModalToolbar">
          <span>Показаны найденные сайты и состояние анализа по каждой теме.</span>
          <button className="button compact" type="button" onClick={handleRequestCompetitors} disabled={!competitorRequestItems.length || actionId === "bulk:collect-competitors"}>
            <Globe2 size={15} /> {actionId === "bulk:collect-competitors" ? "Запрашиваю" : competitorRequestItems.length ? `Собрать недостающие (${competitorRequestItems.length})` : "Все конкуренты собраны"}
          </button>
        </div>
        <div className="taskSummaryDetailsList">
          {expandedItems.map((item) => {
            const itemResearch = researchByItem.get(item.id);
            const results = itemResearch?.results || [];
            const briefReady = Boolean(item.competitor_brief || itemResearch?.brief);
            return (
              <section className="taskSummaryDetailGroup" key={item.id}>
                <div className="taskCompetitorDetailHeading">
                  <strong>{item.topic}</strong>
                  <span>{results.length} URL · {itemResearch?.pages.length || 0} страниц · {briefReady ? "анализ готов" : competitorStatusLabel(item, itemResearch)}</span>
                </div>
                {results.length ? (
                  <ul className="taskCompetitorLinks">
                    {results.slice(0, 10).map((result) => <li key={result.id}><a href={result.url} target="_blank" rel="noreferrer">{result.title || result.url}</a></li>)}
                  </ul>
                ) : <small className="fieldHint">Конкуренты ещё не собраны.</small>}
              </section>
            );
          })}
        </div>
      </Modal>
    ) : null}
    </>
  );
}

function competitorStatusLabel(item: ContentItem, research?: CompetitorResearch) {
  const status = research?.status || item.competitor_research_status;
  if (status === "queued") return "В очереди";
  if (status === "collecting_serp") return "Собираю выдачу Google";
  if (status === "fetching_pages") return "Загружаю страницы";
  if (status === "research_failed") return "Ошибка сбора";
  if (item.competitor_brief || research?.brief) return "Да, анализ готов";
  if ((research?.pages.length || 0) > 0) return "Страницы собраны";
  if ((research?.results.length || 0) > 0) return "URL собраны";
  if ((research?.queries.length || 0) > 0 || item.competitor_research_status === "queries_ready") return "Есть запросы";
  return "Нет";
}

function GenerationProgressCell({ item }: { item: ContentItem }) {
  const complete = ["generated", "approved", "scheduled", "retry_scheduled", "publication_paused", "publishing", "published"].includes(item.status);
  const progress = Math.max(0, Math.min(100, complete ? 100 : item.generation_progress || 0));
  const stage = item.status === "generation_queued"
    ? "В очереди"
    : item.status === "generating"
      ? "Gemini генерирует текст"
      : item.status === "generation_failed"
        ? "Ошибка генерации"
        : complete
          ? "Готово"
          : "Не запускалась";
  return (
    <div className="generationProgressCell" title={item.generation_error || undefined}>
      <span>{item.generated_at ? formatDate(item.generated_at) : "-"}</span>
      <small className={item.generation_error ? "danger" : ""}>{stage}</small>
      <div className="generationProgress" aria-label={`Прогресс генерации текста: ${progress}%`}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <b>{progress}%</b>
      <small className="generationWordCount">Слов: {item.word_count > 0 ? item.word_count.toLocaleString("ru-RU") : "—"}</small>
    </div>
  );
}

function CompetitorCell({ item, research }: { item: ContentItem; research?: CompetitorResearch }) {
  const competitors = Array.from(
    new Map((research?.results || []).map((result) => [result.normalized_url || result.url, result])).values()
  );
  const progress = Math.max(0, Math.min(100, research?.progress ?? item.competitor_research_progress ?? 0));
  const error = research?.error || item.competitor_research_error;
  return (
    <div className="queryCell competitorCell" tabIndex={0} aria-label="Показать список собранных конкурентов">
      <span className="queryCount">{competitors.length}</span>
      <span className="cellHint">{competitorStatusLabel(item, research)}</span>
      <div className="competitorProgress" aria-label={`Прогресс сбора конкурентов: ${progress}%`}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <small className={error ? "competitorProgressText danger" : "competitorProgressText"}>{error ? `Ошибка · ${progress}%` : `${progress}%`}</small>
      <div className="queryTooltip competitorTooltip" role="tooltip">
        <strong>Собранные конкуренты</strong>
        {error ? <span className="formError">{error}</span> : null}
        {competitors.length ? (
          <ol>
            {competitors.map((competitor) => (
              <li key={competitor.id}>
                <b>{competitor.title || competitor.url}</b>
                <small>{competitor.url}</small>
              </li>
            ))}
          </ol>
        ) : <span>Конкуренты по этой теме ещё не собраны.</span>}
      </div>
    </div>
  );
}

function QueryCell({
  queries,
  activeAction,
  busy,
  onEdit,
  onRegenerate
}: {
  queries: CompetitorQuery[];
  activeAction: string;
  busy: boolean;
  onEdit: () => void;
  onRegenerate: () => void;
}) {
  const queryTexts = queries.map((query) => query.query).filter(Boolean);
  return (
    <div className="queryCell" tabIndex={0}>
      <span className="queryCount">{queryTexts.length}</span>
      <div className="queryTooltip" role="tooltip">
        <strong>Подготовленные запросы</strong>
        {queryTexts.length ? (
          <ol>
            {queryTexts.map((query) => <li key={query}>{query}</li>)}
          </ol>
        ) : (
          <span>Запросы пока не подготовлены.</span>
        )}
      </div>
      <div className="queryActions">
        <button className="button compact" type="button" onClick={onEdit} disabled={busy}>
          <Search size={15} /> Редактировать
        </button>
        <button className="button compact" type="button" onClick={onRegenerate} disabled={busy}>
          <RefreshCcw size={15} /> {activeAction === "regenerate-queries" ? "Генерация" : "Сгенерировать заново"}
        </button>
      </div>
    </div>
  );
}

function contentRowClassName(item: ContentItem) {
  if (item.status === "published") return "contentRow contentRow-published";
  if (item.status === "generated") return "contentRow contentRow-generated";
  return "";
}

function isPublicationLocked(item: ContentItem) {
  return ["scheduled", "retry_scheduled", "publication_paused", "publishing", "published"].includes(item.status);
}

function canApproveContent(item: ContentItem) {
  return ["generated", "rejected"].includes(item.status);
}

function canPublishContentImmediately(item: ContentItem) {
  return Boolean(item.site_id && item.section_id) && [
    "generated",
    "rejected",
    "approved",
    "scheduled",
    "retry_scheduled",
    "publication_paused",
    "publication_failed"
  ].includes(item.status);
}

function ContentView({ api, sites, content, onChanged }: ViewProps & { sites: Site[]; content: ContentItem[] }) {
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [contentActionId, setContentActionId] = React.useState("");
  const [contentError, setContentError] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [projectSearch, setProjectSearch] = React.useState("");
  const [expandedProjectIds, setExpandedProjectIds] = React.useState<string[]>([]);
  const projectGroups = React.useMemo(() => {
    const knownSiteIds = new Set(sites.map((site) => site.id));
    const groups = sites
      .map((site) => ({
        id: site.id,
        name: site.name,
        baseUrl: site.base_url,
        medalStatus: projectMenuMedalStatus(site),
        items: content.filter((item) => item.site_id === site.id)
      }))
      .sort((first, second) => first.name.localeCompare(second.name, "ru"));
    const unassigned = content.filter((item) => !item.site_id || !knownSiteIds.has(item.site_id));
    if (unassigned.length) {
      groups.push({ id: "__unassigned__", name: "Без проекта", baseUrl: "", medalStatus: "unchecked" as ProjectMedalStatus, items: unassigned });
    }
    return groups;
  }, [content, sites]);
  const visibleProjectGroups = React.useMemo(() => {
    const search = projectSearch.trim().toLocaleLowerCase("ru");
    if (!search) return projectGroups;
    return projectGroups.filter((group) => `${group.name} ${group.baseUrl}`.toLocaleLowerCase("ru").includes(search));
  }, [projectGroups, projectSearch]);
  const selectableIds = React.useMemo(() => visibleProjectGroups.flatMap((group) => group.items.map((item) => item.id)), [visibleProjectGroups]);
  const selectedItems = content.filter((item) => selectedIds.includes(item.id));
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const bulkApproveItems = selectedItems.filter(canApproveContent);
  const bulkDeleteItems = selectedItems.filter((item) => !isPublicationLocked(item));

  React.useEffect(() => {
    setSelectedIds((current) => current.filter((id) => selectableIds.includes(id)));
  }, [selectableIds]);

  async function approve(id: string) {
    setContentError("");
    try {
      await api(`/content/${id}/approve`, { method: "POST" });
      setSelectedPreview((current) => current && current.id === id ? { ...current, status: "approved" } : current);
      await onChanged();
    } catch (error) {
      setContentError(error instanceof Error ? error.message : "Не удалось согласовать текст.");
    }
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? [] : selectableIds);
  }

  function toggleProject(projectId: string) {
    setExpandedProjectIds((current) => current.includes(projectId) ? current.filter((id) => id !== projectId) : [...current, projectId]);
  }

  function toggleProjectSelection(items: ContentItem[]) {
    const itemIds = items.map((item) => item.id);
    const projectSelected = itemIds.length > 0 && itemIds.every((id) => selectedIds.includes(id));
    setSelectedIds((current) => projectSelected
      ? current.filter((id) => !itemIds.includes(id))
      : Array.from(new Set([...current, ...itemIds]))
    );
  }

  async function bulkApprove() {
    if (!bulkApproveItems.length) return;
    setContentError("");
    setContentActionId("bulk:approve");
    try {
      const results = await Promise.allSettled(bulkApproveItems.map((item) => api(`/content/${item.id}/approve`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedIds([]);
      await onChanged();
      if (failed) {
        setContentError(`Не удалось согласовать часть текстов: ${failed}. Проверьте, выбран ли пункт меню.`);
      }
    } catch (error) {
      setContentError(error instanceof Error ? error.message : "Не удалось согласовать выбранные тексты.");
    } finally {
      setContentActionId("");
    }
  }

  async function bulkDelete() {
    if (!bulkDeleteItems.length) return;
    const confirmed = window.confirm(`Удалить выбранные тексты: ${bulkDeleteItems.length}?`);
    if (!confirmed) return;
    setContentError("");
    setContentActionId("bulk:delete");
    try {
      const results = await Promise.allSettled(bulkDeleteItems.map((item) => api(`/content/${item.id}`, { method: "DELETE" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedIds([]);
      setSelectedPreview((current) => current && bulkDeleteItems.some((item) => item.id === current.id) ? null : current);
      await onChanged();
      if (failed) {
        setContentError(`Не удалось удалить часть текстов: ${failed}. Scheduled/published контент не удаляется.`);
      }
    } catch (error) {
      setContentError(error instanceof Error ? error.message : "Не удалось удалить выбранные тексты.");
    } finally {
      setContentActionId("");
    }
  }

  async function regenerate(item: ContentItem) {
    setContentError("");
    setContentActionId(`${item.id}:generate`);
    try {
      const updated = await api<ContentItem>(`/content/${item.id}/generate`, { method: "POST" });
      setSelectedPreview((current) => current && current.id === item.id ? updated : current);
      await onChanged();
    } catch (error) {
      setContentError(error instanceof Error ? error.message : "Не удалось запустить повторную генерацию.");
    } finally {
      setContentActionId("");
    }
  }

  async function deleteItem(item: ContentItem) {
    const confirmed = window.confirm(`Удалить сгенерированный контент по теме "${item.topic}"?`);
    if (!confirmed) return;
    setContentError("");
    setContentActionId(`${item.id}:delete`);
    try {
      await api(`/content/${item.id}`, { method: "DELETE" });
      setSelectedPreview((current) => current && current.id === item.id ? null : current);
      await onChanged();
    } catch (error) {
      setContentError(error instanceof Error ? error.message : "Не удалось удалить контент.");
    } finally {
      setContentActionId("");
    }
  }

  return (
    <section className="viewStack">
      <DataPanel title="Контент">
        <label className="projectSearchField">
          <Search size={18} />
          <input
            type="search"
            value={projectSearch}
            onChange={(event) => setProjectSearch(event.target.value)}
            placeholder="Найти проект по названию или адресу"
          />
        </label>
        <div className="bulkToolbar">
          <label className="checkboxRow bulkSelectAll">
            <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
            Выбрать все
          </label>
          <span className="fieldHint">Выбрано: {selectedIds.length}</span>
          <button className="button compact approve" type="button" onClick={bulkApprove} disabled={!bulkApproveItems.length || contentActionId === "bulk:approve"}>
            <CheckCircle2 size={15} /> {contentActionId === "bulk:approve" ? "Согласовываю" : `Approve выбранные (${bulkApproveItems.length})`}
          </button>
          <button className="button compact danger" type="button" onClick={bulkDelete} disabled={!bulkDeleteItems.length || contentActionId === "bulk:delete"}>
            <Trash2 size={15} /> {contentActionId === "bulk:delete" ? "Удаляю" : `Удалить выбранные (${bulkDeleteItems.length})`}
          </button>
        </div>
        <div className="contentProjectTree">
          {visibleProjectGroups.map((group) => {
            const expanded = expandedProjectIds.includes(group.id);
            const projectItemIds = group.items.map((item) => item.id);
            const projectSelected = projectItemIds.length > 0 && projectItemIds.every((id) => selectedIds.includes(id));
            const publishedCount = group.items.filter((item) => item.status === "published").length;
            return (
              <article className={`contentProject ${expanded ? "expanded" : ""}`} key={group.id}>
                <button className="contentProjectHeader" type="button" onClick={() => toggleProject(group.id)} aria-expanded={expanded}>
                  <span className="contentProjectChevron">{expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}</span>
                  <span className="contentProjectIdentity">
                    <span className="contentProjectName">
                      <strong>{group.name}</strong>
                      {group.id !== "__unassigned__" ? <ProjectVerificationMedal status={group.medalStatus} /> : null}
                    </span>
                    <span>{group.baseUrl || "Проект не назначен"}</span>
                  </span>
                  <span className="contentProjectStats">
                    <span>Тем: {group.items.length}</span>
                    <span>Опубликовано: {publishedCount}</span>
                  </span>
                </button>
                {expanded ? (
                  <div className="contentProjectBody">
                    <div className="projectSelectionRow">
                      <label className="checkboxRow">
                        <input type="checkbox" checked={projectSelected} onChange={() => toggleProjectSelection(group.items)} disabled={!group.items.length} />
                        Выбрать все темы проекта
                      </label>
                    </div>
                    {group.items.length ? (
                      <ResponsiveTable
                        columns={["Выбор", "Тема", "Slug", "Слова", "Статус", "Действие"]}
                        rows={group.items.map((item) => [
                          <input className="rowCheckbox" type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelected(item.id)} aria-label={`Выбрать ${item.topic}`} />,
                          <TopicMetaCell item={item} />,
                          item.slug,
                          item.word_count,
                          <StatusBadge status={item.status} />,
                          <div className="userActions">
                            <button className="button compact" type="button" onClick={() => setSelectedPreview(item)}><FileText size={15} /> Просмотр</button>
                            <button className="button compact" type="button" onClick={() => regenerate(item)} disabled={contentActionId.startsWith(item.id) || isPublicationLocked(item)} title={item.competitor_brief ? "Повторная генерация пойдет с сохраненным анализом конкурентов." : "Анализ конкурентов не найден, генерация пойдет без competitor brief."}>
                              <Play size={15} /> {contentActionId === `${item.id}:generate` ? "Генерация" : "Сгенерировать заново"}
                            </button>
                            <button className="button compact danger" type="button" onClick={() => deleteItem(item)} disabled={contentActionId.startsWith(item.id) || isPublicationLocked(item)} title={isPublicationLocked(item) ? "Нельзя удалить контент из публикационной очереди" : undefined}>
                              <Trash2 size={15} /> {contentActionId === `${item.id}:delete` ? "Удаляю" : "Удалить"}
                            </button>
                            <button className="button compact approve" type="button" onClick={() => approve(item.id)} disabled={!canApproveContent(item)}>Approve</button>
                          </div>
                        ])}
                        rowClassNames={group.items.map(contentRowClassName)}
                      />
                    ) : <EmptyState text="В этом проекте пока нет добавленных тем." />}
                  </div>
                ) : null}
              </article>
            );
          })}
          {!visibleProjectGroups.length ? <EmptyState text="Проекты по этому запросу не найдены." /> : null}
        </div>
        {contentError ? <span className="formError">{contentError}</span> : null}
      </DataPanel>

      {selectedPreview ? (
        <ContentPreviewModal
          item={selectedPreview}
          onClose={() => setSelectedPreview(null)}
          actions={
            <>
              <button className="button compact" type="button" onClick={() => regenerate(selectedPreview)} disabled={contentActionId.startsWith(selectedPreview.id) || isPublicationLocked(selectedPreview)}>
                <Play size={15} /> Сгенерировать заново
              </button>
              <button className="button compact approve" type="button" onClick={() => approve(selectedPreview.id)} disabled={!canApproveContent(selectedPreview)}>Approve</button>
            </>
          }
        />
      ) : null}
    </section>
  );
}

function PublicationsView({ api, sites, content, onOpenProject, onChanged }: ViewProps & { sites: Site[]; content: ContentItem[]; onOpenProject: (site: Site) => void }) {
  const [name, setName] = React.useState("Daily publication");
  const [siteId, setSiteId] = React.useState("");
  const [interval, setIntervalValue] = React.useState<1440 | 720 | 420>(1440);
  const [campaigns, setCampaigns] = React.useState<PublicationCampaign[]>([]);
  const [campaignQueue, setCampaignQueue] = React.useState<PublicationCampaignQueue | null>(null);
  const [campaignQueueLoadingId, setCampaignQueueLoadingId] = React.useState("");
  const [publishingQueueItemId, setPublishingQueueItemId] = React.useState("");
  const [publicationContent, setPublicationContent] = React.useState<PublicationContentItem[]>([]);
  const [expandedProjectIds, setExpandedProjectIds] = React.useState<string[]>([]);
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = React.useState("");
  const [formError, setFormError] = React.useState("");
  const approved = publicationContent.filter((item) => item.status === "approved" && (!siteId || item.site_id === siteId));
  const publicationProjectGroups = React.useMemo(() => sites
    .map((site) => ({
      site,
      items: publicationContent.filter((item) => item.site_id === site.id)
    }))
    .filter((group) => group.items.length > 0)
    .sort((left, right) => left.site.name.localeCompare(right.site.name, undefined, { sensitivity: "base" })), [publicationContent, sites]);

  const loadCampaigns = React.useCallback(async () => {
    setCampaigns(await api<PublicationCampaign[]>("/publication-campaigns"));
  }, [api]);

  const loadPublicationContent = React.useCallback(async () => {
    setPublicationContent(await api<PublicationContentItem[]>("/publication-content"));
  }, [api]);

  React.useEffect(() => {
    Promise.all([loadCampaigns(), loadPublicationContent()])
      .catch((error: unknown) => setFormError(error instanceof Error ? error.message : "Не удалось загрузить данные публикаций."));
  }, [loadCampaigns, loadPublicationContent]);

  function togglePublicationProject(projectId: string) {
    setExpandedProjectIds((current) => current.includes(projectId)
      ? current.filter((id) => id !== projectId)
      : [...current, projectId]);
  }

  async function openContentPreview(contentId: string) {
    setPreviewLoadingId(contentId);
    setFormError("");
    try {
      setSelectedPreview(await api<ContentItem>(`/content/${contentId}`));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось загрузить текст и метаданные.");
    } finally {
      setPreviewLoadingId("");
    }
  }

  async function createCampaign(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    try {
      await api("/publication-campaigns", {
        method: "POST",
        body: JSON.stringify({
          name,
          site_id: siteId,
          content_item_ids: approved.map((item) => item.id),
          start_at: new Date().toISOString(),
          interval_minutes: interval,
          items_per_run: 1
        })
      });
      await Promise.all([onChanged(), loadCampaigns(), loadPublicationContent()]);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось создать кампанию.");
    }
  }

  async function changeCampaign(campaign: PublicationCampaign, action: "pause" | "resume" | "stop") {
    setFormError("");
    try {
      await api(`/publication-campaigns/${campaign.id}`, { method: "PATCH", body: JSON.stringify({ action }) });
      await Promise.all([onChanged(), loadCampaigns()]);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось изменить кампанию.");
    }
  }

  async function openCampaignQueue(campaign: PublicationCampaign) {
    setCampaignQueueLoadingId(campaign.id);
    setFormError("");
    try {
      setCampaignQueue(await api<PublicationCampaignQueue>(`/publication-campaigns/${campaign.id}/queue`));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось загрузить очередь задания.");
    } finally {
      setCampaignQueueLoadingId("");
    }
  }

  async function publishCampaignQueueItem(item: PublicationQueueItem) {
    if (!window.confirm(`Опубликовать текст «${item.topic}» сейчас, без ожидания очереди?`)) return;
    setPublishingQueueItemId(item.id);
    setFormError("");
    try {
      await api<ContentItem>(`/content/${item.id}/publish-immediately`, { method: "POST" });
      if (campaignQueue) {
        setCampaignQueue(await api<PublicationCampaignQueue>(`/publication-campaigns/${campaignQueue.campaign.id}/queue`));
      }
      await Promise.all([onChanged(), loadCampaigns(), loadPublicationContent()]);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось опубликовать текст.");
    } finally {
      setPublishingQueueItemId("");
    }
  }

  return (
    <section className="viewStack">
      <div className="publicationProjectsInfo publicationPageInfo" role="note">
        <ListChecks size={17} />
        <span>На этой странице отображаются только проекты, для которых добавлена хотя бы одна тема и/или существует сгенерированный контент.</span>
      </div>
      <DataPanel title="Создать кампанию публикации">
        <form className="formGrid" onSubmit={createCampaign}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Сайт
            <SearchableSelect
              value={siteId}
              onChange={setSiteId}
              options={[{ value: "", label: "Выберите сайт" }, ...publicationProjectGroups.map((group) => projectSearchOption(group.site))]}
              searchPlaceholder="Найти сайт"
            />
          </label>
          <label>
            Режим публикации
            <select value={interval} onChange={(event) => setIntervalValue(Number(event.target.value) as 1440 | 720 | 420)}>
              <option value={1440}>1 текст в день · каждые 24 часа</option>
              <option value={720}>2 текста в день · каждые 12 часов</option>
              <option value={420}>3 текста в день · каждые 7 часов</option>
            </select>
          </label>
          <div className="formActions wide">
            <button className="button primary" type="submit" disabled={!approved.length || !siteId}><Play size={18} /> Запланировать approved ({approved.length})</button>
          </div>
          {formError ? <span className="formError wide">{formError}</span> : null}
        </form>
      </DataPanel>
      <DataPanel title="Все кампании">
        <ResponsiveTable
          columns={["Название", "Сайт", "Старт", "Интервал", "Статус", "Действия"]}
          rows={campaigns.map((campaign) => [
            campaign.name,
            sites.find((site) => site.id === campaign.site_id)?.name || campaign.site_id,
            formatDate(campaign.start_at),
            publicationIntervalLabel(campaign.interval_minutes),
            <StatusBadge status={campaign.status} />,
            <div className="userActions">
              <button className="button compact" type="button" onClick={() => void openCampaignQueue(campaign)} disabled={campaignQueueLoadingId === campaign.id}>
                <ListChecks size={15} /> {campaignQueueLoadingId === campaign.id ? "Загрузка…" : "Очередь"}
              </button>
              {campaign.status === "active" ? <button className="button compact campaignActionIconButton" type="button" onClick={() => changeCampaign(campaign, "pause")} title="Приостановить" aria-label="Приостановить кампанию"><Pause size={15} /></button> : null}
              {campaign.status === "paused" ? <button className="button compact" type="button" onClick={() => changeCampaign(campaign, "resume")}><Play size={15} /> Resume</button> : null}
              {["active", "paused"].includes(campaign.status) ? <button className="button compact danger campaignActionIconButton" type="button" onClick={() => changeCampaign(campaign, "stop")} title="Остановить" aria-label="Остановить кампанию"><X size={15} /></button> : null}
            </div>
          ])}
        />
      </DataPanel>
      {campaignQueue ? (
        <Modal
          title={`Очередь: ${campaignQueue.campaign.name}`}
          subtitle={`${publicationIntervalLabel(campaignQueue.campaign.interval_minutes)} · элементов: ${campaignQueue.items.length}`}
          onClose={() => setCampaignQueue(null)}
          wide
          className="campaignQueueModal"
        >
          <ResponsiveTable
            columns={["№", "Тема", "Пункт меню", "Время", "Статус", "Действия"]}
            rows={campaignQueue.items.map((item, index) => [
              index + 1,
              <button className="compactContentTopic publicationTopicButton" type="button" onClick={() => void openContentPreview(item.id)} disabled={previewLoadingId === item.id} title="Просмотреть текст и метаданные"><ContentTopicLabel item={item} /></button>,
              item.section_name || "Не выбран",
              item.published_at ? `Опубликовано ${formatDate(item.published_at)}` : item.scheduled_at ? formatDate(item.scheduled_at) : "—",
              <StatusBadge status={item.status} />,
              ["scheduled", "retry_scheduled", "publication_paused", "approved"].includes(item.status) ? (
                <button className="button compact primary publishImmediatelyButton" type="button" onClick={() => void publishCampaignQueueItem(item)} disabled={publishingQueueItemId === item.id}>
                  <Send size={14} /> {publishingQueueItemId === item.id ? "Отправляем…" : "Отправить"}
                </button>
              ) : "—"
            ])}
            wrapperClassName="campaignQueueTable"
          />
        </Modal>
      ) : null}
      <DataPanel title={`Очередь публикации · ${publicationProjectGroups.length}`}>
        <div className="publicationProjectTree">
          {publicationProjectGroups.map(({ site, items }) => {
            const expanded = expandedProjectIds.includes(site.id);
            const generatedCount = items.filter((item) => Boolean(item.generated_at)).length;
            const queuedCount = items.filter((item) => ["scheduled", "retry_scheduled", "publication_paused", "publishing"].includes(item.status)).length;
            const publishedCount = items.filter((item) => item.status === "published").length;
            const errorCount = items.filter((item) => item.status === "publication_failed").length;
            const canon = site.cache_canon || site.base_url.replace(/^https?:\/\//, "").replace(/\/$/, "");
            return (
              <article className={`publicationProject ${expanded ? "expanded" : ""}`} key={site.id}>
                <div className="publicationProjectHeader">
                  <button className="publicationProjectToggle" type="button" onClick={() => togglePublicationProject(site.id)} aria-expanded={expanded}>
                    <span className="publicationProjectChevron">{expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
                    <span className="publicationProjectIdentity">
                      <span className="publicationProjectIdentityTitle">
                        <strong>{site.name}</strong>
                        <ProjectVerificationMedal status={projectMenuMedalStatus(site)} />
                      </span>
                      <small title={canon}>Main: {canon}</small>
                    </span>
                    <span className="publicationProjectCounters">
                      <span>Тем сгенерировано: <b>{generatedCount}</b></span>
                      <span>Добавлено в очередь: <b>{queuedCount}</b></span>
                      <span>Опубликовано: <b>{publishedCount}</b></span>
                      <span className={errorCount ? "hasErrors" : ""}>Ошибки: <b>{errorCount}</b></span>
                    </span>
                  </button>
                  <button className="button compact publicationProjectOpenButton" type="button" onClick={() => onOpenProject(site)} title={`Открыть контент и публикацию проекта ${site.name}`}>
                    <FileText size={14} /> Контент и публикация
                  </button>
                </div>
                {expanded ? (
                  <div className="publicationProjectBody">
                    <ResponsiveTable
                      columns={["Тема", "Статус", "Slug", "Слова", "Сгенерировано", "Опубликовано"]}
                      rows={items.map((item) => [
                        <button className="compactContentTopic publicationTopicButton" type="button" onClick={() => void openContentPreview(item.id)} disabled={previewLoadingId === item.id} title="Просмотреть текст и метаданные"><ContentTopicLabel item={item} /></button>,
                        <StatusBadge status={item.status} />,
                        <code>{item.slug}</code>,
                        item.word_count,
                        item.generated_at ? formatDate(item.generated_at) : "—",
                        item.published_at ? formatDate(item.published_at) : "—"
                      ])}
                      wrapperClassName="publicationContentTable"
                    />
                  </div>
                ) : null}
              </article>
            );
          })}
          {!publicationProjectGroups.length ? <EmptyState text="Проектов с добавленными темами пока нет." /> : null}
        </div>
      </DataPanel>
      {selectedPreview ? <ContentPreviewModal item={selectedPreview} onClose={() => setSelectedPreview(null)} /> : null}
    </section>
  );
}

function ProvidersView({ api, providers, onChanged }: ViewProps & { providers: AiProvider[] }) {
  const [name, setName] = React.useState("Gemini");
  const [providerType, setProviderType] = React.useState<"custom" | "gemini" | "dataforseo">("gemini");
  const [endpointUrl, setEndpointUrl] = React.useState("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
  const [model, setModel] = React.useState("gemini-3.5-flash");
  const [apiKey, setApiKey] = React.useState("");
  const [apiLogin, setApiLogin] = React.useState("");
  const [apiPassword, setApiPassword] = React.useState("");
  const [validatingId, setValidatingId] = React.useState<string | null>(null);

  async function createProvider(event: React.FormEvent) {
    event.preventDefault();
    const payload = providerType === "dataforseo"
      ? { name, provider_type: providerType, endpoint_url: endpointUrl, model, api_login: apiLogin, api_password: apiPassword }
      : { name, provider_type: providerType, endpoint_url: endpointUrl, model, api_key: apiKey || null };
    await api("/ai-providers", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    setName("Gemini");
    setProviderType("gemini");
    setEndpointUrl("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
    setModel("gemini-3.5-flash");
    setApiKey("");
    setApiLogin("");
    setApiPassword("");
    onChanged();
  }

  async function validateProvider(providerId: string) {
    setValidatingId(providerId);
    try {
      await api(`/ai-providers/${providerId}/validate`, { method: "POST" });
      onChanged();
    } finally {
      setValidatingId(null);
    }
  }

  return (
    <section className="viewStack">
      <DataPanel title="Подключить API provider">
        <form className="formGrid" onSubmit={createProvider}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder={providerType === "dataforseo" ? "DataForSEO" : "Gemini"} />
          </label>
          <label>
            Тип API
            <select
              value={providerType}
              onChange={(event) => {
                const nextType = event.target.value as "custom" | "gemini" | "dataforseo";
                setProviderType(nextType);
                if (nextType === "gemini") {
                  setName((value) => value || "Gemini");
                  setEndpointUrl("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
                  setModel("gemini-3.5-flash");
                } else if (nextType === "dataforseo") {
                  setName("DataForSEO");
                  setEndpointUrl("https://api.dataforseo.com/v3");
                  setModel("Google Organic SERP Live Advanced");
                }
              }}
            >
              <option value="gemini">Gemini</option>
              <option value="dataforseo">DataForSEO SERP</option>
              <option value="custom">Custom / tunnel</option>
            </select>
          </label>
          <label>
            Endpoint URL
            <input value={endpointUrl} onChange={(event) => setEndpointUrl(event.target.value)} required placeholder="https://..." />
          </label>
          <label>
            Модель
            <input value={model} onChange={(event) => setModel(event.target.value)} required placeholder="gpt-..." />
          </label>
          {providerType === "dataforseo" ? (
            <>
              <label>
                API login
                <input value={apiLogin} onChange={(event) => setApiLogin(event.target.value)} required placeholder="email@example.com" />
              </label>
              <label>
                API password
                <input value={apiPassword} onChange={(event) => setApiPassword(event.target.value)} required type="password" />
              </label>
            </>
          ) : (
            <label>
              API key
              <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" />
            </label>
          )}
          <div className="formActions wide"><button className="button primary" type="submit"><span className="buttonPlusIcon"><Plus size={15} /></span> Сохранить provider</button></div>
        </form>
      </DataPanel>
      <DataPanel title="Подключенные API">
        <ResponsiveTable
          columns={["Название", "Тип", "Модель", "Endpoint", "Статус ключа", "Проверен", "Prompt", "Output", "Всего токенов", "Последнее", "Добавлен", "Активен", "Действие"]}
          rows={providers.map((provider) => [
            provider.name,
            humanProviderType(provider.provider_type),
            provider.model,
            provider.endpoint_url,
            <ProviderValidationCell provider={provider} />,
            provider.validated_at ? formatDate(provider.validated_at) : "-",
            formatNumber(provider.prompt_tokens_used || 0),
            formatNumber(provider.completion_tokens_used || 0),
            formatNumber(provider.total_tokens_used || 0),
            provider.last_used_at ? formatDate(provider.last_used_at) : "-",
            formatDate(provider.created_at),
            provider.is_active ? "Да" : "Нет",
            <button className="button compact" type="button" onClick={() => validateProvider(provider.id)} disabled={validatingId === provider.id}>
              <ShieldCheck size={16} />
              {validatingId === provider.id ? "Проверка" : "Проверить"}
            </button>
          ])}
        />
      </DataPanel>
    </section>
  );
}

type SiteTableColumn = "rowNumber" | "select" | "name" | "title" | "canon" | "language" | "status" | "internalPages" | "menuType" | "menuCount" | "domainsCount";
type SiteSummaryFilter = "projects" | "working" | "menu" | "test" | "duplicate" | "all";

const DEFAULT_SITE_COLUMN_ORDER: SiteTableColumn[] = ["rowNumber", "select", "name", "title", "canon", "language", "status", "internalPages", "menuType", "menuCount", "domainsCount"];
const SITE_COLUMN_LABELS: Record<SiteTableColumn, string> = {
  rowNumber: "№",
  select: "",
  name: "Name",
  title: "Title главной",
  canon: "Main",
  language: "Язык",
  status: "Статус",
  internalPages: "Внутренние страницы",
  menuType: "Тип меню",
  menuCount: "Пункты меню",
  domainsCount: "Доменов в сетке"
};
const SITE_COLUMN_SORT_KEYS: Record<SiteTableColumn, string | null> = {
  rowNumber: null,
  select: null,
  name: "name",
  title: "title",
  canon: "canon",
  language: "language",
  status: "status",
  internalPages: "internalPages",
  menuType: "menuType",
  menuCount: "menuCount",
  domainsCount: "domainsCount"
};

const LANGUAGE_COUNTRIES: Record<string, string> = {
  ar: "AE", bg: "BG", cs: "CZ", da: "DK", de: "DE", en: "GB", es: "ES", et: "EE", fi: "FI",
  fr: "FR", hu: "HU", it: "IT", lt: "LT", nl: "NL", pl: "PL", pt: "PT", ro: "RO", ru: "RU",
  sk: "SK", sr: "RS", sv: "SE", tr: "TR", uk: "UA"
};

function localeCountryCode(value: string): string | null {
  const parts = value.trim().split(/[-_]/).filter(Boolean);
  const explicitCountry = [...parts].reverse().find((part, index) => part.length === 2 && (parts.length > 1 || index > 0));
  if (explicitCountry) return explicitCountry.toUpperCase();
  const normalized = parts[0]?.toLowerCase() || "";
  return LANGUAGE_COUNTRIES[normalized] || (normalized.length === 2 ? normalized.toUpperCase() : null);
}

function localeFlag(countryCode: string | null): string {
  if (!countryCode || !/^[A-Z]{2}$/.test(countryCode)) return "";
  return String.fromCodePoint(...countryCode.split("").map((character) => 127397 + character.charCodeAt(0)));
}

type ProjectMedalStatus = "gold" | "verified" | "missing" | "unchecked";

function menuMedalStatus(checkedAt: string | null, headerRendered: boolean | null, footerRendered: boolean | null): ProjectMedalStatus {
  if (!checkedAt || headerRendered == null) return "unchecked";
  if (!headerRendered) return "missing";
  return footerRendered === true ? "gold" : "verified";
}

function projectMenuMedalStatus(site: Site): ProjectMedalStatus {
  return menuMedalStatus(site.menu_capabilities_checked_at, site.header_menu_rendered, site.footer_menu_rendered);
}

function ProjectVerificationMedal({ status }: { status: ProjectMedalStatus }) {
  const statusText = status === "gold"
    ? "Проверка пройдена: рендеринг Header и Footer реализован"
    : status === "verified" ? "Проверка Header пройдена"
    : status === "missing" ? "Проверено: рендеринг Header-меню не реализован" : "Проверка Header ещё не выполнена";
  return (
    <span className={`projectVerificationMedal is${status[0].toUpperCase()}${status.slice(1)}`} title={statusText} aria-label={statusText}>
      <MenuReadyMedal tone={status === "missing" ? "red" : status === "gold" ? "gold" : "green"} />
    </span>
  );
}

function projectSearchOption(site: Site): SearchableSelectOption {
  const flag = localeFlag(localeCountryCode(site.cache_geo || site.cache_language || ""));
  const networkDomains = Array.isArray(site.cache_domains) ? site.cache_domains : [];
  return {
    value: site.id,
    label: site.name,
    leading: flag ? <span className="projectSelectFlag" aria-hidden="true">{flag}</span> : undefined,
    indicator: <ProjectVerificationMedal status={projectMenuMedalStatus(site)} />,
    keywords: [site.name, site.cache_canon || "", site.base_url, ...networkDomains].filter(Boolean).join(" ")
  };
}

function LocaleCode({ value }: { value: string | null }) {
  if (!value) return <>—</>;
  const flag = localeFlag(localeCountryCode(value));
  return <span className="siteLocaleCode">{flag ? <span aria-hidden="true">{flag}</span> : null}<b>{value.replace(/_/g, "-")}</b></span>;
}

function SitesView({ api, sites, currentUsername, favoritesOnly = false, readOnly = false, onChanged }: ViewProps & { sites: Site[]; currentUsername: string; favoritesOnly?: boolean; readOnly?: boolean }) {
  const preferencesKey = `sites-table-preferences:${currentUsername}`;
  const storedPreferences = React.useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem(preferencesKey) || "{}") as {
        statusFilters?: Site["project_status"][];
        menuTypeFilters?: string[];
        siteSort?: { key: string; direction: "asc" | "desc" } | null;
        columnOrder?: SiteTableColumn[];
        hiddenColumns?: SiteTableColumn[];
        rowsPerPage?: number | "all";
        summaryFilter?: SiteSummaryFilter | null;
        medalFilter?: ProjectMedalStatus | null;
        geoFilter?: string;
        brandFilter?: string;
      };
    } catch {
      return {};
    }
  }, [preferencesKey]);
  const [managedSites, setManagedSites] = React.useState<Site[]>(sites);
  const [cacheResult, setCacheResult] = React.useState<ProjectCacheSyncResult | null>(null);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [geoFilter, setGeoFilter] = React.useState(() => storedPreferences.geoFilter || "");
  const [brandFilter, setBrandFilter] = React.useState(() => storedPreferences.brandFilter || "");
  const [syncing, setSyncing] = React.useState(false);
  const [syncError, setSyncError] = React.useState("");
  const [selectedProjectNames, setSelectedProjectNames] = React.useState<string[]>([]);
  const [syncMessage, setSyncMessage] = React.useState("");
  const [summaryFilter, setSummaryFilter] = React.useState<SiteSummaryFilter | null>(() => storedPreferences.summaryFilter || null);
  const [medalFilter, setMedalFilter] = React.useState<ProjectMedalStatus | null>(() => {
    const stored = storedPreferences.medalFilter;
    return stored && (["gold", "verified", "missing", "unchecked"] as ProjectMedalStatus[]).includes(stored) ? stored : null;
  });
  const [siteSort, setSiteSort] = React.useState<{ key: string; direction: "asc" | "desc" } | null>(storedPreferences.siteSort?.key === "geo" ? null : storedPreferences.siteSort || null);
  const [deletingDuplicates, setDeletingDuplicates] = React.useState(false);
  const [menuPreview, setMenuPreview] = React.useState<{ name: string; header: unknown[]; footer: unknown[] } | null>(null);
  const [columnsSettingsOpen, setColumnsSettingsOpen] = React.useState(false);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [rowsPerPage, setRowsPerPage] = React.useState<number | "all">(() => {
    const stored = storedPreferences.rowsPerPage;
    return stored === "all" || [25, 50, 100, 250].includes(Number(stored)) ? stored as number | "all" : 50;
  });
  const statusFilterOptions: Array<{ value: Site["project_status"]; label: string }> = [
    { value: "test", label: "Тестовый" },
    { value: "working", label: "Рабочий" },
    { value: "not_in_focus", label: "Не в фокусе" },
    { value: "duplicate", label: "Дубликат" }
  ];
  const menuTypeFilterOptions = [
    { value: "header_footer", label: "Header + Footer" },
    { value: "header", label: "Только Header" },
    { value: "footer", label: "Только Footer" },
    { value: "none", label: "Без меню" }
  ];
  const allStatusFilters = statusFilterOptions.map((option) => option.value);
  const allMenuTypeFilters = menuTypeFilterOptions.map((option) => option.value);
  const [statusFilters, setStatusFilters] = React.useState<Site["project_status"][]>(() => {
    const stored = storedPreferences.statusFilters;
    return Array.isArray(stored) && stored.every((value) => allStatusFilters.includes(value)) ? stored : allStatusFilters;
  });
  const [menuTypeFilters, setMenuTypeFilters] = React.useState<string[]>(() => {
    const stored = storedPreferences.menuTypeFilters;
    return Array.isArray(stored) && stored.every((value) => allMenuTypeFilters.includes(value)) ? stored : allMenuTypeFilters;
  });
  const [columnOrder, setColumnOrder] = React.useState<SiteTableColumn[]>(() => {
    const stored = storedPreferences.columnOrder;
    return Array.isArray(stored)
      && stored.length === DEFAULT_SITE_COLUMN_ORDER.length
      && DEFAULT_SITE_COLUMN_ORDER.every((column) => stored.includes(column))
      ? stored
      : DEFAULT_SITE_COLUMN_ORDER;
  });
  const [hiddenColumns, setHiddenColumns] = React.useState<SiteTableColumn[]>(() => {
    const stored = storedPreferences.hiddenColumns;
    return Array.isArray(stored) && stored.every((column) => DEFAULT_SITE_COLUMN_ORDER.includes(column)) ? stored : [];
  });
  const [favoriteSiteIds, setFavoriteSiteIds] = React.useState<string[]>([]);
  const visibleColumnOrder = columnOrder.filter((column) => !hiddenColumns.includes(column) && (!readOnly || column !== "select"));

  React.useEffect(() => {
    localStorage.setItem(preferencesKey, JSON.stringify({ statusFilters, menuTypeFilters, siteSort, columnOrder, hiddenColumns, rowsPerPage, summaryFilter, medalFilter, geoFilter, brandFilter }));
  }, [brandFilter, columnOrder, geoFilter, hiddenColumns, medalFilter, menuTypeFilters, preferencesKey, rowsPerPage, siteSort, statusFilters, summaryFilter]);

  React.useEffect(() => {
    api<{ site_ids: string[] }>("/me/favorite-sites")
      .then((result) => setFavoriteSiteIds(result.site_ids))
      .catch((error: unknown) => setSyncError(error instanceof Error ? error.message : "Не удалось загрузить избранное"));
  }, [api]);

  const loadManagedSites = React.useCallback(async () => {
    if (readOnly) {
      setManagedSites(sites);
      return;
    }
    setManagedSites(await api<Site[]>("/sites/cache/projects"));
  }, [api, readOnly, sites]);

  React.useEffect(() => {
    loadManagedSites().catch((error: unknown) => setSyncError(error instanceof Error ? error.message : "Не удалось загрузить проекты"));
  }, [loadManagedSites]);

  async function syncCache(names: string[] = []) {
    setSyncing(true);
    setSyncError("");
    setSyncMessage("");
    try {
      const result = await api<ProjectCacheSyncResult>("/sites/cache/sync", {
        method: "POST",
        body: JSON.stringify({ names })
      });
      setCacheResult((current) => {
        if (!names.length || !current) return result;
        const updatedById = new Map(result.projects.map((project) => [project.external_project_id, project]));
        const mergedProjects = current.projects.map((project) => updatedById.get(project.external_project_id) || project);
        return { ...result, cache_count: current.cache_count, matched_count: current.matched_count, projects: mergedProjects };
      });
      setSyncMessage(names.length
        ? `Обновлено выбранных проектов: ${result.updated_count + result.created_count}.`
        : `Данные получены: ${formatNumber(result.cache_count)} сайтов. Рабочих проектов: ${result.matched_count}; добавлено: ${result.created_count}; обновлено: ${result.updated_count}.`);
      if (names.length) setSelectedProjectNames([]);
      onChanged();
      await loadManagedSites();
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Не удалось получить данные проектов");
    } finally {
      setSyncing(false);
    }
  }

  const statusPriority = (status: Site["project_status"]) => {
    if (status === "test") return 0;
    if (status === "working") return 1;
    if (status === "not_in_focus") return 2;
    return 3;
  };
  const domainRows = managedSites.map((site) => {
    const headerMenuCount = Array.isArray(site.default_menu.header) ? site.default_menu.header.length : 0;
    const footerMenuCount = Array.isArray(site.default_menu.footer) ? site.default_menu.footer.length : 0;
    return {
      key: `site:${site.id}`,
      id: site.id,
      name: site.name,
      baseUrl: site.base_url,
      isFavorite: favoriteSiteIds.includes(site.id),
      canon: site.cache_canon || site.base_url.replace(/^https?:\/\//, "").replace(/\/$/, ""),
      language: site.cache_language,
      geo: site.cache_geo,
      homepageTitle: site.homepage_title,
      externalProjectId: site.external_project_id,
      isTest: site.is_test_project,
      isWorking: site.project_status === "working",
      projectStatus: site.project_status,
      hasMenu: site.has_menu,
      medalStatus: projectMenuMedalStatus(site),
      headerMenuCount,
      footerMenuCount,
      headerMenu: Array.isArray(site.default_menu.header) ? site.default_menu.header : [],
      footerMenu: Array.isArray(site.default_menu.footer) ? site.default_menu.footer : [],
      menuTypeKey: headerMenuCount && footerMenuCount ? "header_footer" : headerMenuCount ? "header" : footerMenuCount ? "footer" : "none",
      menuType: headerMenuCount && footerMenuCount ? "Header + Footer" : headerMenuCount ? "Header" : footerMenuCount ? "Footer" : "",
      menuCount: headerMenuCount + footerMenuCount,
      internalPagesCount: site.internal_pages_count,
      domainsCount: site.domains_count,
      domains: Array.isArray(site.cache_domains) ? site.cache_domains : [],
      syncedAt: site.cache_synced_at
    };
  }).sort((left, right) => {
    const favoriteComparison = Number(right.isFavorite) - Number(left.isFavorite);
    if (favoriteComparison) return favoriteComparison;
    if (!siteSort) {
      return statusPriority(left.projectStatus) - statusPriority(right.projectStatus)
        || Number(right.hasMenu) - Number(left.hasMenu)
        || left.name.localeCompare(right.name);
    }
    const values: Record<string, [string | number, string | number]> = {
      name: [left.name, right.name],
      title: [left.homepageTitle || "", right.homepageTitle || ""],
      canon: [left.canon, right.canon],
      language: [left.language || "", right.language || ""],
      geo: [left.geo || "", right.geo || ""],
      status: [statusPriority(left.projectStatus), statusPriority(right.projectStatus)],
      internalPages: [left.internalPagesCount, right.internalPagesCount],
      menuType: [left.menuType, right.menuType],
      menuCount: [left.menuCount, right.menuCount],
      domainsCount: [left.domainsCount, right.domainsCount]
    };
    const [leftValue, rightValue] = values[siteSort.key];
    const comparison = typeof leftValue === "number" && typeof rightValue === "number"
      ? leftValue - rightValue
      : String(leftValue).localeCompare(String(rightValue), "ru", { numeric: true, sensitivity: "base" });
    return comparison * (siteSort.direction === "asc" ? 1 : -1) || left.name.localeCompare(right.name);
  });
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const normalizedBrandFilter = brandFilter.trim().toLowerCase();
  const geoOptions = Array.from(new Set(domainRows.map((row) => (row.geo || "").trim().toLowerCase()).filter(Boolean)))
    .sort((left, right) => left.localeCompare(right));
  const matchesSummaryFilter = (row: (typeof domainRows)[number]) => {
    if (!summaryFilter || summaryFilter === "all") return true;
    if (summaryFilter === "projects") return Boolean(row.externalProjectId);
    if (summaryFilter === "working") return row.projectStatus === "working";
    if (summaryFilter === "menu") return row.hasMenu;
    if (summaryFilter === "test") return row.projectStatus === "test";
    return row.projectStatus === "duplicate";
  };
  const filteredRows = domainRows.filter((row) => (
    (!favoritesOnly || row.isFavorite)
    && matchesSummaryFilter(row)
    && (!medalFilter || row.medalStatus === medalFilter)
    && statusFilters.includes(row.projectStatus)
    && menuTypeFilters.includes(row.menuTypeKey)
    && (!geoFilter || (row.geo || "").trim().toLowerCase() === geoFilter)
    && (!normalizedBrandFilter || [row.name, row.homepageTitle || "", row.canon, ...row.domains].some((value) => value.toLowerCase().includes(normalizedBrandFilter)))
    && (!normalizedQuery || [row.name, row.homepageTitle || "", row.canon, row.externalProjectId || "", row.projectStatus, ...row.domains].some((value) => value.toLowerCase().includes(normalizedQuery)))
  ));
  const totalPages = rowsPerPage === "all" ? 1 : Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));
  const activePage = Math.min(currentPage, totalPages);
  const pageStart = rowsPerPage === "all" ? 0 : (activePage - 1) * rowsPerPage;
  const visibleRows = rowsPerPage === "all" ? filteredRows : filteredRows.slice(pageStart, pageStart + rowsPerPage);
  const workingCount = managedSites.filter((site) => site.project_status === "working").length;
  const menuCount = managedSites.filter((site) => site.has_menu).length;
  const duplicateCount = managedSites.filter((site) => site.project_status === "duplicate").length;
  const latestCacheSync = managedSites
    .map((site) => site.cache_synced_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => Date.parse(right) - Date.parse(left))[0] || null;
  const selectedNames = new Set(selectedProjectNames);
  const selectableFilteredNames = filteredRows.filter((row) => row.externalProjectId).map((row) => row.name);
  const allFilteredSelected = Boolean(selectableFilteredNames.length) && selectableFilteredNames.every((name) => selectedNames.has(name));
  const statusFilterActive = statusFilters.length !== statusFilterOptions.length;
  const menuTypeFilterActive = menuTypeFilters.length !== menuTypeFilterOptions.length;

  React.useEffect(() => {
    setCurrentPage(1);
  }, [brandFilter, geoFilter, medalFilter, menuTypeFilters, rowsPerPage, searchQuery, siteSort, statusFilters, summaryFilter]);

  function toggleSummaryFilter(filter: SiteSummaryFilter) {
    setSummaryFilter((current) => current === filter ? null : filter);
  }

  function toggleMedalFilter(filter: ProjectMedalStatus) {
    setMedalFilter((current) => current === filter ? null : filter);
  }

  function toggleSelectedProject(name: string) {
    setSelectedProjectNames((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
  }

  async function toggleFavoriteSite(siteId: string) {
    const result = await api<{ site_ids: string[] }>(`/me/favorite-sites/${siteId}`, {
      method: favoriteSiteIds.includes(siteId) ? "DELETE" : "PUT"
    });
    setFavoriteSiteIds(result.site_ids);
  }

  function toggleAllFilteredProjects() {
    setSelectedProjectNames((current) => {
      const visibleNames = new Set(selectableFilteredNames);
      if (allFilteredSelected) return current.filter((name) => !visibleNames.has(name));
      return [...new Set([...current, ...selectableFilteredNames])];
    });
  }

  const siteSortKeys = visibleColumnOrder.map((column) => SITE_COLUMN_SORT_KEYS[column]);

  function sortSitesByColumn(columnIndex: number) {
    const key = siteSortKeys[columnIndex];
    if (!key) return;
    setSiteSort((current) => {
      if (!current || current.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  }

  function toggleFilterValue<T extends string>(value: T, setValues: React.Dispatch<React.SetStateAction<T[]>>) {
    setValues((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  }

  function moveSiteColumn(column: SiteTableColumn, direction: -1 | 1) {
    setColumnOrder((current) => {
      const index = current.indexOf(column);
      const nextIndex = index + direction;
      if (column === "rowNumber" || index < 0 || nextIndex < 1 || nextIndex >= current.length) return current;
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  }

  function toggleSiteColumn(column: SiteTableColumn) {
    setHiddenColumns((current) => {
      if (current.includes(column)) return current.filter((item) => item !== column);
      if (visibleColumnOrder.length === 1) return current;
      return [...current, column];
    });
    if (siteSort?.key === SITE_COLUMN_SORT_KEYS[column]) setSiteSort(null);
  }

  async function updateProjectStatus(siteId: string, projectStatus: Site["project_status"]) {
    setSyncError("");
    try {
      await api<Site>(`/sites/${siteId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ project_status: projectStatus })
      });
      await loadManagedSites();
      onChanged();
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Не удалось изменить статус проекта");
    }
  }

  async function deleteDuplicates() {
    if (!duplicateCount) return;
    if (!window.confirm(`Удалить дубликаты из нашей системы: ${duplicateCount}? Внешние данные изменены не будут.`)) return;
    setDeletingDuplicates(true);
    setSyncError("");
    setSyncMessage("");
    try {
      const result = await api<DuplicateSitesDeleteResult>("/sites/cache/duplicates", { method: "DELETE" });
      setSelectedProjectNames([]);
      setSyncMessage(`Удалено дубликатов: ${result.deleted_count}.${result.skipped_count ? ` Пропущено связанных проектов: ${result.skipped_count}.` : ""}`);
      await loadManagedSites();
      onChanged();
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Не удалось удалить дубликаты");
    } finally {
      setDeletingDuplicates(false);
    }
  }

  return (
    <section className="viewStack sitesManagementView">
      <DataPanel title={readOnly ? "Обзор сайтов" : "Панель управления сайтами"}>
        <div className="siteCacheToolbar">
          <div className="siteCacheStats">
            <button className={summaryFilter === "projects" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("projects")} aria-pressed={summaryFilter === "projects"}><span>Проекты</span><strong>{formatNumber(cacheResult?.cache_count || managedSites.filter((site) => site.external_project_id).length)}</strong></button>
            <button className={summaryFilter === "working" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("working")} aria-pressed={summaryFilter === "working"}><span>Рабочие</span><strong>{formatNumber(workingCount)}</strong></button>
            <button className={summaryFilter === "menu" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("menu")} aria-pressed={summaryFilter === "menu"}><span>С меню</span><strong>{formatNumber(menuCount)}</strong></button>
            <button className={summaryFilter === "test" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("test")} aria-pressed={summaryFilter === "test"}><span>Тестовые</span><strong>{formatNumber(managedSites.filter((site) => site.project_status === "test").length)}</strong></button>
            <button className={summaryFilter === "duplicate" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("duplicate")} aria-pressed={summaryFilter === "duplicate"}><span>Дубликаты</span><strong>{formatNumber(duplicateCount)}</strong></button>
            <button className={summaryFilter === "all" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("all")} aria-pressed={summaryFilter === "all"}><span>Всего сайтов</span><strong>{formatNumber(managedSites.length)}</strong></button>
          </div>
          {!readOnly ? (
            <>
              <button className="button primary siteCacheSyncButton" type="button" onClick={() => syncCache()} disabled={syncing}>
                <RefreshCcw size={18} className={syncing ? "spin" : ""} />
                {syncing ? "Обновляем данные" : "Обновить данные"}
              </button>
              <button className="button secondary siteCacheSyncButton" type="button" onClick={() => syncCache(selectedProjectNames)} disabled={syncing || !selectedProjectNames.length}>
                <RefreshCcw size={18} /> Обновить выбранные ({selectedProjectNames.length})
              </button>
              <button className="button danger siteCacheSyncButton" type="button" onClick={deleteDuplicates} disabled={syncing || deletingDuplicates || !duplicateCount}>
                <Trash2 size={18} /> {deletingDuplicates ? "Удаляем" : `Удалить дубликаты (${duplicateCount})`}
              </button>
            </>
          ) : null}
        </div>
        <div className="siteCacheUpdatedAt">
          <CalendarClock size={17} />
          <span>Последнее обновление</span>
          <strong>{latestCacheSync ? formatDate(latestCacheSync) : "Данные еще не обновлялись"}</strong>
        </div>
        {syncMessage ? <div className="siteCacheResult">{syncMessage}</div> : null}
        {syncError ? <div className="formError siteCacheError">{syncError}</div> : null}
      </DataPanel>
      <aside className="siteMedalLegend" aria-label="Обозначения статусов проверки меню">
        <strong className="siteMedalLegendTitle">Статусы проверки меню</strong>
        <button className={`siteMedalLegendItem ${medalFilter === "gold" ? "active" : ""}`} type="button" onClick={() => toggleMedalFilter("gold")} aria-pressed={medalFilter === "gold"}>
          <ProjectVerificationMedal status="gold" />
          <span><b>Золотая</b> — Header и Footer реализованы</span>
        </button>
        <button className={`siteMedalLegendItem ${medalFilter === "verified" ? "active" : ""}`} type="button" onClick={() => toggleMedalFilter("verified")} aria-pressed={medalFilter === "verified"}>
          <ProjectVerificationMedal status="verified" />
          <span><b>Зелёная</b> — Header реализован</span>
        </button>
        <button className={`siteMedalLegendItem ${medalFilter === "missing" ? "active" : ""}`} type="button" onClick={() => toggleMedalFilter("missing")} aria-pressed={medalFilter === "missing"}>
          <ProjectVerificationMedal status="missing" />
          <span><b>Красная</b> — рендеринг меню не реализован</span>
        </button>
        <button className={`siteMedalLegendItem ${medalFilter === "unchecked" ? "active" : ""}`} type="button" onClick={() => toggleMedalFilter("unchecked")} aria-pressed={medalFilter === "unchecked"}>
          <ProjectVerificationMedal status="unchecked" />
          <span><b>Серая</b> — проверка ещё не выполнена</span>
        </button>
      </aside>
      <DataPanel
        title={(
          <span className="siteDomainsTitle">
            {favoritesOnly ? "Избранные проекты" : "Домены"}
            <small>{filteredRows.length === domainRows.length ? formatNumber(domainRows.length) : `${formatNumber(filteredRows.length)} из ${formatNumber(domainRows.length)}`}</small>
            <small className="siteVisibleRowsCount">На странице: {formatNumber(visibleRows.length)}</small>
          </span>
        )}
        actions={(
          <button className="iconButton siteColumnsSettingsButton" type="button" onClick={() => setColumnsSettingsOpen(true)} title="Настроить порядок столбцов" aria-label="Настроить порядок столбцов">
            <Settings size={15} />
          </button>
        )}
      >
        <div className="siteCacheSearch">
          <Search size={18} />
          <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Поиск по домену" />
          <label className="siteCacheFilter">
            <span>GEO</span>
            <select value={geoFilter} onChange={(event) => setGeoFilter(event.target.value)} aria-label="Фильтр сайтов по GEO">
              <option value="">Все GEO</option>
              {geoOptions.map((geo) => <option value={geo} key={geo}>{localeFlag(localeCountryCode(geo)) || "🌐"} {geo.toUpperCase()}</option>)}
            </select>
          </label>
          <label className="siteCacheFilter siteBrandFilter">
            <span>Бренд</span>
            <input value={brandFilter} onChange={(event) => setBrandFilter(event.target.value)} placeholder="Название бренда" aria-label="Фильтр сайтов по бренду" />
          </label>
          <label className="siteRowsPerPage">
            <span>Строк</span>
            <select value={rowsPerPage} onChange={(event) => setRowsPerPage(event.target.value === "all" ? "all" : Number(event.target.value))} aria-label="Количество строк на странице">
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="250">250</option>
              <option value="all">Все</option>
            </select>
          </label>
          <button className="button secondary siteSortResetButton" type="button" onClick={() => setSiteSort(null)} disabled={!siteSort}>Сбросить сортировку</button>
          <span>{filteredRows.length ? `${formatNumber(pageStart + 1)}–${formatNumber(pageStart + visibleRows.length)} из ${formatNumber(filteredRows.length)}` : `0 из ${formatNumber(domainRows.length)}`}</span>
        </div>
        {summaryFilter || medalFilter || statusFilterActive || menuTypeFilterActive || geoFilter || normalizedBrandFilter ? (
          <div className="siteActiveFilters" role="status">
            <strong><ListChecks size={16} /> Включены фильтры</strong>
            {summaryFilter ? (
              <button type="button" onClick={() => setSummaryFilter(null)}>
                Панель: {{ projects: "Проекты", working: "Рабочие", menu: "С меню", test: "Тестовые", duplicate: "Дубликаты", all: "Все сайты" }[summaryFilter]}
                <X size={13} />
              </button>
            ) : null}
            {medalFilter ? (
              <button type="button" onClick={() => setMedalFilter(null)}>
                Проверка меню: {{ gold: "золотая", verified: "зелёная", missing: "красная", unchecked: "серая" }[medalFilter]}
                <X size={13} />
              </button>
            ) : null}
            {statusFilterActive ? (
              <button type="button" onClick={() => setStatusFilters(allStatusFilters)}>
                Статус: {statusFilters.length ? statusFilterOptions.filter((option) => statusFilters.includes(option.value)).map((option) => option.label).join(", ") : "ничего не выбрано"}
                <X size={13} />
              </button>
            ) : null}
            {menuTypeFilterActive ? (
              <button type="button" onClick={() => setMenuTypeFilters(allMenuTypeFilters)}>
                Тип меню: {menuTypeFilters.length ? menuTypeFilterOptions.filter((option) => menuTypeFilters.includes(option.value)).map((option) => option.label).join(", ") : "ничего не выбрано"}
                <X size={13} />
              </button>
            ) : null}
            {geoFilter ? (
              <button type="button" onClick={() => setGeoFilter("")}>
                GEO: {geoFilter.toUpperCase()}
                <X size={13} />
              </button>
            ) : null}
            {normalizedBrandFilter ? (
              <button type="button" onClick={() => setBrandFilter("")}>
                Бренд: {brandFilter.trim()}
                <X size={13} />
              </button>
            ) : null}
            <button className="siteResetFilters" type="button" onClick={() => { setSummaryFilter(null); setMedalFilter(null); setStatusFilters(allStatusFilters); setMenuTypeFilters(allMenuTypeFilters); setGeoFilter(""); setBrandFilter(""); }}>Сбросить все</button>
          </div>
        ) : null}
        <ResponsiveTable
          columns={visibleColumnOrder.map((column) => SITE_COLUMN_LABELS[column])}
          columnKeys={visibleColumnOrder}
          columnHeaders={{
            [visibleColumnOrder.indexOf("select")]: (
              <label className={`tableSelectAllButton ${selectableFilteredNames.length ? "" : "disabled"}`} title="Выбрать все домены в текущем списке">
                <input type="checkbox" checked={allFilteredSelected} disabled={!selectableFilteredNames.length} onChange={toggleAllFilteredProjects} />
              </label>
            ),
            [visibleColumnOrder.indexOf("status")]: (
              <TableFilterHeader
                label="Статус"
                options={statusFilterOptions}
                selectedValues={statusFilters}
                onToggle={(value) => toggleFilterValue(value as Site["project_status"], setStatusFilters)}
                onSelectAll={() => setStatusFilters(statusFilterOptions.map((option) => option.value))}
                onSort={(direction) => setSiteSort({ key: "status", direction })}
                onResetSort={() => setSiteSort(null)}
                sortDirection={siteSort?.key === "status" ? siteSort.direction : undefined}
              />
            ),
            [visibleColumnOrder.indexOf("menuType")]: (
              <TableFilterHeader
                label="Тип меню"
                options={menuTypeFilterOptions}
                selectedValues={menuTypeFilters}
                onToggle={(value) => toggleFilterValue(value, setMenuTypeFilters)}
                onSelectAll={() => setMenuTypeFilters(menuTypeFilterOptions.map((option) => option.value))}
                onSort={(direction) => setSiteSort({ key: "menuType", direction })}
                onResetSort={() => setSiteSort(null)}
                sortDirection={siteSort?.key === "menuType" ? siteSort.direction : undefined}
              />
            )
          }}
          rows={visibleRows.map((row, rowIndex) => {
            const cells: Record<SiteTableColumn, React.ReactNode> = {
              rowNumber: formatNumber(pageStart + rowIndex + 1),
              select: <input type="checkbox" checked={selectedNames.has(row.name)} disabled={!row.externalProjectId} onChange={() => toggleSelectedProject(row.name)} aria-label={`Выбрать проект ${row.name}`} />,
              name: (
                <span className="siteNameCell">
                  <span className="siteNameWithFlag">
                    {localeFlag(localeCountryCode(row.geo || row.language || "")) ? <span aria-hidden="true">{localeFlag(localeCountryCode(row.geo || row.language || ""))}</span> : null}
                    <a
                      className="siteProjectDomainLink"
                      href={pathForRoute("workspace", "topics", row.name)}
                      onClick={() => {
                        localStorage.setItem(`workspace_site_id:${currentUsername}`, row.id);
                        localStorage.removeItem("workspace_site_id");
                      }}
                      title={`Открыть проект ${row.name}`}
                    >
                      <strong>{row.name}</strong>
                    </a>
                    <ProjectVerificationMedal status={row.medalStatus} />
                  </span>
                  <span className="siteNameActions">
                    <button
                      className={`siteRowActionButton siteFavoriteButton ${row.isFavorite ? "active" : ""}`}
                      type="button"
                      onClick={() => toggleFavoriteSite(row.id)}
                      title={row.isFavorite ? "Убрать из избранного" : "Добавить в избранное"}
                      aria-label={`${row.isFavorite ? "Убрать из избранного" : "Добавить в избранное"}: ${row.name}`}
                    >
                      <Star size={15} />
                    </button>
                    <a
                      className="siteRowActionButton"
                      href={row.baseUrl}
                      target="_blank"
                      rel="noreferrer"
                      title="Открыть сайт"
                      aria-label={`Открыть сайт ${row.name}`}
                    >
                      <Globe2 size={15} />
                    </a>
                    <a
                      className="siteRowActionButton"
                      href={pathForRoute("workspace", "topics", row.name)}
                      onClick={() => {
                        localStorage.setItem(`workspace_site_id:${currentUsername}`, row.id);
                        localStorage.removeItem("workspace_site_id");
                      }}
                      title="Открыть задачи проекта"
                      aria-label={`Открыть задачи проекта ${row.name}`}
                    >
                      <FolderKanban size={15} />
                    </a>
                  </span>
                </span>
              ),
              title: row.homepageTitle ? (
                <SiteTitleTooltip name={row.name} title={row.homepageTitle} />
              ) : "—",
              canon: <strong className="siteMainDomain">{row.canon}</strong>,
              language: <LocaleCode value={row.language} />,
              status: readOnly ? (
                <span className={`siteStatusReadonly ${row.projectStatus}`}>
                  {{ test: "Тестовый", working: "Рабочий", not_in_focus: "Не в фокусе", duplicate: "Дубликат" }[row.projectStatus]}
                </span>
              ) : (
                <select className={`siteStatusSelect ${row.projectStatus}`} value={row.projectStatus} onChange={(event) => updateProjectStatus(row.id, event.target.value as Site["project_status"])}>
                  <option value="test">Тестовый</option>
                  <option value="working">Рабочий</option>
                  <option value="not_in_focus">Не в фокусе</option>
                  <option value="duplicate">Дубликат</option>
                </select>
              ),
              internalPages: formatNumber(row.internalPagesCount),
              menuType: row.headerMenuCount && row.footerMenuCount
                ? <span className="siteMenuTypeBadge">Header + Footer</span>
                : row.headerMenuCount
                  ? <span className="siteMenuTypeBadge">Header</span>
                  : row.footerMenuCount
                    ? <span className="siteMenuTypeBadge">Footer</span>
                    : "—",
              menuCount: row.menuCount ? (
                <button className="siteMenuBadge siteMenuDetailsButton" type="button" onClick={() => setMenuPreview({ name: row.name, header: row.headerMenu, footer: row.footerMenu })} aria-label={`Показать пункты меню проекта ${row.name}`}>
                  {formatNumber(row.menuCount)}
                </button>
              ) : "0",
              domainsCount: formatNumber(row.domainsCount)
            };
            return visibleColumnOrder.map((column) => cells[column]);
          })}
          rowClassNames={visibleRows.map((row) => {
            const statusClass = row.projectStatus === "duplicate" ? "duplicate" : row.isTest ? "test" : row.isWorking ? "working" : "unfocused";
            return `siteDomainRow ${statusClass} ${row.hasMenu ? "hasMenu" : ""} ${row.isFavorite ? "favorite" : ""}`.trim();
          })}
          wrapperClassName="siteDomainsTable"
          sortableColumnIndexes={visibleColumnOrder.map((column, index) => SITE_COLUMN_SORT_KEYS[column] && !["status", "menuType"].includes(column) ? index : -1).filter((index) => index >= 0)}
          sortColumnIndex={siteSort ? siteSortKeys.indexOf(siteSort.key) : null}
          sortDirection={siteSort?.direction}
          onSortColumn={sortSitesByColumn}
        />
        {totalPages > 1 ? (
          <div className="siteTablePagination">
            <button className="button secondary compact" type="button" onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} disabled={activePage === 1}><ChevronLeft size={15} /> Назад</button>
            <span>Страница <strong>{formatNumber(activePage)}</strong> из {formatNumber(totalPages)}</span>
            <button className="button secondary compact" type="button" onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))} disabled={activePage === totalPages}>Вперёд <ChevronRight size={15} /></button>
          </div>
        ) : null}
      </DataPanel>
      {columnsSettingsOpen ? (
        <Modal title="Порядок столбцов" subtitle="Настройка сохранится для текущего пользователя" onClose={() => setColumnsSettingsOpen(false)} className="siteColumnsModal">
          <div className="siteColumnsOrderList">
            {columnOrder.map((column) => {
              const index = columnOrder.indexOf(column);
              const visible = !hiddenColumns.includes(column);
              return (
              <div key={column}>
                <label className="siteColumnVisibility">
                  <input type="checkbox" checked={visible} onChange={() => toggleSiteColumn(column)} disabled={visible && visibleColumnOrder.length === 1} />
                  <span>{SITE_COLUMN_LABELS[column] || "Чекбокс выбора"}</span>
                </label>
                <div>
                  <button type="button" onClick={() => moveSiteColumn(column, -1)} disabled={column === "rowNumber" || index === 1} aria-label="Переместить столбец выше"><ChevronUp size={15} /></button>
                  <button type="button" onClick={() => moveSiteColumn(column, 1)} disabled={column === "rowNumber" || index === columnOrder.length - 1} aria-label="Переместить столбец ниже"><ChevronDown size={15} /></button>
                </div>
              </div>
              );
            })}
          </div>
          <div className="formActions">
            <button className="button secondary compact" type="button" onClick={() => { setColumnOrder(DEFAULT_SITE_COLUMN_ORDER); setHiddenColumns([]); }}>По умолчанию</button>
            <button className="button primary compact" type="button" onClick={() => setColumnsSettingsOpen(false)}>Готово</button>
          </div>
        </Modal>
      ) : null}
      {menuPreview ? (
        <Modal
          title={`Пункты меню: ${menuPreview.name}`}
          subtitle={`Header: ${menuPreview.header.length} · Footer: ${menuPreview.footer.length}`}
          onClose={() => setMenuPreview(null)}
          wide
          className="siteMenuModal"
        >
          <div className="siteMenuPreviewGrid">
            <SiteMenuPreviewSection title="Header" items={menuPreview.header} />
            <SiteMenuPreviewSection title="Footer" items={menuPreview.footer} />
          </div>
        </Modal>
      ) : null}
    </section>
  );
}

function SiteTitleTooltip({ name, title }: { name: string; title: string }) {
  const [open, setOpen] = React.useState(false);
  const [position, setPosition] = React.useState({ left: 0, top: 0 });
  const buttonRef = React.useRef<HTMLButtonElement>(null);

  function toggleTooltip() {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const width = Math.min(480, window.innerWidth - 24);
      setPosition({
        left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        top: Math.min(rect.bottom + 7, window.innerHeight - 180)
      });
    }
    setOpen((current) => !current);
  }

  React.useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <>
      <button ref={buttonRef} className="siteHomepageTitleButton" type="button" onClick={toggleTooltip} aria-expanded={open} aria-label={`Показать полный title проекта ${name}`}>
        <strong className="siteHomepageTitle">{title}</strong>
      </button>
      {open ? createPortal(
        <>
          <button className="siteTitleTooltipDismiss" type="button" onClick={() => setOpen(false)} aria-label="Закрыть подсказку" />
          <div className="siteTitleTooltip" style={position} role="tooltip">
            <small>{name}</small>
            <strong>{title}</strong>
            <button type="button" onClick={() => setOpen(false)} aria-label="Закрыть подсказку"><X size={16} /></button>
          </div>
        </>,
        document.body
      ) : null}
    </>
  );
}

type MenuPreviewItem = { title: string; path: string; externalId: string };
type MenuTreeNode = { key: string; item: MenuPreviewItem; section?: Section; children: MenuTreeNode[] };

function menuPreviewItem(item: unknown, index: number): MenuPreviewItem {
    if (typeof item === "string") return { title: item, path: "", externalId: slugFromText(item) };
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      const title = `Пункт ${index + 1}`;
      return { title, path: String(item ?? ""), externalId: slugFromText(title) };
    }
    const value = item as Record<string, unknown>;
    const itemTitle = [value.title, value.name, value.label, value.text].find((entry) => typeof entry === "string" && entry.trim());
    const itemPath = [value.path, value.url, value.href, value.slug].find((entry) => typeof entry === "string" && entry.trim());
    const externalId = [value.external_id, value.externalId, value.id].find((entry) =>
      (typeof entry === "string" && entry.trim()) || typeof entry === "number"
    );
    const resolvedTitle = typeof itemTitle === "string" ? itemTitle : `Пункт ${index + 1}`;
    return {
      title: resolvedTitle,
      path: typeof itemPath === "string" ? itemPath : "",
      externalId: typeof externalId === "string" || typeof externalId === "number" ? String(externalId) : slugFromText(resolvedTitle)
    };
}

function normalizedTreePath(value: string): string {
  const rawValue = value.trim();
  if (!rawValue) return "";
  const withoutQuery = rawValue.split(/[?#]/, 1)[0];
  if (!withoutQuery) return "";
  const path = withoutQuery.replace(/^https?:\/\/[^/]+/i, "").replace(/^\/+|\/+$/g, "");
  return path ? `/${path}/` : "/";
}

function nestedPreviewItems(item: unknown): unknown[] {
  if (!item || typeof item !== "object" || Array.isArray(item)) return [];
  const value = item as Record<string, unknown>;
  const nested = value.children ?? value.items ?? value.submenu ?? value.subMenu;
  return Array.isArray(nested) ? nested : [];
}

function buildMenuTree(items: unknown[], sections: Section[]): MenuTreeNode[] {
  type FlatNode = MenuTreeNode & { explicitParentKey?: string; order: number };
  const flat: FlatNode[] = [];
  let sequence = 0;
  const visit = (rawItems: unknown[], explicitParentKey?: string) => {
    rawItems.forEach((rawItem, index) => {
      const item = menuPreviewItem(rawItem, index);
      const key = `cached:${sequence++}:${item.externalId}:${normalizedTreePath(item.path)}`;
      flat.push({ key, item, children: [], explicitParentKey, order: flat.length });
      visit(nestedPreviewItems(rawItem), key);
    });
  };
  visit(items);

  const sectionMatches = new Map<string, FlatNode>();
  for (const section of sections) {
    const sectionPath = normalizedTreePath(section.path);
    const matched = flat.find((node) =>
      !node.section && (
        node.item.externalId.toLocaleLowerCase() === section.external_id.toLocaleLowerCase()
        || Boolean(sectionPath && normalizedTreePath(node.item.path) === sectionPath)
      )
    );
    if (matched) {
      matched.section = section;
      sectionMatches.set(section.id, matched);
      continue;
    }
    const node: FlatNode = {
      key: `section:${section.id}`,
      item: { title: section.name, path: section.path, externalId: section.external_id },
      section,
      children: [],
      order: flat.length
    };
    flat.push(node);
    sectionMatches.set(section.id, node);
  }

  const byKey = new Map(flat.map((node) => [node.key, node]));
  const parentByKey = new Map<string, FlatNode>();
  for (const node of flat) {
    const explicitParent = node.explicitParentKey ? byKey.get(node.explicitParentKey) : undefined;
    const storedParent = node.section?.parent_id ? sectionMatches.get(node.section.parent_id) : undefined;
    const nodePath = normalizedTreePath(node.item.path);
    const inferredParent = nodePath
      ? flat
          .filter((candidate) => candidate.key !== node.key)
          .map((candidate) => ({ candidate, path: normalizedTreePath(candidate.item.path) }))
          .filter(({ path }) => path && path !== "/" && path !== nodePath && nodePath.startsWith(path))
          .sort((left, right) => right.path.length - left.path.length)[0]?.candidate
      : undefined;
    const parent = storedParent || explicitParent || inferredParent;
    if (parent) parentByKey.set(node.key, parent);
  }

  for (const node of flat) node.children = [];
  for (const node of flat) parentByKey.get(node.key)?.children.push(node);
  const sortNodes = (nodes: MenuTreeNode[]) => {
    nodes.sort((left, right) => (flat.find((node) => node.key === left.key)?.order || 0) - (flat.find((node) => node.key === right.key)?.order || 0));
    nodes.forEach((node) => sortNodes(node.children));
  };
  const roots = flat.filter((node) => !parentByKey.has(node.key));
  sortNodes(roots);
  return roots;
}

function countMenuTree(nodes: MenuTreeNode[]): number {
  return nodes.reduce((count, node) => count + 1 + countMenuTree(node.children), 0);
}

function collapsibleMenuKeys(nodes: MenuTreeNode[]): Set<string> {
  const keys = new Set<string>();
  const collect = (current: MenuTreeNode[]) => current.forEach((node) => {
    if (node.children.length) keys.add(node.key);
    collect(node.children);
  });
  collect(nodes);
  return keys;
}

function nestedContentSlug(sectionPath: string, contentSlug: string): string {
  const parent = normalizedTreePath(sectionPath) || "/";
  const contentPath = normalizedTreePath(contentSlug);
  const parts = contentPath.split("/").filter(Boolean);
  const leaf = parts.at(-1) || "";
  if (!leaf) return parent;
  return parent === "/" ? `/${leaf}/` : `${parent}${leaf}/`;
}

function SiteMenuPreviewSection({ title, items, sections = [], content = [], icon, action, children, adoptingParentKey, activeParentTreeKey, pagePreviewLoadingKey, onPreviewPage, onAddContent, onAddChild }: { title: string; items: unknown[]; sections?: Section[]; content?: ContentItem[]; icon?: React.ReactNode; action?: React.ReactNode; children?: React.ReactNode; adoptingParentKey?: string | null; activeParentTreeKey?: string; pagePreviewLoadingKey?: string | null; onPreviewPage?: (item: MenuPreviewItem, treeKey: string) => void; onAddContent?: (item: MenuPreviewItem, section: Section | undefined) => void; onAddChild?: (item: MenuPreviewItem, section: Section | undefined, treeKey: string) => void }) {
  const menuType = title.includes("Footer") ? "footer" : "header";
  const tree = React.useMemo(() => buildMenuTree(items, sections), [items, sections]);
  const [collapsedKeys, setCollapsedKeys] = React.useState<Set<string>>(() => collapsibleMenuKeys(tree));
  const [collapsedPageKeys, setCollapsedPageKeys] = React.useState<Set<string>>(() => new Set());
  const itemCount = countMenuTree(tree);
  const toggleNode = (key: string) => setCollapsedKeys((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const togglePages = (key: string) => setCollapsedPageKeys((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const renderNodes = (nodes: MenuTreeNode[], depth = 0): React.ReactNode => (
    <ul className="siteMenuTree" role={depth ? "group" : "tree"}>
      {nodes.map((node) => {
        const parentKey = `${menuType}:${node.item.externalId}`;
        const hasChildren = node.children.length > 0;
        const nestedCount = countMenuTree(node.children);
        const collapsed = collapsedKeys.has(node.key);
        const pagesCollapsed = collapsedPageKeys.has(node.key);
        const nestedPages = node.section
          ? content
              .filter((item) => item.section_id === node.section?.id && (Boolean(item.generated_at) || item.status === "published"))
              .sort((left, right) => {
                if (left.status === "published" && right.status !== "published") return 1;
                if (left.status !== "published" && right.status === "published") return -1;
                return left.topic.localeCompare(right.topic);
              })
          : [];
        return (
          <li className="siteMenuTreeNode" key={node.key} role="treeitem" aria-expanded={hasChildren ? !collapsed : undefined}>
            <div className="siteMenuTreeRow">
              {hasChildren ? <span className="siteMenuTreeBranchSpacer" /> : <button className="siteMenuTreeToggle" type="button" disabled><span /></button>}
              <div className="siteMenuPreviewItemText"><strong>{node.item.title}</strong>{node.item.path ? <code>{node.item.path}</code> : null}</div>
              {onPreviewPage ? <button className="siteMenuPagePreviewButton" type="button" onClick={() => onPreviewPage(node.item, node.key)} disabled={pagePreviewLoadingKey === node.key} title="Просмотреть текст страницы" aria-label={`Просмотреть текст страницы: ${node.item.title}`}>{pagePreviewLoadingKey === node.key ? <LoaderCircle size={14} /> : <Eye size={14} />}</button> : null}
              {nestedPages.length ? (
                <button className="siteMenuNestedPageCount" type="button" onClick={() => togglePages(node.key)} aria-expanded={!pagesCollapsed} aria-label={`${pagesCollapsed ? "Развернуть" : "Свернуть"} вложенные страницы пункта ${node.item.title}`}>
                  {pagesCollapsed ? <ChevronRight size={13} /> : <ChevronDown size={13} />} Страниц: {nestedPages.length}
                </button>
              ) : null}
              {hasChildren ? <button className="siteMenuTreeToggle hasChildren" type="button" onClick={() => toggleNode(node.key)} aria-label={`${collapsed ? "Развернуть" : "Свернуть"} ${node.item.title}`}>
                {collapsed ? <ChevronRight size={17} /> : <ChevronDown size={17} />}<span className="siteMenuTreeToggleLabel">{collapsed ? "Показать все" : "Свернуть"}</span><span className="siteMenuTreeNestedCount">{nestedCount}</span>
              </button> : null}
              {onAddContent ? <button className="siteMenuAddContentButton" type="button" onClick={() => onAddContent(node.item, node.section)} title={`Добавить контент в «${node.item.title}»`}><FilePlus2 size={15} /> Контент</button> : null}
              {onAddChild ? <button className="siteMenuAddChildButton" type="button" onClick={() => onAddChild(node.item, node.section, node.key)} disabled={Boolean(adoptingParentKey)} title={`Добавить дочерний пункт в «${node.item.title}»`}><span className="buttonPlusIcon"><Plus size={15} /></span> {adoptingParentKey === parentKey ? "Открываем…" : "Добавить"}</button> : null}
            </div>
            {activeParentTreeKey === node.key && children ? <div className="siteMenuTreeChildForm">{children}</div> : null}
            {nestedPages.length && !pagesCollapsed ? (
              <ul className="siteMenuNestedPages" aria-label={`Страницы в пункте ${node.item.title}`}>
                {nestedPages.map((page) => (
                  <li key={page.id}>
                    <span className="siteMenuNestedPageIcon"><FileText size={13} /></span>
                    <span className="siteMenuNestedPageText">
                      <strong title={page.topic}>{page.topic}</strong>
                      <code>{nestedContentSlug(node.item.path || node.section?.path || "/", page.slug)}</code>
                    </span>
                    <StatusBadge status={page.status} />
                  </li>
                ))}
              </ul>
            ) : null}
            {hasChildren && !collapsed ? renderNodes(node.children, depth + 1) : null}
          </li>
        );
      })}
    </ul>
  );

  return (
    <section className="siteMenuPreviewSection">
      <h3><span className="siteMenuPreviewTitle">{icon}{title} <span>{itemCount}</span></span></h3>
      {itemCount ? (
        <div className="siteMenuTreeViewport">{renderNodes(tree)}</div>
      ) : <div className="siteMenuPreviewEmpty">Пунктов нет</div>}
      {action ? <div className="siteMenuPreviewAction">{action}</div> : null}
      {children && !activeParentTreeKey ? children : null}
    </section>
  );
}

function TableFilterHeader({ label, options, selectedValues, onToggle, onSelectAll, onSort, onResetSort, sortDirection }: {
  label: string;
  options: Array<{ value: string; label: string }>;
  selectedValues: string[];
  onToggle: (value: string) => void;
  onSelectAll: () => void;
  onSort: (direction: "asc" | "desc") => void;
  onResetSort: () => void;
  sortDirection?: "asc" | "desc";
}) {
  const [open, setOpen] = React.useState(false);
  const [position, setPosition] = React.useState({ left: 0, top: 0 });
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  const filterActive = selectedValues.length !== options.length;

  function toggleOpen() {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPosition({ left: Math.min(rect.left, window.innerWidth - 280), top: rect.bottom + 6 });
    }
    setOpen((current) => !current);
  }

  React.useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <>
      <button ref={buttonRef} className={`tableFilterButton ${filterActive ? "active" : ""}`} type="button" onClick={toggleOpen} aria-expanded={open}>
        <span>{label}</span>
        {filterActive ? <small>{selectedValues.length}</small> : null}
        <ChevronDown size={15} />
      </button>
      {open ? createPortal(
        <>
          <button className="tableFilterDismiss" type="button" onClick={() => setOpen(false)} aria-label="Закрыть фильтр" />
          <div className="tableFilterPopover" style={position} onClick={(event) => event.stopPropagation()}>
            <strong>Фильтр: {label}</strong>
            <div className="tableFilterOptions">
              {options.map((option) => (
                <label key={option.value}>
                  <input type="checkbox" checked={selectedValues.includes(option.value)} onChange={() => onToggle(option.value)} />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
            <button className="tableFilterSelectAll" type="button" onClick={onSelectAll}>Показать все</button>
            <div className="tableFilterSortActions">
              <button className={sortDirection === "asc" ? "active" : ""} type="button" onClick={() => onSort("asc")}><ChevronUp size={14} /> По возрастанию</button>
              <button className={sortDirection === "desc" ? "active" : ""} type="button" onClick={() => onSort("desc")}><ChevronDown size={14} /> По убыванию</button>
              {sortDirection ? <button type="button" onClick={onResetSort}>Сбросить сортировку</button> : null}
            </div>
          </div>
        </>,
        document.body
      ) : null}
    </>
  );
}

function UserGuideView() {
  const quickSteps = [
    ["1", "Выберите проект", "Откройте рабочий экран, найдите домен и проверьте данные проекта."],
    ["2", "Создайте задачу", "Укажите язык, гео, объём, промпт и при необходимости пункт меню."],
    ["3", "Проверьте текст", "Откройте предпросмотр, назначьте раздел и нажмите «Принять»."],
    ["4", "Опубликуйте", "Отправьте принятые тексты сразу или через публикационную кампанию."],
  ];

  return (
    <div className="userGuidePage">
      <section className="guideHero">
        <div className="guideHeroCopy">
          <span className="guideKicker"><BookOpen size={18} /> Инструкция пользователя</span>
          <h2>От темы до опубликованной страницы</h2>
          <p>Пошаговое руководство по выбору проекта, генерации, проверке, привязке к меню и публикации контента.</p>
          <div className="guideHeroActions">
            <a className="button primary" href="#guide-quick-start"><Play size={17} /> Быстрый старт</a>
            <a className="button secondary" href="#guide-statuses"><ListChecks size={17} /> Статусы и ошибки</a>
          </div>
        </div>
        <div className="guideHeroFlow" aria-label="Схема работы">
          {quickSteps.map(([number, title]) => <div key={number}><span>{number}</span><strong>{title}</strong></div>)}
        </div>
      </section>

      <nav className="guideContents" aria-label="Содержание инструкции">
        <strong>Содержание</strong>
        <a href="#guide-quick-start">Быстрый старт</a>
        <a href="#guide-project">Проект</a>
        <a href="#guide-generation">Генерация</a>
        <a href="#guide-content">Контент</a>
        <a href="#guide-menu">Меню</a>
        <a href="#guide-statuses">Статусы</a>
      </nav>

      <section className="guideSection" id="guide-quick-start">
        <GuideSectionTitle number="01" title="Быстрый старт" subtitle="Минимальный рабочий сценарий состоит из четырёх шагов." />
        <div className="guideStepGrid">
          {quickSteps.map(([number, title, text]) => <article className="guideStepCard" key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}
        </div>
        <div className="guideTip"><CheckCircle2 size={21} /><div><strong>Перед публикацией</strong><p>Текст должен быть принят и привязан к нужному пункту меню. Тогда система сформирует полный вложенный URL.</p></div></div>
      </section>

      <section className="guideSection" id="guide-project">
        <GuideSectionTitle number="02" title="Выбор и обновление проекта" subtitle="Все операции выполняются в рамках выбранного домена." />
        <div className="guideMediaLayout">
          <figure className="guideScreenshot"><img src="/guide/project-workspace.svg" alt="Рабочий экран проекта" /><figcaption>Верхняя панель проекта и основные вкладки.</figcaption></figure>
          <div className="guideChecklist">
            <h3>Что находится в верхней панели</h3>
            <ol>
              <li><strong>Домен и MAIN</strong> — идентифицируют выбранный проект.</li>
              <li><strong>Три иконки MAIN</strong> — перейти на сайт, копировать адрес и открыть универсальную админку.</li>
              <li><strong>Обновить проект</strong> — получает с сервера актуальные страницы и меню.</li>
              <li><strong>Header и Footer</strong> — показывают результат проверки рендеринга меню.</li>
            </ol>
            <GuideNote icon={<CircleAlert size={18} />}>Красный статус меню означает ошибку проверки или отсутствие подтверждённого рендеринга, а не отсутствие пунктов в JSON.</GuideNote>
          </div>
        </div>
      </section>

      <section className="guideSection" id="guide-generation">
        <GuideSectionTitle number="03" title="Создание задачи и генерация" subtitle="Gemini создаёт темы и тексты с учётом проекта, гео, языка и раздела меню." />
        <div className="guideMediaLayout reverse">
          <div className="guideChecklist">
            <h3>Как создать задачу</h3>
            <ol>
              <li>Нажмите <strong>«Новая задача на генерацию»</strong>.</li>
              <li>Проверьте проект, гео, язык, количество слов и версию промпта.</li>
              <li>Выберите пункт меню, если материалы относятся к определённому разделу.</li>
              <li>Нажмите <strong>«Сгенерировать 10 тем»</strong>, проверьте список и запустите задачу.</li>
            </ol>
            <GuideNote icon={<Sparkles size={18} />}>При выбранном пункте меню его тематика добавляется в скрытый промпт. Уже существующие темы проверяются на совпадения.</GuideNote>
          </div>
          <figure className="guideScreenshot"><img src="/guide/generation-task.svg" alt="Форма создания задачи генерации" /><figcaption>Параметры задачи и генерация десяти тем.</figcaption></figure>
        </div>
      </section>

      <section className="guideSection" id="guide-content">
        <GuideSectionTitle number="04" title="Проверка и публикация контента" subtitle="Принятие подтверждает готовность редакции, публикация отправляет страницу на сервер." />
        <figure className="guideScreenshot wide"><img src="/guide/content-publication.svg" alt="Таблица контента с действиями" /><figcaption>Выбирайте отдельные строки или все материалы чекбоксом в заголовке.</figcaption></figure>
        <div className="guideActionGrid">
          <article><Eye size={22} /><h3>Просмотреть</h3><p>Иконка глаза открывает текст, URL, meta description и структуру заголовков.</p></article>
          <article><SquareCheckBig size={22} /><h3>Принять</h3><p>Подтверждает готовность текста. Материал получает статус «Ожидает публикации».</p></article>
          <article><Send size={22} /><h3>Опубликовать</h3><p>Отправляет выбранные страницы сразу, даже если они находятся в очереди кампании.</p></article>
        </div>
      </section>

      <section className="guideSection" id="guide-menu">
        <GuideSectionTitle number="05" title="Меню и вложенные страницы" subtitle="Здесь отображаются Header, Footer и страницы внутри каждого пункта." />
        <div className="guideRules">
          <div><strong>Добавить пункт</strong><span>Создаёт новую запись Header или Footer с правильным порядком.</span></div>
          <div><strong>Показать все</strong><span>Раскрывает страницы, вложенные в выбранный пункт меню.</span></div>
          <div><strong>Иконка глаза</strong><span>Открывает текст страницы из актуального JSON проекта.</span></div>
          <div><strong>Полный slug</strong><span>Для вложенной страницы используется путь <code>/раздел/страница/</code>.</span></div>
        </div>
      </section>

      <section className="guideSection" id="guide-statuses">
        <GuideSectionTitle number="06" title="Статусы и действия при ошибке" subtitle="Подписи и числа в карточках отражают актуальное состояние материалов." />
        <div className="guideStatusGrid">
          <article className="success"><CheckCircle2 /><div><strong>Сгенерировано / Принято</strong><p>Материал готов к проверке или подтверждён редактором.</p></div></article>
          <article className="pending"><CalendarClock /><div><strong>Ожидает публикации</strong><p>Материал принят и включён в процесс публикации.</p></div></article>
          <article className="progress"><Activity /><div><strong>Генерация / Публикуется</strong><p>Операция выполняется, индикатор показывает прогресс.</p></div></article>
          <article className="error"><AlertTriangle /><div><strong>Ошибка</strong><p>В логах доступны endpoint, HTTP-код и повтор запроса.</p></div></article>
        </div>
        <div className="guideRecovery"><h3>Если операция не завершилась</h3><ol><li>Обновите данные и проверьте новый статус.</li><li>Откройте сообщение об ошибке или «Логи запросов».</li><li>Проверьте endpoint, код ответа и пользователя-инициатора.</li><li>Повторите запрос из лога либо перезапустите только ошибочную операцию.</li></ol></div>
      </section>
    </div>
  );
}

function GuideSectionTitle({ number, title, subtitle }: { number: string; title: string; subtitle: string }) {
  return <div className="guideSectionHeading"><span>{number}</span><div><h2>{title}</h2><p>{subtitle}</p></div></div>;
}

function GuideNote({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="guideNote">{icon}<span>{children}</span></div>;
}

function SettingsView({ api, currentUser, users, inputStyle, onInputStyleChange, onChanged }: ViewProps & {
  currentUser: User | null;
  users: User[];
  inputStyle: InputStyle;
  onInputStyleChange: (style: InputStyle) => void;
}) {
  const [inputSettingsExpanded, setInputSettingsExpanded] = React.useState(false);

  return (
    <section className="viewStack">
      <DataPanel title="Профиль">
        <div className="accountHeader">
          <div>
            <span>Аккаунт</span>
            <strong>{currentUser?.username || "..."}</strong>
          </div>
          {currentUser ? <RoleBadge admin={currentUser.is_admin} /> : null}
        </div>
        <PasswordChangeForm api={api} />
      </DataPanel>

      {currentUser?.is_admin ? (
        <>
          <UsersAdminPanel api={api} currentUser={currentUser} users={users} onChanged={onChanged} />
          <AdminMenuVisibilityQueuePanel api={api} />
          <AdminRequestLogsPanel api={api} />
        </>
      ) : null}

      <DataPanel title="Настройки проекта">
        <div className="settingsList">
          <div><strong>Адрес сервиса</strong><span>https://ai-seo-content-panel.site</span></div>
          <div><strong>Frontend</strong><span>React, CSS Modules/global CSS, без Tailwind и CDN</span></div>
          <div><strong>Backend</strong><span>FastAPI, PostgreSQL, Redis, Celery</span></div>
          <div><strong>Payload</strong><span>Simple: menu + pages; Full: menu + pages + casinos</span></div>
          <div><strong>Content</strong><span>Editor.js blocks: header, paragraph, list, table, shortcode, image, faq, toc, quote, plusMinus</span></div>
          <div><strong>Deploy</strong><span>Git push через SSH-ключ на production remote</span></div>
        </div>
      </DataPanel>

      <section className={`dataPanel inputStyleSettingsPanel ${inputSettingsExpanded ? "expanded" : ""}`}>
        <button className="inputStyleSettingsToggle" type="button" onClick={() => setInputSettingsExpanded((current) => !current)} aria-expanded={inputSettingsExpanded}>
          <span className="inputStyleSettingsIcon"><Edit3 size={20} /></span>
          <span className="inputStyleSettingsText">
            <strong>Оформление полей ввода</strong>
            <small>Текущий стиль: {INPUT_STYLE_OPTIONS.find((option) => option.id === inputStyle)?.name}. Нажмите, чтобы {inputSettingsExpanded ? "свернуть" : "изменить"}.</small>
          </span>
          {inputSettingsExpanded ? <ChevronUp size={22} /> : <ChevronDown size={22} />}
        </button>
        {inputSettingsExpanded ? (
          <div className="inputStyleSettingsBody">
            <div className="inputStyleHeader">
              <p>Выберите один из 10 вариантов. Стиль применяется сразу ко всем полям, выпадающим спискам и поиску.</p>
              <span>Выбрано: <strong>{INPUT_STYLE_OPTIONS.find((option) => option.id === inputStyle)?.name}</strong></span>
            </div>
            <div className="inputStyleGrid" role="radiogroup" aria-label="Стиль полей ввода">
              {INPUT_STYLE_OPTIONS.map((option) => (
                <button
                  className={`inputStyleCard ${inputStyle === option.id ? "isSelected" : ""}`}
                  data-preview-style={option.id}
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={inputStyle === option.id}
                  onClick={() => onInputStyleChange(option.id)}
                >
                  <span className="inputStyleCardTitle">
                    <strong>{option.name}</strong>
                    {inputStyle === option.id ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
                  </span>
                  <small>{option.description}</small>
                  <span className="inputStylePreview" aria-hidden="true">
                    <span className="inputStylePreviewField">Пример поля</span>
                    <span className="inputStylePreviewField isFocused">Активное поле</span>
                  </span>
                </button>
              ))}
            </div>
            <p className="inputStyleFootnote">Настройка сохраняется в текущем браузере и применяется также к окну авторизации.</p>
          </div>
        ) : null}
      </section>
    </section>
  );
}

function AdminMenuVisibilityQueuePanel({ api }: Pick<ViewProps, "api">) {
  const [checks, setChecks] = React.useState<MenuVisibilityCheck[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const loadChecks = React.useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError("");
    try {
      setChecks(await api<MenuVisibilityCheck[]>("/admin/menu-visibility-checks"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Не удалось загрузить очередь проверок меню");
    } finally {
      setLoading(false);
    }
  }, [api]);

  React.useEffect(() => {
    void loadChecks(true);
    const intervalId = window.setInterval(() => void loadChecks(), 5000);
    return () => window.clearInterval(intervalId);
  }, [loadChecks]);

  const statusLabel = (status: string) => ({
    queued: "Ожидает",
    running: "Выполняется",
    completed: "Завершено",
    failed: "Ошибка"
  }[status] || status);

  return (
    <DataPanel
      title="Очередь проверок отображения меню"
      actions={<button className="button secondary compact" type="button" onClick={() => void loadChecks(true)} disabled={loading}><RefreshCcw size={15} /> {loading ? "Обновляем" : "Обновить"}</button>}
    >
      <p className="panelHint">Chromium выполняет не более одной проверки одновременно. Результаты сохраняются до изменения проекта или ручного повторного запуска.</p>
      {error ? <div className="formError">{error}</div> : null}
      {!loading && !checks.length ? <EmptyState text="Проверок пока нет." /> : (
        <ResponsiveTable
          columns={["Создано", "Проект", "Пользователь", "Статус", "Начало", "Завершение", "Код / ошибка"]}
          rows={checks.map((check) => [
            formatDate(check.created_at),
            <a className="requestLogProjectLink" href={pathForRoute("workspace", "overview", check.site_name)}>{check.site_name}</a>,
            check.requested_by_username || "Система",
            <span className={`requestLogResult ${check.status === "completed" ? "success" : check.status === "failed" ? "error" : "pending"}`}>{statusLabel(check.status)}</span>,
            check.started_at ? formatDate(check.started_at) : "—",
            check.finished_at ? formatDate(check.finished_at) : "—",
            check.error_code
              ? <span className="menuCheckError" title={check.error_message || check.error_code}><code>{check.error_code}</code>{check.error_message ? <small>{check.error_message}</small> : null}</span>
              : "—"
          ])}
        />
      )}
    </DataPanel>
  );
}

function AdminRequestLogsPanel({ api }: Pick<ViewProps, "api">) {
  const [logs, setLogs] = React.useState<AdminRequestLog[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [retryingId, setRetryingId] = React.useState("");

  const loadLogs = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setLogs(await api<AdminRequestLog[]>("/admin/request-logs"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Не удалось загрузить логи запросов");
    } finally {
      setLoading(false);
    }
  }, [api]);

  React.useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  async function retryRequest(log: AdminRequestLog) {
    if (!log.can_retry || retryingId) return;
    setRetryingId(log.id);
    setError("");
    try {
      await api(`/admin/request-logs/${log.id}/retry`, { method: "POST" });
      await loadLogs();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Не удалось повторить запрос");
    } finally {
      setRetryingId("");
    }
  }

  return (
    <DataPanel
      title="Логи запросов"
      actions={<button className="button secondary compact" type="button" onClick={loadLogs} disabled={loading}><RefreshCcw size={15} /> {loading ? "Обновляем" : "Обновить"}</button>}
    >
      {error ? <div className="formError">{error}</div> : null}
      {!loading && !logs.length ? <EmptyState text="Запросов пока нет." /> : (
        <ResponsiveTable
          columns={["Дата и время", "Проект", "Пользователь", "Что отправили", "Метод", "Куда", "Результат", "Действия"]}
          rows={logs.map((log) => [
            formatDate(log.created_at),
            <a className="requestLogProjectLink" href={pathForRoute("workspace", "overview", log.project_name)}>{log.project_name}</a>,
            log.actor_username || "—",
            <span className="requestLogAction"><strong>{log.action}</strong>{log.item_name ? <small>{log.item_name}</small> : null}</span>,
            <code className="requestLogMethod">{log.method}</code>,
            <span className="requestLogDestination" title={log.destination}>{log.destination}</span>,
            <span className={`requestLogResult ${log.result === "Успешно" ? "success" : log.result === "Ошибка" ? "error" : "pending"}`}>{log.result}{log.status_code ? ` · ${log.status_code}` : ""}</span>,
            <button className="button compact secondary requestLogRetryButton" type="button" onClick={() => void retryRequest(log)} disabled={!log.can_retry || Boolean(retryingId)} title={log.can_retry ? "Повторить этот запрос" : "Успешную публикацию контента повторять нельзя"}><RefreshCcw size={14} /> {retryingId === log.id ? "Повторяем" : "Повторить"}</button>
          ])}
        />
      )}
    </DataPanel>
  );
}

function PasswordChangeForm({ api }: Pick<ViewProps, "api">) {
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [formError, setFormError] = React.useState("");
  const [saved, setSaved] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaved(false);
    setFormError("");
    if (newPassword !== confirmPassword) {
      setFormError("Новый пароль и подтверждение не совпадают.");
      return;
    }
    try {
      await api("/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSaved(true);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось обновить пароль");
    }
  }

  return (
    <form className="formGrid compactForm" onSubmit={submit}>
      <label>
        Текущий пароль
        <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
      </label>
      <label>
        Новый пароль
        <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={8} />
      </label>
      <label>
        Повтор нового пароля
        <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={8} />
      </label>
      <div className="formActions alignEnd">
        <button className="button primary" type="submit"><KeyRound size={18} /> Обновить пароль</button>
      </div>
      {formError ? <span className="formError wide">{formError}</span> : null}
      {saved ? <span className="formSuccess wide">Пароль обновлен.</span> : null}
    </form>
  );
}

function UsersAdminPanel({ api, currentUser, users, onChanged }: ViewProps & { currentUser: User; users: User[] }) {
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState(() => generateSecurePassword());
  const [isAdmin, setIsAdmin] = React.useState(false);
  const [formError, setFormError] = React.useState("");
  const [passwordActionId, setPasswordActionId] = React.useState("");
  const [passwordCopiedId, setPasswordCopiedId] = React.useState("");
  const [generatedPasswordNotice, setGeneratedPasswordNotice] = React.useState("Предложен новый безопасный пароль.");

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ username, password, is_admin: isAdmin })
      });
      setUsername("");
      setPassword(generateSecurePassword());
      setGeneratedPasswordNotice("Пользователь создан. Подготовлен новый пароль для следующего пользователя.");
      setIsAdmin(false);
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось создать пользователя");
    }
  }

  async function generatePasswordForNewUser() {
    setFormError("");
    const generatedPassword = generateSecurePassword();
    setPassword(generatedPassword);
    try {
      await copyTextToClipboard(generatedPassword);
      setGeneratedPasswordNotice("Безопасный пароль сгенерирован и скопирован.");
    } catch {
      setGeneratedPasswordNotice("Безопасный пароль сгенерирован и добавлен в поле.");
    }
  }

  async function updateUser(user: User, changes: Partial<Pick<User, "is_admin" | "is_active">>) {
    setFormError("");
    try {
      await api<User>(`/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify(changes)
      });
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось обновить пользователя");
    }
  }

  async function resetAndCopyPassword(user: User) {
    const confirmed = window.confirm(`Текущий пароль пользователя «${user.username}» нельзя прочитать. Создать новый пароль и скопировать его?`);
    if (!confirmed) return;
    setFormError("");
    setPasswordActionId(user.id);
    setPasswordCopiedId("");
    try {
      const result = await api<{ password: string }>(`/users/${user.id}/reset-password`, { method: "POST" });
      try {
        await copyTextToClipboard(result.password);
        setPasswordCopiedId(user.id);
        window.setTimeout(() => setPasswordCopiedId((current) => current === user.id ? "" : current), 2400);
      } catch {
        window.prompt(`Новый пароль пользователя ${user.username}. Скопируйте его сейчас:`, result.password);
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось создать новый пароль");
    } finally {
      setPasswordActionId("");
    }
  }

  return (
    <DataPanel title="Пользователи">
      <div className="subPanelTitle"><Users size={18} /><strong>Доступы</strong></div>
      <form className="formGrid compactForm" onSubmit={createUser}>
        <label>
          Логин
          <input value={username} onChange={(event) => setUsername(event.target.value)} required minLength={2} />
        </label>
        <label>
          Пароль
          <span className="generatedPasswordControl">
            <input type="text" autoComplete="new-password" value={password} onChange={(event) => { setPassword(event.target.value); setGeneratedPasswordNotice(""); }} required minLength={8} />
            <button className="button secondary" type="button" onClick={() => void generatePasswordForNewUser()}><KeyRound size={16} /> Сгенерировать пароль</button>
          </span>
        </label>
        <label className="checkboxRow">
          <input type="checkbox" checked={isAdmin} onChange={(event) => setIsAdmin(event.target.checked)} />
          Администратор
        </label>
        <div className="formActions alignEnd">
          <button className="button primary" type="submit"><UserPlus size={18} /> Создать пользователя</button>
        </div>
        {formError ? <span className="formError wide">{formError}</span> : null}
        {generatedPasswordNotice ? <span className="formSuccess wide">{generatedPasswordNotice}</span> : null}
      </form>

      <ResponsiveTable
        columns={["Пользователь", "Роль", "Статус", "Создан", "Действия"]}
        rows={users.map((user) => [
          user.username,
          <RoleBadge admin={user.is_admin} />,
          user.is_active ? "Активен" : "Отключен",
          formatDate(user.created_at),
          <div className="userActions">
            <button
              className="button compact"
              type="button"
              onClick={() => updateUser(user, { is_admin: !user.is_admin })}
              disabled={user.id === currentUser.id && user.is_admin}
            >
              {user.is_admin ? "Снять admin" : "Сделать admin"}
            </button>
            <button
              className={`button compact ${user.is_active ? "danger" : ""}`}
              type="button"
              onClick={() => updateUser(user, { is_active: !user.is_active })}
              disabled={user.id === currentUser.id}
            >
              {user.is_active ? "Отключить" : "Включить"}
            </button>
            <button className="button compact secondary" type="button" onClick={() => void resetAndCopyPassword(user)} disabled={Boolean(passwordActionId)}>
              <Copy size={15} /> {passwordActionId === user.id ? "Создаём пароль" : passwordCopiedId === user.id ? "Скопировано" : "Скопировать пароль"}
            </button>
          </div>
        ])}
      />
    </DataPanel>
  );
}

type ViewProps = {
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
  onChanged: () => void;
};

function NavButton({ href, icon, label, active, onClick }: { href: string; icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <a
      className={`navButton ${active ? "active" : ""}`}
      href={href}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onClick();
      }}
    >
      {icon}
      <span>{label}</span>
    </a>
  );
}

function TabButton({ href, icon, label, active, attention = false, onClick }: { href: string; icon?: React.ReactNode; label: string; active: boolean; attention?: boolean; onClick: () => void }) {
  return (
    <a
      className={`tabButton ${active ? "active" : ""} ${attention ? "attention" : ""}`}
      href={href}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onClick();
      }}
    >
      {icon}
      {label}
    </a>
  );
}

function KpiCard({ icon, label, value, danger, onClick, active }: { icon: React.ReactNode; label: string; value: number; danger?: boolean; onClick?: () => void; active?: boolean }) {
  const className = `kpiCard ${danger ? "danger" : ""} ${onClick ? "interactive" : ""} ${active ? "active" : ""}`.trim();
  const content = <><div className="kpiIcon">{icon}</div><span>{label}</span><strong>{value}</strong></>;
  return onClick
    ? <button className={className} type="button" onClick={onClick} aria-expanded={active}>{content}</button>
    : <div className={className}>{content}</div>;
}

type SearchableSelectOption = {
  value: string;
  label: string;
  leading?: React.ReactNode;
  indicator?: React.ReactNode;
  keywords?: string;
  description?: string;
  badge?: string;
  badgeTone?: "warning" | "neutral";
  tone?: "test" | "menu";
};

function SearchableSelect({
  value,
  options,
  onChange,
  searchPlaceholder = "Начните вводить для поиска",
  disabled = false,
  ariaLabel,
  showSelectedIndicator = true,
  optionPredicate,
  dropdownToolbar,
  renderOptionAction
}: {
  value: string;
  options: SearchableSelectOption[];
  onChange: (value: string) => void;
  searchPlaceholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  showSelectedIndicator?: boolean;
  optionPredicate?: (option: SearchableSelectOption) => boolean;
  dropdownToolbar?: React.ReactNode;
  renderOptionAction?: (option: SearchableSelectOption) => React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [activeIndex, setActiveIndex] = React.useState(0);
  const [dropdownStyle, setDropdownStyle] = React.useState<React.CSSProperties>({});
  const controlRef = React.useRef<HTMLButtonElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);
  const listboxId = React.useId();
  const selected = options.find((option) => option.value === value);
  const normalizedQuery = query.trim().toLocaleLowerCase("ru-RU");
  const visibleOptions = optionPredicate ? options.filter(optionPredicate) : options;
  const filteredOptions = normalizedQuery
    ? visibleOptions.filter((option) => `${option.label} ${option.value} ${option.keywords || ""}`.toLocaleLowerCase("ru-RU").includes(normalizedQuery))
    : visibleOptions;

  const updateDropdownPosition = React.useCallback(() => {
    const control = controlRef.current;
    if (!control) return;
    const rect = control.getBoundingClientRect();
    const availableBelow = window.innerHeight - rect.bottom - 12;
    const availableAbove = rect.top - 12;
    const desiredHeight = Math.min(360, Math.max(210, options.length * 44 + 62));
    const placeAbove = availableBelow < Math.min(240, desiredHeight) && availableAbove > availableBelow;
    const maxHeight = Math.max(180, Math.min(desiredHeight, placeAbove ? availableAbove : availableBelow));
    setDropdownStyle({
      left: Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8)),
      top: placeAbove ? Math.max(8, rect.top - maxHeight - 4) : rect.bottom + 4,
      width: Math.min(rect.width, window.innerWidth - 16),
      maxHeight
    });
  }, [options.length]);

  React.useEffect(() => {
    if (!open) return;
    updateDropdownPosition();
    window.requestAnimationFrame(() => {
      searchRef.current?.focus();
      dropdownRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    });
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!controlRef.current?.contains(target) && !dropdownRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    window.addEventListener("resize", updateDropdownPosition);
    window.addEventListener("scroll", updateDropdownPosition, true);
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      window.removeEventListener("resize", updateDropdownPosition);
      window.removeEventListener("scroll", updateDropdownPosition, true);
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [open, updateDropdownPosition]);

  React.useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function showOptions() {
    if (disabled) return;
    setQuery("");
    setActiveIndex(Math.max(0, options.findIndex((option) => option.value === value)));
    setOpen(true);
  }

  function chooseOption(option: SearchableSelectOption) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
    window.requestAnimationFrame(() => controlRef.current?.focus());
  }

  return (
    <div className={`searchableSelect ${open ? "isOpen" : ""}`}>
      <button
        ref={controlRef}
        className="searchableSelectControl"
        type="button"
        disabled={disabled}
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        onClick={() => open ? setOpen(false) : showOptions()}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            showOptions();
          }
        }}
      >
        <span className="searchableSelectControlValue">
          {selected?.leading}
          <span className="searchableSelectControlLabel">{selected?.label || "Выберите значение"}</span>
          {showSelectedIndicator && selected?.indicator ? <span className="searchableSelectOptionIndicator">{selected.indicator}</span> : null}
        </span>
        <ChevronDown className="searchableSelectChevron" size={17} />
      </button>
      {open ? createPortal(
        <div ref={dropdownRef} className="searchableSelectDropdown" style={dropdownStyle}>
          <div className="searchableSelectSearch">
            <Search size={16} />
            <input
              ref={searchRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveIndex((current) => Math.min(current + 1, filteredOptions.length - 1));
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveIndex((current) => Math.max(current - 1, 0));
                } else if (event.key === "Enter" && filteredOptions[activeIndex]) {
                  event.preventDefault();
                  chooseOption(filteredOptions[activeIndex]);
                } else if (event.key === "Escape") {
                  event.preventDefault();
                  setOpen(false);
                  controlRef.current?.focus();
                }
              }}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              autoComplete="off"
            />
          </div>
          {dropdownToolbar ? <div className="searchableSelectToolbar">{dropdownToolbar}</div> : null}
          <div className="searchableSelectOptions" id={listboxId} role="listbox">
            {filteredOptions.length ? filteredOptions.map((option, index) => (
              <div
                className={`searchableSelectOption ${option.value === value ? "selected" : ""} ${index === activeIndex ? "active" : ""} ${option.tone || ""}`}
                role="option"
                tabIndex={0}
                aria-selected={option.value === value}
                key={`${option.value}:${option.label}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => chooseOption(option)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    chooseOption(option);
                  }
                }}
              >
                <span className="searchableSelectOptionContent">
                  <span className="searchableSelectOptionHeading">
                    {option.leading}
                    <span className="searchableSelectOptionLabel">{option.label}</span>
                    {option.indicator ? <span className="searchableSelectOptionIndicator">{option.indicator}</span> : null}
                  </span>
                  {option.description ? <small>{option.description}</small> : null}
                </span>
                <span className="searchableSelectOptionAside">
                  {option.badge !== undefined ? <small className={`searchableSelectOptionBadge ${option.badgeTone === "neutral" ? "neutral" : ""}`}>{option.badge}</small> : null}
                  {option.value === value ? <CheckCircle2 size={16} /> : null}
                  {renderOptionAction ? (
                    <span onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
                      {renderOptionAction(option)}
                    </span>
                  ) : null}
                </span>
              </div>
            )) : <div className="searchableSelectEmpty">{optionPredicate && !normalizedQuery ? "В избранном пока нет проектов" : "Ничего не найдено"}</div>}
          </div>
        </div>,
        document.body
      ) : null}
    </div>
  );
}

function DataPanel({ id, title, actions, children, collapseKey, allowCollapse = true, className = "" }: { id?: string; title: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; collapseKey?: string; allowCollapse?: boolean; className?: string }) {
  const accordionContext = React.useContext(WorkspaceAccordionContext);
  const automaticKey = typeof title === "string" ? title.split(" · ")[0].trim().toLowerCase().replace(/[^a-zа-яё0-9]+/gi, "-") : "";
  const effectiveCollapseKey = collapseKey || automaticKey;
  const collapsible = Boolean(allowCollapse && accordionContext?.allowPanelCollapse && effectiveCollapseKey);
  const [expanded, setExpanded] = usePersistentWorkspacePanelState(effectiveCollapseKey || "static-panel", true);

  React.useEffect(() => {
    if (!collapsible) return;
    const openPanel = (event: Event) => {
      const detail = (event as CustomEvent<{ key?: string; exclusive?: boolean }>).detail;
      const publicationPanelKeys = ["project-content", "project-campaigns", "publication-process", "publication-queue", "publication-backlog"];
      if (detail?.exclusive && publicationPanelKeys.includes(effectiveCollapseKey)) {
        setExpanded(detail.key === effectiveCollapseKey);
      } else if (detail?.key === effectiveCollapseKey) {
        setExpanded(true);
      }
    };
    window.addEventListener("workspace:open-panel", openPanel);
    return () => window.removeEventListener("workspace:open-panel", openPanel);
  }, [collapsible, effectiveCollapseKey, setExpanded]);

  return (
    <section id={id} className={`dataPanel ${collapsible ? "collapsibleDataPanel" : ""} ${collapsible && !expanded ? "collapsed" : ""} ${className}`.trim()}>
      <div className="panelHeader">
        {collapsible ? (
          <button className="dataPanelCollapseToggle" type="button" onClick={() => setExpanded((current) => !current)} aria-expanded={expanded} title={expanded ? "Свернуть блок" : "Развернуть блок"}>
            <h2>{title}</h2>
            <span>{expanded ? "Свернуть" : "Показать"}</span>
            {expanded ? <ChevronUp size={19} /> : <ChevronDown size={19} />}
          </button>
        ) : <h2>{title}</h2>}
        {actions && (!collapsible || expanded) ? actions : null}
      </div>
      {(!collapsible || expanded) ? <div className="dataPanelBody">{children}</div> : null}
    </section>
  );
}

function ResponsiveTable({ columns, columnKeys = [], rows, rowClassNames, wrapperClassName = "", sortableColumnIndexes = [], sortColumnIndex = null, sortDirection, onSortColumn, columnHeaders = {} }: { columns: string[]; columnKeys?: string[]; rows: React.ReactNode[][]; rowClassNames?: string[]; wrapperClassName?: string; sortableColumnIndexes?: number[]; sortColumnIndex?: number | null; sortDirection?: "asc" | "desc"; onSortColumn?: (columnIndex: number) => void; columnHeaders?: Record<number, React.ReactNode> }) {
  if (!rows.length) return <EmptyState text="Данных пока нет." />;
  return (
    <div className={`tableWrap ${wrapperClassName}`.trim()}>
      <table>
        <thead><tr>{columns.map((column, columnIndex) => (
          <th className={columnKeys[columnIndex] ? `column-${columnKeys[columnIndex]}` : undefined} key={`${column}:${columnIndex}`}>
            {columnHeaders[columnIndex] || (sortableColumnIndexes.includes(columnIndex) ? (
              <button className={`tableSortButton ${sortColumnIndex === columnIndex ? "active" : ""}`} type="button" onClick={() => onSortColumn?.(columnIndex)}>
                <span>{column}</span>
                {sortColumnIndex === columnIndex && sortDirection === "desc" ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
              </button>
            ) : column)}
          </th>
        ))}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => <tr className={rowClassNames?.[rowIndex] || undefined} key={rowIndex}>{row.map((cell, cellIndex) => <td className={columnKeys[cellIndex] ? `column-${columnKeys[cellIndex]}` : undefined} data-label={columns[cellIndex]} key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function Modal({ title, subtitle, children, onClose, wide, className = "", headerActions }: { title: string; subtitle?: string; children: React.ReactNode; onClose: () => void; wide?: boolean; className?: string; headerActions?: React.ReactNode }) {
  return (
    <div className="modalOverlay" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={onClose}>
      <div className={`modalDialog ${wide ? "wide" : ""} ${className}`.trim()} onMouseDown={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <div className="modalTitleGroup">
            <h2 id="modal-title">{title}</h2>
            {subtitle ? <small>{subtitle}</small> : null}
          </div>
          <div className="modalHeaderControls">
            {headerActions}
            <button className="iconButton" type="button" onClick={onClose} aria-label="Закрыть окно"><X size={18} /></button>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

function ContentPreviewModal({ item, promptName, actions, onClose }: { item: ContentItem; promptName?: string | null; actions?: React.ReactNode; onClose: () => void }) {
  const previewDescription = contentItemDescription(item);
  return (
    <Modal title={`Просмотр текста: ${item.topic}`} subtitle="Название темы используется как Title страницы" onClose={onClose} wide className="contentPreviewModal">
      <div className="contentPreviewHeader">
        <div className="contentPreviewInfo">
          <div className="contentPreviewMetaLine">
            <span>URL: <code>{item.slug}</code></span>
            <PromptBadge name={item.generation_prompt_name || promptName} />
            {item.competitor_brief ? <span className="researchBadge">На основе анализа конкурентов</span> : null}
            <span>Сгенерировано: {item.generated_at ? formatDate(item.generated_at) : "-"}</span>
          </div>
          <div className="previewDescriptionCompact">
            <strong>Meta Description</strong>
            <span>{previewDescription || "Не заполнен"}</span>
          </div>
        </div>
        <div className="userActions contentPreviewActions">
          <StatusBadge status={item.status} />
          {actions}
        </div>
      </div>
      <div className="contentPreviewGeneration">
        <span className="previewGenerationLabel">Генерация</span>
        <GenerationProgressCell item={item} />
      </div>
      <div className="previewStructureLegend">
        Метки H1–H4 показаны только для проверки структуры и не добавляются в опубликованный текст.
      </div>
      <ContentPreviewBody item={item} />
    </Modal>
  );
}

function ProjectPagePreviewModal({ preview, onClose }: { preview: ProjectPagePreview; onClose: () => void }) {
  return (
    <Modal title={`Просмотр страницы: ${preview.title}`} subtitle="Текст получен из актуального JSON проекта" onClose={onClose} wide className="contentPreviewModal">
      <div className="contentPreviewHeader">
        <div className="contentPreviewInfo">
          <div className="contentPreviewMetaLine"><span>URL: <code>{preview.slug}</code></span></div>
          <div className="previewDescriptionCompact"><strong>Meta Description</strong><span>{previewPlainText(preview.description) || "Не заполнен"}</span></div>
        </div>
      </div>
      <div className="previewStructureLegend">Метки H1–H4 показаны только для проверки структуры страницы.</div>
      <ContentPreviewBody generatedJson={{ pages: [preview.page] }} />
    </Modal>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function PromptBadge({ name }: { name?: string | null }) {
  const label = name || "Промпт не указан";
  const isImproved = /v\s*2|улучш|доработ/i.test(label);
  return <span className={`promptBadge ${isImproved ? "improved" : ""}`}>{label}</span>;
}

function CasinoRatingMedal({ enabled }: { enabled: boolean }) {
  const label = enabled ? "В тексте предусмотрен рейтинг казино" : "В тексте нет рейтинга казино";
  return (
    <span className={`casinoRatingMedal ${enabled ? "active" : "inactive"}`} title={label} aria-label={label}>
      <Medal size={17} />
    </span>
  );
}

function ContentTopicLabel({ item }: { item: { topic: string; include_casino_rating: boolean } }) {
  return <span className="contentTopicWithRating"><span>{item.topic}</span><CasinoRatingMedal enabled={item.include_casino_rating} /></span>;
}

function TopicMetaCell({ item, promptName }: { item: ContentItem; promptName?: string | null }) {
  const generationPrompt = item.generation_prompt_name || promptName || "Промпт не указан";
  const generationDate = item.generated_at || item.updated_at;
  const generationMeta = item.generated_json?.generation_meta;
  const competitorResearch = generationMeta && typeof generationMeta === "object" && !Array.isArray(generationMeta)
    ? (generationMeta as Record<string, unknown>).competitor_research
    : null;
  const usedCompetitorResearch = competitorResearch && typeof competitorResearch === "object" && !Array.isArray(competitorResearch)
    && (competitorResearch as Record<string, unknown>).status === "used";
  return (
    <div className="topicMetaCell">
      <strong><ContentTopicLabel item={item} /></strong>
      <PromptBadge name={generationPrompt} />
      {usedCompetitorResearch ? <span className="researchBadge">На основе анализа конкурентов</span> : null}
      <span>Генерация: {generationDate ? formatDate(generationDate) : "-"}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    active: "Активно",
    approved: "Принято",
    brief_ready: "Бриф готов",
    collecting: "Сбор данных",
    collecting_serp: "Сбор выдачи",
    completed: "Завершено",
    completed_with_errors: "Завершено с ошибками",
    discovered: "Обнаружено",
    draft: "Черновик",
    empty: "Нет данных",
    failed: "Ошибка",
    fetch_failed: "Ошибка загрузки",
    fetched: "Загружено",
    fetching_pages: "Загрузка страниц",
    generated: "Сгенерировано",
    generating: "Генерация",
    generation_failed: "Ошибка генерации",
    generation_queued: "В очереди на генерацию",
    invalid: "Ошибка",
    not_requested: "Не запрошено",
    pages_fetched: "Страницы загружены",
    paused: "Приостановлено",
    pending: "Ожидает",
    publication_failed: "Ошибка публикации",
    publication_paused: "Публикация приостановлена",
    published: "Опубликовано",
    publishing: "Публикуется",
    publishing_all: "Публикуем все",
    queries_ready: "Запросы готовы",
    queued: "В очереди",
    rejected: "Отклонено",
    research_failed: "Ошибка анализа",
    retry_scheduled: "Повтор запланирован",
    scheduled: "Запланировано",
    serp_collected: "Выдача собрана",
    stopped: "Остановлено",
    synced: "Синхронизировано",
    unchecked: "Не проверено",
    valid: "Готово"
  };
  return <span className={`status status-${status.replaceAll("_", "-")}`}>{labels[status] || status}</span>;
}

function CampaignStatusBadge({ status }: { status: string }) {
  const label = status === "active" ? "В работе" : status === "publishing_all" ? "Публикуем все" : null;
  return label
    ? <span className={`status status-${status.replaceAll("_", "-")}`}>{label}</span>
    : <StatusBadge status={status} />;
}

function ProviderValidationCell({ provider }: { provider: AiProvider }) {
  const status = provider.validation_status || "unchecked";
  const labels: Record<string, string> = {
    valid: "Валиден",
    invalid: "Ошибка",
    unchecked: "Не проверен"
  };
  return (
    <div className="cellStack">
      <span className={`status status-${status.replaceAll("_", "-")}`} title={provider.validation_message || undefined}>
        {labels[status] || status}
      </span>
      {provider.validation_message ? <span className="cellHint">{provider.validation_message}</span> : null}
    </div>
  );
}

function RoleBadge({ admin }: { admin: boolean }) {
  return <span className={`roleBadge ${admin ? "admin" : ""}`}>{admin ? "Администратор" : "Пользователь"}</span>;
}

function sectionLabel(sectionId: string | null, sections: Section[]) {
  if (!sectionId) return "Не выбран";
  const section = sections.find((item) => item.id === sectionId);
  return section ? `${section.name} · ${section.path}` : sectionId;
}

function viewTitle(view: AppView, _workspaceTab: WorkspaceTab) {
  if (view === "workspace") {
    return "С каким проектом сегодня поработаем?";
  }

  const titles: Record<Exclude<AppView, "workspace">, string> = {
    dashboard: "Dashboard",
    prompts: "Промпты",
    tasks: "Задачи генерации",
    taskArchive: "Архив задач",
    content: "Контент",
    publications: "Контент и публикации",
    providers: "API Providers",
    sites: "Сайты",
    favorites: "Избранное",
    guide: "Инструкция по работе",
    settings: "Настройки"
  };
  return titles[view];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function publicationIntervalLabel(intervalMinutes: number) {
  if (intervalMinutes === 1440) return "1 текст/день · 24 ч";
  if (intervalMinutes === 720) return "2 текста/день · 12 ч";
  if (intervalMinutes === 420) return "3 текста/день · 7 ч";
  return `${intervalMinutes} мин.`;
}

function defaultPromptTemplate(prompts: PromptTemplate[]): PromptTemplate | null {
  return prompts.find((prompt) => prompt.is_default)
    || prompts.find((prompt) => prompt.name === "Промпт рабочий")
    || latestPromptTemplate(prompts);
}

function latestPromptTemplate(prompts: PromptTemplate[]): PromptTemplate | null {
  return [...prompts].sort((left, right) => {
    const createdDifference = new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    if (createdDifference) return createdDifference;
    const leftVersion = Number(left.name.match(/\bv\s*(\d+)\s*$/i)?.[1] || 0);
    const rightVersion = Number(right.name.match(/\bv\s*(\d+)\s*$/i)?.[1] || 0);
    if (rightVersion !== leftVersion) return rightVersion - leftVersion;
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
  })[0] || null;
}

function humanPayloadMode(value: string) {
  if (value === "full_site") return "Full site";
  if (value === "simple_page") return "Simple page";
  return "Site default";
}

function humanProviderType(value: string) {
  if (value === "gemini") return "Gemini";
  if (value === "dataforseo") return "DataForSEO SERP";
  return "Custom";
}

function isGenerationProvider(provider: AiProvider) {
  return provider.provider_type === "gemini" || provider.provider_type === "custom";
}

function countryFlag(code: string) {
  if (!/^[A-Z]{2}$/.test(code)) return "";
  return code
    .split("")
    .map((letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)))
    .join("");
}

function countryLabel(code: string) {
  const country = COUNTRIES.find((item) => item.code === code.toUpperCase());
  return country ? `${country.flag} ${country.code}` : code;
}

function languageLabel(code: string, languages: LanguageOption[] = LANGUAGE_OPTIONS) {
  const language = languages.find((item) => item.code === code.toLowerCase());
  return language ? `${language.flag} ${language.code.toUpperCase()}` : code.toUpperCase();
}

function contentItemTitle(item: ContentItem) {
  const pages = item.generated_json.pages;
  if (Array.isArray(pages) && pages[0] && typeof pages[0] === "object" && "title" in pages[0]) {
    return String((pages[0] as { title?: unknown }).title || item.topic);
  }
  return item.topic;
}

function contentItemDescription(item: ContentItem) {
  const pages = item.generated_json.pages;
  if (Array.isArray(pages) && pages[0] && typeof pages[0] === "object" && "description" in pages[0]) {
    return previewPlainText((pages[0] as { description?: unknown }).description);
  }
  return "";
}

function previewPlainText(value: unknown) {
  return String(value ?? "").replace(/<[^>]+>/g, "").trim();
}

function ContentPreviewBody({ item, generatedJson }: { item?: ContentItem; generatedJson?: Record<string, unknown> }) {
  const source = generatedJson || item?.generated_json || {};
  const pages = source.pages;
  if (!Array.isArray(pages) || !pages[0] || typeof pages[0] !== "object") {
    return <pre className="contentPreviewText modalContentText">{JSON.stringify(source, null, 2)}</pre>;
  }
  const page = pages[0] as { description?: unknown; content?: { blocks?: Array<Record<string, unknown>> } };
  const blocks = page.content?.blocks || [];

  return (
    <div className="contentPreviewBody modalContentText">
      {blocks.map((block, blockIndex) => {
        const data = block.data as Record<string, unknown> | unknown[] | undefined;
        if (block.type === "header" && data && !Array.isArray(data)) {
          const rawLevel = Number(data.level);
          const level = Math.min(4, Math.max(1, Number.isFinite(rawLevel) ? rawLevel : 2)) as 1 | 2 | 3 | 4;
          const HeadingTag = `h${level}` as "h1" | "h2" | "h3" | "h4";
          const headingLabels = {
            1: "H1 · ГЛАВНЫЙ ЗАГОЛОВОК СТАТЬИ",
            2: "H2 · РАЗДЕЛ СТАТЬИ",
            3: "H3 · ПОДРАЗДЕЛ",
            4: "H4 · ВЛОЖЕННЫЙ ПОДРАЗДЕЛ"
          };
          return (
            <section className={`previewHeading previewHeadingH${level}`} key={String(block.id || blockIndex)}>
              <span className="previewBlockLabel">{headingLabels[level]}</span>
              <HeadingTag>{previewPlainText(data.text)}</HeadingTag>
            </section>
          );
        }
        if (block.type === "paragraph" && data && !Array.isArray(data)) {
          return <p className="previewParagraph" key={String(block.id || blockIndex)}>{previewPlainText(data.text)}</p>;
        }
        if (block.type === "list" && data && !Array.isArray(data) && Array.isArray(data.items)) {
          const items = data.items as unknown[];
          const ListTag = data.style === "ordered" ? "ol" : "ul";
          return <ListTag className="previewList" key={String(block.id || blockIndex)}>{items.map((entry, entryIndex) => <li key={entryIndex}>{previewPlainText(entry)}</li>)}</ListTag>;
        }
        if (block.type === "table" && data && !Array.isArray(data) && Array.isArray(data.content)) {
          return (
            <div className="previewTableWrap" key={String(block.id || blockIndex)}>
              <table className="previewTable"><tbody>{(data.content as unknown[]).map((row, rowIndex) => (
                <tr key={rowIndex}>{(Array.isArray(row) ? row : [row]).map((cell, cellIndex) => <td key={cellIndex}>{previewPlainText(cell)}</td>)}</tr>
              ))}</tbody></table>
            </div>
          );
        }
        if (block.type === "faq" && Array.isArray(data)) {
          return (
            <section className="previewFaq" key={String(block.id || blockIndex)}>
              <span className="previewBlockLabel">FAQ</span>
              {data.map((entry, entryIndex) => {
                const faq = entry as { question?: unknown; answer?: unknown };
                return <div key={entryIndex}><strong>{previewPlainText(faq.question)}</strong><p>{previewPlainText(faq.answer)}</p></div>;
              })}
            </section>
          );
        }
        return null;
      })}
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("ru-RU").format(value);
}

function toDateTimeInputValue(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function slugFromText(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/gi, "-")
    .replace(/^-+|-+$/g, "") || "menu-item";
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
