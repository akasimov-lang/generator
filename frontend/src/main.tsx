import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BellRing,
  Bot,
  CalendarClock,
  CheckCircle2,
  Database,
  Edit3,
  ExternalLink,
  FileText,
  FolderKanban,
  Globe2,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Moon,
  Play,
  Plus,
  RefreshCcw,
  Send,
  Settings,
  ShieldCheck,
  Sun,
  UserPlus,
  Users
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
  site_id: string | null;
  section_id: string | null;
  geo: string;
  language: string;
  payload_mode: string;
  topics_count: number;
  target_words: number | null;
  status: string;
  created_at: string;
  prompt_template_name: string | null;
  prompt_template: string | null;
};

type ContentItem = {
  id: string;
  site_id: string | null;
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
  updated_at: string;
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
  provider_type: "custom" | "gemini";
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

type ThemeMode = "light" | "dark";
type AppView = "dashboard" | "workspace" | "tasks" | "content" | "publications" | "providers" | "sites" | "settings";
type WorkspaceTab = "overview" | "topics" | "prompts" | "content" | "publication" | "menu";

type AppRoute = {
  view: AppView;
  workspaceTab: WorkspaceTab;
};

const API_BASE = "/api";
const DEFAULT_WORKSPACE_TAB: WorkspaceTab = "overview";
const DEFAULT_ROUTE: AppRoute = { view: "dashboard", workspaceTab: DEFAULT_WORKSPACE_TAB };

const MAIN_VIEW_PATHS: Record<Exclude<AppView, "workspace">, string> = {
  dashboard: "/dashboard",
  tasks: "/tasks",
  content: "/content",
  publications: "/publications",
  providers: "/ai-providers",
  sites: "/sites",
  settings: "/settings"
};

const WORKSPACE_TAB_PATHS: Record<WorkspaceTab, string> = {
  overview: "/project-overview",
  topics: "/project-topics",
  prompts: "/project-prompts",
  content: "/project-content",
  publication: "/project-publication",
  menu: "/project-menu"
};

function routeFromPath(pathname: string): AppRoute {
  const path = pathname.replace(/\/+$/, "") || "/";
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
  return !["workspace", "settings"].includes(view);
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

Контекст ниши:
Онлайн-казино, ставки, casino providers, легальные Anbieter, лицензии, Spielerschutz, Zahlungen, Auszahlungen, KYC, Datenschutz, Limits, sichere Online Casinos.

Главная цель:
Создать полезную, структурированную, юридически аккуратную страницу, которая полно отвечает на поисковый интент пользователя и пригодна для редакторской проверки перед публикацией.

Внутренняя SEO-логика, НЕ выводить в текст:
1. Главный интент.
2. 8-12 подинтентов.
3. Главный ключ.
4. Вторичные ключи.
5. FAQ-запросы.
6. Legal/Safety/Payment кластеры.
7. Гипотетические content gaps.
8. Риски фактов, которые нужно проверить редактору.

Для страниц по Германии обязательно раскрыть:
- Was bedeutet GGL-Lizenz?
- Warum ist Lizenzprüfung wichtig?
- Wie erkennt man sichere Anbieter?
- Welche Rolle spielen KYC und Identitätsprüfung?
- Was muss man vor Einzahlung prüfen?
- Unterschied zwischen Einzahlung und Auszahlung.
- Spielerschutz, Limits und Selbstausschluss.
- Für wen sind Online Casinos nicht geeignet?
- Welche Warnsignale sollte man beachten?

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

const LANGUAGE_OPTIONS = [
  { code: "de", name: "Deutsch" },
  { code: "en", name: "English" },
  { code: "ru", name: "Русский" },
  { code: "es", name: "Español" },
  { code: "fr", name: "Français" },
  { code: "it", name: "Italiano" },
  { code: "pl", name: "Polski" },
  { code: "pt", name: "Português" },
  { code: "nl", name: "Nederlands" }
];

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
    const [nextDashboard, nextTasks, nextContent] = nextUser.is_admin
      ? await Promise.all([
        api<Dashboard>("/dashboard"),
        api<Task[]>("/tasks"),
        api<ContentItem[]>("/content")
      ])
      : [null, [], []] as [Dashboard | null, Task[], ContentItem[]];
    const nextUsers = nextUser.is_admin ? await api<User[]>("/users") : [];
    setCurrentUser(nextUser);
    setDashboard(nextDashboard);
    setTasks(nextTasks);
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
      <div className="loginPage">
        <div className="loginPanel">
          <div className="brandMark large"><ShieldCheck size={28} /></div>
          <h1>Загрузка панели</h1>
          <p>{message || "Проверяем сессию и права пользователя."}</p>
        </div>
      </div>
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
              <NavButton href={pathForRoute("tasks")} icon={<ListChecks />} label="Задачи" active={activeView === "tasks"} onClick={() => navigateTo("tasks")} />
              <NavButton href={pathForRoute("content")} icon={<FileText />} label="Контент" active={activeView === "content"} onClick={() => navigateTo("content")} />
              <NavButton href={pathForRoute("publications")} icon={<Send />} label="Публикации" active={activeView === "publications"} onClick={() => navigateTo("publications")} />
              <NavButton href={pathForRoute("providers")} icon={<Bot />} label="AI Providers" active={activeView === "providers"} onClick={() => navigateTo("providers")} />
              <NavButton href={pathForRoute("sites")} icon={<Globe2 />} label="Сайты" active={activeView === "sites"} onClick={() => navigateTo("sites")} />
            </>
          ) : (
            <NavButton href={pathForRoute("workspace", DEFAULT_WORKSPACE_TAB)} icon={<FolderKanban />} label="Рабочий экран" active={activeView === "workspace"} onClick={() => navigateTo("workspace", DEFAULT_WORKSPACE_TAB)} />
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
              }}
              title="Выйти"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {message ? <div className="notice">{message}</div> : null}

        {activeView === "workspace" && <ProjectWorkspaceView api={api} sites={sites} providers={providers} isAdmin={isAdmin} activeTab={workspaceTab} onTabChange={(tab) => navigateTo("workspace", tab)} onChanged={loadAll} />}
        {isAdmin && activeView === "dashboard" && dashboard && <DashboardView dashboard={dashboard} tasks={tasks} content={content} />}
        {isAdmin && activeView === "tasks" && <TasksView api={api} sites={sites} providers={providers} tasks={tasks} onChanged={loadAll} />}
        {isAdmin && activeView === "content" && <ContentView api={api} content={content} onChanged={loadAll} />}
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

function LoginScreen({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
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
  }

  return (
    <div className="loginPage">
      <form className="loginPanel" onSubmit={submit}>
        <div className="brandMark large"><ShieldCheck size={28} /></div>
        <h1>Content Generator Admin</h1>
        <p>Вход в панель генерации и публикации контента.</p>
        <label>
          Логин
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Пароль
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus />
        </label>
        {error ? <span className="formError">{error}</span> : null}
        <button className="button primary" type="submit">Войти</button>
      </form>
    </div>
  );
}

function DashboardView({ dashboard, tasks, content }: { dashboard: Dashboard; tasks: Task[]; content: ContentItem[] }) {
  return (
    <section className="viewStack">
      <div className="kpiGrid">
        <KpiCard icon={<Database />} label="Всего задач" value={dashboard.stats.total_tasks} />
        <KpiCard icon={<CheckCircle2 />} label="Сгенерировано" value={dashboard.stats.generated} />
        <KpiCard icon={<FileText />} label="Ждет approve" value={dashboard.stats.awaiting_approve} />
        <KpiCard icon={<Send />} label="В очереди" value={dashboard.stats.scheduled} />
        <KpiCard icon={<Activity />} label="Опубликовано" value={dashboard.stats.published} />
        <KpiCard icon={<AlertTriangle />} label="Ошибки" value={dashboard.stats.errors} danger />
      </div>
      <div className="gridTwo">
        <DataPanel title="Активные задачи">
          <ResponsiveTable
            columns={["Задача", "Гео", "Язык", "Тем", "Статус"]}
            rows={tasks.slice(0, 8).map((task) => [task.title, task.geo, task.language, task.topics_count, <StatusBadge status={task.status} />])}
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
    </section>
  );
}

function ProjectWorkspaceView({
  api,
  sites,
  providers,
  isAdmin,
  activeTab,
  onTabChange,
  onChanged
}: ViewProps & {
  sites: Site[];
  providers: AiProvider[];
  isAdmin: boolean;
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}) {
  const [selectedSiteId, setSelectedSiteId] = React.useState(() => localStorage.getItem("workspace_site_id") || "");
  const [overview, setOverview] = React.useState<SiteOverview | null>(null);
  const [siteTasks, setSiteTasks] = React.useState<Task[]>([]);
  const [siteContent, setSiteContent] = React.useState<ContentItem[]>([]);
  const [sections, setSections] = React.useState<Section[]>([]);
  const [promptTemplates, setPromptTemplates] = React.useState<PromptTemplate[]>([]);
  const [basePrompt, setBasePrompt] = React.useState<PromptTemplate | null>(null);
  const [logs, setLogs] = React.useState<PublicationLog[]>([]);
  const [workspaceError, setWorkspaceError] = React.useState("");
  const selectedSite = sites.find((site) => site.id === selectedSiteId) || null;

  const loadProject = React.useCallback(async () => {
    if (!selectedSiteId) return;
    setWorkspaceError("");
    const [nextOverview, nextTasks, nextContent, nextSections, nextPrompts, nextBasePrompt, nextLogs] = await Promise.all([
      api<SiteOverview>(`/sites/${selectedSiteId}/overview`),
      api<Task[]>(`/sites/${selectedSiteId}/tasks`),
      api<ContentItem[]>(`/sites/${selectedSiteId}/content`),
      api<Section[]>(`/sites/${selectedSiteId}/sections`),
      api<PromptTemplate[]>(`/sites/${selectedSiteId}/prompt-templates`),
      api<PromptTemplate>("/prompt-templates/base"),
      api<PublicationLog[]>(`/sites/${selectedSiteId}/publication-logs`)
    ]);
    setOverview(nextOverview);
    setSiteTasks(nextTasks);
    setSiteContent(nextContent);
    setSections(nextSections);
    setPromptTemplates(nextPrompts);
    setBasePrompt(nextBasePrompt);
    setLogs(nextLogs);
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
      setBasePrompt(null);
      setLogs([]);
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
            <select value={selectedSiteId} onChange={(event) => setSelectedSiteId(event.target.value)}>
              {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
            </select>
          </label>
          <div className="projectMeta">
            <strong>{selectedSite?.base_url || "..."}</strong>
            <span>{selectedSite ? humanPayloadMode(selectedSite.payload_mode) : ""}</span>
          </div>
          <button className="button secondary" type="button" onClick={() => refreshProject()}><RefreshCcw size={18} /> Обновить проект</button>
        </div>
        <div className="workspaceTabs">
          <TabButton href={pathForRoute("workspace", "overview")} label="Обзор" active={activeTab === "overview"} onClick={() => onTabChange("overview")} />
          <TabButton href={pathForRoute("workspace", "topics")} label="Темы" active={activeTab === "topics"} onClick={() => onTabChange("topics")} />
          <TabButton href={pathForRoute("workspace", "prompts")} label="Промпты" active={activeTab === "prompts"} onClick={() => onTabChange("prompts")} />
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
        <ProjectTopicsPanel key={selectedSite.id} api={api} site={selectedSite} providers={providers} sections={sections} promptTemplates={promptTemplates} tasks={siteTasks} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "prompts" ? (
        <ProjectPromptsPanel key={selectedSite.id} api={api} site={selectedSite} promptTemplates={promptTemplates} basePrompt={basePrompt} isAdmin={isAdmin} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "content" ? (
        <ProjectContentPanel key={selectedSite.id} api={api} content={siteContent} sections={sections} onChanged={refreshProject} />
      ) : null}
      {selectedSite && activeTab === "publication" ? (
        <ProjectPublicationPanel key={selectedSite.id} api={api} site={selectedSite} content={siteContent} sections={sections} onChanged={refreshProject} />
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
  const [targetWords, setTargetWords] = React.useState(1600);
  const [topics, setTopics] = React.useState("");
  const [providerId, setProviderId] = React.useState("");
  const [promptTemplateId, setPromptTemplateId] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [shortcode, setShortcode] = React.useState("");
  const [formError, setFormError] = React.useState("");
  const [taskDetails, setTaskDetails] = React.useState<TaskDetails | null>(null);
  const [selectedPreview, setSelectedPreview] = React.useState<ContentItem | null>(null);
  const [detailsError, setDetailsError] = React.useState("");
  const [detailsLoadingId, setDetailsLoadingId] = React.useState("");
  const topicCount = topics.split("\n").map((line) => line.trim()).filter(Boolean).length;
  const selectedPrompt = promptTemplates.find((prompt) => prompt.id === promptTemplateId) || promptTemplates.find((prompt) => prompt.is_default) || promptTemplates[0];

  React.useEffect(() => {
    if (!providerId) {
      const geminiProvider = providers.find((provider) => provider.provider_type === "gemini" && provider.is_active);
      if (geminiProvider) {
        setProviderId(geminiProvider.id);
      }
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
        topics: cleanTopics
      })
    });
    await api(`/tasks/${task.id}/generate`, { method: "POST" });
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
    } catch (error) {
      setDetailsError(error instanceof Error ? error.message : "Не удалось открыть задачу.");
    } finally {
      setDetailsLoadingId("");
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
            <select value={sectionId} onChange={(event) => setSectionId(event.target.value)}>
              <option value="">Выбрать позже</option>
              {sections.map((section) => <option key={section.id} value={section.id}>{section.name} · {section.path}</option>)}
            </select>
          </label>
          <label>
            Страна
            <select value={geo} onChange={(event) => setGeo(event.target.value)} required>
              {COUNTRIES.map((country) => <option key={country.code} value={country.code}>{country.flag} {country.code} · {country.name}</option>)}
            </select>
          </label>
          <label>
            Язык
            <select value={language} onChange={(event) => setLanguage(event.target.value)} required>
              {LANGUAGE_OPTIONS.map((option) => <option key={option.code} value={option.code}>{option.name} · {option.code}</option>)}
            </select>
          </label>
          <label>
            Количество слов
            <input value={targetWords} onChange={(event) => setTargetWords(Number(event.target.value))} type="number" min={300} max={8000} step={100} required />
          </label>
          <label>
            AI Provider
            <select value={providerId} onChange={(event) => setProviderId(event.target.value)}>
              <option value="">Stub generator</option>
              {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
            </select>
          </label>
          <label>
            Промпт генерации
            <select value={promptTemplateId} onChange={(event) => setPromptTemplateId(event.target.value)}>
              {promptTemplates.map((prompt) => <option key={prompt.id} value={prompt.id}>{prompt.is_default ? "Default · " : ""}{prompt.name}</option>)}
            </select>
          </label>
          <label>
            Shortcode
            <input value={shortcode} onChange={(event) => setShortcode(event.target.value)} placeholder="showcase-redesign" />
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
          <div className="formActions wide"><button className="button primary" type="submit"><Plus size={18} /> Создать и сгенерировать</button></div>
        </form>
      </DataPanel>
      <DataPanel title="Задачи проекта">
        <ResponsiveTable
          columns={["Задача", "Тем", "Страна", "Язык", "Слова", "Промпт", "Статус", "Действие"]}
          rows={tasks.map((task) => [
            task.title,
            task.topics_count,
            countryLabel(task.geo),
            task.language,
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
            <div><span>Язык</span><strong>{taskDetails.task.language}</strong></div>
            <div><span>Слов</span><strong>{taskDetails.task.target_words || "-"}</strong></div>
            <div><span>Тем</span><strong>{taskDetails.task.topics_count}</strong></div>
            <div><span>Промпт</span><PromptBadge name={taskDetails.task.prompt_template_name} /></div>
          </div>
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
        <DataPanel title={`Просмотр текста: ${selectedPreview.topic}`}>
          <div className="contentPreviewHeader">
            <div>
              <span>{selectedPreview.slug}</span>
              <strong>{contentItemTitle(selectedPreview)}</strong>
              <PromptBadge name={selectedPreview.generation_prompt_name || taskDetails?.task.prompt_template_name} />
              <span>Дата генерации: {selectedPreview.generated_at ? formatDate(selectedPreview.generated_at) : "-"}</span>
            </div>
            <StatusBadge status={selectedPreview.status} />
          </div>
          <pre className="contentPreviewText">{contentItemPreviewText(selectedPreview)}</pre>
        </DataPanel>
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
              Это общий список промптов для всех проектов. При генерации система автоматически подставляет значения из формы: <code>{"{{TOPIC}}"}</code>, <code>{"{{GEO}}"}</code>, <code>{"{{LANGUAGE}}"}</code>, <code>{"{{TARGET_WORDS}}"}</code>, <code>{"{{SITE_NAME}}"}</code>, <code>{"{{SLUG}}"}</code>, <code>{"{{CURRENT_YEAR}}"}</code>, <code>{"{{SHORTCODE}}"}</code>.
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
              <button className="button compact" type="button" onClick={() => openEditor(item)}><Edit3 size={15} /> Открыть</button>
              <button className="button compact" type="button" onClick={() => approve(item)} disabled={["approved", "scheduled", "published"].includes(item.status)}>Approve</button>
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
              <select value={sectionId} onChange={(event) => setSectionId(event.target.value)}>
                <option value="">Не выбран</option>
                {sections.map((section) => <option key={section.id} value={section.id}>{section.name} · {section.path}</option>)}
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
        </DataPanel>
      ) : null}
    </section>
  );
}

function ProjectPublicationPanel({ api, site, content, sections, onChanged }: ViewProps & { site: Site; content: ContentItem[]; sections: Section[] }) {
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
            <select value={sectionId} onChange={(event) => setSectionId(event.target.value)}>
              <option value="">Все approved</option>
              {sections.map((section) => <option key={section.id} value={section.id}>{section.name} · {section.path}</option>)}
            </select>
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

function TasksView({ api, sites, providers, tasks, onChanged }: ViewProps & { sites: Site[]; providers: AiProvider[]; tasks: Task[] }) {
  const [title, setTitle] = React.useState("");
  const [geo, setGeo] = React.useState("DE");
  const [language, setLanguage] = React.useState("EN");
  const [topics, setTopics] = React.useState("");
  const [siteId, setSiteId] = React.useState("");
  const [providerId, setProviderId] = React.useState("");
  const [payloadMode, setPayloadMode] = React.useState("site_default");
  const [shortcode, setShortcode] = React.useState("");
  const [includeToc, setIncludeToc] = React.useState(true);
  const [includeFaq, setIncludeFaq] = React.useState(true);

  React.useEffect(() => {
    if (!providerId) {
      const geminiProvider = providers.find((provider) => provider.provider_type === "gemini" && provider.is_active);
      if (geminiProvider) {
        setProviderId(geminiProvider.id);
      }
    }
  }, [providerId, providers]);

  async function createTask(event: React.FormEvent) {
    event.preventDefault();
    const payload = {
      title,
      geo,
      language,
      site_id: siteId || null,
      ai_provider_id: providerId || null,
      payload_mode: payloadMode,
      shortcode: shortcode.trim() || null,
      include_toc: includeToc,
      include_faq: includeFaq,
      topics: topics.split("\n").map((line: string) => line.trim()).filter(Boolean)
    };
    const task = await api<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) });
    await api(`/tasks/${task.id}/generate`, { method: "POST" });
    setTitle("");
    setTopics("");
    setShortcode("");
    onChanged();
  }

  return (
    <section className="viewStack">
      <DataPanel title="Создать задачу генерации">
        <form className="formGrid" onSubmit={createTask}>
          <label>
            Название задачи
            <input value={title} onChange={(event) => setTitle(event.target.value)} required placeholder="Casino Bonuses DE" />
          </label>
          <label>
            Гео
            <input value={geo} onChange={(event) => setGeo(event.target.value)} required />
          </label>
          <label>
            Язык
            <input value={language} onChange={(event) => setLanguage(event.target.value)} required />
          </label>
          <label>
            Сайт
            <select value={siteId} onChange={(event) => setSiteId(event.target.value)}>
              <option value="">Не выбран</option>
              {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
            </select>
          </label>
          <label>
            AI Provider
            <select value={providerId} onChange={(event) => setProviderId(event.target.value)}>
              <option value="">Stub generator</option>
              {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
            </select>
          </label>
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
          <label className="wide">
            Темы, каждая с новой строки
            <textarea value={topics} onChange={(event) => setTopics(event.target.value)} required rows={8} placeholder="best online casinos in Germany" />
          </label>
          <div className="formActions wide">
            <button className="button primary" type="submit"><Plus size={18} /> Создать и сгенерировать</button>
          </div>
        </form>
      </DataPanel>
      <DataPanel title="Все задачи">
        <ResponsiveTable columns={["Задача", "Гео", "Язык", "Формат", "Тем", "Статус"]} rows={tasks.map((task) => [task.title, task.geo, task.language, humanPayloadMode(task.payload_mode), task.topics_count, <StatusBadge status={task.status} />])} />
      </DataPanel>
    </section>
  );
}

function ContentView({ api, content, onChanged }: ViewProps & { content: ContentItem[] }) {
  async function approve(id: string) {
    await api(`/content/${id}/approve`, { method: "POST" });
    onChanged();
  }

  return (
    <DataPanel title="Контент">
      <ResponsiveTable
        columns={["Тема", "Slug", "Слова", "Статус", "Действие"]}
        rows={content.map((item) => [
          <TopicMetaCell item={item} />,
          item.slug,
          item.word_count,
          <StatusBadge status={item.status} />,
          <button className="button compact" onClick={() => approve(item.id)} disabled={item.status === "approved" || item.status === "scheduled" || item.status === "published"}>Approve</button>
        ])}
      />
    </DataPanel>
  );
}

function PublicationsView({ api, sites, content, onChanged }: ViewProps & { sites: Site[]; content: ContentItem[] }) {
  const [name, setName] = React.useState("Daily publication");
  const [siteId, setSiteId] = React.useState("");
  const [interval, setIntervalValue] = React.useState(1440);
  const approved = content.filter((item) => item.status === "approved" && (!siteId || item.site_id === siteId));

  async function createCampaign(event: React.FormEvent) {
    event.preventDefault();
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
    onChanged();
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
            <select value={siteId} onChange={(event) => setSiteId(event.target.value)} required>
              <option value="">Выберите сайт</option>
              {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
            </select>
          </label>
          <label>
            Интервал, минут
            <input type="number" value={interval} onChange={(event) => setIntervalValue(Number(event.target.value))} min={5} />
          </label>
          <div className="formActions wide">
            <button className="button primary" type="submit" disabled={!approved.length || !siteId}><Play size={18} /> Запланировать approved ({approved.length})</button>
          </div>
        </form>
      </DataPanel>
      <DataPanel title="Готово к публикации">
        <ResponsiveTable columns={["Тема", "Статус", "Slug"]} rows={approved.map((item) => [<TopicMetaCell item={item} />, <StatusBadge status={item.status} />, item.slug])} />
      </DataPanel>
    </section>
  );
}

function ProvidersView({ api, providers, onChanged }: ViewProps & { providers: AiProvider[] }) {
  const [name, setName] = React.useState("Gemini");
  const [providerType, setProviderType] = React.useState<"custom" | "gemini">("gemini");
  const [endpointUrl, setEndpointUrl] = React.useState("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
  const [model, setModel] = React.useState("gemini-3.5-flash");
  const [apiKey, setApiKey] = React.useState("");
  const [validatingId, setValidatingId] = React.useState<string | null>(null);

  async function createProvider(event: React.FormEvent) {
    event.preventDefault();
    await api("/ai-providers", {
      method: "POST",
      body: JSON.stringify({ name, provider_type: providerType, endpoint_url: endpointUrl, model, api_key: apiKey || null })
    });
    setName("Gemini");
    setProviderType("gemini");
    setEndpointUrl("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
    setModel("gemini-3.5-flash");
    setApiKey("");
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
      <DataPanel title="Подключить AI API / tunnel">
        <form className="formGrid" onSubmit={createProvider}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder="Gemini" />
          </label>
          <label>
            Тип API
            <select
              value={providerType}
              onChange={(event) => {
                const nextType = event.target.value as "custom" | "gemini";
                setProviderType(nextType);
                if (nextType === "gemini") {
                  setName((value) => value || "Gemini");
                  setEndpointUrl("https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent");
                  setModel("gemini-3.5-flash");
                }
              }}
            >
              <option value="gemini">Gemini</option>
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
          <label>
            API key
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" />
          </label>
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

function KpiCard({ icon, label, value, danger }: { icon: React.ReactNode; label: string; value: number; danger?: boolean }) {
  return <div className={`kpiCard ${danger ? "danger" : ""}`}><div className="kpiIcon">{icon}</div><span>{label}</span><strong>{value}</strong></div>;
}

function DataPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="dataPanel"><div className="panelHeader"><h2>{title}</h2></div>{children}</section>;
}

function ResponsiveTable({ columns, rows }: { columns: string[]; rows: React.ReactNode[][] }) {
  if (!rows.length) return <EmptyState text="Данных пока нет." />;
  return (
    <div className="tableWrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td data-label={columns[cellIndex]} key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
      </table>
    </div>
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
  return (
    <div className="topicMetaCell">
      <strong>{item.topic}</strong>
      <PromptBadge name={generationPrompt} />
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
      topics: "Рабочий экран: темы",
      prompts: "Рабочий экран: промпты",
      content: "Рабочий экран: контент",
      publication: "Рабочий экран: публикация",
      menu: "Рабочий экран: меню"
    };
    return tabTitles[workspaceTab];
  }

  const titles: Record<Exclude<AppView, "workspace">, string> = {
    dashboard: "Dashboard",
    tasks: "Задачи генерации",
    content: "Контент",
    publications: "Публикации",
    providers: "AI Providers",
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
  return "Custom";
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

function contentItemTitle(item: ContentItem) {
  const pages = item.generated_json.pages;
  if (Array.isArray(pages) && pages[0] && typeof pages[0] === "object" && "title" in pages[0]) {
    return String((pages[0] as { title?: unknown }).title || item.topic);
  }
  return item.topic;
}

function contentItemPreviewText(item: ContentItem) {
  const pages = item.generated_json.pages;
  if (!Array.isArray(pages) || !pages[0] || typeof pages[0] !== "object") {
    return JSON.stringify(item.generated_json, null, 2);
  }
  const page = pages[0] as { description?: unknown; content?: { blocks?: Array<Record<string, unknown>> } };
  const lines: string[] = [];
  if (page.description) lines.push(String(page.description));
  for (const block of page.content?.blocks || []) {
    const data = block.data as Record<string, unknown> | undefined;
    if (block.type === "header" && data?.text) lines.push(`\n${String(data.text)}`);
    if (block.type === "paragraph" && data?.text) lines.push(String(data.text));
    if (block.type === "list" && Array.isArray(data?.items)) {
      lines.push((data.items as unknown[]).map((itemText) => `- ${String(itemText)}`).join("\n"));
    }
    if (block.type === "table" && Array.isArray(data?.content)) {
      lines.push((data.content as unknown[]).map((row) => Array.isArray(row) ? row.map(String).join(" | ") : String(row)).join("\n"));
    }
    if (block.type === "faq" && Array.isArray(data)) {
      lines.push(data.map((entry) => {
        const faq = entry as { question?: unknown; answer?: unknown };
        return `Q: ${String(faq.question || "")}\nA: ${String(faq.answer || "")}`;
      }).join("\n\n"));
    }
  }
  return lines.join("\n\n").replace(/<[^>]+>/g, "").trim() || JSON.stringify(item.generated_json, null, 2);
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
