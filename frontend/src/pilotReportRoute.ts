type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;

/** Older report links used ?id for every job kind, including maintenance reports. */
export async function maintenanceReportFallback(api:Api,id:string,error:unknown):Promise<string|null> {
 const status=(error as {statusCode?:number}|null)?.statusCode;
 if(status!==400&&status!==404)return null;
 try {
  const report=await api<{entries?:unknown}>(`/auto-reglue/maintenance-reports/${encodeURIComponent(id)}`,{cache:"no-store"});
  return Array.isArray(report?.entries)?`/auto-reglue/pilot/report?maintenance=${encodeURIComponent(id)}`:null;
 } catch { return null; }
}
