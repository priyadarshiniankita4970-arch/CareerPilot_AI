const API = "";
const $ = (id) => document.getElementById(id);
let token = localStorage.getItem("cp_token") || "";
let currentUser = JSON.parse(localStorage.getItem("cp_user") || "null");
let authMode = "login";
let toastTimer;

const safe = (value = "") => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const initials = (value = "CP") => value.trim().split(/\s+/).slice(0,2).map(s=>s[0]||"").join("").toUpperCase();
function notify(message){const t=$("toast");t.textContent=message;t.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove("show"),3200)}
function setError(id,msg){const el=$(id);el.textContent=msg;el.classList.toggle("hidden",!msg)}
async function api(path, options={}) {
  const headers = {...(options.headers||{})};
  if(token) headers.Authorization = `Bearer ${token}`;
  if(options.body && !(options.body instanceof FormData) && typeof options.body !== "string"){headers["Content-Type"]="application/json";options.body=JSON.stringify(options.body)}
  const res = await fetch(API+path,{...options,headers});
  let data={};try{data=await res.json()}catch{}
  if(!res.ok) throw new Error(data.detail || data.message || `Request failed (${res.status})`);
  return data;
}
function setSession(data){token=data.token;currentUser=data.user;localStorage.setItem("cp_token",token);localStorage.setItem("cp_user",JSON.stringify(currentUser));updateHeader()}
function clearSession(){token="";currentUser=null;localStorage.removeItem("cp_token");localStorage.removeItem("cp_user");updateHeader()}
function updateHeader(){
  $("loginOpen").classList.toggle("hidden",!!currentUser);
  $("registerOpen").classList.toggle("hidden",!!currentUser);
  $("dashboardOpen").classList.toggle("hidden",!currentUser);
  $("logoutBtn").classList.toggle("hidden",!currentUser);
  if(currentUser){$("dashboardOpen").textContent="Dashboard";}
}
$("dashboardOpen").onclick=()=>openDashboard();
function openModal(id){$(id).classList.remove("hidden");document.body.style.overflow="hidden"}
function closeModal(id){$(id).classList.add("hidden");if(!document.querySelector(".modal:not(.hidden)"))document.body.style.overflow=""}
function openAuth(mode="login",role="student"){
  authMode=mode;$("authForm").reset();setError("authError","");$("authTitle").textContent=mode==="login"?"Your next chapter awaits.":"Start your next chapter.";
  $("authDescription").textContent=mode==="login"?"Log in to continue your career journey.":"Create your profile and make your next move.";
  $("authEyebrow").textContent=mode==="login"?"WELCOME BACK":"JOIN CAREERPILOT";
  $("nameGroup").classList.toggle("hidden",mode==="login");$("roleGroup").classList.toggle("hidden",mode==="login");$("companyGroup").classList.toggle("hidden",mode==="login"||role!=="recruiter");
  $("authRole").value=role;$("authSubmit").innerHTML=mode==="login"?"Log in ↗":"Create account ↗";
  $("authSwitch").innerHTML=mode==="login"?'New to CareerPilot? <button type="button" id="switchAuth">Create an account</button>':'Already have an account? <button type="button" id="switchAuth">Log in</button>';
  $("switchAuth").onclick=()=>openAuth(mode==="login"?"register":"login",role);
  openModal("authModal");
}
$("authRole").addEventListener("change",()=>{$("companyGroup").classList.toggle("hidden",$("authRole").value!=="recruiter")});
$("loginOpen").onclick=()=>currentUser?openDashboard():openAuth("login");
$("registerOpen").onclick=()=>openAuth("register");
$("ctaRegister").onclick=()=>openAuth("register");
$("heroRecruiter").onclick=()=>openAuth("register","recruiter");
$("logoutBtn").onclick=()=>{clearSession();notify("You have logged out.");loadJobs()};
document.querySelectorAll("[data-close]").forEach(el=>el.addEventListener("click",()=>closeModal(el.dataset.close)));
$("authForm").addEventListener("submit",async e=>{
  e.preventDefault();setError("authError","");
  const mode=authMode,role=$("authRole").value;
  const payload={email:$("authEmail").value.trim(),password:$("authPassword").value};
  if(mode==="register"){payload.name=$("authName").value.trim();payload.role=role;if(role==="recruiter")payload.company=$("authCompany").value.trim()}
  const submit=$("authSubmit");submit.disabled=true;submit.textContent="Please wait…";
  try{const result=await api(mode==="login"?"/api/auth/login":"/api/auth/register",{method:"POST",body:payload});setSession(result);closeModal("authModal");notify(`Welcome${currentUser.name?" "+currentUser.name.split(" ")[0]:""}!`);await loadJobs();openDashboard()}
  catch(err){setError("authError",err.message)}
  finally{submit.disabled=false;submit.innerHTML=mode==="login"?"Log in ↗":"Create account ↗"}
});

function jobCard(job){
 const skills=(job.skills||[]).slice(0,4).map(s=>`<span>${safe(s)}</span>`).join("");
 const date=job.created_at?new Date(job.created_at).toLocaleDateString(undefined,{month:"short",day:"numeric"}):"New";
 return `<article class="job-card"><div class="job-card-top"><div class="company-mark">${safe(initials(job.company))}</div><div class="job-card-badges"><span class="job-type">${safe(job.job_type||"Full-time")}</span>${currentUser?.role==="student"?`<button class="btn btn-outline small-btn" data-savejob="${safe(job.id)}" title="Save job">♡ Save</button>`:""}</div></div><h3>${safe(job.title)}</h3><div class="job-company">${safe(job.company)}</div><div class="job-details"><span>⌖ ${safe(job.location)}</span><span>◷ ${safe(job.experience||"Fresher")}</span><span>· ${safe(date)}</span></div><p class="job-desc">${safe(job.description)}</p><div class="job-skills">${skills||"<span>Skills discussed during interview</span>"}</div><div class="job-card-footer"><span class="salary">${safe(job.salary||"Not disclosed")}</span><button class="btn btn-primary apply-btn" data-apply="${safe(job.id)}">View & apply ↗</button></div></article>`;
}
async function loadJobs(){
 const params=new URLSearchParams();if($("searchInput").value.trim())params.set("search",$("searchInput").value.trim());if($("locationInput").value.trim())params.set("location",$("locationInput").value.trim());if($("typeFilter").value)params.set("job_type",$("typeFilter").value);
 $("jobsGrid").innerHTML='<div class="empty-state"><div class="loader"></div><p>Finding opportunities…</p></div>';
 try{const data=await api("/api/jobs?"+params.toString());$("jobsCount").textContent=`${data.total} ${data.total===1?"opportunity":"opportunities"} found`;if(!data.items.length){$("jobsGrid").innerHTML='<div class="empty-state"><h3>No roles found just yet</h3><p>Try a different search, or check back soon for new opportunities.</p></div>';return}
 $("jobsGrid").innerHTML=data.items.map(jobCard).join("");document.querySelectorAll("[data-apply]").forEach(b=>b.onclick=()=>viewApply(b.dataset.apply));document.querySelectorAll("[data-savejob]").forEach(b=>b.onclick=async()=>{if(!currentUser){openAuth("login");return}try{const r=await api(`/api/jobs/${b.dataset.savejob}/save`,{method:"POST"});notify(r.message);b.textContent="✓ Saved";b.disabled=true}catch(e){notify(e.message)}})}
 catch(err){$("jobsCount").textContent="Could not load jobs";$("jobsGrid").innerHTML=`<div class="empty-state"><h3>Could not connect to CareerPilot</h3><p>${safe(err.message)}. Start the FastAPI server and make sure MongoDB is running.</p><button class="btn btn-outline" onclick="loadJobs()">Try again</button></div>`}
}
async function viewApply(id){
 try{const {job}=await api(`/api/jobs/${id}`);const modal=$("dashboardModal");$("dashboardTitle").textContent=job.title;$("dashboardWelcome").textContent=`${job.company} · ${job.location}`;let actions="";
 if(!currentUser) actions='<button class="btn btn-primary" id="jobLoginBtn">Log in to apply ↗</button>';
 else if(currentUser.role==="student") actions=`<button class="btn btn-primary" id="applyConfirm" data-job="${safe(job.id)}">Submit application ↗</button><button class="btn btn-outline" id="matchBtn" data-job="${safe(job.id)}">Check resume match</button>`;
 else actions='<p class="muted-text">Recruiter accounts can post and manage jobs from the dashboard.</p>';
 $("dashboardContent").innerHTML=`<div class="job-details"><span>⌖ ${safe(job.location)}</span><span>${safe(job.job_type)}</span><span>${safe(job.experience||"Fresher")}</span><span>${safe(job.salary||"Not disclosed")}</span></div><h3 class="dashboard-section-title">About this role</h3><p class="muted-text" style="line-height:1.8;white-space:pre-wrap">${safe(job.description)}</p><h3 class="dashboard-section-title">Skills</h3><div class="job-skills">${(job.skills||[]).map(s=>`<span>${safe(s)}</span>`).join("")||"Not specified"}</div><div class="dashboard-actions">${actions}</div><div id="matchOutput"></div>`;
 openModal("dashboardModal");
 if($("jobLoginBtn"))$("jobLoginBtn").onclick=()=>{closeModal("dashboardModal");openAuth("login")};
 if($("applyConfirm"))$("applyConfirm").onclick=async()=>{try{const d=await api(`/api/jobs/${id}/apply`,{method:"POST"});notify(d.message);$("applyConfirm").disabled=true;$("applyConfirm").textContent="Application submitted ✓"}catch(e){notify(e.message)}};
 if($("matchBtn"))$("matchBtn").onclick=async()=>{const out=$("matchOutput");out.innerHTML='<div class="loader"></div>';try{const m=await api(`/api/resume/match/${id}`);out.innerHTML=`<div class="match-result"><div class="match-score">${m.score}% match</div><p>${safe(m.message)}</p><strong class="muted-text">Matched skills</strong><div class="job-skills">${m.matched_skills.map(s=>`<span>${safe(s)}</span>`).join("")||"<span>None found yet</span>"}</div><strong class="muted-text">Skills to build</strong><div class="job-skills">${m.missing_skills.map(s=>`<span>${safe(s)}</span>`).join("")||"<span>No missing listed skills</span>"}</div></div>`}catch(e){out.innerHTML=`<p class="form-error">${safe(e.message)}</p>`}}
 }catch(e){notify(e.message)}
}
$("searchBtn").onclick=loadJobs;$("refreshJobs").onclick=loadJobs;$("searchInput").addEventListener("keydown",e=>{if(e.key==="Enter")loadJobs()});$("locationInput").addEventListener("keydown",e=>{if(e.key==="Enter")loadJobs()});$("typeFilter").onchange=loadJobs;

async function openDashboard(){
 if(!currentUser){openAuth("login");return}
 $("dashboardTitle").textContent=`Hi, ${currentUser.name.split(" ")[0]}`;$("dashboardWelcome").textContent=currentUser.role==="student"?"Your career journey, all in one place.":"Your hiring workspace, all in one place.";openModal("dashboardModal");$("dashboardContent").innerHTML='<div class="loader"></div>';
 try{
  const d=await api("/api/dashboard");
  if(currentUser.role==="student"){
   const [apps,savedJobs]=await Promise.all([api("/api/applications/mine"),api("/api/saved-jobs")]);
   $("dashboardContent").innerHTML=`<div class="dash-stats"><div class="dash-stat"><strong>${d.applications}</strong><span>Applications</span></div><div class="dash-stat"><strong>${d.jobs_available}</strong><span>Open roles</span></div><div class="dash-stat"><strong>${d.resume_uploaded?"✓":"—"}</strong><span>Resume ${d.resume_uploaded?"uploaded":"not uploaded"}</span></div></div><div class="dashboard-actions"><button class="btn btn-primary" id="uploadResumeBtn">Upload resume</button><button class="btn btn-outline" id="interviewBtn">Interview practice</button><input id="resumeFile" type="file" accept=".pdf,.docx,.txt" class="hidden"></div><div id="resumeResult"></div><h3 class="dashboard-section-title">My applications</h3><div class="dashboard-list">${apps.items.length?apps.items.map(a=>`<div class="dashboard-row"><div><strong>${safe(a.job_title)}</strong><small>${safe(a.company)} · ${safe(a.location)} · ${new Date(a.created_at).toLocaleDateString()}</small></div><span class="status">${safe(a.status)}</span></div>`).join(""):'<p class="muted-text">No applications yet. Browse opportunities and apply to a role.</p>'}</div><h3 class="dashboard-section-title">Saved jobs</h3><div class="dashboard-list">${savedJobs.items.length?savedJobs.items.map(j=>`<div class="dashboard-row"><div><strong>${safe(j.title)}</strong><small>${safe(j.company)} · ${safe(j.location)}</small></div><button class="btn btn-outline small-btn" data-unsavejob="${safe(j.id)}">Remove</button></div>`).join(''):'<p class="muted-text">Save jobs from the opportunity board to revisit them here.</p>'}</div><div id="interviewArea"></div>`;
   document.querySelectorAll("[data-unsavejob]").forEach(b=>b.onclick=async()=>{try{await api(`/api/jobs/${b.dataset.unsavejob}/save`,{method:"DELETE"});notify("Job removed from saved list.");openDashboard()}catch(e){notify(e.message)}});
   $("uploadResumeBtn").onclick=()=>$("resumeFile").click();
   $("resumeFile").onchange=async()=>{const f=$("resumeFile").files[0];if(!f)return;const fd=new FormData();fd.append("file",f);$("resumeResult").innerHTML='<p class="muted-text">Uploading and checking your resume…</p>';try{const r=await api("/api/resume/upload",{method:"POST",body:fd});$("resumeResult").innerHTML=`<div class="match-result"><strong>Resume analyzed: ${safe(r.filename)}</strong><p><b>${safe(r.quality_score)}% resume section checklist</b> · ${r.skills_count} skills found. ${safe(r.note)}</p>${(r.suggestions||[]).length?`<p>Suggestions: ${r.suggestions.map(safe).join(" ")}</p>`:""}<div class="job-skills">${r.skills.map(s=>`<span>${safe(s)}</span>`).join("")||"<span>No recognized skills found</span>"}</div></div>`;notify("Resume uploaded successfully.")}catch(e){$("resumeResult").innerHTML=`<p class="form-error">${safe(e.message)}</p>`}};
   $("interviewBtn").onclick=async()=>{const area=$("interviewArea");area.innerHTML='<div class="loader"></div>';try{const q=await api("/api/interview/questions?role=Python%20Developer&level=Beginner");area.innerHTML='<h3 class="dashboard-section-title">Interview practice · Python Developer</h3>'+q.items.map((x,i)=>`<details class="dashboard-row" style="display:block"><summary style="cursor:pointer;font-size:12px;font-weight:700">${i+1}. ${safe(x.question)}</summary><p class="muted-text" style="line-height:1.7">${safe(x.sample_answer)}</p></details>`).join("")}catch(e){area.textContent=e.message}};
   await renderStudentExtras();
  }else if(currentUser.role==="recruiter"){
   const [jobs,apps]=await Promise.all([api("/api/recruiter/jobs"),api("/api/recruiter/applications")]);
   $("dashboardContent").innerHTML=`<div class="dash-stats"><div class="dash-stat"><strong>${d.active_jobs}</strong><span>Active jobs</span></div><div class="dash-stat"><strong>${d.applications_received}</strong><span>Applications received</span></div><div class="dash-stat"><strong>${jobs.items.length}</strong><span>Total postings</span></div></div><button id="newJobBtn" class="btn btn-primary">＋ Post a job</button><h3 class="dashboard-section-title">Your job postings</h3><div class="dashboard-list">${jobs.items.length?jobs.items.map(j=>`<div class="dashboard-row"><div><strong>${safe(j.title)} ${j.is_active?"":"(Closed)"}</strong><small>${safe(j.location)} · ${j.application_count} applications</small></div><div class="inline-form"><button class="btn btn-outline small-btn" data-edit="${safe(j.id)}">Edit</button>${j.is_active?`<button class="danger-link" data-closejob="${safe(j.id)}">Close</button>`:""}</div></div>`).join(""):'<p class="muted-text">No jobs posted yet. Add your first opportunity.</p>'}</div><h3 class="dashboard-section-title">Candidates</h3><div class="dashboard-list">${apps.items.length?apps.items.map(a=>`<div class="dashboard-row"><div><strong>${safe(a.student_name)} · ${safe(a.job_title)}</strong><small>${safe(a.student_email)} · ${new Date(a.created_at).toLocaleDateString()}</small></div><select data-status="${safe(a.id)}"><option ${a.status==="Applied"?"selected":""} disabled>Applied</option>${["Reviewing","Shortlisted","Rejected","Hired"].map(s=>`<option ${a.status===s?"selected":""}>${s}</option>`).join("")}</select></div>`).join(""):'<p class="muted-text">Candidate applications will appear here.</p>'}</div>`;
   $("newJobBtn").onclick=()=>openJobForm();
   document.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>openJobForm(jobs.items.find(j=>j.id===b.dataset.edit)));
   document.querySelectorAll("[data-closejob]").forEach(b=>b.onclick=async()=>{if(!confirm("Close this job posting?"))return;try{await api(`/api/jobs/${b.dataset.closejob}`,{method:"DELETE"});notify("Job closed.");openDashboard();loadJobs()}catch(e){notify(e.message)}});
   document.querySelectorAll("[data-status]").forEach(s=>s.onchange=async()=>{try{await api(`/api/recruiter/applications/${s.dataset.status}`,{method:"PATCH",body:{status:s.value}});notify("Application status updated.")}catch(e){notify(e.message)}});
  }else{
   await renderAdminDashboard(d);
  }
 }catch(e){$("dashboardContent").innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
}

async function renderStudentExtras(){
 const host=$("dashboardContent");
 host.insertAdjacentHTML("beforeend", `
 <section class="feature-panel"><h3 class="dashboard-section-title">Recommended for you</h3><p class="muted-text">Recommendations use your resume skills and saved profile headline/summary to rank relevant roles.</p><div id="recommendationList" class="dashboard-list"><p class="muted-text">Loading recommendations…</p></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">ATS resume checker</h3><p class="muted-text">Run a structured resume checklist and optionally compare your resume keywords with a job.</p><div class="dashboard-actions"><select id="atsJob" class="roadmap-select"><option value="">General ATS checklist</option></select><button class="btn btn-outline" id="runAts">Check my resume</button></div><div id="atsResult" class="dashboard-list"><p class="muted-text">Upload a resume first, then run the check.</p></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Application success analytics</h3><p class="muted-text">Track your application pipeline and positive outcomes.</p><div id="applicationAnalytics" class="dashboard-list"><p class="muted-text">Loading your analytics…</p></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Student portfolio generator</h3><p class="muted-text">Generate a clean portfolio page from your saved resume profile.</p><div class="dashboard-actions"><button class="btn btn-outline" id="generatePortfolio">Generate portfolio preview</button><button class="btn btn-outline" id="downloadPortfolio" disabled>Download HTML portfolio</button></div><div id="portfolioPreview" class="dashboard-list"></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Notifications <span id="notificationCount" class="status">… unread</span></h3><div id="notificationList" class="dashboard-list"><p class="muted-text">Loading notifications…</p></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Resume builder</h3><p class="muted-text">Save a structured resume profile to MongoDB and export a plain-text draft.</p>
 <form id="resumeBuilderForm"><div class="form-grid">
 <div class="form-group"><label>Professional headline</label><input id="rbHeadline" maxlength="160" placeholder="MCA Student | Aspiring Software Developer"></div>
 <div class="form-group"><label>Portfolio / LinkedIn links</label><input id="rbLinks" maxlength="500" placeholder="https://..."></div>
 <div class="form-group"><label>Education</label><textarea id="rbEducation" rows="3" placeholder="Degree, institution, year"></textarea></div>
 <div class="form-group"><label>Experience</label><textarea id="rbExperience" rows="3" placeholder="Internship or work experience"></textarea></div>
 <div class="form-group"><label>Summary</label><textarea id="rbSummary" rows="3" placeholder="A short professional summary"></textarea></div>
 <div class="form-group"><label>Projects</label><textarea id="rbProjects" rows="3" placeholder="Project name, technology, outcome"></textarea></div>
 </div><div class="form-group"><label>Skills (comma separated)</label><input id="rbSkills" placeholder="Python, FastAPI, MongoDB, HTML, CSS"></div>
 <div class="dashboard-actions"><button class="btn btn-primary" type="submit">Save resume profile</button><button class="btn btn-outline" type="button" id="rbDownload">Export resume draft</button></div><div id="resumeBuilderMessage"></div></form></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Skill gap & learning roadmap</h3><div class="dashboard-actions"><select id="roadmapRole" class="roadmap-select"><option>Python Developer</option><option>Frontend Developer</option><option>Data Analyst</option><option>AI/ML Developer</option></select><button class="btn btn-outline" id="loadRoadmap">Build my roadmap</button></div><div id="roadmapList" class="dashboard-list"><p class="muted-text">Choose a target role to generate your learning roadmap.</p></div></section>
 <section class="feature-panel"><h3 class="dashboard-section-title">Mock interview coach</h3><div class="dashboard-actions"><select id="interviewRole" class="roadmap-select"><option>Python Developer</option><option>FastAPI Developer</option><option>SQL / Database</option><option>HR Interview</option></select><button class="btn btn-outline" id="newInterviewQuestion">Get a practice question</button></div><div id="mockQuestion" class="match-result"><p class="muted-text">Generate a question, answer it in your own words, and receive rubric-based feedback.</p></div><form id="mockAnswerForm"><div class="form-group"><label>Your answer</label><textarea id="mockAnswer" rows="4" required placeholder="Write your answer here..."></textarea></div><button class="btn btn-primary" type="submit">Evaluate my answer</button><div id="mockFeedback"></div></form></section>`);
 // Load saved resume profile
 try{
   const data=await api("/api/resume-builder"),r=data.resume||{};
   $("rbHeadline").value=r.headline||"";$("rbLinks").value=r.links||"";$("rbEducation").value=r.education||"";
   $("rbExperience").value=r.experience||"";$("rbSummary").value=r.summary||"";$("rbProjects").value=r.projects||"";
   $("rbSkills").value=(r.skills||[]).join(", ");
 }catch(e){$("resumeBuilderMessage").innerHTML=`<p class="muted-text">${safe(e.message)}</p>`}
 // recommendations
 try{
   const r=await api("/api/recommendations");
   $("recommendationList").innerHTML=r.items.length?r.items.map(j=>`<div class="dashboard-row"><div><strong>${safe(j.title)} · ${safe(j.match_score)}% skill match</strong><small>${safe(j.company)} · ${safe(j.location)} — ${safe(j.recommendation_reason)}</small></div><button class="btn btn-outline small-btn" data-recommend-view="${safe(j.id)}">View</button></div>`).join(""):'<p class="muted-text">No recommendations yet. Upload a resume and explore open roles.</p>';
   document.querySelectorAll("[data-recommend-view]").forEach(b=>b.onclick=()=>viewApply(b.dataset.recommendView));
 }catch(e){$("recommendationList").innerHTML=`<p class="muted-text">${safe(e.message)}</p>`}
 // notifications
 async function refreshNotifications(){
  try{const n=await api("/api/notifications");$("notificationCount").textContent=`${n.unread} unread`;
   $("notificationList").innerHTML=n.items.length?n.items.map(x=>`<div class="dashboard-row"><div><strong>${safe(x.title)} ${x.read?"":"• NEW"}</strong><small>${safe(x.message)} · ${safe(new Date(x.created_at).toLocaleString())}</small></div>${x.read?"":`<button class="btn btn-outline small-btn" data-notifyread="${safe(x.id)}">Mark read</button>`}</div>`).join(""):'<p class="muted-text">No notifications yet. Application updates will appear here.</p>';
   document.querySelectorAll("[data-notifyread]").forEach(b=>b.onclick=async()=>{try{await api(`/api/notifications/${b.dataset.notifyread}/read`,{method:"PATCH"});await refreshNotifications()}catch(e){notify(e.message)}});
  }catch(e){$("notificationList").innerHTML=`<p class="muted-text">${safe(e.message)}</p>`}
 }
 await refreshNotifications();
 // resume builder
 $("resumeBuilderForm").onsubmit=async e=>{e.preventDefault();const body={headline:$("rbHeadline").value.trim(),links:$("rbLinks").value.trim(),education:$("rbEducation").value.trim(),experience:$("rbExperience").value.trim(),summary:$("rbSummary").value.trim(),projects:$("rbProjects").value.trim(),skills:$("rbSkills").value.split(",").map(x=>x.trim()).filter(Boolean)};
  try{const r=await api("/api/resume-builder",{method:"POST",body});$("resumeBuilderMessage").innerHTML=`<p class="status">${safe(r.message)}</p>`;notify("Resume profile saved to MongoDB.")}catch(e){$("resumeBuilderMessage").innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
 };
 $("rbDownload").onclick=()=>{const text=[currentUser.name,$("rbHeadline").value,$("rbSummary").value,"EDUCATION\n"+$("rbEducation").value,"EXPERIENCE\n"+$("rbExperience").value,"PROJECTS\n"+$("rbProjects").value,"SKILLS\n"+$("rbSkills").value,"LINKS\n"+$("rbLinks").value].filter(Boolean).join("\n\n");const blob=new Blob([text],{type:"text/plain;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="CareerPilot_Resume_Draft.txt";a.click();URL.revokeObjectURL(url)};
 // skill roadmap
 async function loadRoadmap(){
  const target=$("roadmapRole").value;const list=$("roadmapList");list.innerHTML='<p class="muted-text">Building roadmap…</p>';
  try{const [r,p]=await Promise.all([api("/api/skill-roadmap?target_role="+encodeURIComponent(target)),api("/api/skill-roadmap/progress")]);const doneMap=new Map(p.items.map(x=>[x.title,x.done]));
   list.innerHTML=r.steps.map(s=>{const done=doneMap.has(s.title)?doneMap.get(s.title):s.done;return `<label class="dashboard-row roadmap-item"><span><strong>${safe(s.title)}</strong><small>${safe(s.deliverable)}</small></span><input type="checkbox" data-roadmap="${safe(s.title)}" ${done?"checked":""}></label>`}).join("");
   list.querySelectorAll("[data-roadmap]").forEach(c=>c.onchange=async()=>{try{await api("/api/skill-roadmap/progress",{method:"POST",body:{title:c.dataset.roadmap,done:c.checked}});notify("Roadmap progress saved.")}catch(e){notify(e.message);c.checked=!c.checked}});
  }catch(e){list.innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
 }
 $("loadRoadmap").onclick=loadRoadmap;await loadRoadmap();
 // mock interview
 let activeQuestion=null;
 $("newInterviewQuestion").onclick=async()=>{try{const role=$("interviewRole").value;const q=await api("/api/interview/questions?role="+encodeURIComponent(role)+"&level=Intermediate");activeQuestion=q.items[Math.floor(Math.random()*q.items.length)];$("mockQuestion").innerHTML=`<strong>${safe(activeQuestion.question)}</strong><details><summary>Show sample answer after you try</summary><p class="muted-text">${safe(activeQuestion.sample_answer)}</p></details>`;$("mockFeedback").innerHTML="";$("mockAnswer").value=""}catch(e){$("mockQuestion").textContent=e.message}};
 $("mockAnswerForm").onsubmit=async e=>{e.preventDefault();if(!activeQuestion){notify("Generate a practice question first.");return}try{const r=await api("/api/interview/evaluate",{method:"POST",body:{role:$("interviewRole").value,question:activeQuestion.question,answer:$("mockAnswer").value,expected_keywords:[]}});$("mockFeedback").innerHTML=`<div class="match-result"><div class="match-score">${r.score}/100</div><p>${safe(r.feedback)}</p><strong>Keywords covered</strong><div class="job-skills">${r.matched_keywords.map(x=>`<span>${safe(x)}</span>`).join("")||"<span>Keep practicing</span>"}</div><strong>Consider including</strong><div class="job-skills">${r.suggested_keywords.map(x=>`<span>${safe(x)}</span>`).join("")||"<span>Good coverage</span>"}</div><p class="muted-text">${safe(r.note)}</p></div>`}catch(e){$("mockFeedback").innerHTML=`<p class="form-error">${safe(e.message)}</p>`}};

 // Populate target job selector for ATS keyword comparison
 try{
  const jobs=await api("/api/jobs?limit=50");
  $("atsJob").insertAdjacentHTML("beforeend",jobs.items.map(x=>`<option value="${safe(x.id)}">${safe(x.title)} · ${safe(x.company)}</option>`).join(""));
 }catch(e){}
 $("runAts").onclick=async()=>{
  const out=$("atsResult");out.innerHTML='<p class="muted-text">Checking your resume…</p>';
  try{
   const id=$("atsJob").value;const r=await api("/api/resume/ats-check"+(id?"?job_id="+encodeURIComponent(id):"") ,{method:"POST"});
   out.innerHTML=`<div class="match-result"><div class="match-score">${r.ats_score}/100</div><strong>Resume structure score</strong><div class="job-skills">${Object.entries(r.checks).map(([k,v])=>`<span>${v?"✓":"○"} ${safe(k)}</span>`).join("")}</div><p><strong>Suggestions</strong></p><ul>${r.suggestions.map(x=>`<li>${safe(x)}</li>`).join("")}</ul><p class="muted-text">${safe(r.disclaimer)}</p></div>`;
  }catch(e){out.innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
 };
 async function loadApplicationAnalytics(){
  const host=$("applicationAnalytics");
  try{
   const r=await api("/api/analytics/applications");
   host.innerHTML=`<div class="dash-stats"><div class="dash-stat"><strong>${r.total}</strong><span>Total applications</span></div><div class="dash-stat"><strong>${r.success_rate}%</strong><span>Shortlisted / hired rate</span></div><div class="dash-stat"><strong>${r.positive_outcomes}</strong><span>Positive outcomes</span></div></div><div class="job-skills">${Object.entries(r.status_counts).map(([k,v])=>`<span>${safe(k)}: ${v}</span>`).join("")}</div><p class="muted-text">${safe(r.note)}</p>`;
  }catch(e){host.innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
 }
 await loadApplicationAnalytics();
 let portfolioHtml="";
 $("generatePortfolio").onclick=async()=>{
  const host=$("portfolioPreview");host.innerHTML='<p class="muted-text">Building your portfolio…</p>';
  try{
   const p=await api("/api/portfolio");
   const esc=x=>safe(x||"").replace(/\n/g,"<br>");
   portfolioHtml=`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${safe(p.name)} | Portfolio</title><style>body{font:16px Arial,sans-serif;max-width:850px;margin:50px auto;padding:0 24px;color:#20213a;line-height:1.7}header{padding:35px;background:#f1efff;border-radius:18px}h1{margin:0;color:#6048ce}h2{margin-top:30px;color:#6048ce}li{margin:6px 0}.tag{display:inline-block;background:#eeeaff;padding:5px 10px;border-radius:20px;margin:4px}</style></head><body><header><h1>${safe(p.name)}</h1><p><b>${safe(p.headline)}</b></p><p>${safe(p.email)} ${p.links?" · "+safe(p.links):""}</p></header><h2>About</h2><p>${esc(p.summary)||"Add a professional summary in your CareerPilot resume builder."}</p><h2>Skills</h2><p>${(p.skills||[]).map(x=>`<span class="tag">${safe(x)}</span>`).join("")}</p><h2>Education</h2><p>${esc(p.education)}</p><h2>Experience</h2><p>${esc(p.experience)}</p><h2>Projects</h2><p>${esc(p.projects)}</p></body></html>`;
   host.innerHTML=`<div class="match-result"><strong>${safe(p.name)} — ${safe(p.headline)}</strong><p>${safe(p.summary||"Add your summary in Resume Builder.")}</p><div class="job-skills">${(p.skills||[]).map(x=>`<span>${safe(x)}</span>`).join("")}</div><p class="muted-text">Preview generated from your saved profile. Download to save a standalone HTML file.</p></div>`;
   $("downloadPortfolio").disabled=false;
  }catch(e){host.innerHTML=`<p class="form-error">${safe(e.message)}</p>`}
 };
 $("downloadPortfolio").onclick=()=>{
  if(!portfolioHtml)return;const blob=new Blob([portfolioHtml],{type:"text/html;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="CareerPilot_Student_Portfolio.html";a.click();URL.revokeObjectURL(url);
 };

}
async function renderAdminDashboard(d){
 const data=await api("/api/admin/overview");
 $("dashboardContent").innerHTML=`<div class="dash-stats"><div class="dash-stat"><strong>${d.users}</strong><span>Total users</span></div><div class="dash-stat"><strong>${d.students}</strong><span>Students</span></div><div class="dash-stat"><strong>${d.recruiters}</strong><span>Recruiters</span></div><div class="dash-stat"><strong>${d.active_jobs}</strong><span>Active jobs</span></div><div class="dash-stat"><strong>${d.applications}</strong><span>Applications</span></div></div><h3 class="dashboard-section-title">User directory</h3><div class="dashboard-list">${data.users.map(u=>`<div class="dashboard-row"><div><strong>${safe(u.name)} · ${safe(u.role)}</strong><small>${safe(u.email)} · Joined ${safe((u.created_at||"").slice(0,10))}</small></div></div>`).join("")}</div><h3 class="dashboard-section-title">Job moderation</h3><div class="dashboard-list">${data.jobs.map(j=>`<div class="dashboard-row"><div><strong>${safe(j.title)} · ${safe(j.company)}</strong><small>${j.is_active?"Visible to students":"Hidden / closed"}</small></div><button class="btn btn-outline small-btn" data-admin-toggle="${safe(j.id)}">${j.is_active?"Hide job":"Reopen job"}</button></div>`).join("")}</div>`;
 document.querySelectorAll("[data-admin-toggle]").forEach(b=>b.onclick=async()=>{try{const r=await api(`/api/admin/jobs/${b.dataset.adminToggle}/toggle`,{method:"PATCH"});notify(r.message);const updated=await api("/api/dashboard");await renderAdminDashboard(updated)}catch(e){notify(e.message)}});
}

function openJobForm(job=null){
 $("jobForm").reset();setError("jobError","");$("editJobId").value=job?.id||"";$("jobModalTitle").textContent=job?"Edit opportunity":"Post an opportunity";
 if(job){$("jobTitle").value=job.title;$("jobCompany").value=job.company;$("jobLocation").value=job.location;$("jobType").value=job.job_type;$("jobSalary").value=job.salary;$("jobExperience").value=job.experience;$("jobSkills").value=(job.skills||[]).join(", ");$("jobDescription").value=job.description}
 closeModal("dashboardModal");openModal("jobModal");
}
$("jobForm").addEventListener("submit",async e=>{
 e.preventDefault();setError("jobError","");const id=$("editJobId").value;
 const body={title:$("jobTitle").value.trim(),company:$("jobCompany").value.trim(),location:$("jobLocation").value.trim(),job_type:$("jobType").value,salary:$("jobSalary").value.trim()||"Not disclosed",experience:$("jobExperience").value.trim()||"Fresher",skills:$("jobSkills").value.split(",").map(s=>s.trim()).filter(Boolean),description:$("jobDescription").value.trim()};
 try{await api(id?`/api/jobs/${id}`:"/api/jobs",{method:id?"PUT":"POST",body});closeModal("jobModal");notify(id?"Job updated successfully.":"Job posted successfully.");await loadJobs();openDashboard()}catch(e){setError("jobError",e.message)}
});
$("themeToggle").onclick=()=>{document.body.classList.toggle("light");localStorage.setItem("cp_theme",document.body.classList.contains("light")?"light":"dark")};
if(localStorage.getItem("cp_theme")==="light")document.body.classList.add("light");
$("year").textContent=new Date().getFullYear();
updateHeader();loadJobs();
if(currentUser){api("/api/auth/me").catch(()=>{clearSession()})}
