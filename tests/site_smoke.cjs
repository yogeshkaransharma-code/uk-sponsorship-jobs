// Smoke-test SponsorHQ job search without a browser or paid data sources.
"use strict";
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const site=fs.readFileSync("site.js","utf8").replace(/init\(\);\s*$/,"");
const cx=vm.createContext({URL,Date});
const {sectorForJob,renderCard,matchesJob}=vm.runInContext(site+"\n({sectorForJob,renderCard,matchesJob})",cx);
const fallback="Other / unclassified";
for(const [title,expected] of [
 ["Registered Nurse","Healthcare & Social Care"],
 ["Secondary School Teacher","Education"],
 ["Warehouse Operative","Logistics & Transport"],
 ["Chef de Partie","Hospitality & Tourism"],
 ["Paralegal","Legal"],
 ["Retail Store Assistant","Retail & Consumer"],
 ["Site Manager - Construction","Construction & Property"],
 ["Software Developer","Technology & IT"],
]) assert.equal(sectorForJob({title,industry:fallback}),expected,title);
assert.equal(sectorForJob({title:"Account Executive",industry:"Insurance"}),"Insurance");
const base={active:true,title:"Insurance Claims Handler",company:"Example Ltd",location:"Manchester",
 salary:"£38,000",sponsorship:"unknown",industry:"Other / unclassified",job_function:"Insurance & Claims",
 experience_level:"Not specified",apply_url:"https://jobs.example.org/123"};
const unknown=renderCard(base);
assert.match(unknown,/Visa sponsorship: not confirmed for this vacancy/);
assert.doesNotMatch(unknown,/Licence match pending|Sponsorship details|Past sponsorship/);
assert.match(unknown,/Read full job advert/);
const stated=renderCard({...base,sponsorship:"stated",evidence:"We offer visa sponsorship for this role.",
 description_excerpt:"You will handle commercial insurance claims."});
assert.match(stated,/Visa sponsorship: stated in advert/);
assert.match(stated,/We offer visa sponsorship for this role/);
assert.match(stated,/You will handle commercial insurance claims/);
vm.runInContext('filter="stated"',cx);
assert.equal(matchesJob(base),false);
assert.equal(matchesJob({...base,sponsorship:"stated"}),true);
assert.equal(matchesJob({...base,sponsorship:"unavailable"}),false);
vm.runInContext('filter="all";industryFilter="Healthcare & Social Care"',cx);
assert.equal(matchesJob({...base,_sector:"Healthcare & Social Care"}),true);
assert.equal(matchesJob({...base,_sector:"Insurance"}),false);
console.log("SponsorHQ search, industries and upfront sponsorship: smoke tests passed");
