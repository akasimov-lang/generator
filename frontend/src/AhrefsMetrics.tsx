import React from 'react';
import {metricCount,metricForDomain,metricTitle,type DomainMetricsMap} from './domainMetrics';
export function DomainMetrics({domain,metrics}:{domain:string;metrics:DomainMetricsMap}) {const value=metricForDomain(metrics,domain);if(!value)return null;return <span className="domainMetrics" title={metricTitle(value)} aria-label={metricTitle(value)}><span>DR <b>{metricCount(value.dr)}</b></span><span>BL <b>{metricCount(value.backlinks_all,true)}</b></span><span>RD <b>{metricCount(value.referring_domains_all,true)}</b></span></span>;}
