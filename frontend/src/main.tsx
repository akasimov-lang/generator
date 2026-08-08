import React from "react";
import ReactDOM from "react-dom/client";
import { createPortal } from "react-dom";
import { LANGUAGE_OPTIONS, type LanguageOption } from "./languageOptions";
import {
  Activity,
  AlertTriangle,
  Archive,
  BellRing,
  Bot,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CheckCircle2,
  Copy,
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
  default_banners: string[];
  showcase_payload: Record<string, unknown> | null;
};

type Section = {
  id: string;
  site_id: string;
  external_id: string;
  name: string;
  path: string;
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
type AppView = "dashboard" | "workspace" | "prompts" | "tasks" | "taskArchive" | "content" | "publications" | "providers" | "sites" | "settings";
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
  const workspaceEntry = Object.entries(WORKSPACE_TAB_PATHS).find(([, routePath]) => routePath === path);
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

function pathForRoute(view: AppView, workspaceTab: WorkspaceTab = DEFAULT_WORKSPACE_TAB) {
  if (view === "workspace") return WORKSPACE_TAB_PATHS[workspaceTab];
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

function App() {
  const initialRoute = React.useMemo(() => routeFromPath(window.location.pathname), []);
  const [token, setToken] = React.useState(() => localStorage.getItem("admin_token") || "");
  const [theme, setTheme] = React.useState<ThemeMode>(() => (localStorage.getItem("theme_mode") === "dark" ? "dark" : "light"));
  const [activeView, setActiveView] = React.useState<AppView>(initialRoute.view);
  const [workspaceTab, setWorkspaceTab] = React.useState<WorkspaceTab>(initialRoute.workspaceTab);
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

  const navigateTo = React.useCallback((view: AppView, nextWorkspaceTab: WorkspaceTab = workspaceTab, replace = false) => {
    const normalizedWorkspaceTab = view === "workspace" ? nextWorkspaceTab : workspaceTab;
    const nextPath = pathForRoute(view, normalizedWorkspaceTab);
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
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(options.headers || {})
        }
      });
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
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme_mode", theme);
  }, [theme]);

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
    const nextPath = pathForRoute(activeView, activeView === "workspace" ? workspaceTab : DEFAULT_WORKSPACE_TAB);
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
          <div className="brandMark large"><ShieldCheck size={28} /></div>
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
          <div className="brandMark"><Bot size={20} /></div>
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

        {activeView === "workspace" && <ProjectWorkspaceView api={api} sites={sites} providers={providers} activeTab={workspaceTab} onTabChange={(tab) => navigateTo("workspace", tab)} onChanged={loadAll} />}
        {activeView === "prompts" && <PromptsView api={api} sites={sites} isAdmin={isAdmin} onChanged={loadAll} />}
        {isAdmin && activeView === "dashboard" && dashboard && <DashboardView api={api} dashboard={dashboard} tasks={tasks} content={content} sites={sites} onChanged={loadAll} />}
        {isAdmin && activeView === "tasks" && <TasksView api={api} sites={sites} providers={providers} tasks={tasks} onChanged={loadAll} />}
        {isAdmin && activeView === "taskArchive" && <TaskArchiveView api={api} tasks={archivedTasks} onChanged={loadAll} />}
        {isAdmin && activeView === "content" && <ContentView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {isAdmin && activeView === "publications" && <PublicationsView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {isAdmin && activeView === "providers" && <ProvidersView api={api} providers={providers} onChanged={loadAll} />}
        {isAdmin && activeView === "sites" && <SitesView api={api} sites={sites} onChanged={loadAll} />}
        {activeView === "settings" && <SettingsView api={api} currentUser={currentUser} users={users} onChanged={loadAll} />}
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
          <div className="brandMark"><Bot size={20} /></div>
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
        <div className="brandMark large"><ShieldCheck size={28} /></div>
        <h1>AI Content panel</h1>
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

function DashboardView({ api, dashboard, tasks, content, sites, onChanged }: ViewProps & { dashboard: Dashboard; tasks: Task[]; content: ContentItem[]; sites: Site[] }) {
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
            rows={tasks.slice(0, 8).map((task) => [task.title, countryLabel(task.geo), languageLabel(task.language), task.topics_count, <StatusBadge status={task.status} />])}
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
  activeTab,
  onTabChange,
  onChanged
}: ViewProps & {
  sites: Site[];
  providers: AiProvider[];
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}) {
  const [selectedSiteId, setSelectedSiteId] = React.useState(() => localStorage.getItem("workspace_site_id") || "");
  const [overview, setOverview] = React.useState<SiteOverview | null>(null);
  const [siteTasks, setSiteTasks] = React.useState<Task[]>([]);
  const [siteContent, setSiteContent] = React.useState<ContentItem[]>([]);
  const [sections, setSections] = React.useState<Section[]>([]);
  const [promptTemplates, setPromptTemplates] = React.useState<PromptTemplate[]>([]);
  const [logs, setLogs] = React.useState<PublicationLog[]>([]);
  const [campaigns, setCampaigns] = React.useState<PublicationCampaign[]>([]);
  const [workspaceError, setWorkspaceError] = React.useState("");
  const selectedSite = sites.find((site) => site.id === selectedSiteId) || null;

  const loadProject = React.useCallback(async () => {
    if (!selectedSiteId) return;
    setWorkspaceError("");
    const [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextLogs, nextCampaigns] = await Promise.all([
      api<SiteOverview>(`/sites/${selectedSiteId}/overview`),
      api<Task[]>(`/sites/${selectedSiteId}/tasks`),
      api<ContentItem[]>(`/sites/${selectedSiteId}/content`),
      api<Section[]>(`/sites/${selectedSiteId}/sections`),
      api<PromptTemplate[]>(`/sites/${selectedSiteId}/prompt-templates`),
      api<PublicationLog[]>(`/sites/${selectedSiteId}/publication-logs`),
      api<PublicationCampaign[]>(`/sites/${selectedSiteId}/publication-campaigns`)
    ]);
    setOverview(nextOverview);
    setSiteTasks(nextTasks);
    setSiteContent(nextContent);
    setSections(nextSections);
    setPromptTemplates(nextPrompts);
    setLogs(nextLogs);
    setCampaigns(nextCampaigns);
  }, [api, selectedSiteId]);

  React.useEffect(() => {
    if (sites.length && (!selectedSiteId || !sites.some((site) => site.id === selectedSiteId))) {
      setSelectedSiteId(sites[0].id);
    }
  }, [selectedSiteId, sites]);

  React.useEffect(() => {
    if (selectedSiteId) {
      localStorage.setItem("workspace_site_id", selectedSiteId);
      setOverview(null);
      setSiteTasks([]);
      setSiteContent([]);
      setSections([]);
      setPromptTemplates([]);
      setLogs([]);
      setCampaigns([]);
      setWorkspaceError("");
      loadProject().catch((error: unknown) => setWorkspaceError(error instanceof Error ? error.message : "Не удалось загрузить проект"));
    }
  }, [loadProject, selectedSiteId]);

  async function refreshProject() {
    await loadProject();
    await onChanged();
  }

  if (!sites.length) {
    return <EmptyState text="Сначала добавьте сайт в админском разделе Сайты." />;
  }

  return (
    <section className="viewStack">
      <DataPanel title="Рабочий проект">
        <div className="projectHeader">
          <label>
            Проект
            <SearchableSelect
              value={selectedSiteId}
              onChange={setSelectedSiteId}
              options={sites.map((site) => ({ value: site.id, label: site.name }))}
              searchPlaceholder="Найти проект"
            />
          </label>
          <div className="projectMeta">
            <strong>{selectedSite?.base_url || "..."}</strong>
            <span>{selectedSite ? humanPayloadMode(selectedSite.payload_mode) : ""}</span>
          </div>
          <button className="button secondary" type="button" onClick={() => refreshProject()}><RefreshCcw size={18} /> Обновить проект</button>
        </div>
        <div className="workspaceTabs">
          <TabButton href={pathForRoute("workspace", "overview")} label="Обзор" active={activeTab === "overview"} onClick={() => onTabChange("overview")} />
          <TabButton href={pathForRoute("workspace", "topics")} label="Задачи" active={activeTab === "topics"} onClick={() => onTabChange("topics")} />
          <TabButton href={pathForRoute("workspace", "content")} label="Контент" active={activeTab === "content"} onClick={() => onTabChange("content")} />
          <TabButton href={pathForRoute("workspace", "publication")} label="Публикация" active={activeTab === "publication"} onClick={() => onTabChange("publication")} />
          <TabButton href={pathForRoute("workspace", "menu")} label="Меню" active={activeTab === "menu"} onClick={() => onTabChange("menu")} />
        </div>
        {workspaceError ? <div className="notice">{workspaceError}</div> : null}
      </DataPanel>

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
      {selectedSite && activeTab === "content" ? (
        <ProjectContentPanel key={selectedSite.id} api={api} content={siteContent} sections={sections} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "publication" ? (
        <ProjectPublicationPanel key={selectedSite.id} api={api} site={selectedSite} content={siteContent} sections={sections} campaigns={campaigns} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "menu" ? (
        <ProjectMenuPanel api={api} site={selectedSite} sections={sections} onChanged={refreshProject} />
      ) : null}
    </section>
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
  const [geo, setGeo] = React.useState("DE");
  const [language, setLanguage] = React.useState("de");
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
              options={sites.map((site) => ({ value: site.id, label: site.name }))}
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

function ProjectContentPanel({ api, content, sections, onChanged }: ViewProps & { content: ContentItem[]; sections: Section[] }) {
  const [selectedItem, setSelectedItem] = React.useState<ContentItem | null>(null);
  const [jsonDraft, setJsonDraft] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [editorError, setEditorError] = React.useState("");

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
        <ResponsiveTable
          columns={["Тема", "Меню", "Слова", "Статус", "Опубликовано", "Действия"]}
          rows={content.map((item) => [
            <TopicMetaCell item={item} />,
            sectionLabel(item.section_id, sections),
            item.word_count,
            <StatusBadge status={item.status} />,
            item.published_url ? <a href={item.published_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> URL</a> : item.published_at ? formatDate(item.published_at) : "-",
            <div className="userActions">
              <button className="button compact" type="button" onClick={() => openEditor(item)} disabled={isPublicationLocked(item)}><Edit3 size={15} /> Открыть</button>
              <button className="button compact approve" type="button" onClick={() => approve(item)} disabled={!canApproveContent(item)}>Approve</button>
            </div>
          ])}
        />
        {editorError ? <span className="formError">{editorError}</span> : null}
      </DataPanel>

      {selectedItem ? (
        <DataPanel title={`Редактирование: ${selectedItem.topic}`}>
          <form className="formGrid" onSubmit={saveContent}>
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
        </DataPanel>
      ) : null}
    </section>
  );
}

function ProjectPublicationPanel({ api, site, content, sections, campaigns, onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[]; campaigns: PublicationCampaign[] }) {
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
      <DataPanel title="Запустить публикацию">
        <form className="formGrid" onSubmit={createCampaign}>
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
      </DataPanel>
      <DataPanel title="Кампании проекта">
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
      </DataPanel>
      <DataPanel title="Approved к публикации">
        <ResponsiveTable
          columns={["Тема", "Меню", "Slug"]}
          rows={approved.map((item) => [<TopicMetaCell item={item} />, sectionLabel(item.section_id, sections), item.slug])}
        />
      </DataPanel>
    </section>
  );
}

function ProjectMenuPanel({ api, site, sections, onChanged }: ViewProps & { site: Site; sections: Section[] }) {
  const [name, setName] = React.useState("");
  const [externalId, setExternalId] = React.useState("");
  const [path, setPath] = React.useState("");
  const [formError, setFormError] = React.useState("");

  async function createSection(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    await api(`/sites/${site.id}/sections`, {
      method: "POST",
      body: JSON.stringify({
        name,
        external_id: externalId || slugFromText(name),
        path: path || "/"
      })
    });
    setName("");
    setExternalId("");
    setPath("");
    await onChanged();
  }

  return (
    <section className="viewStack">
      <DataPanel title="Добавить пункт меню">
        <form className="formGrid" onSubmit={createSection}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            External ID
            <input value={externalId} onChange={(event) => setExternalId(event.target.value)} placeholder="casino-bonuses" />
          </label>
          <label className="wide">
            Path
            <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="/casino-bonuses/" />
          </label>
          {formError ? <span className="formError wide">{formError}</span> : null}
          <div className="formActions wide"><button className="button primary" type="submit"><Plus size={18} /> Добавить</button></div>
        </form>
      </DataPanel>
      <DataPanel title="Пункты меню проекта">
        <ResponsiveTable
          columns={["Название", "External ID", "Path"]}
          rows={sections.map((section) => [section.name, section.external_id, section.path])}
        />
      </DataPanel>
    </section>
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
  const [geo, setGeo] = React.useState("DE");
  const [language, setLanguage] = React.useState("en");
  const [topics, setTopics] = React.useState("");
  const [siteId, setSiteId] = React.useState(fixedSite?.id || "");
  const [providerId, setProviderId] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [promptTemplateId, setPromptTemplateId] = React.useState("");
  const [targetWords, setTargetWords] = React.useState(DEFAULT_TARGET_WORDS);
  const [payloadMode, setPayloadMode] = React.useState("site_default");
  const [shortcode, setShortcode] = React.useState("");
  const [includeToc, setIncludeToc] = React.useState(true);
  const [includeFaq, setIncludeFaq] = React.useState(true);
  const [collectCompetitors, setCollectCompetitors] = React.useState(false);
  const [createFormExpanded, setCreateFormExpanded] = React.useState(false);
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
      topics: cleanTopics
    };
    try {
      const task = await api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) });
      if (!collectCompetitors) {
        await api(`/tasks/${task.id}/generate`, { method: "POST" });
      }
      setTopics("");
      setShortcode("");
      setCreateFormExpanded(false);
      await onChanged();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Не удалось создать задачу.");
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
                ...sites.map((site) => ({ value: site.id, label: site.name }))
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
            <button className="button primary" type="submit">
              <Plus size={18} /> {collectCompetitors ? "Создать без автогенерации" : "Создать и сгенерировать"}
            </button>
          </div>
        </form> : null}
      </section>
      <DataPanel title="Все задачи">
        <AdminTasksAccordion
          tasks={tasks}
          expandedTaskId={expandedTaskId}
          expandedDetails={expandedDetails}
          research={expandedResearch}
          loadingId={detailsLoadingId}
          actionId={taskActionId}
          onToggle={toggleTask}
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
  expandedTaskId,
  expandedDetails,
  research,
  loadingId,
  actionId,
  onToggle,
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
  expandedTaskId: string;
  expandedDetails: TaskDetails | null;
  research: CompetitorResearch[];
  loadingId: string;
  actionId: string;
  onToggle: (task: Task) => Promise<void>;
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
            <th>Формат</th>
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
                  <td data-label="Формат">{humanPayloadMode(task.payload_mode)}</td>
                  <td data-label="Тем">{task.topics_count}</td>
                  <td data-label="Статус"><StatusBadge status={task.status} /></td>
                  <td data-label="Действия">
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
                  </td>
                </tr>
                {expanded ? (
                  <tr className="expandedRow">
                    <td colSpan={8}>
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
        items: content.filter((item) => item.site_id === site.id)
      }))
      .sort((first, second) => first.name.localeCompare(second.name, "ru"));
    const unassigned = content.filter((item) => !item.site_id || !knownSiteIds.has(item.site_id));
    if (unassigned.length) {
      groups.push({ id: "__unassigned__", name: "Без проекта", baseUrl: "", items: unassigned });
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
                    <strong>{group.name}</strong>
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
              options={[{ value: "", label: "Выберите сайт" }, ...sites.map((site) => ({ value: site.id, label: site.name }))]}
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

function SitesView({ api, sites, onChanged }: ViewProps & { sites: Site[] }) {
  const [name, setName] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState("");
  const [publicationEndpoint, setPublicationEndpoint] = React.useState("");
  const [apiToken, setApiToken] = React.useState("");
  const [payloadMode, setPayloadMode] = React.useState<"simple_page" | "full_site">("simple_page");
  const [editorVersion, setEditorVersion] = React.useState("2.31.0");
  const [defaultMenuJson, setDefaultMenuJson] = React.useState('{\n  "header": [],\n  "footer": []\n}');
  const [banners, setBanners] = React.useState("");
  const [showcaseJson, setShowcaseJson] = React.useState("");
  const [formError, setFormError] = React.useState("");

  async function createSite(event: React.FormEvent) {
    event.preventDefault();
    setFormError("");
    let defaultMenu: Record<string, unknown>;
    let showcasePayload: Record<string, unknown> | null = null;
    try {
      defaultMenu = JSON.parse(defaultMenuJson);
      if (showcaseJson.trim()) {
        showcasePayload = JSON.parse(showcaseJson);
      }
    } catch {
      setFormError("Проверь JSON в меню или showcase/casinos.");
      return;
    }
    await api("/sites", {
      method: "POST",
      body: JSON.stringify({
        name,
        base_url: baseUrl,
        publication_endpoint: publicationEndpoint,
        api_token: apiToken || null,
        payload_mode: payloadMode,
        editor_version: editorVersion,
        default_menu: defaultMenu,
        default_banners: banners.split(",").map((item: string) => item.trim()).filter(Boolean),
        showcase_payload: showcasePayload
      })
    });
    setName("");
    setBaseUrl("");
    setPublicationEndpoint("");
    setApiToken("");
    setPayloadMode("simple_page");
    setEditorVersion("2.31.0");
    setDefaultMenuJson('{\n  "header": [],\n  "footer": []\n}');
    setBanners("");
    setShowcaseJson("");
    onChanged();
  }

  return (
    <section className="viewStack">
      <DataPanel title="Подключить сайт">
        <form className="formGrid" onSubmit={createSite}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder="Main site" />
          </label>
          <label>
            Base URL
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} required placeholder="https://site.com" />
          </label>
          <label className="wide">
            Endpoint публикации
            <input value={publicationEndpoint} onChange={(event) => setPublicationEndpoint(event.target.value)} required placeholder="https://site.com/api/pages/create" />
          </label>
          <label>
            API token
            <input value={apiToken} onChange={(event) => setApiToken(event.target.value)} type="password" />
          </label>
          <label>
            Формат публикации
            <select value={payloadMode} onChange={(event) => setPayloadMode(event.target.value as "simple_page" | "full_site")}>
              <option value="simple_page">Simple: menu + pages</option>
              <option value="full_site">Full: menu + pages + casinos</option>
            </select>
          </label>
          <label>
            Editor.js version
            <input value={editorVersion} onChange={(event) => setEditorVersion(event.target.value)} />
          </label>
          <label className="wide">
            Menu JSON
            <textarea value={defaultMenuJson} onChange={(event) => setDefaultMenuJson(event.target.value)} rows={5} />
          </label>
          <label>
            Banners
            <input value={banners} onChange={(event) => setBanners(event.target.value)} placeholder="banner, top-banner" />
          </label>
          <label className="wide">
            Casinos / showcase JSON для full site
            <textarea value={showcaseJson} onChange={(event) => setShowcaseJson(event.target.value)} rows={6} placeholder='{"basic": [], "standard": []}' />
          </label>
          {formError ? <span className="formError wide">{formError}</span> : null}
          <div className="formActions wide"><button className="button primary" type="submit"><Plus size={18} /> Сохранить сайт</button></div>
        </form>
      </DataPanel>
      <DataPanel title="Сайты">
        <ResponsiveTable columns={["Название", "Формат", "Editor", "Base URL", "Endpoint"]} rows={sites.map((site) => [site.name, humanPayloadMode(site.payload_mode), site.editor_version || "2.31.0", site.base_url, site.publication_endpoint])} />
      </DataPanel>
    </section>
  );
}

function SettingsView({ api, currentUser, users, onChanged }: ViewProps & { currentUser: User | null; users: User[] }) {
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
        <UsersAdminPanel api={api} currentUser={currentUser} users={users} onChanged={onChanged} />
      ) : null}

      <DataPanel title="Настройки проекта">
        <div className="settingsList">
          <div><strong>Доступ по IP</strong><span>http://91.199.133.86</span></div>
          <div><strong>Frontend</strong><span>React, CSS Modules/global CSS, без Tailwind и CDN</span></div>
          <div><strong>Backend</strong><span>FastAPI, PostgreSQL, Redis, Celery</span></div>
          <div><strong>Payload</strong><span>Simple: menu + pages; Full: menu + pages + casinos</span></div>
          <div><strong>Content</strong><span>Editor.js blocks: header, paragraph, list, table, shortcode, image, faq, toc, quote, plusMinus</span></div>
          <div><strong>Deploy</strong><span>Git push через SSH-ключ на production remote</span></div>
        </div>
      </DataPanel>
    </section>
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
  keywords?: string;
};

function SearchableSelect({
  value,
  options,
  onChange,
  searchPlaceholder = "Начните вводить для поиска",
  disabled = false,
  ariaLabel
}: {
  value: string;
  options: SearchableSelectOption[];
  onChange: (value: string) => void;
  searchPlaceholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
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
  const filteredOptions = normalizedQuery
    ? options.filter((option) => `${option.label} ${option.value} ${option.keywords || ""}`.toLocaleLowerCase("ru-RU").includes(normalizedQuery))
    : options;

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
        <span>{selected?.label || "Выберите значение"}</span>
        <ChevronDown size={17} />
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
          <div className="searchableSelectOptions" id={listboxId} role="listbox">
            {filteredOptions.length ? filteredOptions.map((option, index) => (
              <button
                className={`searchableSelectOption ${option.value === value ? "selected" : ""} ${index === activeIndex ? "active" : ""}`}
                type="button"
                role="option"
                aria-selected={option.value === value}
                key={`${option.value}:${option.label}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => chooseOption(option)}
              >
                <span>{option.label}</span>
                {option.value === value ? <CheckCircle2 size={16} /> : null}
              </button>
            )) : <div className="searchableSelectEmpty">Ничего не найдено</div>}
          </div>
        </div>,
        document.body
      ) : null}
    </div>
  );
}

function DataPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="dataPanel"><div className="panelHeader"><h2>{title}</h2></div>{children}</section>;
}

function ResponsiveTable({ columns, rows, rowClassNames, wrapperClassName = "" }: { columns: string[]; rows: React.ReactNode[][]; rowClassNames?: string[]; wrapperClassName?: string }) {
  if (!rows.length) return <EmptyState text="Данных пока нет." />;
  return (
    <div className={`tableWrap ${wrapperClassName}`.trim()}>
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => <tr className={rowClassNames?.[rowIndex] || undefined} key={rowIndex}>{row.map((cell, cellIndex) => <td data-label={columns[cellIndex]} key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
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
      content: "Рабочий экран: контент",
      publication: "Рабочий экран: публикация",
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
