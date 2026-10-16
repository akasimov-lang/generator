import React from "react";
import { Globe2 } from "lucide-react";
import icons from "./brandIcons.json";

export function BrandIcon({ brand }: { brand: string }) {
  const key = brand.normalize("NFKC").toLowerCase().replace(/[^a-z0-9]/g, "");
  const source = (icons as Record<string, string>)[key];
  const [failedSource, setFailedSource] = React.useState<string | null>(null);
  const general = !brand || brand === "Общие ключи" || brand === "Бренд не указан";
  return <span className="brandTableIcon" aria-hidden="true">
    {!general && source && failedSource !== source
      ? <img src={source} alt="" width={20} height={20} loading="lazy" onError={() => setFailedSource(source)} />
      : general ? <Globe2 size={18} /> : <span>{brand.trim().slice(0, 2).toUpperCase()}</span>}
  </span>;
}
