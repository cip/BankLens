// Profile changes open isolated sessions; old tabs retain their index and exports.
(()=>{
  'use strict';
  const select=document.getElementById('profile-select'),button=document.getElementById('profile-switch'),status=document.getElementById('profile-status');
  let selected='',pending=false,available=false;
  async function request(route,payload){const response=await fetch(route,{cache:'no-store',...(payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-BankLens-Request':'1'},body:JSON.stringify(payload)})});if(!response.ok)throw new Error('profile_failed');return response.json();}
  const origins={examples:'Arbeitsbeispiele',bundled:'Mitgeliefert',local:'Lokal',legacy:'Bisherige Profildatei'};
  async function refresh(){
    try{const data=await request('api/profiles');selected=data.selected_profile;select.replaceChildren();for(const profile of data.profiles){const option=document.createElement('option');option.value=profile.reference;option.textContent=`${profile.name} · ${origins[profile.origin]}${profile.revision?' · Revision '+profile.revision:''}`;select.append(option);}select.value=selected;const active=data.profiles.find(p=>p.reference===selected);status.textContent=active?`Verwendet: ${active.name} · ${origins[active.origin]}${active.revision?' · Revision '+active.revision:''}.`:'Das gewählte Profil ist nicht verfügbar.';if(data.invalid_profiles)status.textContent+=' Mindestens ein Profil konnte nicht geladen werden.';available=true;update();}
    catch{status.textContent='Profilauswahl nach dem Laden eines Auszugsordners verfügbar.';}
  }
  function update(){const busy=window.banklensProfileBusy?.()||false;button.disabled=pending||busy||!available||select.value===selected;select.disabled=!available||pending||busy;}
  select.addEventListener('change',update);
  button.addEventListener('click',async()=>{
    if(window.banklensProfileBusy?.())return;
    pending=true;update();status.textContent='Profil wird in einer neuen Sitzung geöffnet …';
    try{const result=await request('api/profile/select',{reference:select.value});if(!/^\/[A-Za-z0-9_-]{32,100}\/$/.test(result.session_path))throw new Error('invalid_response');location.assign(result.session_path+(location.pathname.endsWith('/proof.html')?'proof.html':''));}
    catch{status.textContent='Profilwechsel fehlgeschlagen. Der bisherige Stand bleibt erhalten.';pending=false;update();}
  });
  window.addEventListener('banklens-profile-saved',refresh);
  window.addEventListener('banklens-controls',update);
  window.addEventListener('banklens-recognition-source',event=>{status.textContent=event.detail;});
  refresh();
})();
