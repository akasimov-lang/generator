import React from "react";
import { type NetworkEditItem } from "./networkEditQueue";

export function NetworkEditStatus({item, retry}: {item?: NetworkEditItem; retry: (id:string)=>void}) {
  if (!item || item.status === "completed") return null;
  const error = item.status === "failed" || item.status === "unconfirmed";
  return <small className={`networkEditStatus${error ? " error" : ""}`} title={item.message} role={error ? "alert" : "status"}>
    {item.message}
    {item.status === "unconfirmed" && <button type="button" className="networkRetryLink" onClick={()=>retry(item.id)}>Проверить отправку</button>}
  </small>;
}
