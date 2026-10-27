// Shared folder control. Paths go only to the local toolkit, never to a URL.
(()=>{
  'use strict';
  const form=document.getElementById('source-form'),input=document.getElementById('source-directory'),button=document.getElementById('source-load'),status=document.getElementById('source-status');
  const errors={invalid_directory:'Bitte einen Ordnerpfad eingeben.',absolute_directory_required:'Bitte den vollständigen Ordnerpfad eingeben, zum Beispiel /Users/…/Kontoauszüge. Auch ~/… funktioniert.',directory_not_found:'Der Ordner wurde nicht gefunden. Bitte den Pfad prüfen.',not_a_directory:'Dieser Pfad führt zu einer Datei. Bitte einen Ordner angeben.',directory_contains_state:'Bitte einen eigenen Eingabeordner außerhalb des BankLens-Arbeitsstands wählen.',no_pdfs:'In diesem Ordner liegen keine PDF-Dateien. Unterordner werden nicht durchsucht.',directory_unreadable:'Der Ordner oder eine PDF-Datei konnte nicht geöffnet werden. Bitte Zugriffsrechte und PDFs prüfen.',too_many_directories:'Für diese Serversitzung sind bereits viele Ordner geöffnet. Bitte das Toolkit neu starten.'};
  function show(text,error=false){status.textContent=text;status.classList.toggle('error',error);}
  async function request(route,payload){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),60000);
    const options={cache:'no-store',signal:controller.signal};
    if(payload!==undefined)Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-BankLens-Request':'1'},body:JSON.stringify(payload)});
    try{const response=await fetch(route,options),result=await response.json();if(!response.ok)throw new Error(result.error);return result;}finally{clearTimeout(timer);}
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!input.value.trim()){show(errors.invalid_directory,true);input.focus();return;}
    button.disabled=true;input.disabled=true;form.setAttribute('aria-busy','true');show('PDF-Dateien im Ordner werden lokal geladen …');
    try{
      const result=await request('api/source/load',{directory:input.value});
      const proof=location.pathname.endsWith('/proof.html');
      const next=new URL(result.session_path+(proof?'proof.html#einlesen':''),location.href);
      if(next.origin!==location.origin||!/^\/[A-Za-z0-9_-]{32,100}\//.test(next.pathname))throw new Error('invalid_response');
      show(`${result.document_count} PDFs geladen. Arbeitsstand wird geöffnet …`);
      location.assign(next.href);
    }catch(error){show(errors[error.message]||'Der lokale Ordner konnte nicht geladen werden. Bitte Verbindung und Toolkit prüfen.',true);}
    finally{button.disabled=false;input.disabled=false;form.removeAttribute('aria-busy');}
  });
  async function initialize(){
    if(location.protocol==='file:'){show('Bitte über die lokale Serveradresse öffnen.',true);return;}
    try{const source=await request('api/source');input.value=source.directory;show(`${source.document_count} PDF${source.document_count===1?'':'s'} · ${source.page_count} Seiten im aktuellen Ordner.`);button.disabled=false;input.disabled=false;}
    catch{show('Keine Verbindung zur Ordnerauswahl. Bitte den lokalen Server neu starten.',true);}
  }
  initialize();
})();
