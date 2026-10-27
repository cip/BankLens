"""Local text geometry and example-based field recognition.

Document strings are only used inside the toolkit/browser. Reusable profiles
store roles, geometry and format classes, never example values or filenames.
Scores express heuristic ranking, not calibrated probabilities.
"""
from __future__ import annotations

import hashlib
import math
import re
import pypdfium2.raw as pdfium_raw
from .version import RECOGNITION_REVISION


FIELDS = {
    "owner.name": "Kontoinhaber · Name",
    "owner.address.line1": "Eigene Adresse · Zeile 1",
    "owner.address.line2": "Eigene Adresse · Zeile 2",
    "owner.address.line3": "Eigene Adresse · Zeile 3",
    "account.number": "Kontonummer",
    "account.iban": "IBAN",
    "account.currency": "Kontowährung",
    "statement.date": "Auszugsdatum",
    "statement.period": "Auszugszeitraum",
    "statement.opening_balance": "Anfangssaldo",
    "statement.closing_balance": "Endsaldo",
    "transaction.row": "Ganze Buchung (auch mehrzeilig)",
    "transaction.booking_date": "Buchung · Buchungsdatum",
    "transaction.value_date": "Buchung · Valutadatum",
    "transaction.full_text": "Buchung · Gesamter Buchungstext",
    "transaction.recipient": "Buchung · Empfänger / Auftraggeber",
    "transaction.description": "Buchung · Textausschnitt (optional)",
    "transaction.reference": "Buchung · Referenz",
    "transaction.mandate_reference": "Buchung · Mandatsreferenz",
    "transaction.creditor_id": "Buchung · Creditor-ID",
    "transaction.amount": "Buchung · Betrag",
    "transaction.currency": "Buchung · Währung",
}
DATE = re.compile(r"\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\.?$")
AMOUNT = re.compile(r"[+−-]?(?:\d{1,3}(?:[. ,]\d{3})*|\d+)[,.]\d{2}(?:[+−-])?$")


def bounds(tokens):
    x = min(t["box"][0] for t in tokens)
    y = min(t["box"][1] for t in tokens)
    right = max(t["box"][0] + t["box"][2] for t in tokens)
    bottom = max(t["box"][1] + t["box"][3] for t in tokens)
    return [x, y, right - x, bottom - y]


def normalize_box(box, crop, rotation):
    left, bottom, right, top = crop
    width, height = right - left, top - bottom
    def point(x, y):
        if rotation == 90:
            return ((y-bottom)/height, (x-left)/width)
        if rotation == 180:
            return ((right-x)/width, (y-bottom)/height)
        if rotation == 270:
            return ((top-y)/height, (right-x)/width)
        return ((x-left)/width, (top-y)/height)
    l, b, r, t = box
    corners = [point(x, y) for x in (l, r) for y in (b, t)]
    x, y = max(0, min(p[0] for p in corners)), max(0, min(p[1] for p in corners))
    right, bottom = min(1, max(p[0] for p in corners)), min(1, max(p[1] for p in corners))
    return [x, y, max(0, right-x), max(0, bottom-y)]


def extract_layout(page, number):
    """Word-level text layer; selection always snaps to complete PDF words."""
    textpage = page.get_textpage()
    words, glyphs = [], []
    rotation, crop = page.get_rotation(), page.get_bbox()
    def finish():
        if glyphs:
            words.append({"id": glyphs[0]["id"], "text": "".join(g["text"] for g in glyphs),
                          "box": bounds(glyphs),"rotation":glyphs[0]["rotation"],"char_end":glyphs[-1]["id"]+1})
            glyphs.clear()
    try:
        for index in range(textpage.count_chars()):
            char = textpage.get_text_range(index, 1)
            if not char or char.isspace() or any(ord(c) < 32 for c in char):
                finish()
                continue
            box = normalize_box(textpage.get_charbox(index), crop, rotation)
            if box[2] <= 0 or box[3] <= 0:
                finish()
                continue
            flow_box = normalize_box(textpage.get_charbox(index,loose=True),crop,rotation)
            # PDFium reports character rotation in display-clockwise radians.
            direction=(rotation+round(math.degrees(pdfium_raw.FPDFText_GetCharAngle(textpage,index))))%360
            if glyphs and glyphs[-1]["rotation"]!=direction:
                finish()
            glyph = {"id": index, "text": char, "box": box,"flow_box":flow_box,"rotation":direction}
            if glyphs and direction in (0, 180):
                previous = glyphs[-1]["flow_box"]
                if abs((flow_box[1]+flow_box[3]/2)-(previous[1]+previous[3]/2)) > max(flow_box[3],previous[3])*.65 or flow_box[0]-(previous[0]+previous[2]) > max(flow_box[3],previous[3])*.6:
                    finish()
            glyphs.append(glyph)
        finish()
    finally:
        textpage.close()
    # Group baselines instead of trusting PDF content-stream reading order.
    lines = []
    for word in sorted(words, key=lambda w: (w["box"][1]+w["box"][3]/2, w["box"][0])):
        center = word["box"][1] + word["box"][3]/2
        match = next((line for line in reversed(lines[-8:])
                      if word["rotation"]==0 and line["rotation"]==0 and abs(center-line["center"]) < max(word["box"][3],line["height"])*.6), None)
        if match is None:
            match = {"center": center, "height": word["box"][3], "words": [],"rotation":word["rotation"]}
            lines.append(match)
        match["words"].append(word)
    ordered, public_lines = [], []
    for index, line in enumerate(sorted(lines, key=lambda l: l["center"])):
        tokens = sorted(line["words"], key=lambda w: w["box"][0])
        for token in tokens:
            token["line"] = index
        ordered.extend(tokens)
        public_lines.append({"id": index, "token_ids": [w["id"] for w in tokens], "box": bounds(tokens)})
    width, height = page.get_size()
    return {"page": number, "width": width, "height": height, "rotation": rotation,
            "tokens": ordered, "lines": public_lines,
            "selection_available": bool(ordered), "recognition_supported": rotation == 0}


def value_type(field):
    if field.endswith("date"):
        return "date"
    if field.endswith("amount") or field.endswith("balance"):
        return "amount"
    if field.endswith("iban"):
        return "iban"
    if field.endswith("currency"):
        return "currency"
    return "text"


def matches(text, kind):
    value = text.strip().replace("\u00a0", " ")
    if kind == "date":
        return bool(DATE.fullmatch(value))
    if kind == "amount":
        return bool(AMOUNT.fullmatch(value.replace(" ", "")))
    if kind == "iban":
        return bool(re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", value.replace(" ", "")))
    if kind == "currency":
        return value in ("EUR", "USD", "GBP", "CHF", "€", "$", "£")
    return bool(value)


def candidates(layout, kind, column=None):
    """Typed contiguous words, including split IBAN/date/amount tokens."""
    result, seen = [], set()
    by_line = {}
    for token in layout["tokens"]:
        by_line.setdefault(token["line"], []).append(token)
    for words in by_line.values():
        for start in range(len(words)):
            limit = 10 if kind == "iban" else 4
            for length in range(1, min(limit, len(words)-start)+1):
                group = words[start:start+length]
                if len(group) > 1 and any(b["box"][0]-(a["box"][0]+a["box"][2]) > .025 for a,b in zip(group,group[1:])):
                    break
                box = bounds(group)
                if column and not column[0] <= box[0]+box[2]/2 <= column[1]:
                    continue
                if matches(" ".join(t["text"] for t in group), kind):
                    if kind=="amount" and start+length<len(words):
                        sign=words[start+length]
                        if sign["text"] in ("-","+","−") and sign["box"][0]-(box[0]+box[2])<.015:
                            group=group+[sign]
                            box=bounds(group)
                    key = tuple(t["id"] for t in group)
                    if key not in seen:
                        seen.add(key)
                        result.append({"tokens": group, "box": box})
                    break
    if kind=="amount":
        largest=[]
        for item in sorted(result,key=lambda c:-len(c["tokens"])):
            ids={t["id"] for t in item["tokens"]}
            if not any(ids <= {t["id"] for t in chosen["tokens"]} for chosen in largest):
                largest.append(item)
        return largest
    return result


def selected(layout, ids):
    wanted = set(ids)
    return [t for t in layout["tokens"] if t["id"] in wanted]


def text_lines(tokens):
    lines = {}
    for token in tokens:
        lines.setdefault(token["line"], []).append(token)
    return sorted((sorted(group,key=lambda t:t["box"][0]) for group in lines.values()),
                  key=lambda group: bounds(group)[1])


def first_column(tokens):
    """A multiline name selection must not absorb distant header columns."""
    result=[]
    for token in sorted(tokens,key=lambda t:t["box"][0]):
        if result and token["box"][0]-(result[-1]["box"][0]+result[-1]["box"][2])>.045:
            break
        result.append(token)
    return result


def row_family(tokens):
    """Only known transaction-type words enter profiles, never party names."""
    lines = text_lines(tokens)
    text = " ".join(t["text"].upper() for t in (lines[0] if lines else []))
    if re.search(r"\b(?:POS|E-COMM|ECOMM|KARTENZAHLUNG)\b",text):
        return "card"
    if "LASTSCHRIFT" in text:
        return "direct_debit"
    if "ÜBERWEISUNG" in text or "UEBERWEISUNG" in text:
        return "transfer"
    return "generic"


def table_context(layout):
    """Recognize printed column headings, with no fixed page coordinates."""
    for line in text_lines(layout["tokens"]):
        captions = [(t,re.sub(r"[^a-zäöü]","",t["text"].lower())) for t in line]
        amounts = [t for t,word in captions if word in ("betrag","amount")]
        booking = [t for t,word in captions if word in ("datum","date","buchungsdatum") or word.startswith("buchungsnr") or word.startswith("buchungstext")]
        if not amounts or not booking:
            continue
        values = [t for t,word in captions if word in ("wert","valuta","wertstellung")]
        amount = min(amounts,key=lambda t:t["box"][0])
        return {"top":max(t["box"][1]+t["box"][3] for t in line)+.002,
                "left":min(t["box"][0] for t in booking)-.01,
                "amount_column":[max(0,amount["box"][0]-.015),1],
                "value_column":([max(0,values[0]["box"][0]-.015),amount["box"][0]-.005] if values else None)}
    return None


def summary_boundary(layout,top=0):
    """Account-summary boxes are outside the transaction table.

    An opening balance alone above the first booking is not an end marker.
    Multiple summary captions or a closing/totals caption start the footer.
    """
    labels={"alterkontostand":"opening","neuerkontostand":"closing",
            "summederbelastungen":"debits","summedergutschriften":"credits"}
    boundaries=[]
    for line in text_lines([t for t in layout["tokens"] if t.get("rotation",0)==0]):
        if bounds(line)[1]<=top:
            continue
        matches_found=[]
        for start in range(len(line)):
            for count in range(1,min(4,len(line)-start)+1):
                phrase="".join(re.sub(r"[^a-zäöüß]","",t["text"].casefold()) for t in line[start:start+count])
                if phrase in labels:
                    matches_found.append((start,labels[phrase],bounds(line[start:start+count])[1]))
                    break
        roles={match[1] for match in matches_found}
        if len(roles)>=2 or any(start==0 and role!="opening" for start,role,y in matches_found):
            boundaries.append(min(y for start,role,y in matches_found)-.001)
    return min(boundaries) if boundaries else None


def block_structure(profile,layout):
    context = table_context(layout)
    top = context["top"] if context else 0
    footer, continuation_footer = summary_boundary(layout,top) or 1, False
    for line in text_lines(layout["tokens"]):
        y = bounds(line)[1]
        if y <= top:
            continue
        text = " ".join(t["text"].lower() for t in line).strip()
        if text.startswith(("fortsetzung folgt","neuer saldo","alter saldo","kontostand","endsaldo","anfangssaldo","summe soll","summe haben")):
            if y < footer:
                footer = y-.003
                continuation_footer = text.startswith("fortsetzung folgt")
    date_matches = [c for c in candidates(layout,"date") if top<=c["box"][1]<footer]
    if context:
        limit = min(context["left"]+.12,context["value_column"][0] if context["value_column"] else context["amount_column"][0])
        possible = [c for c in date_matches if context["left"]-.005 <= c["box"][0] < limit]
        # A card timestamp is a date too. Only the leftmost recurring date
        # column starts bookings; the inline purchase date never does.
        if possible:
            left = min(c["box"][0] for c in possible)
            anchors = [c for c in possible if abs(c["box"][0]-left)<.014]
        else:
            anchors = []
    else:
        anchors = [c for c in date_matches if any(a["column"][0]<=c["box"][0]+c["box"][2]/2<=a["column"][1] for a in profile["anchors"])]
    by_line = {}
    for anchor in sorted(anchors,key=lambda c:c["box"][0]):
        by_line.setdefault(anchor["tokens"][0]["line"],anchor)
    anchors = sorted(by_line.values(),key=lambda c:c["box"][1])
    amount_column = (context["amount_column"] if context else profile.get("amount_column"))
    if not amount_column:
        amount_rules = [r for r in profile["transaction_rules"] if r["field"]=="transaction.amount"]
        amount_column = ([max(0,min(r["column"][0] for r in amount_rules)-.015),1] if amount_rules else [.7,1])
    value_column = context["value_column"] if context else profile.get("value_column")
    return anchors,amount_column,value_column,footer,continuation_footer,context


def transaction_blocks(profile,layout):
    anchors,amount_column,value_column,footer,continues,context=block_structure(profile,layout)
    blocks=[]
    heights=sorted(t["box"][3] for t in layout["tokens"] if t["box"][3]>0)
    normal_height=heights[len(heights)//2] if heights else .012
    for index,anchor in enumerate(anchors):
        ay=anchor["box"][1]
        bottom=anchors[index+1]["box"][1]-.002 if index+1<len(anchors) else footer
        left=max(0,anchor["box"][0]-.008)
        group=[t for t in layout["tokens"] if t.get("rotation",0)==0 and ay-.004<=t["box"][1]+t["box"][3]/2<bottom and t["box"][0]>=left
               and not (t["box"][3]>normal_height*2.8 and t["box"][2]<t["box"][3]*.5)]
        amounts=candidates({**layout,"tokens":group},"amount",amount_column)
        # A right-aligned terminal amount is authoritative; card purchase
        # amounts in the description column must never be used as row totals.
        terminal=max(amounts,key=lambda c:(c["box"][1],c["box"][0])) if amounts else None
        partial=terminal is None
        if partial and not (context and index==len(anchors)-1 and continues):
            continue
        if terminal and profile.get("amount_terminal",True):
            end=terminal["box"][1]+terminal["box"][3]+.003
            group=[t for t in group if t["box"][1]+t["box"][3]/2<=end]
        elif terminal and index==len(anchors)-1 and footer==1:
            learned_height=max((r["box"][3] for r in profile["row_rules"]),default=normal_height)
            end=max(terminal["box"][1]+terminal["box"][3],ay+learned_height)+.006
            group=[t for t in group if t["box"][1]+t["box"][3]/2<=end]
        if not group:
            continue
        values=candidates({**layout,"tokens":group},"date",value_column) if value_column else []
        if not value_column:
            values=[v for v in candidates({**layout,"tokens":group},"date") if v["box"][0]>anchor["box"][0]+.08 and v["box"][0]<amount_column[0]]
        value=min(values,key=lambda v:abs(v["box"][1]-(terminal["box"][1] if terminal else ay))) if values else None
        blocks.append({"tokens":group,"anchor":anchor,"amount":terminal,"value_date":value,
                       "partial":partial,"family":row_family(group)})
    return blocks


def block_body_tokens(block):
    excluded=set()
    for key in ("anchor","amount","value_date"):
        if block.get(key):
            excluded.update(t["id"] for t in block[key]["tokens"])
    return [t for t in block["tokens"] if t["id"] not in excluded]


def compile_profile(workspace, get_layout):
    samples, ignored = [], 0
    for document in workspace["documents"]:
        for annotation in document["annotations"]:
            if annotation["kind"] != "example":
                continue
            layout = get_layout(document["document_id"], annotation["page"])
            tokens = selected(layout, annotation["token_ids"])
            tokens=[t for t in tokens if t.get("rotation",0)==0]
            kind = value_type(annotation["field"])
            if not tokens or not layout["recognition_supported"] or (kind != "text" and not matches(" ".join(t["text"] for t in tokens),kind)):
                ignored += 1
                continue
            groups = [first_column(line) for line in text_lines(tokens)] if annotation["field"] == "owner.name" else [tokens]
            for index,group in enumerate(groups):
                sample={**annotation,"document_id":document["document_id"],"tokens":group,
                        "box":bounds(group),"layout":layout}
                if annotation["field"]=="owner.name" and annotation.get("entity_id") and len(groups)>1:
                    sample["entity_id"]=f"holder-{min(99,int(annotation['entity_id'].split('-')[1])+index)}"
                samples.append(sample)
    # Repeated owner names are separate entities, including old examples made
    # before explicit owner slots existed. No name string enters the profile.
    for sample in samples:
        if sample["field"] == "owner.name" and not sample.get("entity_id"):
            peers = sorted({round(s["box"][1],4) for s in samples if s["field"]=="owner.name" and s["document_id"]==sample["document_id"] and s["page"]==sample["page"]})
            sample["entity_id"] = f"holder-{peers.index(round(sample['box'][1],4))+1}"
    anchor_samples = [s for s in samples if s["field"]=="transaction.booking_date"]
    if not anchor_samples:
        for sample in samples:
            if sample["field"]=="transaction.row":
                dates=candidates({**sample["layout"],"tokens":sample["tokens"]},"date")
                if dates:
                    anchor_samples.append({**sample,"box":min(dates,key=lambda c:c["box"][0])["box"]})
    anchors=[]
    for sample in anchor_samples:
        x,y,w,h=sample["box"]
        column=[max(0,x-.008),min(1,x+w+.008)]
        if not any(abs(sum(a["column"])/2-sum(column)/2)<.01 for a in anchors):
            anchors.append({"column":column,"value_type":"date"})
    amount_samples=[s["box"] for s in samples if s["field"]=="transaction.amount"]
    terminals=[]
    for sample in samples:
        if sample["field"]=="transaction.row":
            amounts=candidates({**sample["layout"],"tokens":sample["tokens"]},"amount")
            if amounts:
                rightmost=max(amounts,key=lambda a:a["box"][0]+a["box"][2]/2)
                amount_samples.append(rightmost["box"])
                terminals.append(sample["box"][1]+sample["box"][3]-(rightmost["box"][1]+rightmost["box"][3])<.006)
    profile={"schema_version":1,"engine":"layout-examples-v2","profile_name":workspace["profile_name"],
             "recognition_revision":RECOGNITION_REVISION,
             "anchors":anchors,"header_rules":[],"row_rules":[],"transaction_rules":[],
             "row_requires_amount":bool(amount_samples),"amount_terminal":all(terminals) if terminals else True}
    profile["auto_table"]=any(table_context(s["layout"]) is not None for s in samples)
    if amount_samples:
        profile["amount_column"]=[max(0,min(b[0] for b in amount_samples)-.02),1]
    value_samples=[s["box"] for s in samples if s["field"]=="transaction.value_date"]
    if value_samples:
        profile["value_column"]=[max(0,min(b[0] for b in value_samples)-.01),min(1,max(b[0]+b[2] for b in value_samples)+.01)]
    for sample in samples:
        x,y,w,h=sample["box"]
        field=sample["field"]
        if field=="transaction.full_text":
            continue # Derived from the entire block, never a learned substring.
        rule={"field":field,"value_type":value_type(field),"box":[x,y,w,h],
              "page_scope":"first" if sample["page"]==1 else "following"}
        if not field.startswith("transaction."):
            context=table_context(sample["layout"])
            if context and y+h/2>=context["top"]:
                ignored+=1
                continue
            if sample.get("entity_id"):
                rule["entity_id"]=sample["entity_id"]
            profile["header_rules"].append(rule)
            continue
        blocks=transaction_blocks(profile,sample["layout"])
        wanted={t["id"] for t in sample["tokens"]}
        related=[b for b in blocks if wanted & {t["id"] for t in b["tokens"]}]
        if not related:
            ignored+=1
            continue
        block=max(related,key=lambda b:len(wanted & {t["id"] for t in b["tokens"]}))
        ay=block["anchor"]["box"][1]
        lines=text_lines(block["tokens"])
        selected_lines=[i for i,line in enumerate(lines) if any(t["id"] in wanted for t in line)]
        rule.update({"dy":[y-ay,y+h-ay],"column":[max(0,x-.006),min(1,x+w+.012)],
                     "line_offset":min(selected_lines,default=0),"line_count":len(selected_lines),
                     "to_end":field=="transaction.description" and bool(selected_lines) and max(selected_lines)==len(lines)-1,
                     "family":block["family"]})
        if field=="transaction.row":
            profile["row_rules"].append(rule)
        else:
            profile["transaction_rules"].append(rule)
    for rule in profile["transaction_rules"]:
        if rule["value_type"]=="text":
            later=[r["box"][0] for r in profile["transaction_rules"] if r["box"][0]>rule["box"][0]+.025]
            if later:
                rule["column"][1]=max(rule["column"][1],min(later)-.008)
    for key in ("header_rules","row_rules","transaction_rules"):
        profile[key]=list({str(rule):rule for rule in profile[key]}.values())
    profile["ignored_example_count"]=ignored
    return profile


def predict(profile, layout, document_id, existing=(), previous=None, row_events=None, field_links=None):
    if not layout["recognition_supported"]:
        return []
    output,seen=[],set()
    def add(field,tokens,reason,row_id=None,**properties):
        ids=tuple(sorted(t["id"] for t in tokens))
        if not ids:
            return None
        identifier=hashlib.sha256(f"{document_id}:{layout['page']}:{field}:{ids}".encode()).hexdigest()[:24]
        def overlaps(annotation):
            return len(set(annotation["token_ids"]) & set(ids))/min(len(annotation["token_ids"]),len(ids))>=.7
        same=next((a for a in existing if a["page"]==layout["page"] and a["field"]==field and overlaps(a) and a["kind"] in ("example","confirmed")),None)
        if same:
            if field=="transaction.row" and row_events is not None:
                row_events.append({"id":same["id"],"page":layout["page"],**properties})
            elif row_id is not None and field_links is not None:
                # An existing manual/confirmed value may predate its row.
                # Keep its text, status and id; repair only the relationship.
                field_links.append({"id":same["id"],"field":field,"row_id":row_id})
            return same["id"]
        if any(a["page"]==layout["page"] and a["field"]==field and a["kind"]=="rejected" and overlaps(a) for a in existing):
            return None
        key=(field,ids)
        if key not in seen:
            seen.add(key)
            output.append({"id":identifier,"page":layout["page"],"field":field,"token_ids":list(ids),
                           "kind":"suggestion","reason":reason,"row_id":row_id,
                           "recognition_revision":RECOGNITION_REVISION,**properties})
            if field=="transaction.row" and row_events is not None:
                row_events.append({"id":identifier,"page":layout["page"],**properties})
        return identifier
    for rule in profile["header_rules"]:
        if (layout["page"]==1)!=(rule["page_scope"]=="first"):
            continue
        x,y,w,h=rule["box"]
        context=table_context(layout)
        if context and y+h/2>=context["top"]:
            continue
        group=[t for t in layout["tokens"] if t.get("rotation",0)==0 and abs(t["box"][1]+t["box"][3]/2-(y+h/2))<=max(.006,h*.6)
               and x-.008<=t["box"][0]+t["box"][2]/2<=min(1,x+max(w*1.5,.08))]
        if group and matches(" ".join(t["text"] for t in group),rule["value_type"]):
            add(rule["field"],group,"Passende Kopfzeile",entity_id=rule.get("entity_id"))
    blocks=transaction_blocks(profile,layout)
    if previous:
        anchors,amount_column,value_column,footer,continues,context=block_structure(profile,layout)
        if context:
            bottom=anchors[0]["box"][1]-.002 if anchors else footer
            group=[t for t in layout["tokens"] if t.get("rotation",0)==0 and context["top"]<=t["box"][1]<bottom and t["box"][0]>=context["left"]]
            amounts=candidates({**layout,"tokens":group},"amount",amount_column)
            if amounts or (group and not anchors and continues):
                terminal=max(amounts,key=lambda a:a["box"][1]) if amounts else None
                if terminal:
                    end=terminal["box"][1]+terminal["box"][3]+.003
                    group=[t for t in group if t["box"][1]+t["box"][3]/2<=end]
                values=candidates({**layout,"tokens":group},"date",value_column) if value_column else []
                blocks.insert(0,{"tokens":group,"anchor":None,"amount":terminal,"value_date":max(values,key=lambda a:a["box"][1]) if values else None,
                    "partial":terminal is None,"family":previous.get("family","generic"),"continuation_of":previous["id"]})
    for block in blocks:
        row_id=add("transaction.row",block["tokens"],"Block zwischen linken Buchungsdaten; rechter Betrag als Abschluss",
                   partial=block["partial"],family=block["family"],continuation_of=block.get("continuation_of"))
        if row_id is None:
            continue
        # Dates, amounts and currencies are identified within the entire block,
        # independent of the number of continuation lines in the example.
        if block["anchor"]:
            add("transaction.booking_date",block["anchor"]["tokens"],"Linkes Datum beginnt die Buchung",row_id)
        if block["amount"]:
            add("transaction.amount",block["amount"]["tokens"],"Rechter Buchungsbetrag, nicht Betrag im Kartentext",row_id)
        if block["value_date"]:
            add("transaction.value_date",block["value_date"]["tokens"],"Wertdatum nahe dem abschließenden Betrag",row_id)
        body=block_body_tokens(block)
        add("transaction.full_text",body,"Vollständiger Buchungstext; Zeichen und Kürzel unverändert",row_id)
        lines=text_lines(block["tokens"])
        for rule in profile["transaction_rules"]:
            if rule["field"] in ("transaction.row","transaction.booking_date","transaction.amount","transaction.value_date"):
                continue
            if rule["value_type"]!="text":
                for found in candidates({**layout,"tokens":block["tokens"]},rule["value_type"],rule["column"]):
                    add(rule["field"],found["tokens"],"Passendes Format in der Buchungsspalte",row_id)
                continue
            if rule.get("family","generic") not in ("generic",block["family"]):
                continue
            offset=rule.get("line_offset",0)
            count=max(1,rule.get("line_count",1))
            chosen=lines[offset:] if rule.get("to_end") else lines[offset:offset+count]
            group=[t for line in chosen for t in line if rule["column"][0]<=t["box"][0]+t["box"][2]/2<=rule["column"][1]]
            if group:
                add(rule["field"],group,"Textposition innerhalb derselben Buchungsart",row_id)
    return output


def recognize_page(profile,layout,document_id,existing=(),previous=None):
    rows,links=[],[]
    suggestions=predict(profile,layout,document_id,existing,previous,row_events=rows,field_links=links)
    parents={}
    for link in links:
        parents.setdefault(link["id"],set()).add(link["row_id"])
    safe_links=list({link["id"]:link for link in links if len(parents[link["id"]])==1}.values())
    pending=next((row for row in reversed(rows) if row.get("partial")),None)
    return {"suggestions":suggestions,"rows":rows,"field_links":safe_links,
            "ambiguous_field_links":sum(len(ids)>1 for ids in parents.values()),
            "carry":({"id":pending["id"],"family":pending.get("family","generic")} if pending else None),
            "recognition_revision":RECOGNITION_REVISION}


def repair_missing_parents(workspace):
    """Restore only unambiguous missing links; never change field contents."""
    repaired=0
    for document in workspace["documents"]:
        rows=[a for a in document["annotations"] if a["field"]=="transaction.row" and a["kind"]!="rejected"
              and (a["kind"]!="suggestion" or a.get("recognition_revision")==RECOGNITION_REVISION)]
        known={row["id"] for row in rows}
        for field in document["annotations"]:
            if field["kind"]=="rejected" or not field["field"].startswith("transaction.") or field["field"]=="transaction.row" or field.get("row_id") in known:
                continue
            ids=set(field["token_ids"])
            candidates=[row for row in rows if row["page"]==field["page"] and ids and ids<=set(row["token_ids"])]
            if len(candidates)==1:
                field["row_id"]=candidates[0]["id"]
                repaired+=1
    return repaired
