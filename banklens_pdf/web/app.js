'use strict';
const $ = id => document.getElementById(id);
let workspace, fields={}, current=0, page=1, ready=false, loading=false, scanning=false, cancelScan=false;
let dirty=false, revision=0, generation=0, history=[], layout=null, selectedIDs=[], editing=null, profileAvailable=false;
const layouts=new Map(), svgNS='http://www.w3.org/2000/svg';
const EXPECTED_API_VERSION=7,EXPECTED_REVISION='booking-blocks-4';
let serverCompatible=false,recognitionRevision=EXPECTED_REVISION;
function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
async function api(route,payload){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),payload===undefined?30000:60000);
  const options={cache:'no-store',signal:controller.signal};
  if(payload!==undefined)Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-BankLens-Request':'1'},body:JSON.stringify(payload)});
  try{const response=await fetch(route,options);if(!response.ok)throw new Error('local_operation_failed');return await response.json();}
  finally{clearTimeout(timer);}
}
const doc=()=>workspace.documents[current];
const outdated=a=>a.kind==='suggestion'&&a.recognition_revision!==recognitionRevision;
const active=a=>a.kind!=='rejected'&&!outdated(a);
function shown(a){const filter=$('filter').value;return !filter||(filter==='structure'?(a.field==='transaction.row'||!a.field.startsWith('transaction.')):a.field===filter);}
function pageAnnotations(){return doc().annotations.filter(a=>a.page===page&&active(a));}
function tokens(ids,source=layout){const set=new Set(ids);return source?source.tokens.filter(t=>set.has(t.id)):[];}
function textOf(ids,source=layout){let previous=null;return tokens(ids,source).map(t=>{const sep=previous===null?'':previous===t.line?' ':'\n';previous=t.line;return sep+t.text;}).join('');}
function controls(){
  const busy=!ready||loading||scanning;
  for(const id of ['document','page','field','scope','profile-name','filter','fine-fields'])$(id).disabled=busy;
  $('previous').disabled=busy||page<=1;$('next').disabled=busy||page>=doc().page_count;
  $('add-example').disabled=busy||!selectedIDs.length;$('whole-line').disabled=busy||!selectedIDs.length;$('clear-selection').disabled=busy||!selectedIDs.length;$('whole-booking').disabled=busy||!selectedIDs.length;$('holder').disabled=busy;
  const examples=ready?workspace.documents.flatMap(d=>d.annotations).filter(a=>a.kind==='example').length:0;
  $('recognize').disabled=busy||!serverCompatible||!examples;$('apply-profile').disabled=busy||!serverCompatible||!profileAvailable;$('refresh-suggestions').disabled=busy||!serverCompatible||(!examples&&!profileAvailable);
  $('save').disabled=!ready||scanning||!dirty;$('undo').disabled=busy||!history.length;
  $('accept-page').disabled=busy||!pageAnnotations().some(a=>a.kind==='suggestion');
  $('next-suggestion').disabled=busy||!workspace.documents.some(d=>d.annotations.some(a=>a.kind==='suggestion'&&active(a)));
  $('cancel').hidden=!scanning;$('progress').hidden=!scanning;
  $('dirty').textContent=dirty?'Ungespeichert':'Gespeichert';$('dirty').classList.toggle('changed',dirty);
  $('add-example').textContent=editing?'Korrektur als Beispiel speichern':'Als Beispiel zuordnen';
}
function remember(){history.push(JSON.stringify(workspace));if(history.length>20)history.shift();}
function changed(){dirty=true;revision++;render();controls();}
function select(ids){selectedIDs=[...new Set(ids)];$('selection-preview').textContent=selectedIDs.length?textOf(selectedIDs):'Wähle einen Text im PDF.';renderMarks();controls();}
function clearSelection(){editing=null;window.getSelection()?.removeAllRanges();select([]);}
function svgElement(type,attributes){const n=document.createElementNS(svgNS,type);for(const [k,v]of Object.entries(attributes))n.setAttribute(k,v);return n;}
function drawTokens(ids,kind,block=false){
  const groups=new Map();for(const token of tokens(ids)){
    if(kind!=='selected'&&(token.rotation??0)!==0)continue;
    const key=block?'block':token.line;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(token);
  }
  for(const group of groups.values()){
    const x=Math.min(...group.map(t=>t.box[0])),y=Math.min(...group.map(t=>t.box[1]));
    const right=Math.max(...group.map(t=>t.box[0]+t.box[2])),bottom=Math.max(...group.map(t=>t.box[1]+t.box[3]));
    $('overlay').append(svgElement('rect',{x:x*1000,y:y*1000,width:(right-x)*1000,height:(bottom-y)*1000,class:`field-mark ${kind}`}));
  }
}
function renderMarks(){
  $('overlay').replaceChildren();if(!workspace||!layout)return;
  const filter=$('filter').value;
  for(const a of pageAnnotations()){if(shown(a))drawTokens(a.token_ids,`${a.kind} ${a.field==='transaction.row'?'row-mark':''}`,a.field==='transaction.row');}
  if(selectedIDs.length)drawTokens(selectedIDs,'selected');
}
function annotationAction(annotation,kind){if(scanning)return;remember();annotation.kind=kind;changed();message(kind==='rejected'?'Vorschlag verworfen. Er wird bei der nächsten Erkennung ausgespart.':'Zuordnung übernommen.');}
function button(label,action){const b=document.createElement('button');b.textContent=label;b.className='small-action';b.disabled=scanning;b.addEventListener('click',action);return b;}
function formatValid(field,text){
  const value=text.trim().replace(/\s+/g,'');
  if(field.endsWith('amount')||field.endsWith('balance'))return /^[+−-]?(?:\d{1,3}(?:[.,]\d{3})*|\d+)[,.]\d{2}[+−-]?$/.test(value);
  if(field.endsWith('date'))return /^\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\.?$/.test(value);
  if(field.endsWith('currency'))return /^(EUR|USD|GBP|CHF|€|\$|£)$/.test(value);
  if(field.endsWith('iban'))return /^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(value);
  return true;
}
const fineRoles=new Set(['transaction.recipient','transaction.reference','transaction.mandate_reference','transaction.creditor_id','transaction.description','transaction.currency']);
function populateFields(){
  const selected=$('field').value;$('field').replaceChildren();
  for(const [value,label] of Object.entries(fields)){if(fineRoles.has(value)&&!$('fine-fields').checked)continue;const option=document.createElement('option');option.value=value;option.textContent=label;$('field').append(option);}
  if([...$('field').options].some(o=>o.value===selected))$('field').value=selected;holderControls();
}
function setField(value){if(fineRoles.has(value))$('fine-fields').checked=true;populateFields();$('field').value=value;holderControls();}
$('fine-fields').addEventListener('change',populateFields);
function holderControls(){
  const role=$('field').value,owner=role.startsWith('owner.');$('holder-control').hidden=!owner;
  const currentValue=$('holder').value;const slots=new Set(['holder-1','holder-2']);
  for(const d of workspace.documents)for(const a of d.annotations)if(a.entity_id)slots.add(a.entity_id);
  const max=Math.min(99,Math.max(...[...slots].map(id=>Number(id.split('-')[1])))+1);slots.add('holder-'+max);
  $('holder').replaceChildren();
  const automatic=document.createElement('option');automatic.value='';automatic.textContent=role==='owner.name'?'Automatisch nach Namenszeile':'Gemeinsame Adresse / ohne Person';$('holder').append(automatic);
  for(const id of [...slots].sort((a,b)=>Number(a.split('-')[1])-Number(b.split('-')[1]))){const option=document.createElement('option');option.value=id;option.textContent='Kontoinhaber '+id.split('-')[1];$('holder').append(option);}
  if([...$('holder').options].some(o=>o.value===currentValue))$('holder').value=currentValue;
}
function renderOwners(){
  $('owners').replaceChildren();let count=0;
  for(const a of pageAnnotations().filter(a=>a.field==='owner.name')){
    const lines=new Map();for(const t of tokens(a.token_ids)){if(!lines.has(t.line))lines.set(t.line,[]);lines.get(t.line).push(t);}
    for(const group of lines.values()){count++;const item=document.createElement('div'),label=document.createElement('strong'),value=document.createElement('span');label.textContent='Kontoinhaber '+(a.entity_id?.split('-')[1]||count);value.textContent=group.map(t=>t.text).join(' ');item.append(label,value);$('owners').append(item);}
  }
  if(!count)$('owners').textContent='Noch keine Namen zugeordnet.';
}
function renderRows(){
  const annotations=pageAnnotations(),rows=annotations.filter(a=>a.field==='transaction.row');$('rows-body').replaceChildren();$('rows-table').hidden=!rows.length;$('rows-empty').hidden=!!rows.length;
  for(const row of rows){const children=annotations.filter(a=>a.row_id===row.id);const value=field=>{const child=children.find(a=>a.field===field);return child?textOf(child.token_ids):'—';};const tr=document.createElement('tr');for(const text of [row.continuation_of?'Fortsetzung':row.partial?(row.continued_on?'Weiter auf Seite '+row.continued_on:'Fortsetzung offen'):row.kind==='suggestion'?'Vorschlag':'Zugeordnet',row.continuation_of?'vorige Seite':value('transaction.booking_date'),value('transaction.value_date'),value('transaction.full_text')!=='—'?value('transaction.full_text'):value('transaction.description'),value('transaction.amount')]){const td=document.createElement('td');td.textContent=text;tr.append(td);}$('rows-body').append(tr);}
}
function render(){
  if(!workspace)return;renderMarks();$('annotations').replaceChildren();const annotations=pageAnnotations();$('empty').hidden=!!annotations.length;
  $('counts').textContent=`${annotations.filter(a=>a.kind==='example').length} Beispiele · ${annotations.filter(a=>a.kind==='suggestion').length} Vorschläge`;
  for(const annotation of annotations){
    if(!shown(annotation))continue;
    const li=document.createElement('li'),info=document.createElement('div'),title=document.createElement('strong'),value=document.createElement('small'),actions=document.createElement('div');
    title.textContent=(fields[annotation.field]||annotation.field)+(annotation.entity_id?' · Person '+annotation.entity_id.split('-')[1]:'');value.textContent=textOf(annotation.token_ids);value.title=value.textContent;info.append(title,value);if(annotation.kind==='example'&&!formatValid(annotation.field,value.textContent)){const warning=document.createElement('small');warning.className='format-warning';warning.textContent='Format prüfen: Bitte einen Feldwert statt der Überschrift markieren.';info.append(warning);}
    const badge=document.createElement('span');badge.className=`annotation-kind ${annotation.kind}`;badge.textContent={example:'Beispiel',suggestion:'Vorschlag',confirmed:'Übernommen'}[annotation.kind];info.append(badge);
    actions.className='annotation-actions';
    if(annotation.kind==='suggestion')actions.append(button('Übernehmen',()=>annotationAction(annotation,'confirmed')),button('Verwerfen',()=>annotationAction(annotation,'rejected')));
    actions.append(button('Korrigieren',()=>{editing=annotation.id;setField(annotation.field);select(annotation.token_ids);message('Wähle bei Bedarf anderen Text und das passende Feld. Speichere die Korrektur als Beispiel.');}));
    if(annotation.kind!=='suggestion')actions.append(button('Entfernen',()=>{remember();if(annotation.kind==='example')doc().annotations=doc().annotations.filter(a=>a.id!==annotation.id);else annotation.kind='rejected';changed();}));
    if(annotation.kind==='suggestion')actions.append(button('Als Beispiel',()=>annotationAction(annotation,'example')));
    li.append(info,actions);$('annotations').append(li);
  }
  const all=workspace.documents.flatMap(d=>d.annotations);$('summary').textContent=`${all.filter(a=>a.kind==='example').length} Beispiele · ${all.filter(a=>a.kind==='suggestion'&&active(a)).length} offene Vorschläge · ${all.filter(a=>a.field==='transaction.row'&&active(a)&&!a.continuation_of).length} Buchungen im Testset`;
  const stale=all.filter(outdated).length;
  $('revision-notice').hidden=serverCompatible&&!stale;
  $('revision-message').textContent=!serverCompatible?'Der Server läuft mit einer älteren Version. Bitte das Toolkit im Startterminal neu starten.':`${stale} alte Vorschläge werden ausgeblendet. Mit der aktuellen Version neu berechnen; deine Beispiele und Bestätigungen bleiben erhalten.`;
  renderOwners();renderRows();holderControls();
}
function buildTextLayer(){
  const layer=$('text-layer');layer.replaceChildren();if(!layout)return;
  const rect=$('paper').getBoundingClientRect(),canvas=document.createElement('canvas'),context=canvas.getContext('2d');
  for(const token of layout.tokens){
    const span=document.createElement('span');span.className='token';span.dataset.token=token.id;span.textContent=token.text+' ';
    const [x,y,w,h]=token.box;let width=w*rect.width,height=h*rect.height;
    const rotation=token.rotation??layout.rotation??0;let left=x*rect.width,top=y*rect.height;
    if(rotation===90){left+=width;[width,height]=[height,width];}else if(rotation===180){left+=width;top+=height;}else if(rotation===270){top+=height;[width,height]=[height,width];}
    const fontSize=Math.max(1,height*1.35);context.font=`${fontSize}px Arial`;const measured=context.measureText(token.text).width||1;
    Object.assign(span.style,{left:`${left}px`,top:`${top}px`,fontSize:`${fontSize}px`,lineHeight:`${height}px`,height:`${height}px`,transform:`rotate(${rotation}deg) scaleX(${width/measured})`});
    layer.append(span);
  }
}
async function getLayout(documentID,number){const key=`${documentID}/${number}`;if(!layouts.has(key)){layouts.set(key,await api(`api/text/${documentID}/${number}.json`));if(layouts.size>8)layouts.delete(layouts.keys().next().value);}return layouts.get(key);}
async function showPage(){
  const request=++generation;let imageTimer;loading=true;$('retry-page').hidden=true;layout=null;selectedIDs=[];editing=null;document.body.classList.add('busy');$('text-layer').replaceChildren();$('overlay').replaceChildren();$('selection-preview').textContent='Wähle einen Text im PDF.';controls();
  $('page').value=page;$('page').max=doc().page_count;$('page-count').textContent=`/ ${doc().page_count}`;$('loading').hidden=false;$('loading').textContent='Seite und auswählbarer Text werden geladen …';
  try{
    const image=$('page-image');
    const imageReady=new Promise((resolve,reject)=>{
      imageTimer=setTimeout(()=>reject(new Error('image_timeout')),30000);
      image.onload=()=>{clearTimeout(imageTimer);resolve();};
      image.onerror=()=>{clearTimeout(imageTimer);reject(new Error('image_failed'));};
      image.src=`api/page/${doc().document_id}/${page}.png`;
    });
    const [result]=await Promise.all([getLayout(doc().document_id,page),imageReady]);if(request!==generation)return;
    layout=result;loading=false;$('loading').hidden=true;document.body.classList.remove('busy');buildTextLayer();render();controls();
    if(!layout.selection_available)message('Diese Seite enthält keinen auswählbaren Text. Für solche Seiten ist später lokale OCR nötig.',true);
    else if(!layout.recognition_supported)message('Textauswahl ist möglich. Automatische Erkennung für gedrehte Seiten wird noch nicht unterstützt.',true);
  }catch{if(request!==generation)return;loading=false;layout=null;$('loading').textContent='Die Seite konnte nicht geladen werden. Du kannst es erneut versuchen oder zurückblättern.';$('retry-page').hidden=false;document.body.classList.add('busy');controls();message('Seitenladen fehlgeschlagen oder Zeitgrenze erreicht. Deine Zuordnungen bleiben erhalten.',true);}
  finally{clearTimeout(imageTimer);}
}
$('retry-page').addEventListener('click',showPage);
function captureSelection(event){
  if(!ready||loading||scanning||!layout)return;
  const selection=window.getSelection();
  if(selection&&!selection.isCollapsed&&selection.rangeCount){const range=selection.getRangeAt(0);if(!$('text-layer').contains(range.startContainer)||!$('text-layer').contains(range.endContainer))return;const ids=[];for(const span of $('text-layer').querySelectorAll('.token')){const node=span.firstChild;if(!range.intersectsNode(span))continue;if(range.startContainer===node&&range.startOffset>=node.length)continue;if(range.endContainer===node&&range.endOffset===0)continue;ids.push(Number(span.dataset.token));}select(ids);}
  else if(event?.target?.closest('.token'))select([Number(event.target.closest('.token').dataset.token)]);
}
$('text-layer').addEventListener('mouseup',captureSelection);$('text-layer').addEventListener('touchend',()=>setTimeout(captureSelection,50));document.addEventListener('selectionchange',()=>{if(!window.getSelection()?.isCollapsed)captureSelection();});
new ResizeObserver(()=>{if(layout&&!loading)buildTextLayer();}).observe($('paper'));
$('clear-selection').addEventListener('click',clearSelection);
$('whole-line').addEventListener('click',()=>{const lines=new Set(tokens(selectedIDs).map(t=>t.line));select(layout.tokens.filter(t=>lines.has(t.line)).map(t=>t.id));});
$('whole-booking').addEventListener('click',async()=>{
  if(!selectedIDs.length||loading||scanning)return;$('whole-booking').disabled=true;
  try{const result=await api('api/block',{workspace,document_id:doc().document_id,page,token_ids:selectedIDs});
    if(result.found){select(result.token_ids);$('field').value='transaction.row';holderControls();message(result.partial?'Buchung bis zum Seitenende ausgewählt. Die Fortsetzung wird gesondert erkannt.':'Ganze Buchung ausgewählt, einschließlich Wertdatum und rechtem Betrag.');}
    else message('Wähle Text innerhalb einer Buchung. Falls die Spalten noch unbekannt sind, ordne zuerst das linke Buchungsdatum zu.',true);
  }catch{message('Der Buchungsblock konnte nicht bestimmt werden.',true);}controls();
});
$('add-example').addEventListener('click',async()=>{
  if(!selectedIDs.length||!layout)return;const field=$('field').value;
  if(field==='transaction.full_text'){
    loading=true;controls();
    try{const block=await api('api/block',{workspace,document_id:doc().document_id,page,token_ids:selectedIDs});
      if(!block.found||!block.full_text_ids?.length){message('Wähle Text innerhalb einer erkennbaren Buchung. Der gesamte Buchungstext wird dann als Einheit zugeordnet.',true);return;}
      select(block.full_text_ids);
    }catch{message('Der vollständige Buchungstext konnte nicht bestimmt werden.',true);return;}
    finally{loading=false;controls();}
  }

  if(!formatValid(field,textOf(selectedIDs))){message('Das ist kein passender Feldwert. Bitte den eigentlichen Betrag, das Datum oder die Währung markieren – nicht die Überschrift.',true);return;}
  remember();
  if(editing){const previous=doc().annotations.find(a=>a.id===editing);if(previous){if(previous.kind==='example')doc().annotations=doc().annotations.filter(a=>a.id!==editing);else previous.kind='rejected';}}
  let groups=[tokens(selectedIDs)];
  if(field==='owner.name'){const lines=new Map();for(const token of groups[0]){if(!lines.has(token.line))lines.set(token.line,[]);lines.get(token.line).push(token);}groups=[...lines.values()].map(line=>{const group=[];for(const token of line.sort((a,b)=>a.box[0]-b.box[0])){const previous=group.at(-1);if(previous&&token.box[0]-(previous.box[0]+previous.box[2])>.045)break;group.push(token);}return group;});}
  const existingNameLines=doc().annotations.filter(a=>a.page===page&&a.field==='owner.name'&&active(a)).flatMap(a=>tokens(a.token_ids).map(t=>t.line));
  const orderedNameLines=[...new Set([...existingNameLines,...groups.flatMap(g=>g.map(t=>t.line))])].sort((a,b)=>a-b);
  groups.forEach((group,index)=>{
    const ids=group.map(t=>t.id),sorted=[...ids].sort((a,b)=>a-b);
    const duplicate=doc().annotations.find(a=>a.page===page&&a.field===field&&a.kind==='example'&&JSON.stringify([...a.token_ids].sort((a,b)=>a-b))===JSON.stringify(sorted));
    if(duplicate)return;
    doc().annotations=doc().annotations.filter(a=>!(a.kind==='suggestion'&&a.page===page&&a.field===field&&a.token_ids.some(id=>ids.includes(id))));
    const parent=doc().annotations.find(a=>a.page===page&&a.field==='transaction.row'&&active(a)&&ids.every(id=>a.token_ids.includes(id)));
    const id=crypto.randomUUID(),annotation={id,page,field,token_ids:ids,kind:'example',row_id:field==='transaction.row'?null:parent?.id||null};
    if(field.startsWith('owner.')){const explicit=$('holder').value;if(field==='owner.name')annotation.entity_id=explicit?'holder-'+(Number(explicit.split('-')[1])+index):'holder-'+(orderedNameLines.indexOf(group[0].line)+1);else if(explicit)annotation.entity_id=explicit;}
    doc().annotations.push(annotation);
    if(field==='transaction.row')for(const child of doc().annotations)if(child.page===page&&child.field!=='transaction.row'&&child.field.startsWith('transaction.')&&child.token_ids.every(t=>ids.includes(t)))child.row_id=id;
  });
  clearSelection();changed();message(field==='owner.name'?'Kontoinhaber einzeln zugeordnet.':'Beispiel zugeordnet.');
});
$('field').addEventListener('change',()=>{
  const field=$('field').value;holderControls();
  $('field-help').textContent=field==='owner.name'?'Jede Namenszeile wird als eigener Kontoinhaber gespeichert. Du kannst mehrere Namen gemeinsam auswählen.':field.startsWith('owner.address')?'Die Adresse kann einer Person zugeordnet werden oder gemeinsam gelten.':field==='transaction.amount'?'Wähle den rechten Buchungsbetrag. Ein Betrag mitten im Kartentext kann eine andere Bedeutung haben.':field==='account.currency'?'Wähle die Kontowährung, zum Beispiel EUR. Die Überschrift Währung ist kein Feldwert.':field==='transaction.row'?'Ein Wort anklicken und Ganze Buchung auswählen verwenden. Zwei- und mehrzeilige Buchungen werden als Block behandelt.':field.startsWith('transaction.')?'Wähle den Feldwert innerhalb einer Buchung. Datum und Betrag können auf unterschiedlichen Zeilen stehen.':'Dieses Feld gehört zum Auszugskopf.';
});
$('filter').addEventListener('change',render);
$('previous').addEventListener('click',()=>{if(page>1){page--;showPage();}});$('next').addEventListener('click',()=>{if(page<doc().page_count){page++;showPage();}});
$('page').addEventListener('change',()=>{const wanted=Number($('page').value);if(Number.isInteger(wanted)&&wanted>=1&&wanted<=doc().page_count){page=wanted;showPage();}else $('page').value=page;});
$('document').addEventListener('change',()=>{current=Number($('document').value);page=1;showPage();});
$('profile-name').addEventListener('change',()=>{remember();workspace.profile_name=$('profile-name').value.trim()||'Bank Austria';changed();});
$('undo').addEventListener('click',()=>{if(history.length){workspace=JSON.parse(history.pop());$('profile-name').value=workspace.profile_name;clearSelection();changed();message('Letzte Änderung rückgängig gemacht.');}});
$('accept-page').addEventListener('click',()=>{remember();for(const a of pageAnnotations())if(a.kind==='suggestion')a.kind='confirmed';changed();message('Vorschläge dieser Seite übernommen.');});
$('next-suggestion').addEventListener('click',()=>{const locations=[];workspace.documents.forEach((d,index)=>{for(const p of [...new Set(d.annotations.filter(a=>a.kind==='suggestion'&&active(a)).map(a=>a.page))].sort((a,b)=>a-b))locations.push({index,page:p});});const next=locations.find(l=>l.index>current||(l.index===current&&l.page>page))||locations[0];if(next){current=next.index;page=next.page;$('document').value=current;showPage();}});
$('cancel').addEventListener('click',()=>{cancelScan=true;$('recognition-status').textContent='Wird nach der aktuellen Seite angehalten …';});
async function recognize(useSaved=false){
  if(scanning||!serverCompatible)return;scanning=true;cancelScan=false;controls();render();
  try{
    const profile=useSaved?await api('api/profile'):await api('api/learn',workspace);const ignored=profile.ignored_example_count||0;
    if(!profile.anchors.length&&!profile.header_rules.length&&!profile.auto_table){message('Für Buchungen fehlt noch ein Datum oder eine ganze Buchung mit Datum als Beispiel.',true);return;}
    const targets=$('scope').value==='all'?workspace.documents:[doc()];const total=targets.reduce((n,d)=>n+d.page_count,0);let done=0,found=0;
    remember();$('progress').max=total;$('progress').value=0;
    for(const document of targets){let previous=null;for(let number=1;number<=document.page_count;number++){
      if(cancelScan)break;
      $('recognition-status').textContent=`${document.document_id.replace('document-','Dokument ')} · Seite ${number} von ${document.page_count} · ${done}/${total} Seiten`;
      const existing=document.annotations.filter(a=>a.page===number&&a.kind!=='suggestion');
      const result=await api('api/recognize',{profile,document_id:document.document_id,page:number,existing,previous});
      document.annotations=document.annotations.filter(a=>a.page!==number||a.kind!=='suggestion').concat(result.suggestions);
      for(const row of result.rows||[]){const target=document.annotations.find(a=>a.id===row.id);if(target){target.partial=row.partial;target.family=row.family;target.continuation_of=row.continuation_of||null;delete target.continued_on;}if(row.continuation_of){const root=document.annotations.find(a=>a.id===row.continuation_of);if(root)root.continued_on=number;}}
      for(const link of result.field_links||[]){const target=document.annotations.find(a=>a.id===link.id&&a.field===link.field);if(target&&target.kind!=='rejected')target.row_id=link.row_id;}
      previous=result.carry||null;found+=result.suggestions.length;done++;$('progress').value=done;
      dirty=true;revision++;render();
    }if(cancelScan)break;}
    $('recognition-status').textContent=`${done} von ${total} Seiten geprüft · ${found} Vorschläge${cancelScan?' · angehalten':''}. Nicht zugeordnete Texte bleiben sichtbar.${ignored?' '+ignored+' Beispiele wurden wegen unpassendem Format oder fehlendem Buchungsbezug nicht verwendet.':''}`;
    message(ignored?'Erkennung abgeschlossen. Bitte markierte Beispiele mit unpassendem Format prüfen.':'Erkennung abgeschlossen. Für unterschiedliche Buchungsarten kannst du weitere Beispiele ergänzen.',ignored>0);
  }catch{message('Die Erkennung konnte nicht vollständig abgeschlossen werden. Bereits erkannte Vorschläge bleiben erhalten.',true);}
  finally{scanning=false;render();controls();}
}
$('refresh-suggestions').addEventListener('click',()=>{$('scope').value='all';recognize(!workspace.documents.some(d=>d.annotations.some(a=>a.kind==='example')));});
$('recognize').addEventListener('click',()=>recognize(false));$('apply-profile').addEventListener('click',()=>recognize(true));
$('save').addEventListener('click',async()=>{const saving=revision;$('save').disabled=true;try{const result=await api('api/workspace',workspace);if(revision===saving)dirty=false;profileAvailable=profileAvailable||result.profile_updated;message(result.profile_updated?'Bankprofil und Zuordnungen lokal gespeichert.':'Zuordnungen lokal gespeichert. Für ein Erkennungsprofil fehlen noch passende Beispiele.');}catch{message('Speichern fehlgeschlagen. Deine Änderungen bleiben hier erhalten.',true);}controls();});
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
async function initialize(){
  if(location.protocol==='file:'){
    $('loading').textContent='Diese HTML-Datei kann keine PDFs laden. Wechsle zum Tab mit der Adresse http://127.0.0.1:… des gestarteten Toolkits.';
    message('Bitte die lokale Serveradresse öffnen, nicht index.html im Finder. Den Link findest du in diesem Chat oder im Startterminal.',true);
    return;
  }
  try{const [config,state]=await Promise.all([api('api/config'),api('api/workspace')]);fields=config.fields;workspace=state;profileAvailable=config.profile_available;serverCompatible=config.api_version===EXPECTED_API_VERSION&&config.recognition_revision===EXPECTED_REVISION;recognitionRevision=config.recognition_revision||EXPECTED_REVISION;$('app-version').textContent=config.app_version?'v'+config.app_version:'älterer Server';if(!workspace.documents.length)throw new Error('empty');workspace.documents.forEach((d,index)=>{const option=document.createElement('option');option.value=index;option.textContent=`Dokument ${index+1}`;$('document').append(option);});for(const [value,label]of Object.entries(fields)){const option=document.createElement('option');option.value=value;option.textContent=label;$('filter').append(option);}populateFields();$('profile-name').value=workspace.profile_name;ready=true;if(state.repaired_parent_links)dirty=true;controls();message(state.repaired_parent_links?state.repaired_parent_links+' vorhandene Felder wieder mit ihren Buchungen verknüpft. Bitte speichern.':'Bereit. Wähle Text und ordne ihm ein Feld zu.');await showPage();}catch{message('Die Feldwerkstatt konnte nicht geladen werden. Bitte das lokale Toolkit neu starten.',true);$('loading').textContent='Keine Verbindung zur Feldwerkstatt';}}
initialize();
