import React from "react";
import { type NetworkEditItem } from "./networkEditQueue";

export function NetworkEditStatus({item, retry}: {item?: NetworkEditItem; retry: (id:string)=>void}) {
  if (!item || item.status === "completed") return null;
  return <small className={`networkEditStatus${item.status === "failed" ? " error" : ""}`} title={item.message} role={item.status === "failed" ? "alert" : "status"}>
    {item.message}
    {item.status === "unconfirmed" && <button type="button" className="networkRetryLink" onClick={()=>retry(item.id)}>Проверить отправку</button>}
  </small>;
}
