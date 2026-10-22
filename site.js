"use strict";
let jobs=[],sponsors={},query="",filter="all",industryFilter="all",functionFilter="all",levelFilter="all",page=1;
const PAGE_SIZE=30;
const escapeHtml=s=>String(s??"").replace(/[&<>"']/g,c=>c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c.charCodeAt(0)===34?"&quot;":"&#39;");
const safeUrl=s=>{try{const url=new URL(s);return url.protocol==="https:"?url.href:"#"}catch{return "#"}};
const prettyDate=s=>{if(!s)return "Not yet checked";const d=new Date(String(s).slice(0,10)+"T12:00:00");return Number.isNaN(d.getTime())?"Not yet checked":d.toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})};
const labels={stated:"Sponsorship stated",conditional:"Case by case",potential:"Potential",unknown:"Not stated",unavailable:"Not offered"};
function companyData(j){return sponsors[j.legal_name||j.company]||sponsors[j.company]||{}}
function license(j){const c=companyData(j);if(c.status==="verified")return "Skilled Worker · matched";if(c.status==="name_only")return "Possible register match · check entity";return "Licence match pending"}
function historic(j){const h=companyData(j).history||[];return h.length?"Historical CoS evidence available":"No sourced history yet"}
function historyText(j){const h=companyData(j).history||[];return h.length?"<ul>"+h.map(x=>`<li>${escapeHtml(x.value)} ${escapeHtml(x.metric)}, ${escapeHtml(x.period)}, ${escapeHtml(x.route)} — <a target="_blank" rel="noopener noreferrer" href="${escapeHtml(safeUrl(x.source_url))}">source ↗</a></li>`).join("")+"</ul>":"Employer-level CoS figures have not been verified for this legal entity. Missing data does not mean zero sponsorship."}
function render(){const matches=jobs.filter(j=>j.active!==false&&(filter==="all"||j.sponsorship===filter)&&(industryFilter==="all"||j.industry===industryFilter)&&(functionFilter==="all"||j.job_function===functionFilter)&&(levelFilter==="all"||j.experience_level===levelFilter)&&[j.title,j.company,j.location,j.category,j.summary,j.industry,j.job_function].join(" ").toLowerCase().includes(query));const shown=matches.slice(0,PAGE_SIZE*page);document.getElementById("result-count").textContent=matches.length+" "+(matches.length===1?"role":"roles");document.getElementById("jobs").innerHTML=matches.length?shown.map(j=>{const status=["stated","conditional","potential","unavailable"].includes(j.sponsorship)?j.sponsorship:"unknown";return `<article class="job"><div class="job-top"><div><div class="company">${escapeHtml(j.company)}</div><h3>${escapeHtml(j.title)}</h3><div class="job-meta"><span>${escapeHtml(j.location||"Location not specified")}</span><span class="bullet">·</span><span>${escapeHtml(j.salary||"Salary not disclosed")}</span></div></div><span class="status ${status}">${labels[status]}</span></div><div class="evidence ${status==="potential"||status==="unknown"?"unverified":""}"><span class="evidence-label">What the advert says</span>${status==="unknown"?"No explicit sponsorship promise or refusal identified in the advert.":j.evidence?`<q>${escapeHtml(j.evidence)}</q>`:"Sponsorship evidence not available."}</div><div class="job-facts"><div><span class="fact-label">Sponsor licence</span><span class="fact-text">${escapeHtml(license(j))}</span></div><div><span class="fact-label">Past sponsorship</span><span class="fact-text">${escapeHtml(historic(j))}</span></div></div>${j.posting_attribution?.text?`<p class="source-credit">Source credit: ${escapeHtml(j.posting_attribution.text)} · <a href="${escapeHtml(safeUrl(j.posting_attribution.link))}" target="_blank" rel="noopener noreferrer">Original source ↗</a></p>`:""}<div class="job-bottom"><details class="extra"><summary>Evidence &amp; verification details</summary><div class="more">Checked: ${escapeHtml(prettyDate(j.verified_on))}<br>Listing status: ${j.active===true?"Seen on a recent employer feed":j.active===false?"No longer found":"Current opening not yet confirmed"}<br>Licence source: <a href="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers" target="_blank" rel="noopener noreferrer">Home Office register ↗</a> · Licence checked: ${escapeHtml(prettyDate(companyData(j).checked_on))}<br>Employer match basis: ${escapeHtml(companyData(j).match_basis||"Awaiting confirmed legal entity")}<br>Historical CoS evidence: ${historyText(j)}A sponsor licence or historical CoS assignment does not prove this job will sponsor a visa. ${j.review==="auto"?"<strong>Automatically detected text: context requires review.</strong>":""}</div></details><a class="apply" href="${escapeHtml(safeUrl(j.apply_url||j.evidence_url))}" target="_blank" rel="noopener noreferrer">View role &amp; apply ↗</a></div></article>`}).join("")+(shown.length<matches.length?`<button type="button" id="load-more" class="load-more">Show more jobs (${matches.length-shown.length} remaining)</button>`:""):`<div class="notice">No jobs match those filters. Try a different role, company or sponsorship type.</div>`}
document.getElementById("search").addEventListener("input",e=>{query=e.target.value.trim().toLowerCase();page=1;render()});document.getElementById("sponsorship-filter").addEventListener("change",e=>{filter=e.target.value;page=1;render()});
function prepareFilters(){
  const configs=[["industry-filter","industry",v=>v],["function-filter","job_function",v=>v],["level-filter","experience_level",v=>v]];
  for(const [id,key] of configs){
    const el=document.getElementById(id);
    if(!el)continue;
    const names=[...new Set(jobs.filter(j=>j.active!==false).map(j=>j[key]).filter(Boolean))].sort();
    for(const name of names){const opt=document.createElement("option");opt.value=name;opt.textContent=name;el.append(opt);}
  }
}
for(const [id,fn] of [["industry-filter",v=>industryFilter=v],["function-filter",v=>functionFilter=v],["level-filter",v=>levelFilter=v]]){
  document.getElementById(id)?.addEventListener("change",e=>{fn(e.target.value);page=1;render()});
}
document.getElementById("jobs").addEventListener("click",e=>{if(e.target.id==="load-more"){page++;render();}});

async function init(){try{let a,b;if(window.__PREVIEW_DATA__){a=window.__PREVIEW_DATA__.jobs;b=window.__PREVIEW_DATA__.sponsors}else{const [r1,r2]=await Promise.all([fetch("./data/jobs.json",{cache:"no-store"}),fetch("./data/sponsors.json",{cache:"no-store"})]);if(!r1.ok)throw new Error("Jobs not available");a=await r1.json();b=r2.ok?await r2.json():{companies:{}}}jobs=Array.isArray(a.jobs)?a.jobs:[];
if(Array.isArray(a.chunks)&&a.chunks.length){
  document.getElementById("last-reviewed").textContent="Loading the UK jobs catalogue…";
  const pages=await Promise.all(a.chunks.map(async name=>{
    if(typeof name!=="string"||!/^\.\/data\/jobs\/chunk-\d{3}\.json$/.test(name))throw new Error("Invalid job chunk reference");
    const response=await fetch(name,{cache:"no-store"});
    if(!response.ok)throw new Error("One job-data chunk is unavailable");
    const payload=await response.json();
    if(!Array.isArray(payload.jobs))throw new Error("Incorrect job-data format");
    return payload.jobs;
  }));
  for(const pageJobs of pages)jobs.push(...pageJobs);
}
sponsors=b.companies||{};const credit=document.getElementById("headcount-credit");if(credit&&jobs.some(j=>j.source_attribution==="Headcount Labs"))credit.hidden=false;const communityCredit=document.getElementById("community-credit");if(communityCredit&&jobs.some(j=>String(j.source_attribution||"").includes("ConorsCode")))communityCredit.hidden=false;prepareFilters();document.getElementById("last-reviewed").textContent=(a.mode==="automated"?"Job feeds checked ":"Editorial examples reviewed ")+prettyDate(a.updated_at)+(b.updated_at?" · register checked "+prettyDate(b.updated_at):" · register sync pending")+(a.mode==="automated"?" · feed checks may be delayed":" · live availability not yet checked");render()}catch(err){document.getElementById("jobs").innerHTML='<div class="notice">The listings could not be loaded. For local development, start a web server rather than opening this directory using file://.</div>';document.getElementById("last-reviewed").textContent="Data connection unavailable"}}init();
