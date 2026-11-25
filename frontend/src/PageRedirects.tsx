export type PageRedirectGroup = {domain:string;redirects:{url:string;value:string}[]};
export type PageRedirectEdit = {expected?:{rows:{url:string;value:string}[]};page_redirect_domain:string;page_redirect_source:string;page_redirect_target:string;page_redirect_original_domain:string;page_redirect_original_source:string;page_redirect_delete:boolean};

export { PageRedirectWorkspace as PageRedirects } from "./PageRedirectWorkspace";
