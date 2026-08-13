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
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CheckCircle2,
  Copy,
  CornerDownRight,
  Database,
  Edit3,
  Eye,
  ExternalLink,
  FileText,
  FolderKanban,
  Globe2,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LoaderCircle,
  LogOut,
  Moon,
  Play,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
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
  collect_competitors: boolean;
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
  topic: string;
  slug: string;
  status: string;
  word_count: number;
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
  project_status: "test" | "working" | "not_in_focus" | "duplicate";
  is_test_project: boolean;
  has_menu: boolean;
  cache_synced_at: string | null;
  menu_capabilities_checked_at: string | null;
  header_menu_rendered: boolean | null;
  header_menu_nested: boolean | null;
  footer_menu_rendered: boolean | null;
  footer_menu_nested: boolean | null;
};

type MenuCapabilities = {
  checked_at: string | null;
  header_menu_rendered: boolean | null;
  header_menu_nested: boolean | null;
  footer_menu_rendered: boolean | null;
  footer_menu_nested: boolean | null;
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
  sync_status: "pending" | "synced";
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
  created_at: string;
  updated_at: string;
};

type TaskDetails = {
  task: Task;
  items: ContentItem[];
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
  action: string;
  item_name: string | null;
  method: string;
  destination: string;
  result: "Успешно" | "Ошибка" | "Ожидает ответа";
};

type PublicationCampaign = {
  id: string;
  name: string;
  site_id: string;
  status: "active" | "paused" | "stopped" | "completed" | string;
  interval_minutes: number;
  items_per_run: number;
  start_at: string;
  created_at: string;
  updated_at: string;
};

type ThemeMode = "light" | "dark";
type InputStyle = "balanced" | "classic" | "soft" | "inset" | "underline" | "emerald" | "graphite" | "rounded" | "contrast" | "glass";
type AppView = "dashboard" | "workspace" | "prompts" | "tasks" | "taskArchive" | "content" | "publications" | "providers" | "sites" | "favorites" | "settings";
type WorkspaceTab = "overview" | "topics" | "content" | "publication" | "menu";

type AppRoute = {
  view: AppView;
  workspaceTab: WorkspaceTab;
};

const API_BASE = "/api";
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
  settings: "/settings"
};

const WORKSPACE_TAB_PATHS: Record<WorkspaceTab, string> = {
  overview: "/project-overview",
  topics: "/project-tasks",
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
  const routePath = Object.values(WORKSPACE_TAB_PATHS).find((candidate) => path.startsWith(`${candidate}/`));
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
  return !["workspace", "prompts", "settings"].includes(view);
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
        throw new Error("Нужно войти заново");
      }
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(error.detail || "Request failed");
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
    const [nextDashboard, nextTasks, nextArchivedTasks, nextContent] = nextUser.is_admin
      ? await Promise.all([
        api<Dashboard>("/dashboard"),
        api<Task[]>("/tasks"),
        api<Task[]>("/tasks-archive"),
        api<ContentItem[]>("/content")
      ])
      : [null, [], [], []] as [Dashboard | null, Task[], Task[], ContentItem[]];
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
    if (!currentUser.is_admin && isAdminOnlyView(activeView)) {
      navigateTo("workspace", DEFAULT_WORKSPACE_TAB, true);
      return;
    }
    const projectName = activeView === "workspace" ? workspaceProjectNameFromPath(window.location.pathname) : null;
    const nextPath = pathForRoute(activeView, activeView === "workspace" ? workspaceTab : DEFAULT_WORKSPACE_TAB, projectName);
    if (window.location.pathname !== nextPath) {
      window.history.replaceState(null, "", nextPath);
    }
  }, [activeView, currentUser, navigateTo, workspaceTab]);

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

  const isAdmin = currentUser?.is_admin ?? true;

  return (
    <div className="appShell">
      <aside className="sidebar">
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
              <NavButton href={pathForRoute("content")} icon={<FileText />} label="Контент" active={activeView === "content"} onClick={() => navigateTo("content")} />
              <NavButton href={pathForRoute("publications")} icon={<Send />} label="Публикации" active={activeView === "publications"} onClick={() => navigateTo("publications")} />
              <NavButton href={pathForRoute("providers")} icon={<Bot />} label="API Providers" active={activeView === "providers"} onClick={() => navigateTo("providers")} />
              <NavButton href={pathForRoute("sites")} icon={<Globe2 />} label="Сайты" active={activeView === "sites"} onClick={() => navigateTo("sites")} />
              <NavButton href={pathForRoute("favorites")} icon={<Star className="favoriteNavIcon" fill="currentColor" />} label="Избранное" active={activeView === "favorites"} onClick={() => navigateTo("favorites")} />
            </>
          ) : (
            <>
              <NavButton href={pathForRoute("workspace", DEFAULT_WORKSPACE_TAB)} icon={<FolderKanban />} label="Рабочий экран" active={activeView === "workspace"} onClick={() => navigateTo("workspace", DEFAULT_WORKSPACE_TAB)} />
              <NavButton href={pathForRoute("prompts")} icon={<Edit3 />} label="Промпты" active={activeView === "prompts"} onClick={() => navigateTo("prompts")} />
            </>
          )}
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
            {currentUser ? (
              <div className="userPill">
                <span>{currentUser.is_admin ? "Администратор" : "Пользователь"}</span>
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
        {isAdmin && activeView === "tasks" && <TasksView api={api} sites={sites} providers={providers} tasks={tasks} onChanged={loadAll} />}
        {isAdmin && activeView === "taskArchive" && <TaskArchiveView api={api} tasks={archivedTasks} onChanged={loadAll} />}
        {isAdmin && activeView === "content" && <ContentView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {isAdmin && activeView === "publications" && <PublicationsView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {isAdmin && activeView === "providers" && <ProvidersView api={api} providers={providers} onChanged={loadAll} />}
        {isAdmin && activeView === "sites" && <SitesView api={api} sites={sites} currentUsername={currentUser.username} onChanged={loadAll} />}
        {isAdmin && activeView === "favorites" && <SitesView api={api} sites={sites} currentUsername={currentUser.username} favoritesOnly onChanged={loadAll} />}
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
    { icon: <FileText size={18} />, label: "Контент" },
    { icon: <Send size={18} />, label: "Публикации" },
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
              .map((item) => [item.topic, <StatusBadge status={item.status} />, item.scheduled_at ? formatDate(item.scheduled_at) : "-"])}
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
  const projectLoadRequestRef = React.useRef(0);
  const selectedSite = sites.find((site) => site.id === selectedSiteId) || null;
  const routeProjectName = workspaceProjectNameFromPath(window.location.pathname);
  const pendingSectionsCount = sections.filter((section) => section.sync_status !== "synced").length;
  const selectedProjectMedalStatus = menuCapabilities?.checked_at
    ? menuMedalStatus(menuCapabilities.checked_at, menuCapabilities.header_menu_rendered, menuCapabilities.footer_menu_rendered)
    : selectedSite ? projectMenuMedalStatus(selectedSite) : "unchecked";

  const loadProject = React.useCallback(async () => {
    if (!selectedSiteId) return;
    const requestId = projectLoadRequestRef.current + 1;
    projectLoadRequestRef.current = requestId;
    setWorkspaceError("");
    try {
      const [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextLogs, nextCampaigns, nextMenuCapabilities] = await Promise.all([
        api<SiteOverview>(`/sites/${selectedSiteId}/overview`),
        api<Task[]>(`/sites/${selectedSiteId}/tasks`),
        api<ContentItem[]>(`/sites/${selectedSiteId}/content`),
        api<Section[]>(`/sites/${selectedSiteId}/sections`),
        api<PromptTemplate[]>(`/sites/${selectedSiteId}/prompt-templates`),
        api<PublicationLog[]>(`/sites/${selectedSiteId}/publication-logs`),
        api<PublicationCampaign[]>(`/sites/${selectedSiteId}/publication-campaigns`),
        api<MenuCapabilities>(`/sites/${selectedSiteId}/menu-capabilities`).catch(() => null)
      ]);
      if (requestId !== projectLoadRequestRef.current) return;
      setOverview(nextOverview);
      setSiteTasks(nextTasks);
      setSiteContent(nextContent);
      setSections(nextSections);
      setPromptTemplates(nextPrompts);
      setLogs(nextLogs);
      setCampaigns(nextCampaigns);
      setMenuCapabilities(nextMenuCapabilities);
      setWorkspaceError("");
    } catch (error) {
      if (requestId !== projectLoadRequestRef.current) return;
      setWorkspaceError(error instanceof Error ? error.message : "Не удалось загрузить проект");
    }
  }, [api, selectedSiteId]);

  React.useEffect(() => {
    api<{ site_ids: string[] }>("/me/favorite-sites")
      .then((result) => setFavoriteSiteIds(result.site_ids))
      .catch((error: unknown) => setWorkspaceError(error instanceof Error ? error.message : "Не удалось загрузить избранное"));
  }, [api]);

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
      setWorkspaceError("");
      void loadProject();
    }
  }, [loadProject, selectedSiteId, workspaceSiteStorageKey]);

  async function refreshProject(syncExternal = false) {
    if (syncExternal && selectedSite) {
      await api<ProjectCacheSyncResult>("/sites/cache/sync", {
        method: "POST",
        body: JSON.stringify({ names: [selectedSite.name] })
      });
      const refreshedCapabilities = await api<MenuCapabilities>(`/sites/${selectedSite.id}/menu-capabilities?refresh=true`);
      setMenuCapabilities(refreshedCapabilities);
    }
    await onChanged();
    await loadProject();
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

  return (
    <section className="viewStack">
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
                return {
                  ...projectSearchOption(site),
                  keywords: `${site.cache_canon || ""} ${site.is_test_project ? "тестовый проект" : ""}`,
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
                    <small>Canon</small>
                    <span className="projectCanonValue">
                      <a className="projectCanonLink" href={selectedSite.base_url} target="_blank" rel="noreferrer" title={`Открыть ${selectedSite.cache_canon || selectedSite.base_url}`}>
                        <b>{selectedSite.cache_canon || selectedSite.base_url}</b><ExternalLink size={14} />
                      </a>
                      <button className="projectCanonCopyButton" type="button" onClick={copyCanon} title={canonCopied ? "Скопировано" : "Скопировать canon"} aria-label="Скопировать canon">
                        {canonCopied ? <CheckCircle2 size={14} /> : <Copy size={14} />}
                      </button>
                    </span>
                  </span>
                  <span className="projectTitleCard"><small>Title</small><b title={selectedSite.homepage_title || "Title не указан"}>{selectedSite.homepage_title || "—"}</b></span>
                  <span className="projectMetricCard"><small>Доменов в сетке</small><b>{formatNumber(selectedSite.domains_count)}</b></span>
                  <span className="projectMetricCard"><small>Страниц</small><b>{formatNumber(selectedSite.internal_pages_count)}</b></span>
                  <MenuCapabilityCard label="Header" rendered={menuCapabilities?.header_menu_rendered} nested={menuCapabilities?.header_menu_nested} icon="header" />
                  <MenuCapabilityCard label="Footer" rendered={menuCapabilities?.footer_menu_rendered} nested={menuCapabilities?.footer_menu_nested} icon="footer" />
                </div>
              </>
            ) : null}
          </div>
          <button className="button secondary" type="button" onClick={() => refreshProject(true)} disabled={!selectedSite}><RefreshCcw size={18} /> Обновить проект</button>
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
          <TabButton href={pathForRoute("workspace", "overview", selectedSite?.name)} label="Обзор" active={activeTab === "overview"} onClick={() => onTabChange("overview", selectedSite?.name)} />
          <TabButton href={pathForRoute("workspace", "topics", selectedSite?.name)} label="Задачи" active={activeTab === "topics"} onClick={() => onTabChange("topics", selectedSite?.name)} />
          <TabButton href={pathForRoute("workspace", "content", selectedSite?.name)} label="Контент и публикация" active={activeTab === "content" || activeTab === "publication"} onClick={() => onTabChange("content", selectedSite?.name)} />
          <TabButton href={pathForRoute("workspace", "menu", selectedSite?.name)} label="Меню" active={activeTab === "menu"} onClick={() => onTabChange("menu", selectedSite?.name)} />
        </div>
        {workspaceError ? <div className="notice">{workspaceError}</div> : null}
      </DataPanel>

      {!selectedSite ? (
        <div className="workspaceProjectEmpty">
          <span className="workspaceProjectEmptyIcon"><FolderKanban size={34} /></span>
          <div>
            <h2>Выберите проект</h2>
            <p>Выберите проект в поле выше, чтобы открыть рабочий экран. Последний активный проект сохранится для вашего пользователя.</p>
          </div>
        </div>
      ) : null}

      {selectedSite && activeTab === "overview" && overview ? (
        <ProjectOverviewPanel key={selectedSite.id} overview={overview} content={siteContent} sections={sections} logs={logs} />
      ) : null}
      {selectedSite && activeTab === "topics" ? (
        <TasksView
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
      ) : null}
      {selectedSite && (activeTab === "content" || activeTab === "publication") ? (
        <ProjectPublicationPanel key={`${selectedSite.id}:publication-launch`} mode="launch" api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} onChanged={refreshProject} />
      ) : null}
      {selectedSite && (activeTab === "content" || activeTab === "publication") ? (
        <ProjectContentPanel key={`${selectedSite.id}:content`} api={api} site={selectedSite} content={siteContent} sections={sections} onChanged={refreshProject} />
      ) : null}
      {selectedSite && (activeTab === "content" || activeTab === "publication") ? (
        <ProjectPublicationPanel key={`${selectedSite.id}:publication-details`} mode="details" api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "menu" ? (
        <ProjectMenuPanel api={api} site={selectedSite} sections={sections} menuCapabilities={menuCapabilities} onChanged={refreshProject} />
      ) : null}
    </section>
  );
}

function MenuCapabilityCard({ label, rendered, nested, icon }: { label: string; rendered: boolean | null | undefined; nested: boolean | null | undefined; icon: "header" | "footer" }) {
  const statusText = rendered == null ? "Проверяем" : rendered ? "Меню реализовано" : "Меню не реализовано";
  return (
    <span className={`projectMenuCapability ${rendered === true ? "isReady" : rendered === false ? "isMissing" : "isChecking"}`} title={`${label}: ${statusText}${rendered ? nested ? ". Вложенность поддерживается" : ". Только один уровень" : ""}`}>
      <small>{label}</small>
      <span className="projectMenuCapabilityValue">
        {rendered === true ? <MenuReadyMedal /> : rendered === false ? <MenuReadyMedal tone="red" /> : icon === "header" ? <HeaderMenuIcon /> : <FooterMenuIcon />}
        <b>{statusText}</b>
      </span>
      {rendered ? <em>{nested ? "Есть вложенность" : "Один уровень"}</em> : null}
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
  const [formError, setFormError] = React.useState("");
  const [taskDetails, setTaskDetails] = React.useState<TaskDetails | null>(null);
  const [taskResearch, setTaskResearch] = React.useState<CompetitorResearch[]>([]);
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [detailsError, setDetailsError] = React.useState("");
  const [detailsLoadingId, setDetailsLoadingId] = React.useState("");
  const [researchAction, setResearchAction] = React.useState("");
  const topicCount = topics.split("\n").map((line) => line.trim()).filter(Boolean).length;
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === promptTemplateId) || promptTemplates.find((prompt) => prompt.is_default) || promptTemplates[0];

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
      setPromptTemplateId((promptTemplates.find((prompt) => prompt.is_default) || promptTemplates[0]).id);
    }
  }, [promptTemplateId, promptTemplates]);

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
            Собрать конкурентов перед генерацией
          </label>
          <label className="wide">
            Темы, каждая с новой строки
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
              <Plus size={18} /> {collectCompetitors ? "Создать и перейти к запросам" : "Создать и сгенерировать"}
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
          <strong>{item.topic}</strong>
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
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === selectedId) || promptTemplates[0] || null;
  const [name, setName] = React.useState("");
  const [content, setContent] = React.useState("");
  const [isDefault, setIsDefault] = React.useState(true);
  const [editorError, setEditorError] = React.useState("");
  const [editorSuccess, setEditorSuccess] = React.useState("");
  const [baseContent, setBaseContent] = React.useState("");
  const [baseError, setBaseError] = React.useState("");
  const [baseSuccess, setBaseSuccess] = React.useState("");
  const [newPromptSeed, setNewPromptSeed] = React.useState<{ name: string; content: string } | null>(null);
  const isNewPrompt = selectedId === "__new__";

  React.useEffect(() => {
    setBaseContent(basePrompt?.content || "");
    setBaseError("");
    setBaseSuccess("");
  }, [basePrompt]);

  React.useEffect(() => {
    if (!selectedId && promptTemplates.length) {
      setSelectedId((promptTemplates.find((prompt) => prompt.is_default) || promptTemplates[0]).id);
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
                <span>{prompt.is_default ? "Default для проекта" : formatDate(prompt.updated_at)}</span>
                <span>Используется: {prompt.used_by_projects}</span>
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
                <button className="button secondary" type="button" onClick={createPromptFromSelected}>
                  <Plus size={18} /> Создать на основе
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
    </section>
  );
}

function ProjectContentPanel({ api, site, content, sections, onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[] }) {
  const [selectedItem, setSelectedItem] = React.useState<ContentItem | null>(null);
  const [previewItem, setPreviewItem] = React.useState<ContentItem | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [bulkSectionId, setBulkSectionId] = React.useState("");
  const [bulkBusy, setBulkBusy] = React.useState(false);
  const [createMenuVisible, setCreateMenuVisible] = React.useState(false);
  const [menuName, setMenuName] = React.useState("");
  const [menuExternalId, setMenuExternalId] = React.useState("");
  const [menuPath, setMenuPath] = React.useState("");
  const [menuType, setMenuType] = React.useState<"header" | "footer">("header");
  const [jsonDraft, setJsonDraft] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [editorError, setEditorError] = React.useState("");
  const selectableIds = React.useMemo(() => content.filter((item) => !isPublicationLocked(item)).map((item) => item.id), [content]);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const selectedItems = content.filter((item) => selectedIds.includes(item.id));
  const bulkApproveItems = selectedItems.filter((item) => Boolean(item.section_id) && canApproveContent(item));
  const bulkPublishItems = selectedItems.filter((item) => Boolean(item.section_id) && ["generated", "rejected", "approved"].includes(item.status));

  React.useEffect(() => {
    setSelectedIds((current) => current.filter((id) => selectableIds.includes(id)));
  }, [selectableIds]);

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? [] : selectableIds);
  }

  async function applyBulkSection() {
    if (!selectedIds.length || !bulkSectionId) {
      setEditorError(!selectedIds.length ? "Выберите хотя бы один текст." : "Выберите пункт меню.");
      return;
    }
    setEditorError("");
    setBulkBusy(true);
    try {
      const results = await Promise.allSettled(selectedIds.map((id) => api(`/content/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ section_id: bulkSectionId })
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
      if (failed) setEditorError(`Не удалось согласовать ${failed} текстов.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось согласовать выбранные тексты.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function publishSelected() {
    if (!bulkPublishItems.length) return;
    setEditorError("");
    setBulkBusy(true);
    try {
      const results = await Promise.allSettled(bulkPublishItems.map((item) => api(`/content/${item.id}/publish-now`, { method: "POST" })));
      const failed = results.filter((result) => result.status === "rejected").length;
      setSelectedIds([]);
      await onChanged();
      if (failed) setEditorError(`Не удалось отправить в публикацию ${failed} текстов.`);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось отправить выбранные тексты в публикацию.");
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
    await api(`/content/${selectedItem.id}`, {
      method: "PATCH",
      body: JSON.stringify({ generated_json: parsed, section_id: sectionId || null })
    });
    setSelectedItem(null);
    await onChanged();
  }

  async function approve(item: ContentItem) {
    setEditorError("");
    if (!item.section_id) {
      setEditorError("Перед approve выберите пункт меню.");
      openEditor(item);
      return;
    }
    await api(`/content/${item.id}/approve`, { method: "POST" });
    await onChanged();
  }

  return (
    <section className="viewStack">
      <DataPanel title="Контент проекта">
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
              options={[{ value: "", label: "Выберите пункт меню" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
              searchPlaceholder="Найти пункт меню"
              disabled={bulkBusy}
            />
          </div>
          <button className="button compact primary" type="button" onClick={applyBulkSection} disabled={!selectedIds.length || !bulkSectionId || bulkBusy}>
            <CheckCircle2 size={15} /> {bulkBusy ? "Сохраняю" : `Назначить выбранным (${selectedIds.length})`}
          </button>
          <button className="button compact approve" type="button" onClick={approveSelected} disabled={!bulkApproveItems.length || bulkBusy} title={selectedIds.length && !bulkApproveItems.length ? "Сначала назначьте пункт меню текстам со статусом generated" : undefined}>
            <CheckCircle2 size={15} /> Согласовать ({bulkApproveItems.length})
          </button>
          <button className="button compact primary" type="button" onClick={publishSelected} disabled={!bulkPublishItems.length || bulkBusy} title={selectedIds.length && !bulkPublishItems.length ? "Сначала назначьте пункт меню" : "Согласовать и поставить выбранные тексты в очередь публикации"}>
            <Send size={15} /> В публикацию ({bulkPublishItems.length})
          </button>
          <button className="button compact secondary createMenuButton" type="button" onClick={() => setCreateMenuVisible((current) => !current)} disabled={bulkBusy}>
            <Plus size={15} /> Создать пункт меню
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
              <button className="button compact primary" type="submit" disabled={bulkBusy}><Plus size={15} /> Создать</button>
            </div>
          </form>
        ) : null}
        <ResponsiveTable
          columns={["Выбор", "Тема", "Меню", "Слова", "Статус", "Опубликовано", "Действия"]}
          rows={content.map((item) => [
            <input
              className="rowCheckbox"
              type="checkbox"
              checked={selectedIds.includes(item.id)}
              onChange={() => toggleSelected(item.id)}
              disabled={isPublicationLocked(item) || bulkBusy}
              aria-label={`Выбрать ${item.topic}`}
              title={isPublicationLocked(item) ? "Пункт меню опубликованного или запланированного текста изменять нельзя" : undefined}
            />,
            <TopicMetaCell item={item} />,
            sectionLabel(item.section_id, sections),
            item.word_count,
            <StatusBadge status={item.status} />,
            item.published_url ? <a href={item.published_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> URL</a> : item.published_at ? formatDate(item.published_at) : "-",
            <div className="userActions">
              <button className="button compact" type="button" onClick={() => openEditor(item)} disabled={isPublicationLocked(item)} title="Открыть и редактировать JSON payload"><Database size={15} /> JSON</button>
              <button className="button compact" type="button" onClick={() => setPreviewItem(item)} title="Посмотреть готовый текст, Title и Meta Description"><Eye size={15} /> Текст + Meta</button>
              <button className="button compact approve" type="button" onClick={() => approve(item)} disabled={!canApproveContent(item)}>Approve</button>
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
                options={[{ value: "", label: "Не выбран" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
                searchPlaceholder="Найти пункт меню"
              />
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

function ProjectPublicationPanel({ api, site, content, sections, campaigns, mode, onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[]; campaigns: PublicationCampaign[]; mode: "launch" | "details" }) {
  const [launchExpanded, setLaunchExpanded] = React.useState(false);
  const [name, setName] = React.useState("Daily publication");
  const [itemsPerDay, setItemsPerDay] = React.useState(1);
  const [sectionId, setSectionId] = React.useState("");
  const [startAt, setStartAt] = React.useState(() => toDateTimeInputValue(new Date()));
  const [formError, setFormError] = React.useState("");
  const approved = content.filter((item) => item.status === "approved" && (!sectionId || item.section_id === sectionId));

  async function createCampaign(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!approved.length) {
      setFormError("Нет approved-текстов для выбранного фильтра.");
      return;
    }
    try {
      await api(`/sites/${site.id}/publication-campaigns`, {
        method: "POST",
        body: JSON.stringify({
          name,
          content_item_ids: approved.map((item) => item.id),
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

  return (
    <section className="viewStack">
      {mode === "launch" ? <section className={`dataPanel publicationLaunchPanel ${launchExpanded ? "expanded" : ""}`}>
        <button className="publicationLaunchToggle" type="button" onClick={() => setLaunchExpanded((current) => !current)} aria-expanded={launchExpanded}>
          <span className="publicationLaunchIcon"><Send size={20} /></span>
          <span className="publicationLaunchText">
            <strong>Запустить публикацию</strong>
            <small>{launchExpanded ? "Нажмите, чтобы свернуть настройки" : `Нажмите, чтобы настроить кампанию · готово текстов: ${approved.length}`}</small>
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
              Пункт меню
              <SearchableSelect
                value={sectionId}
                onChange={setSectionId}
                options={[{ value: "", label: "Все approved" }, ...sections.map((section) => ({ value: section.id, label: `${section.name} · ${section.path}` }))]}
                searchPlaceholder="Найти пункт меню"
              />
            </label>
            <label>
              Текстов в день
              <input type="number" value={itemsPerDay} onChange={(event) => setItemsPerDay(Number(event.target.value))} min={1} max={24} />
            </label>
            <label>
              Старт
              <input type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} required />
            </label>
            {formError ? <span className="formError wide">{formError}</span> : null}
            <div className="formActions wide">
              <button className="button primary" type="submit" disabled={!approved.length}><Play size={18} /> Запланировать ({approved.length})</button>
            </div>
          </form>
        ) : null}
      </section> : null}
      {mode === "details" ? <DataPanel title="Кампании проекта">
        <ResponsiveTable
          columns={["Кампания", "Старт", "Интервал", "Статус", "Действия"]}
          rows={campaigns.map((campaign) => [
            campaign.name,
            formatDate(campaign.start_at),
            `${campaign.interval_minutes} мин.`,
            <StatusBadge status={campaign.status} />,
            <div className="userActions">
              {campaign.status === "active" ? (
                <button className="button compact" type="button" onClick={() => changeCampaign(campaign, "pause")}>Pause</button>
              ) : null}
              {campaign.status === "paused" ? (
                <button className="button compact" type="button" onClick={() => changeCampaign(campaign, "resume")}><Play size={15} /> Resume</button>
              ) : null}
              {["active", "paused"].includes(campaign.status) ? (
                <button className="button compact danger" type="button" onClick={() => changeCampaign(campaign, "stop")}><X size={15} /> Stop</button>
              ) : null}
            </div>
          ])}
        />
      </DataPanel> : null}
      {mode === "details" ? <DataPanel title="Процесс публикации">
        <ResponsiveTable
          columns={["Тема", "Меню", "Slug"]}
          rows={approved.map((item) => [<TopicMetaCell item={item} />, sectionLabel(item.section_id, sections), item.slug])}
        />
      </DataPanel> : null}
    </section>
  );
}

function ProjectMenuPanel({ api, site, sections, menuCapabilities, onChanged }: ViewProps & { site: Site; sections: Section[]; menuCapabilities: MenuCapabilities | null }) {
  const [name, setName] = React.useState("");
  const [path, setPath] = React.useState("");
  const [menuType, setMenuType] = React.useState<"header" | "footer">("header");
  const [parentId, setParentId] = React.useState("");
  const [parentName, setParentName] = React.useState("");
  const [parentTreeKey, setParentTreeKey] = React.useState("");
  const [formError, setFormError] = React.useState("");
  const [addExpanded, setAddExpanded] = React.useState(false);
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
  const [updatedAt, setUpdatedAt] = React.useState<string | null>(null);
  const [editingSectionId, setEditingSectionId] = React.useState<string | null>(null);
  const [editingSectionName, setEditingSectionName] = React.useState("");
  const [editingSectionPath, setEditingSectionPath] = React.useState("");
  const [savingSectionEdit, setSavingSectionEdit] = React.useState(false);
  const [deletingSectionId, setDeletingSectionId] = React.useState<string | null>(null);
  const [adoptingParentKey, setAdoptingParentKey] = React.useState<string | null>(null);
  const [temporaryParentId, setTemporaryParentId] = React.useState<string | null>(null);
  const [releasingTemporaryParent, setReleasingTemporaryParent] = React.useState(false);
  const cachedHeader = Array.isArray(site.default_menu.header) ? site.default_menu.header : [];
  const cachedFooter = Array.isArray(site.default_menu.footer) ? site.default_menu.footer : [];
  const menuLibrary = React.useMemo(() => {
    const itemsById = new Map(getMenuLibrary(site.cache_language).map((item) => [item.external_id, item]));
    for (const item of Array.isArray(site.menu_library) ? site.menu_library : []) itemsById.set(item.external_id, item);
    return Array.from(itemsById.values());
  }, [site.cache_language, site.menu_library]);
  const existingSectionIds = React.useMemo(() => new Set(sections.map((section) => section.external_id)), [sections]);
  const persistedSections = React.useMemo(() => sections.filter((section) => !section.is_temporary_parent), [sections]);
  const pendingSections = React.useMemo(() => sections.filter((section) => section.sync_status !== "synced"), [sections]);
  const latestPendingChange = React.useMemo(() => pendingSections.reduce<string | null>((latest, section) => {
    if (!latest || new Date(section.updated_at).getTime() > new Date(latest).getTime()) return section.updated_at;
    return latest;
  }, null), [pendingSections]);
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
    setUpdatedAt(null);
  }, [site.id]);

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
              path: item.path || `/${item.externalId}/`,
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
            {menuLibrary.map((item) => <option value={item.name} label={`* ${item.russian_name} · ${item.path}`} key={item.external_id} />)}
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
      <DataPanel title="Структура меню проекта">
        <div className={`projectMenuSyncState ${pendingSections.length ? "isPending" : "isSynced"}`}>
          {pendingSections.length ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
          <div>
            <strong>{pendingSections.length ? `Не синхронизировано изменений: ${pendingSections.length}` : "Данные синхронизированы"}</strong>
            <span>Последняя синхронизация с проектом: {site.cache_synced_at ? formatDate(site.cache_synced_at) : "ещё не выполнялась"}</span>
            {latestPendingChange ? <small>Последнее изменение в нашей системе: {formatDate(latestPendingChange)}</small> : null}
          </div>
        </div>
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
          <SiteMenuPreviewSection key={`${site.id}:header`} title="Меню Header" icon={<HeaderMenuIcon />} items={cachedHeader} sections={sections.filter((section) => section.menu_type === "header")} adoptingParentKey={adoptingParentKey} activeParentTreeKey={inlineMenuType === "header" ? parentTreeKey : ""} onAddChild={(item, section, treeKey) => openChildForm("header", item, section, treeKey)} action={<button className="siteMenuInlineAddButton" type="button" onClick={() => openInlineForm("header")}><Plus size={15} /> Добавить пункт в Header</button>}>
            {inlineMenuType === "header" ? <form className="siteMenuInlineForm" onSubmit={(event) => createSection(event, "header")}>{menuFields("header")}{formError ? <span className="formError">{formError}</span> : null}</form> : null}
          </SiteMenuPreviewSection>
          <SiteMenuPreviewSection key={`${site.id}:footer`} title="Меню Footer" icon={<FooterMenuIcon />} items={cachedFooter} sections={sections.filter((section) => section.menu_type === "footer")} adoptingParentKey={adoptingParentKey} activeParentTreeKey={inlineMenuType === "footer" ? parentTreeKey : ""} onAddChild={(item, section, treeKey) => openChildForm("footer", item, section, treeKey)} action={<button className="siteMenuInlineAddButton" type="button" onClick={() => openInlineForm("footer")}><Plus size={15} /> Добавить пункт в Footer</button>}>
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
              section.sync_status === "synced" ? <span className="syncedBadge">Синхронизировано</span> : <span className="pendingSyncBadge">Не синхронизировано</span>,
              editing ? <div className="menuSectionEditActions"><button className="button compact secondary" type="button" onClick={cancelSectionEdit} disabled={savingSectionEdit}>Отменить</button><button className="button compact primary" type="button" onClick={() => saveSectionEdit(section)} disabled={savingSectionEdit}>Сохранить</button></div> : <div className="menuSectionEditActions"><button className="button compact secondary" type="button" onClick={() => startSectionEdit(section)} disabled={deletingSectionId === section.id}><Edit3 size={14} /> Изменить</button><button className="button compact danger" type="button" onClick={() => deleteSection(section)} disabled={deletingSectionId === section.id}><Trash2 size={14} /> {deletingSectionId === section.id ? "Удаляем" : "Удалить"}</button></div>
            ];
          })}
        /> : null}
      </DataPanel>
      <DataPanel
        title={`Библиотека пунктов меню · ${menuLibrary.length}`}
        actions={<button className="button secondary compact" type="button" onClick={() => setLibraryFormExpanded((current) => !current)}><Plus size={15} /> Новый пункт</button>}
      >
          {libraryFormExpanded ? (
            <form className="menuLibraryCreateForm" onSubmit={addLibraryItem}>
              <label>Название<input value={libraryName} onChange={(event) => setLibraryName(event.target.value)} placeholder="Введите название" required /></label>
              <label>URL<input value={libraryPath} onChange={(event) => setLibraryPath(event.target.value)} placeholder="new-section" required /></label>
              <button className="button primary compact" type="submit" disabled={savingLibraryItem}><Plus size={15} /> {savingLibraryItem ? "Сохраняем" : "Добавить в библиотеку"}</button>
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
  const [payloadMode, setPayloadMode] = React.useState("site_default");
  const [shortcode, setShortcode] = React.useState("");
  const taskCheckboxPreferences = React.useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("task_create_checkbox_preferences") || "{}") as Partial<Record<"includeToc" | "includeFaq" | "collectCompetitors", boolean>>;
    } catch {
      return {};
    }
  }, []);
  const [includeToc, setIncludeToc] = React.useState(taskCheckboxPreferences.includeToc ?? true);
  const [includeFaq, setIncludeFaq] = React.useState(taskCheckboxPreferences.includeFaq ?? true);
  const [collectCompetitors, setCollectCompetitors] = React.useState(taskCheckboxPreferences.collectCompetitors ?? false);
  const [createFormExpanded, setCreateFormExpanded] = React.useState(false);
  const [creatingTaskAction, setCreatingTaskAction] = React.useState<"draft" | "start" | "">("");
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
  const createPanelRef = React.useRef<HTMLElement>(null);
  const hasResearchInProgress = expandedResearch.some((entry) => ACTIVE_RESEARCH_STATUSES.includes(entry.status));
  const hasGenerationInProgress = (expandedDetails?.items || []).some((item) => ACTIVE_GENERATION_STATUSES.includes(item.status));
  const cleanTopics = topics.split("\n").map((line) => line.trim()).filter(Boolean);
  const selectedSite = sites.find((site) => site.id === siteId);
  const automaticTaskTitle = selectedSite
    ? `${selectedSite.name} · ${cleanTopics.length} тем · ${language.toUpperCase()}-${geo.toUpperCase()}`
    : "Выберите проект — название сформируется автоматически";
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === promptTemplateId)
    || promptTemplates.find((prompt) => prompt.is_default)
    || promptTemplates[0];

  React.useEffect(() => {
    if (fixedSite && siteId !== fixedSite.id) {
      setSiteId(fixedSite.id);
    }
  }, [fixedSite, siteId]);

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
      setPromptTemplateId((promptTemplates.find((prompt) => prompt.is_default) || promptTemplates[0]).id);
    }
  }, [promptTemplateId, promptTemplates]);

  React.useEffect(() => {
    const taskId = sessionStorage.getItem("workspace_open_task_id");
    if (!taskId || !tasks.some((task) => task.id === taskId)) return;
    sessionStorage.removeItem("workspace_open_task_id");
    void loadTaskDetails(taskId);
  }, [fixedSite?.id, tasks]);

  React.useEffect(() => {
    localStorage.setItem("task_create_checkbox_preferences", JSON.stringify({ includeToc, includeFaq, collectCompetitors }));
  }, [includeToc, includeFaq, collectCompetitors]);

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
      payload_mode: payloadMode,
      target_words: targetWords || null,
      prompt_template_name: selectedPrompt?.name || null,
      prompt_template: selectedPrompt?.content || null,
      shortcode: shortcode.trim() || null,
      include_toc: includeToc,
      include_faq: includeFaq,
      collect_competitors: collectCompetitors,
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
      setShortcode("");
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
        setTaskError(`Не удалось согласовать часть текстов: ${failed}. Проверьте, выбран ли пункт меню.`);
      }
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось согласовать выбранные тексты.");
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
    if (createFormExpanded) {
      setCreateFormExpanded(false);
      return;
    }
    setCreateFormExpanded(true);
    window.requestAnimationFrame(() => {
      createPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <section className="viewStack">
      <section ref={createPanelRef} className={`dataPanel createTaskPanel ${createFormExpanded ? "expanded" : ""}`}>
        <button
          className="createTaskToggle"
          type="button"
          aria-expanded={createFormExpanded}
          aria-controls="create-generation-task-form"
          onClick={toggleCreateForm}
        >
          <span className="createTaskToggleIcon"><Plus size={20} /></span>
          <span className="createTaskToggleText">
            <strong>Создать задачу генерации</strong>
            <small>{createFormExpanded ? "Нажмите, чтобы свернуть рабочую область" : "Нажмите, чтобы развернуть рабочую область и создать задачу генерации контента по темам"}</small>
          </span>
          {createFormExpanded ? <ChevronDown size={22} /> : <ChevronRight size={22} />}
        </button>
        {createFormExpanded ? <form id="create-generation-task-form" className="formGrid createTaskForm" onSubmit={createTask}>
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
          <label>
            Формат payload
            <select value={payloadMode} onChange={(event) => setPayloadMode(event.target.value)}>
              <option value="site_default">По настройкам сайта</option>
              <option value="simple_page">Simple: menu + pages</option>
              <option value="full_site">Full: menu + pages + casinos</option>
            </select>
          </label>
          <label>
            Shortcode, если нужен
            <input value={shortcode} onChange={(event) => setShortcode(event.target.value)} placeholder="showcase-redesign" />
          </label>
          <label className="checkboxRow">
            <input type="checkbox" checked={includeToc} onChange={(event) => setIncludeToc(event.target.checked)} />
            Добавить содержание
          </label>
          <label className="checkboxRow">
            <input type="checkbox" checked={includeFaq} onChange={(event) => setIncludeFaq(event.target.checked)} />
            Создавать FAQ
          </label>
          <label className="checkboxRow wide">
            <input type="checkbox" checked={collectCompetitors} onChange={(event) => setCollectCompetitors(event.target.checked)} />
            Собрать конкурентов перед генерацией
          </label>
          <label className="wide">
            Темы, каждая с новой строки
            <textarea value={topics} onChange={(event) => setTopics(event.target.value)} required rows={8} placeholder="best online casinos in Germany" />
            <span className="fieldHint">Тем в задаче: {cleanTopics.length}</span>
          </label>
          <div className="formActions wide">
            <button className="button secondary" type="submit" name="taskAction" value="draft" disabled={Boolean(creatingTaskAction)}>
              <FileText size={18} /> {creatingTaskAction === "draft" ? "Сохраняем" : "Сохранить как черновик"}
            </button>
            <button className="button primary" type="submit" name="taskAction" value="start" disabled={Boolean(creatingTaskAction)}>
              <Play size={18} /> {creatingTaskAction === "start" ? "Запускаем" : "Запустить"}
            </button>
          </div>
        </form> : null}
      </section>
      <DataPanel title="Все задачи">
        <AdminTasksAccordion
          tasks={tasks}
          sections={sections}
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
          onBulkApprove={bulkApproveTaskContent}
          onBulkRegenerateQueries={bulkRegenerateCompetitorQueries}
          onBulkCollectCompetitors={bulkCollectTaskCompetitors}
          onBulkRegenerate={bulkRegenerateTaskContent}
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
  onBulkApprove,
  onBulkRegenerateQueries,
  onBulkCollectCompetitors,
  onBulkRegenerate,
  onBulkDelete,
  onShowPrompt
}: {
  tasks: Task[];
  sections: Section[];
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
  onBulkApprove: (items: ContentItem[]) => Promise<void>;
  onBulkRegenerateQueries: (items: ContentItem[]) => Promise<void>;
  onBulkCollectCompetitors: (items: ContentItem[]) => Promise<void>;
  onBulkRegenerate: (items: ContentItem[]) => Promise<void>;
  onBulkDelete: (items: ContentItem[]) => Promise<void>;
  onShowPrompt: (task: Task) => void;
}) {
  const expandedTask = expandedDetails?.task;
  const expandedItems = React.useMemo(() => expandedDetails?.items || [], [expandedDetails?.items]);
  const expandedItemIds = React.useMemo(() => expandedItems.map((item) => item.id), [expandedItems]);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [copyState, setCopyState] = React.useState("");
  const selectedItems = expandedItems.filter((item) => selectedIds.includes(item.id));
  const allSelected = expandedItemIds.length > 0 && expandedItemIds.every((id) => selectedIds.includes(id));
  const bulkApproveItems = selectedItems.filter(canApproveContent);
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
  }, [expandedTaskId]);

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
                  <td data-label="Промпт"><PromptBadge name={task.prompt_template_name} /></td>
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
                            <strong>Темы задачи</strong>
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
                          <div className="accordionSummary">
                            <InfoMetric label="Название темы/задачи" value={expandedTask.title} />
                            <TaskQueriesMetric total={totalQueries} groups={taskQueryGroups} busy={actionId === "bulk:regenerate-queries"} onGenerate={handleGenerateQueries} />
                            <InfoMetric label="Дата загрузки темы" value={formatDate(expandedTask.created_at)} />
                            <InfoMetric label="Дата генерации" value={latestGeneration ? formatDate(latestGeneration) : "-"} />
                            <div className="infoMetric competitorRequestMetric">
                              <span>Конкуренты для генерации</span>
                              <strong>{competitorBriefs ? `${competitorBriefs}/${expandedItems.length} brief` : "Не запрашивались"}</strong>
                              <button className="button compact" type="button" onClick={handleRequestCompetitors} disabled={!competitorRequestItems.length || actionId === "bulk:collect-competitors"}>
                                <Globe2 size={15} /> {actionId === "bulk:collect-competitors" ? "Запрашиваю конкурентов" : competitorRequestItems.length ? `Запросить конкурентов (${competitorRequestItems.length})` : "Конкуренты собраны"}
                              </button>
                            </div>
                            <InfoMetric label="Загрузил" value={expandedTask.created_by_username || "-"} />
                            <InfoMetric label="Промпт" value={expandedTask.prompt_template_name || "Не указан"} />
                            <button className="button compact" type="button" onClick={() => onShowPrompt(expandedTask)}>
                              <Eye size={15} /> Посмотреть промпт
                            </button>
                          </div>
                          <div className="bulkToolbar">
                            <button className="button compact" type="button" onClick={copyTopicNames} disabled={!expandedItems.length}>
                              <Copy size={15} /> Скопировать все названия тем
                            </button>
                            {copyState ? <span className="fieldHint">{copyState}</span> : null}
                            <label className="checkboxRow bulkSelectAll">
                              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} disabled={!expandedItems.length || bulkBusy} />
                              Выбрать все
                            </label>
                            <span className="fieldHint">Выбрано: {selectedIds.length}</span>
                            <button className="button compact approve" type="button" onClick={handleBulkApprove} disabled={!bulkApproveItems.length || actionId === "bulk:approve"}>
                              <CheckCircle2 size={15} /> {actionId === "bulk:approve" ? "Согласовываю" : `Approve выбранные (${bulkApproveItems.length})`}
                            </button>
                            <button className="button compact" type="button" onClick={handleBulkCollectCompetitors} disabled={!bulkCollectItems.length || actionId === "bulk:collect-competitors"}>
                              <Globe2 size={15} /> {actionId === "bulk:collect-competitors" ? "Сбор конкурентов" : `Собрать конкурентов (${bulkCollectItems.length})`}
                            </button>
                            <button className="button compact" type="button" onClick={handleBulkRegenerate} disabled={!bulkRegenerateItems.length || actionId === "bulk:generate"}>
                              <Play size={15} /> {actionId === "bulk:generate" ? "Генерация" : `Сгенерировать выбранные (${bulkRegenerateItems.length})`}
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
  );
}

function InfoMetric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="infoMetric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TaskQueriesMetric({ total, groups, busy, onGenerate }: { total: number; groups: Array<{ topic: string; queries: CompetitorQuery[] }>; busy: boolean; onGenerate: () => void }) {
  return (
    <div className="infoMetric taskQueriesMetric" tabIndex={0} aria-label="Показать запросы для сбора конкурентов">
      <span>Запросы для сбора конкурентов</span>
      <strong>{total}</strong>
      <button className="button compact" type="button" onClick={onGenerate} disabled={busy}>
        <RefreshCcw size={15} /> {busy ? "Генерирую запросы" : "Сгенерировать запросы"}
      </button>
      <div className="queryTooltip taskQueriesTooltip" role="tooltip">
        <strong>Запросы по темам задачи</strong>
        {groups.length ? groups.map((group) => (
          <div className="taskQueryGroup" key={group.topic}>
            <b>{group.topic}</b>
            <ol>
              {group.queries.map((query) => (
                <li key={query.id}>
                  {query.query}
                  <small>{query.status === "serp_collected" ? `Сбор выполнен · результатов: ${query.result_count}` : query.status === "collecting" ? "Сбор выполняется" : "Запрос подготовлен"}</small>
                </li>
              ))}
            </ol>
          </div>
        )) : <span>Запросы пока не подготовлены.</span>}
      </div>
    </div>
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

function PublicationsView({ api, sites, content, onChanged }: ViewProps & { sites: Site[]; content: ContentItem[] }) {
  const [name, setName] = React.useState("Daily publication");
  const [siteId, setSiteId] = React.useState("");
  const [interval, setIntervalValue] = React.useState(1440);
  const [campaigns, setCampaigns] = React.useState<PublicationCampaign[]>([]);
  const [formError, setFormError] = React.useState("");
  const approved = content.filter((item) => item.status === "approved" && (!siteId || item.site_id === siteId));

  const loadCampaigns = React.useCallback(async () => {
    setCampaigns(await api<PublicationCampaign[]>("/publication-campaigns"));
  }, [api]);

  React.useEffect(() => {
    loadCampaigns().catch((error: unknown) => setFormError(error instanceof Error ? error.message : "Не удалось загрузить кампании."));
  }, [loadCampaigns]);

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
      await Promise.all([onChanged(), loadCampaigns()]);
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

  return (
    <section className="viewStack">
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
              options={[{ value: "", label: "Выберите сайт" }, ...sites.map(projectSearchOption)]}
              searchPlaceholder="Найти сайт"
            />
          </label>
          <label>
            Интервал, минут
            <input type="number" value={interval} onChange={(event) => setIntervalValue(Number(event.target.value))} min={5} />
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
            `${campaign.interval_minutes} мин.`,
            <StatusBadge status={campaign.status} />,
            <div className="userActions">
              {campaign.status === "active" ? <button className="button compact" type="button" onClick={() => changeCampaign(campaign, "pause")}>Pause</button> : null}
              {campaign.status === "paused" ? <button className="button compact" type="button" onClick={() => changeCampaign(campaign, "resume")}><Play size={15} /> Resume</button> : null}
              {["active", "paused"].includes(campaign.status) ? <button className="button compact danger" type="button" onClick={() => changeCampaign(campaign, "stop")}><X size={15} /> Stop</button> : null}
            </div>
          ])}
        />
      </DataPanel>
      <DataPanel title="Готово к публикации">
        <ResponsiveTable columns={["Тема", "Статус", "Slug"]} rows={approved.map((item) => [<TopicMetaCell item={item} />, <StatusBadge status={item.status} />, item.slug])} />
      </DataPanel>
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
          <div className="formActions wide"><button className="button primary" type="submit"><Plus size={18} /> Сохранить provider</button></div>
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
  canon: "Canon",
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
  return {
    value: site.id,
    label: site.name,
    leading: flag ? <span className="projectSelectFlag" aria-hidden="true">{flag}</span> : undefined,
    indicator: <ProjectVerificationMedal status={projectMenuMedalStatus(site)} />,
    keywords: `${site.cache_canon || ""} ${site.base_url}`
  };
}

function LocaleCode({ value }: { value: string | null }) {
  if (!value) return <>—</>;
  const flag = localeFlag(localeCountryCode(value));
  return <span className="siteLocaleCode">{flag ? <span aria-hidden="true">{flag}</span> : null}<b>{value.replace(/_/g, "-")}</b></span>;
}

function SitesView({ api, sites, currentUsername, favoritesOnly = false, onChanged }: ViewProps & { sites: Site[]; currentUsername: string; favoritesOnly?: boolean }) {
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
      };
    } catch {
      return {};
    }
  }, [preferencesKey]);
  const [managedSites, setManagedSites] = React.useState<Site[]>(sites);
  const [cacheResult, setCacheResult] = React.useState<ProjectCacheSyncResult | null>(null);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [syncing, setSyncing] = React.useState(false);
  const [syncError, setSyncError] = React.useState("");
  const [selectedProjectNames, setSelectedProjectNames] = React.useState<string[]>([]);
  const [syncMessage, setSyncMessage] = React.useState("");
  const [summaryFilter, setSummaryFilter] = React.useState<SiteSummaryFilter | null>(() => storedPreferences.summaryFilter || null);
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
  const visibleColumnOrder = columnOrder.filter((column) => !hiddenColumns.includes(column));

  React.useEffect(() => {
    localStorage.setItem(preferencesKey, JSON.stringify({ statusFilters, menuTypeFilters, siteSort, columnOrder, hiddenColumns, rowsPerPage, summaryFilter }));
  }, [columnOrder, hiddenColumns, menuTypeFilters, preferencesKey, rowsPerPage, siteSort, statusFilters, summaryFilter]);

  React.useEffect(() => {
    api<{ site_ids: string[] }>("/me/favorite-sites")
      .then((result) => setFavoriteSiteIds(result.site_ids))
      .catch((error: unknown) => setSyncError(error instanceof Error ? error.message : "Не удалось загрузить избранное"));
  }, [api]);

  const loadManagedSites = React.useCallback(async () => {
    setManagedSites(await api<Site[]>("/sites/cache/projects"));
  }, [api]);

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
    && statusFilters.includes(row.projectStatus)
    && menuTypeFilters.includes(row.menuTypeKey)
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
  }, [menuTypeFilters, rowsPerPage, searchQuery, siteSort, statusFilters, summaryFilter]);

  function toggleSummaryFilter(filter: SiteSummaryFilter) {
    setSummaryFilter((current) => current === filter ? null : filter);
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
      <DataPanel title="Панель управления сайтами">
        <div className="siteCacheToolbar">
          <div className="siteCacheStats">
            <button className={summaryFilter === "projects" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("projects")} aria-pressed={summaryFilter === "projects"}><span>Проекты</span><strong>{formatNumber(cacheResult?.cache_count || managedSites.filter((site) => site.external_project_id).length)}</strong></button>
            <button className={summaryFilter === "working" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("working")} aria-pressed={summaryFilter === "working"}><span>Рабочие</span><strong>{formatNumber(workingCount)}</strong></button>
            <button className={summaryFilter === "menu" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("menu")} aria-pressed={summaryFilter === "menu"}><span>С меню</span><strong>{formatNumber(menuCount)}</strong></button>
            <button className={summaryFilter === "test" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("test")} aria-pressed={summaryFilter === "test"}><span>Тестовые</span><strong>{formatNumber(managedSites.filter((site) => site.project_status === "test").length)}</strong></button>
            <button className={summaryFilter === "duplicate" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("duplicate")} aria-pressed={summaryFilter === "duplicate"}><span>Дубликаты</span><strong>{formatNumber(duplicateCount)}</strong></button>
            <button className={summaryFilter === "all" ? "active" : ""} type="button" onClick={() => toggleSummaryFilter("all")} aria-pressed={summaryFilter === "all"}><span>Всего сайтов</span><strong>{formatNumber(managedSites.length)}</strong></button>
          </div>
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
        </div>
        <div className="siteCacheUpdatedAt">
          <CalendarClock size={17} />
          <span>Последнее обновление</span>
          <strong>{latestCacheSync ? formatDate(latestCacheSync) : "Данные еще не обновлялись"}</strong>
        </div>
        {syncMessage ? <div className="siteCacheResult">{syncMessage}</div> : null}
        {syncError ? <div className="formError siteCacheError">{syncError}</div> : null}
      </DataPanel>
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
        {summaryFilter || statusFilterActive || menuTypeFilterActive ? (
          <div className="siteActiveFilters" role="status">
            <strong><ListChecks size={16} /> Включены фильтры</strong>
            {summaryFilter ? (
              <button type="button" onClick={() => setSummaryFilter(null)}>
                Панель: {{ projects: "Проекты", working: "Рабочие", menu: "С меню", test: "Тестовые", duplicate: "Дубликаты", all: "Все сайты" }[summaryFilter]}
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
            <button className="siteResetFilters" type="button" onClick={() => { setSummaryFilter(null); setStatusFilters(allStatusFilters); setMenuTypeFilters(allMenuTypeFilters); }}>Сбросить все</button>
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
                    <strong>{row.name}</strong>
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
              canon: row.canon,
              language: <LocaleCode value={row.language} />,
              status: (
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
    const externalId = [value.external_id, value.externalId, value.id].find((entry) => typeof entry === "string" && entry.trim());
    const resolvedTitle = typeof itemTitle === "string" ? itemTitle : `Пункт ${index + 1}`;
    return {
      title: resolvedTitle,
      path: typeof itemPath === "string" ? itemPath : "",
      externalId: typeof externalId === "string" ? externalId : slugFromText(resolvedTitle)
    };
}

function normalizedTreePath(value: string): string {
  const withoutQuery = value.trim().split(/[?#]/, 1)[0];
  const path = withoutQuery.replace(/^https?:\/\/[^/]+/i, "").replace(/^\/+|\/+$/g, "");
  return path ? `/${path}/` : "";
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

function SiteMenuPreviewSection({ title, items, sections = [], icon, action, children, adoptingParentKey, activeParentTreeKey, onAddChild }: { title: string; items: unknown[]; sections?: Section[]; icon?: React.ReactNode; action?: React.ReactNode; children?: React.ReactNode; adoptingParentKey?: string | null; activeParentTreeKey?: string; onAddChild?: (item: MenuPreviewItem, section: Section | undefined, treeKey: string) => void }) {
  const menuType = title.includes("Footer") ? "footer" : "header";
  const tree = React.useMemo(() => buildMenuTree(items, sections), [items, sections]);
  const [collapsedKeys, setCollapsedKeys] = React.useState<Set<string>>(() => collapsibleMenuKeys(tree));
  const itemCount = countMenuTree(tree);
  const toggleNode = (key: string) => setCollapsedKeys((current) => {
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
        return (
          <li className="siteMenuTreeNode" key={node.key} role="treeitem" aria-expanded={hasChildren ? !collapsed : undefined}>
            <div className="siteMenuTreeRow">
              {hasChildren ? <span className="siteMenuTreeBranchSpacer" /> : <button className="siteMenuTreeToggle" type="button" disabled><span /></button>}
              <div className="siteMenuPreviewItemText"><strong>{node.item.title}</strong>{node.item.path ? <code>{node.item.path}</code> : null}</div>
              {hasChildren ? <button className="siteMenuTreeToggle hasChildren" type="button" onClick={() => toggleNode(node.key)} aria-label={`${collapsed ? "Развернуть" : "Свернуть"} ${node.item.title}`}>
                {collapsed ? <ChevronRight size={17} /> : <ChevronDown size={17} />}<span className="siteMenuTreeToggleLabel">{collapsed ? "Показать все" : "Свернуть"}</span><span className="siteMenuTreeNestedCount">{nestedCount}</span>
              </button> : null}
              {onAddChild ? <button className="siteMenuAddChildButton" type="button" onClick={() => onAddChild(node.item, node.section, node.key)} disabled={Boolean(adoptingParentKey)} title={`Добавить дочерний пункт в «${node.item.title}»`}><Plus size={15} /> {adoptingParentKey === parentKey ? "Открываем…" : "Добавить"}</button> : null}
            </div>
            {activeParentTreeKey === node.key && children ? <div className="siteMenuTreeChildForm">{children}</div> : null}
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

function AdminRequestLogsPanel({ api }: Pick<ViewProps, "api">) {
  const [logs, setLogs] = React.useState<AdminRequestLog[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

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

  return (
    <DataPanel
      title="Логи запросов"
      actions={<button className="button secondary compact" type="button" onClick={loadLogs} disabled={loading}><RefreshCcw size={15} /> {loading ? "Обновляем" : "Обновить"}</button>}
    >
      {error ? <div className="formError">{error}</div> : null}
      {!loading && !logs.length ? <EmptyState text="Запросов пока нет." /> : (
        <ResponsiveTable
          columns={["Дата и время", "Проект", "Что отправили", "Метод", "Куда", "Результат"]}
          rows={logs.map((log) => [
            formatDate(log.created_at),
            <strong>{log.project_name}</strong>,
            <span className="requestLogAction"><strong>{log.action}</strong>{log.item_name ? <small>{log.item_name}</small> : null}</span>,
            <code className="requestLogMethod">{log.method}</code>,
            <span className="requestLogDestination" title={log.destination}>{log.destination}</span>,
            <span className={`requestLogResult ${log.result === "Успешно" ? "success" : log.result === "Ошибка" ? "error" : "pending"}`}>{log.result}</span>
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
  const [password, setPassword] = React.useState("");
  const [isAdmin, setIsAdmin] = React.useState(false);
  const [formError, setFormError] = React.useState("");

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ username, password, is_admin: isAdmin })
      });
      setUsername("");
      setPassword("");
      setIsAdmin(false);
      await onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось создать пользователя");
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
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} />
        </label>
        <label className="checkboxRow">
          <input type="checkbox" checked={isAdmin} onChange={(event) => setIsAdmin(event.target.checked)} />
          Администратор
        </label>
        <div className="formActions alignEnd">
          <button className="button primary" type="submit"><UserPlus size={18} /> Создать пользователя</button>
        </div>
        {formError ? <span className="formError wide">{formError}</span> : null}
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

function TabButton({ href, label, active, onClick }: { href: string; label: string; active: boolean; onClick: () => void }) {
  return (
    <a
      className={`tabButton ${active ? "active" : ""}`}
      href={href}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onClick();
      }}
    >
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
                  {option.badge ? <small className="searchableSelectOptionBadge">{option.badge}</small> : null}
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

function DataPanel({ title, actions, children }: { title: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode }) {
  return <section className="dataPanel"><div className="panelHeader"><h2>{title}</h2>{actions}</div>{children}</section>;
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

function Modal({ title, subtitle, children, onClose, wide, className = "" }: { title: string; subtitle?: string; children: React.ReactNode; onClose: () => void; wide?: boolean; className?: string }) {
  return (
    <div className="modalOverlay" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={onClose}>
      <div className={`modalDialog ${wide ? "wide" : ""} ${className}`.trim()} onMouseDown={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <div className="modalTitleGroup">
            <h2 id="modal-title">{title}</h2>
            {subtitle ? <small>{subtitle}</small> : null}
          </div>
          <button className="iconButton" type="button" onClick={onClose} aria-label="Закрыть окно"><X size={18} /></button>
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

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function PromptBadge({ name }: { name?: string | null }) {
  const label = name || "Промпт не указан";
  const isImproved = /v\s*2|улучш|доработ/i.test(label);
  return <span className={`promptBadge ${isImproved ? "improved" : ""}`}>Промпт: {label}</span>;
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
      <strong>{item.topic}</strong>
      <PromptBadge name={generationPrompt} />
      {usedCompetitorResearch ? <span className="researchBadge">На основе анализа конкурентов</span> : null}
      <span>Генерация: {generationDate ? formatDate(generationDate) : "-"}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status.replaceAll("_", "-")}`}>{status}</span>;
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

function viewTitle(view: AppView, workspaceTab: WorkspaceTab) {
  if (view === "workspace") {
    const tabTitles: Record<WorkspaceTab, string> = {
      overview: "Рабочий экран: обзор",
      topics: "Рабочий экран: задачи",
      content: "Рабочий экран: контент и публикация",
      publication: "Рабочий экран: контент и публикация",
      menu: "Рабочий экран: меню"
    };
    return tabTitles[workspaceTab];
  }

  const titles: Record<Exclude<AppView, "workspace">, string> = {
    dashboard: "Dashboard",
    prompts: "Промпты",
    tasks: "Задачи генерации",
    taskArchive: "Архив задач",
    content: "Контент",
    publications: "Публикации",
    providers: "API Providers",
    sites: "Сайты",
    favorites: "Избранное",
    settings: "Настройки"
  };
  return titles[view];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
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

function ContentPreviewBody({ item }: { item: ContentItem }) {
  const pages = item.generated_json.pages;
  if (!Array.isArray(pages) || !pages[0] || typeof pages[0] !== "object") {
    return <pre className="contentPreviewText modalContentText">{JSON.stringify(item.generated_json, null, 2)}</pre>;
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
