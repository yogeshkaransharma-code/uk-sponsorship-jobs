"use strict";
let jobs=[],sponsors={},query="",filter="all",industryFilter="all",functionFilter="all",levelFilter="all",page=1;
const PAGE_SIZE=30;
const escapeHtml=s=>String(s??"").replace(/[&<>"']/g,c=>c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c.charCodeAt(0)===34?"&quot;":"&#39;");
const safeUrl=s=>{try{const url=new URL(s);return url.protocol==="https:"?url.href:"#"}catch{return "#"}};
const prettyDate=s=>{if(!s)return "Not yet checked";const d=new Date(String(s).slice(0,10)+"T12:00:00");return Number.isNaN(d.getTime())?"Not yet checked":d.toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})};
function companyData(j){return sponsors[j.legal_name||j.company]||sponsors[j.company]||{}}

let locationFilter="",salaryFilter="all",postedFilter="all";
const licenseInfo=j=>companyData(j).status==="verified";
const quotedEvidence=j=>(j.sponsorship==="stated"||j.sponsorship==="conditional")&&j.evidence;
function salaryFloor(value){
  if(!value||value==="Not disclosed")return null;
  const text=String(value).replace(/,/g,"");
  const match=text.match(/£\s*(\d+(?:\.\d+)?)\s*([kK])?/);
  if(!match)return null;
  let n=Number(match[1])*(match[2]?1000:1);
  if(n<1000)return null;
  // Hourly, daily and weekly amounts cannot be compared with annual salary.
  if(/\b(hour|hourly|day|daily|week|weekly|month|monthly)\b/i.test(text))return null;
  return n;
}
function postedWithin(j,days){
  const value=j.posted_at;
  if(!value||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
  const at=Date.parse(value+"T00:00:00Z");
  const age=Date.now()-at;
  return Number.isFinite(at)&&age>=-86400000&&age<=Number(days)*86400000;
}
function matchesJob(j){
  if(j.active===false||j.sponsorship==="unavailable")return false;
  if(filter==="stated"&&j.sponsorship!=="stated")return false;
  if(filter==="conditional"&&j.sponsorship!=="conditional")return false;
  if(filter==="verified"&&!licenseInfo(j))return false;
  if(industryFilter!=="all"&&j.industry!==industryFilter)return false;
  if(functionFilter!=="all"&&j.job_function!==functionFilter)return false;
  if(levelFilter!=="all"&&j.experience_level!==levelFilter)return false;
  if(locationFilter&&!String(j.location||"").toLowerCase().includes(locationFilter))return false;
  if(salaryFilter!=="all"){
    const salary=salaryFloor(j.salary);
    if(salary===null||salary<Number(salaryFilter))return false;
  }
  if(postedFilter!=="all"&&!postedWithin(j,postedFilter))return false;
  if(query&&!([j.title,j.company,j.location,j.job_function,j.industry,j.summary,j.description_excerpt]
    .join(" ").toLowerCase().includes(query)))return false;
  return true;
}
function renderCard(j){
  const url=escapeHtml(safeUrl(j.apply_url||j.evidence_url));
  const name=escapeHtml(j.company||"Employer");
  const title=escapeHtml(j.title||"Vacancy");
  const city=escapeHtml(j.location||"UK location not specified");
  const pay=j.salary&&j.salary!=="Not disclosed"?'<span>'+escapeHtml(j.salary)+'</span>':"";
  const status=j.sponsorship;
  const evidenceTag=status==="stated"
    ?'<span class="status stated">Sponsorship stated in advert</span>'
    :status==="conditional"
      ?'<span class="status conditional">Case by case</span>'
      :licenseInfo(j)?'<span class="status stated">Skilled Worker licence verified</span>':"";
  // Never show an unverified licence as "pending" or a fabricated history of sponsorship.
  const credit=j.posting_attribution?.text
    ?'<div class="source-credit">Source: '+escapeHtml(j.posting_attribution.text)+
      ' · <a target="_blank" rel="noopener noreferrer" href="'+escapeHtml(safeUrl(j.posting_attribution.link))+'">Details ↗</a></div>'
    :"";
  const excerpt=String(j.description_excerpt||"").trim();
  let description="";
  if(excerpt){
    description='<div class="role-summary"><span class="evidence-label">From the job advert</span>'+
      '<p>'+escapeHtml(excerpt)+'</p></div>';
  } else {
    description='<p class="role-missing">Job description not in our current data. Read the original employer advert for responsibilities and requirements.</p>';
  }
  const h=companyData(j).history||[];
  const source=j.evidence_source||"Employer listing";
  const verified=licenseInfo(j)?
    '<p><strong>Employer:</strong> Skilled Worker licence verified against the Home Office register. Not a guarantee for this vacancy.</p>':"";
  const history=h.length?
    '<p><strong>Historical sponsorship:</strong> independently sourced records available.</p>':"";
  const evidence=quotedEvidence(j)?
    '<p><strong>Advert sponsorship wording (automatically detected):</strong> '+escapeHtml(j.evidence)+'</p>':"";
  const details=evidence||verified||history?
    '<details class="extra"><summary>Sponsorship details</summary><div class="more">'+
    evidence+verified+history+'<p>Advert checked: '+escapeHtml(prettyDate(j.verified_on))+
    '. See the original advert to confirm current eligibility.</p></div></details>':"";
  return '<article class="job"><div class="job-top"><div class="job-title-area"><div class="company">'+name+
    '</div><h3>'+title+'</h3><div class="job-meta"><span>'+city+'</span>'+pay+'</div></div>'+
    evidenceTag+'</div>'+description+credit+'<div class="job-bottom">'+details+
    '<a class="apply" href="'+url+'" target="_blank" rel="noopener noreferrer">'+
    (excerpt?'Read full advert & apply ↗':'Read job description & apply ↗')+'</a></div></article>';
}
function render(){
  const matched=jobs.filter(matchesJob);
  const visible=matched.slice(0,PAGE_SIZE*page);
  const el=document.getElementById("jobs");
  document.getElementById("result-count").textContent=matched.length.toLocaleString("en-GB")+
    (matched.length===1?" job":" jobs");
  el.innerHTML=visible.length?visible.map(renderCard).join("")+
    (visible.length<matched.length?'<button type="button" id="load-more" class="load-more">Show more jobs</button>':"")
    :'<div class="notice">No matching jobs. Try a broader search or clear the filters.</div>';
}
function populateFilter(id,key){
  const el=document.getElementById(id);
  if(!el)return;
  const values=[...new Set(jobs.filter(j=>j.active!==false&&j.sponsorship!=="unavailable")
    .map(j=>j[key]).filter(v=>v&&v!=="Other / unclassified"&&v!=="Not classified"&&v!=="Not specified"))].sort();
  for(const value of values){const opt=document.createElement("option");opt.value=value;opt.textContent=value;el.add(opt);}
}
function prepareFilters(){
  populateFilter("industry-filter","industry");
  populateFilter("function-filter","job_function");
  populateFilter("level-filter","experience_level");
}
function wireFilters(){
  const setter=(id,callback)=>{const el=document.getElementById(id);if(el)el.addEventListener("input",event=>{
    callback(event.target.value);page=1;render();
  });};
  setter("search",v=>query=v.toLowerCase().trim());
  setter("location-filter",v=>locationFilter=v.toLowerCase().trim());
  setter("industry-filter",v=>industryFilter=v);
  setter("function-filter",v=>functionFilter=v);
  setter("level-filter",v=>levelFilter=v);
  setter("salary-filter",v=>salaryFilter=v);
  setter("posted-filter",v=>postedFilter=v);
  setter("sponsorship-filter",v=>filter=v);
  document.getElementById("reset-filters")?.addEventListener("click",()=>{
    for(const id of ["search","location-filter"])document.getElementById(id).value="";
    for(const id of ["industry-filter","function-filter","level-filter","salary-filter","posted-filter","sponsorship-filter"])
      document.getElementById(id).value="all";
    query="";locationFilter="";industryFilter="all";functionFilter="all";levelFilter="all";
    salaryFilter="all";postedFilter="all";filter="all";page=1;render();
  });
  document.getElementById("jobs").addEventListener("click",e=>{
    if(e.target.id==="load-more"){page++;render();}
  });
}

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
sponsors=b.companies||{};const credit=document.getElementById("headcount-credit");if(credit&&jobs.some(j=>j.source_attribution==="Headcount Labs"))credit.hidden=false;const communityCredit=document.getElementById("community-credit");if(communityCredit&&jobs.some(j=>String(j.source_attribution||"").includes("ConorsCode")))communityCredit.hidden=false;prepareFilters();wireFilters();document.getElementById("last-reviewed").textContent=(a.mode==="automated"?"Job feeds checked ":"Editorial examples reviewed ")+prettyDate(a.updated_at)+(b.updated_at?" · register checked "+prettyDate(b.updated_at):" · register sync pending")+(a.mode==="automated"?" · feed checks may be delayed":" · live availability not yet checked");render()}catch(err){document.getElementById("jobs").innerHTML='<div class="notice">The listings could not be loaded. For local development, start a web server rather than opening this directory using file://.</div>';document.getElementById("last-reviewed").textContent="Data connection unavailable"}}init();
