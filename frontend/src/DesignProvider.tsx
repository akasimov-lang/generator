import React from "react";

export type DesignVersion = "1.0" | "2.0";
const STORAGE_KEY = "pagepilot_design_version";
const normalizeVersion = (value: string | null): DesignVersion => value === "1.0" ? "1.0" : "2.0";

function storedVersion(): DesignVersion {
  try { return normalizeVersion(localStorage.getItem(STORAGE_KEY)); }
  catch { return "2.0"; }
}

const DesignContext = React.createContext({
  designVersion: "2.0" as DesignVersion,
  setDesignVersion: (_version: DesignVersion) => {}
});

export function DesignProvider({ children }: { children: React.ReactNode }) {
  const [designVersion, updateVersion] = React.useState<DesignVersion>(storedVersion);
  const setDesignVersion = React.useCallback((version: DesignVersion) => {
    updateVersion(version);
    try { localStorage.setItem(STORAGE_KEY, version); } catch { /* Still applies for this session. */ }
  }, []);

  React.useLayoutEffect(() => {
    document.documentElement.dataset.designVersion = designVersion;
    document.title = designVersion === "1.0" ? "AI Content panel — версия 1.0" : "PagePilot — версия 2.0";
    const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (favicon) favicon.href = designVersion === "1.0" ? "/favicon-v1.svg" : "/pagepilot-mark.svg?v=20260916";
  }, [designVersion]);

  React.useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY || event.key === null) updateVersion(storedVersion());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return <DesignContext.Provider value={{ designVersion, setDesignVersion }}>{children}</DesignContext.Provider>;
}

export const useDesign = () => React.useContext(DesignContext);
