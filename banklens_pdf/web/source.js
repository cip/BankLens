// Shared local folder controls for the field workshop and proof mode.
(()=>{
  'use strict';
  const form=document.getElementById('source-form');
  const input=document.getElementById('source-directory');
  const button=document.getElementById('source-load');
  const picker=document.getElementById('source-pick');
  const status=document.getElementById('source-status');
  const errors={
    invalid_directory:'Bitte einen Ordnerpfad eingeben.',
    absolute_directory_required:'Bitte den vollständigen Ordnerpfad eingeben, zum Beispiel /Users/…/Kontoauszüge. Auch ~/… funktioniert.',
    directory_not_found:'Der Ordner wurde nicht gefunden. Bitte den Pfad prüfen.',
    not_a_directory:'Dieser Pfad führt zu einer Datei. Bitte einen Ordner angeben.',
    directory_contains_state:'Bitte einen eigenen Eingabeordner außerhalb des BankLens-Arbeitsstands wählen.',
    no_pdfs:'In diesem Ordner liegen keine PDF-Dateien. Unterordner werden nicht durchsucht.',
    directory_unreadable:'Der Ordner oder eine PDF-Datei konnte nicht geöffnet werden. Bitte Zugriffsrechte und PDFs prüfen.',
    pdf_password:'Mindestens eine PDF benötigt ein Passwort und kann hier nicht geöffnet werden.',
    pdf_invalid:'Mindestens eine PDF ist beschädigt oder hat ein nicht unterstütztes Format.',
    pdf_security:'Mindestens eine PDF verwendet einen nicht unterstützten Sicherheitsschutz.',
    pdf_unreadable:'Mindestens eine PDF konnte nicht gelesen werden. Bitte Zugriffsrechte prüfen.',
    saved_state_unreadable:'Der gespeicherte Arbeitsstand oder das gewählte Profil konnte nicht geladen werden. Bitte den Arbeitsstand nicht löschen und Unterstützung anfordern.',
    folder_open_failed:'Der Ordner konnte wegen eines unerwarteten Fehlers nicht geladen werden. Bitte Unterstützung anfordern.',
    too_many_directories:'Für diese Serversitzung sind bereits viele Ordner geöffnet. Bitte das Toolkit neu starten.',
    directory_picker_unavailable:'Der native Ordnerdialog ist nicht verfügbar. Du kannst den Pfad oben eingeben.',
    directory_picker_failed:'Der Ordnerdialog konnte nicht geöffnet werden.',
    directory_picker_timeout:'Der Ordnerdialog wurde nach zehn Minuten geschlossen.'
  };

  function show(text,error=false){
    status.textContent=text;
    status.classList.toggle('error',error);
  }

  function setBusy(busy){
    button.disabled=busy;
    picker.disabled=busy;
    input.disabled=busy;
    form.toggleAttribute('aria-busy',busy);
  }

  async function request(route,payload,timeoutMs=60000){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeoutMs);
    const options={cache:'no-store',signal:controller.signal};
    if(payload!==undefined)Object.assign(options,{
      method:'POST',headers:{'Content-Type':'application/json','X-BankLens-Request':'1'},
      body:JSON.stringify(payload)
    });
    try{
      const response=await fetch(route,options),result=await response.json();
      if(!response.ok){const error=new Error(result.error);if(typeof result.filename==='string')error.filename=result.filename;throw error;}
      return result;
    }finally{clearTimeout(timer);}
  }

  function showError(error){
    const message=errors[error.message]||'Der lokale Ordner konnte nicht geladen werden. Bitte Verbindung und Toolkit prüfen.';
    show(message+(error.filename?` Betroffene Datei: ${error.filename}`:''),true);
  }

  async function openSession(directory){
    const result=await request('api/source/load',{directory});
    const proof=location.pathname.endsWith('/proof.html');
    const next=new URL(result.session_path+(proof?'proof.html#einlesen':''),location.href);
    if(next.origin!==location.origin||!/^\/[A-Za-z0-9_-]{32,100}\//.test(next.pathname))throw new Error('invalid_response');
    show(`${result.document_count} PDFs geladen. Arbeitsstand wird geöffnet …`);
    location.assign(next.href);
  }

  async function loadDirectory(directory){
    if(!directory.trim()){
      show(errors.invalid_directory,true);
      input.focus();
      return;
    }
    setBusy(true);
    show('PDF-Dateien im Ordner werden lokal geladen …');
    try{await openSession(directory);}
    catch(error){showError(error);}
    finally{setBusy(false);}
  }

  form.addEventListener('submit',event=>{
    event.preventDefault();
    loadDirectory(input.value);
  });

  picker.addEventListener('click',async()=>{
    setBusy(true);
    show('Ordnerauswahl wird geöffnet …');
    try{
      const result=await request('api/source/pick',{},610000);
      if(result.cancelled){show('Ordnerauswahl abgebrochen.');return;}
      if(typeof result.directory!=='string'||!result.directory){throw new Error('invalid_response');}
      input.value=result.directory;
      show('PDF-Dateien im ausgewählten Ordner werden lokal geladen …');
      await openSession(result.directory);
    }catch(error){
      showError(error);
    }finally{setBusy(false);}
  });

  async function initialize(){
    if(location.protocol==='file:'){
      show('Bitte über die lokale Serveradresse öffnen.',true);
      return;
    }
    try{
      const source=await request('api/source');
      input.value=source.directory;
      if(!source.directory){show('Wähle einen Auszugsordner, um zu beginnen.');setBusy(false);return;}
      show(`${source.document_count} PDF${source.document_count===1?'':'s'} · ${source.page_count} Seiten im aktuellen Ordner.`);
      setBusy(false);
    }catch{
      show('Keine Verbindung zur Ordnerauswahl. Bitte den lokalen Server neu starten.',true);
    }
  }

  initialize();
})();
