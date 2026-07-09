import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  Globe2,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Play,
  Plus,
  RefreshCcw,
  Send,
  Settings,
  ShieldCheck,
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
  geo: string;
  language: string;
  payload_mode: string;
  topics_count: number;
  status: string;
  created_at: string;
};

type ContentItem = {
  id: string;
  topic: string;
  slug: string;
  status: string;
  word_count: number;
  scheduled_at: string | null;
  published_url: string | null;
  generated_json: Record<string, unknown>;
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

type AiProvider = {
  id: string;
  name: string;
  endpoint_url: string;
  model: string;
  is_active: boolean;
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

const API_BASE = "/api";

function App() {
  const [token, setToken] = React.useState(() => localStorage.getItem("admin_token") || "");
  const [activeView, setActiveView] = React.useState("dashboard");
  const [dashboard, setDashboard] = React.useState<Dashboard | null>(null);
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [content, setContent] = React.useState<ContentItem[]>([]);
  const [sites, setSites] = React.useState<Site[]>([]);
  const [providers, setProviders] = React.useState<AiProvider[]>([]);
  const [currentUser, setCurrentUser] = React.useState<User | null>(null);
  const [users, setUsers] = React.useState<User[]>([]);
  const [message, setMessage] = React.useState("");

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
    const [nextDashboard, nextTasks, nextContent, nextSites, nextProviders] = await Promise.all([
      api<Dashboard>("/dashboard"),
      api<Task[]>("/tasks"),
      api<ContentItem[]>("/content"),
      api<Site[]>("/sites"),
      api<AiProvider[]>("/ai-providers")
    ]);
    const nextUsers = nextUser.is_admin ? await api<User[]>("/users") : [];
    setCurrentUser(nextUser);
    setDashboard(nextDashboard);
    setTasks(nextTasks);
    setContent(nextContent);
    setSites(nextSites);
    setProviders(nextProviders);
    setUsers(nextUsers);
  }, [api, token]);

  React.useEffect(() => {
    loadAll().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Не удалось загрузить данные"));
  }, [loadAll]);

  if (!token) {
    return <LoginScreen onLogin={setToken} />;
  }

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
          <NavButton icon={<LayoutDashboard />} label="Dashboard" active={activeView === "dashboard"} onClick={() => setActiveView("dashboard")} />
          <NavButton icon={<ListChecks />} label="Задачи" active={activeView === "tasks"} onClick={() => setActiveView("tasks")} />
          <NavButton icon={<FileText />} label="Контент" active={activeView === "content"} onClick={() => setActiveView("content")} />
          <NavButton icon={<Send />} label="Публикации" active={activeView === "publications"} onClick={() => setActiveView("publications")} />
          <NavButton icon={<Bot />} label="AI Providers" active={activeView === "providers"} onClick={() => setActiveView("providers")} />
          <NavButton icon={<Globe2 />} label="Сайты" active={activeView === "sites"} onClick={() => setActiveView("sites")} />
          <NavButton icon={<Settings />} label="Настройки" active={activeView === "settings"} onClick={() => setActiveView("settings")} />
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">Рабочая панель</p>
            <h1>{viewTitle(activeView)}</h1>
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

        {activeView === "dashboard" && dashboard && <DashboardView dashboard={dashboard} tasks={tasks} content={content} />}
        {activeView === "tasks" && <TasksView api={api} sites={sites} providers={providers} tasks={tasks} onChanged={loadAll} />}
        {activeView === "content" && <ContentView api={api} content={content} onChanged={loadAll} />}
        {activeView === "publications" && <PublicationsView api={api} sites={sites} content={content} onChanged={loadAll} />}
        {activeView === "providers" && <ProvidersView api={api} providers={providers} onChanged={loadAll} />}
        {activeView === "sites" && <SitesView api={api} sites={sites} onChanged={loadAll} />}
        {activeView === "settings" && <SettingsView api={api} currentUser={currentUser} users={users} onChanged={loadAll} />}
      </main>
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
            Создавать TOC
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
          item.topic,
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
  const approved = content.filter((item) => item.status === "approved");

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
        <ResponsiveTable columns={["Тема", "Статус", "Slug"]} rows={approved.map((item) => [item.topic, <StatusBadge status={item.status} />, item.slug])} />
      </DataPanel>
    </section>
  );
}

function ProvidersView({ api, providers, onChanged }: ViewProps & { providers: AiProvider[] }) {
  const [name, setName] = React.useState("");
  const [endpointUrl, setEndpointUrl] = React.useState("");
  const [model, setModel] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");

  async function createProvider(event: React.FormEvent) {
    event.preventDefault();
    await api("/ai-providers", {
      method: "POST",
      body: JSON.stringify({ name, endpoint_url: endpointUrl, model, api_key: apiKey || null })
    });
    setName("");
    setEndpointUrl("");
    setModel("");
    setApiKey("");
    onChanged();
  }

  return (
    <section className="viewStack">
      <DataPanel title="Подключить AI API / tunnel">
        <form className="formGrid" onSubmit={createProvider}>
          <label>
            Название
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder="OpenAI tunnel" />
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
      <DataPanel title="AI Providers">
        <ResponsiveTable columns={["Название", "Endpoint", "Модель", "Активен"]} rows={providers.map((provider) => [provider.name, provider.endpoint_url, provider.model, provider.is_active ? "Да" : "Нет"])} />
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

function NavButton({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return <button className={`navButton ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{label}</span></button>;
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

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status.replaceAll("_", "-")}`}>{status}</span>;
}

function RoleBadge({ admin }: { admin: boolean }) {
  return <span className={`roleBadge ${admin ? "admin" : ""}`}>{admin ? "Администратор" : "Пользователь"}</span>;
}

function viewTitle(view: string) {
  const titles: Record<string, string> = {
    dashboard: "Dashboard",
    tasks: "Задачи генерации",
    content: "Контент",
    publications: "Публикации",
    providers: "AI Providers",
    sites: "Сайты",
    settings: "Настройки"
  };
  return titles[view] || "Dashboard";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function humanPayloadMode(value: string) {
  if (value === "full_site") return "Full site";
  if (value === "simple_page") return "Simple page";
  return "Site default";
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
