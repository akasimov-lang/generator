import React from "react";
import { LoaderCircle } from "lucide-react";
import { editActive, type NetworkEditItem } from "./networkEditQueue";

export function NetworkEditStatus({item, retry}: {item?: NetworkEditItem; retry: (id:string)=>void}) {
  if (!item) return null;
  return <small className={`networkEditStatus${item.status === "failed" ? " error" : ""}`} role={item.status === "failed" ? "alert" : "status"}>
    {editActive(item) && <LoaderCircle size={12} className="spin" aria-hidden="true" />}
    {item.message}
    {item.status === "unconfirmed" && <button type="button" className="button secondary compact" onClick={()=>retry(item.id)}>Проверить отправку</button>}
  </small>;
}
