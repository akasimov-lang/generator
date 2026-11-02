import React from "react";
import { Send, LoaderCircle, Network } from "lucide-react";
import { projectNotice } from "./projectNotificationEvents";

type Receipt = { id: string; status: string; message: string; task_id?: string; count: number; response_status?: number; error_code?: string; created_at?: string };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
const pending = (receipt: Receipt | null) => !!receipt && ["index_queued", "index_submitting"].includes(receipt.status);

export function NetworkIndexingButton({ siteId, api }: { siteId: string; api: Api }) {
  const [receipt, setReceipt] = React.useState<Receipt | null>(null);
  const [checking, setChecking] = React.useState(true);
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState("");
  const busy = React.useRef(false);
  const requestId = React.useRef<string | null>(null);
  const mounted = React.useRef(true);
  const path = `/sites/${siteId}/network/indexing`;
  React.useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  React.useEffect(() => {
    let cancelled = false;
    api<Receipt | null>(path, { cache: "no-store" }).then(value => {
      if (!cancelled) setReceipt(value);
    }).catch(cause => { if (!cancelled) setError(String(cause.message || cause)); })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [api, path]);
  React.useEffect(() => {
    if (!pending(receipt)) return;
    let cancelled = false;
    let timer: number;
    const check = async () => {
      try {
        const value = await api<Receipt | null>(path, { cache: "no-store" });
        if (cancelled) return;
        setReceipt(value); setError("");
        if (!pending(value)) return;
      } catch (cause) {
        if (cancelled) return;
        setError(cause instanceof Error ? cause.message : "Не удалось обновить состояние отправки.");
      }
      timer = window.setTimeout(check, 5000);
    };
    timer = window.setTimeout(check, 5000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [api, path, receipt?.status]);
  React.useEffect(() => {
    if (!receipt) return;
    const problem = ["failed", "index_unknown"].includes(receipt.status);
    const code = receipt.response_status ? `HTTP_${receipt.response_status}` : receipt.error_code || receipt.status.toUpperCase();
    projectNotice({ siteId, key: "network-indexing", code, message: receipt.message,
      context: `Индексация сетки${receipt.created_at ? ` · запрос от ${new Date(receipt.created_at).toLocaleString("ru-RU")}` : ""}. ${problem ? "Примечание; на результат переклея не влияет." : ""}`,
      severity: "info", active: true, persist: true });
  }, [receipt, siteId]);
  React.useEffect(() => {
    if (error) projectNotice({siteId, key: "network-indexing-request", code: "INDEXING_REQUEST_UNCONFIRMED", message: error,
      context: "Индексация сетки. HTTP-код не получен; на результат переклея не влияет.", severity: "info", active: true, persist: true});
  }, [error, siteId]);
  const submit = async () => {
    if (busy.current || pending(receipt)) return;
    busy.current = true; setSending(true); setError("");
    requestId.current ||= crypto.randomUUID();
    try {
      const value = await api<Receipt>(path, { method: "POST", body: JSON.stringify({ request_id: requestId.current }) });
      if (mounted.current) { setReceipt(value); requestId.current = null; }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Не удалось получить подтверждение отправки.");
      // Preserve the request id: a network error does not mean the server rejected the task.
    } finally {
      busy.current = false;
      if (mounted.current) setSending(false);
    }
  };
  const working = sending || pending(receipt);
  const unknown = receipt?.status === "index_unknown";
  const label = sending ? "Проверяем сетку…" : receipt?.status === "index_queued" ? "Индексация в очереди" : receipt?.status === "index_submitting" ? "Отправляем сетку…" : "Отправить сетку на индексацию";
  return <div className="networkIndexing">
    <button type="button" className="networkIndexingButton" onClick={submit} disabled={checking || working || unknown}
      aria-busy={checking || working} title={receipt?.message || "Отправить домены основной сетки на индексацию. AMP исключены."}>
      {working ? <LoaderCircle size={16} className="networkIndexingSpinner" aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}{label}
    </button>
    <small role="status" title={receipt?.message}>
      {receipt?.task_id ? `Задача ${receipt.task_id} · ${receipt.count} доменов · принята` : pending(receipt) ? `${receipt!.count} доменов` : ""}
    </small>
  </div>;
}

export function NetworkSitemapButton({siteId,api}:{siteId:string;api:Api}) {
 const [result,setResult]=React.useState<Receipt|null>(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState("");
 const sending=React.useRef(false),requestId=React.useRef<string|null>(null);
 const path=`/sites/${siteId}/network/sitemap`;
 const working=!!result&&["sitemap_queued","sitemap_writing","sitemap_verify"].includes(result.status);
 React.useEffect(()=>{let active=true;api<Receipt|null>(path).then(x=>{if(active)setResult(x);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[api,path]);
 React.useEffect(()=>{if(!working)return;let active=true;const timer=setInterval(()=>{void api<Receipt|null>(path).then(x=>{if(active)setResult(x);}).catch(e=>{if(active)setError(e.message);});},5000);return()=>{active=false;clearInterval(timer);};},[api,path,working]);
 async function update(){if(sending.current)return;sending.current=true;setBusy(true);setError("");requestId.current ||= crypto.randomUUID();try{
  const x=await api<Receipt>(path,{method:"POST",body:JSON.stringify({request_id:requestId.current})});setResult(x);requestId.current=null;
 }catch(e){setError(e instanceof Error?e.message:"Не удалось обновить sitemap");}finally{sending.current=false;setBusy(false);}}
 return <div className="networkIndexing"><button className="networkIndexingButton" type="button" onClick={()=>void update()} disabled={busy||working} title="Обновить sitemap: текущий Main и опубликованные страницы">{busy||working?<LoaderCircle size={16} className="networkIndexingSpinner"/>:<Network size={16}/>}Sitemap</button>
 <small role="status" title={error||result?.message}>{error|| (working?"Обновляем…":result?.status==="sitemap_done"?`Проверено: ${result.count} страниц`:result?.status==="sitemap_failed"?"Ошибка проверки — подробнее при наведении":"")}</small></div>;
}
