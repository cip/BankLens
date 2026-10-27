"""Artificial layout matching the screenshot's structure, never its values."""
import json
import unittest

from banklens_pdf.fields import compile_profile, predict, transaction_blocks, recognize_page, repair_missing_parents, summary_boundary
from banklens_pdf.version import RECOGNITION_REVISION


def layout_fixture(page=1):
    words,lines,tags=[],[],{}
    def line(y, entries, tag=None):
        ids=[]
        for entry in entries:
            x,text,width=entry
            ids.append(len(words))
            words.append({"id":len(words),"text":text,"box":[x,y,width,.012],"line":len(lines)})
        lines.append({"id":len(lines),"token_ids":ids})
        if tag:
            tags[tag]=ids
        return ids
    line(.15,[(.12,"ERIKA_BEISPIEL",.21)],"owner1")
    line(.18,[(.12,"ALEX_MUSTER",.19),(.55,"31.10.2026",.1),(.75,"EUR",.04)],"owner2")
    line(.32,[(.12,"Buchungsnr./Buchungstext",.30),(.75,"Wert",.04),(.84,"Betrag",.06)],"headings")
    if page==2:
        line(.37,[(.18,"MUSTERENERGIE",.25)],"continuation-name")
        line(.394,[(.18,"Mandatsref:",.12),(.32,"MUSTERMANDAT",.2)])
        line(.418,[(.18,"Creditor-ID:",.13),(.34,"MUSTERID",.12),(.75,"06.10",.07),(.91,"18,00-",.08)],"continuation-end")
        y=.48
    else:
        y=.39
    first=line(y,[(.12,"04.10",.07),(.20,"POS",.04),(.32,"99,10",.07),(.52,"03.10.",.08)],"card-start")
    second=line(y+.024,[(.20,"MUSTERLADEN",.23),(.75,"04.10",.07),(.91,"12,34-",.08)],"card-end")
    tags["card"]=first+second
    if page==1:
        all_ids=[]
        all_ids+=line(.454,[(.12,"04.10",.07),(.20,"SEPA",.06),(.28,"Lastschrift",.16)],"debit-start")
        all_ids+=line(.478,[(.20,"MUSTERFIRMA",.23)],"debit-name")
        all_ids+=line(.502,[(.20,"Mandatsref:",.13),(.36,"MUSTERMANDAT",.20)])
        all_ids+=line(.526,[(.20,"Creditor-ID:",.15),(.40,"MUSTERID",.12),(.75,"04.10",.07),(.91,"25,00",.065),(.98,"-",.008)],"debit-end")
        tags["debit"]=all_ids
        line(.56,[(.12,"05.10",.07),(.20,"E-COMM",.1),(.38,"4,00",.06)],"third-start")
        line(.584,[(.20,"ANDERER_LADEN",.25),(.75,"05.10",.07),(.91,"4,00-",.08)],"third-end")
        line(.62,[(.12,"06.10",.07),(.20,"SEPA",.06),(.28,"Lastschrift",.16)],"partial")
        line(.66,[(.25,"Fortsetzung",.16),(.43,"folgt",.08),(.53,"auf",.05),(.60,"Auszugsnummer",.20)],"footer")
        words.append({"id":len(words),"text":"ROTATED_STAMP","box":[.03,.44,.01,.12],"line":len(lines),"rotation":270})
    return {"page":page,"rotation":0,"tokens":words,"lines":lines,"recognition_supported":True},tags


def sample(identifier,field,ids,entity=None):
    return {"id":identifier,"page":1,"field":field,"token_ids":ids,"kind":"example","row_id":None,"entity_id":entity}


class MultiLineTests(unittest.TestCase):
    def setUp(self):
        self.layout,self.tags=layout_fixture()
        t=self.tags
        self.examples=[sample("owners","owner.name",t["owner1"]+[t["owner2"][0]]),
                       sample("row","transaction.row",t["card"]),sample("date","transaction.booking_date",[t["card-start"][0]]),
                       sample("recipient","transaction.recipient",[t["card-end"][0]]),
                       sample("value","transaction.value_date",[t["card-end"][1]]),
                       sample("amount","transaction.amount",[t["card-end"][2]])]
        self.workspace={"profile_name":"Layouttest","documents":[{"document_id":"document-001","annotations":self.examples}]}
        self.profile=compile_profile(self.workspace,lambda d,p:self.layout)

    def test_two_line_example_recognizes_four_line_booking_and_correct_amount(self):
        results=predict(self.profile,self.layout,"document-001",self.examples)
        roots=[r for r in results if r["field"]=="transaction.row"]
        self.assertEqual(len(roots),3)
        debit=next(r for r in roots if set(self.tags["debit-start"])<=set(r["token_ids"]))
        self.assertEqual(set(debit["token_ids"]),set(self.tags["debit"]))
        amount=next(r for r in results if r["row_id"]==debit["id"] and r["field"]=="transaction.amount")
        self.assertEqual(amount["token_ids"],self.tags["debit-end"][-2:])
        value=next(r for r in results if r["row_id"]==debit["id"] and r["field"]=="transaction.value_date")
        self.assertEqual(value["token_ids"],[self.tags["debit-end"][-3]])
        # Card receiver rules must not label a different direct-debit layout.
        self.assertFalse(any(r["row_id"]==debit["id"] and r["field"]=="transaction.recipient" for r in results))
        self.assertFalse(any(set(r["token_ids"]) & set(self.tags["footer"]) for r in results))
        self.assertFalse(any(self.layout["tokens"][-1]["id"] in r["token_ids"] for r in results))

    def test_multiple_owners_are_separate_instances_and_values_are_not_stored(self):
        rules=[r for r in self.profile["header_rules"] if r["field"]=="owner.name"]
        self.assertEqual({r["entity_id"] for r in rules},{"holder-1","holder-2"})
        fresh=predict(self.profile,self.layout,"document-002")
        names=[r for r in fresh if r["field"]=="owner.name"]
        self.assertEqual(len(names),2)
        self.assertEqual({r["entity_id"] for r in names},{"holder-1","holder-2"})
        for word in self.layout["tokens"]:
            if word["text"].startswith(("ERIKA","ALEX","MUSTER","ANDERER")):
                self.assertNotIn(word["text"],json.dumps(self.profile))

    def test_caption_is_not_a_valid_amount_example(self):
        self.workspace["documents"][0]["annotations"].append(sample("bad-caption","transaction.amount",[self.tags["headings"][-1]]))
        profile=compile_profile(self.workspace,lambda d,p:self.layout)
        self.assertEqual(profile["ignored_example_count"],1)
        self.assertEqual(profile["amount_column"],self.profile["amount_column"])

    def test_partial_booking_and_following_page_fragment_are_linked(self):
        first=predict(self.profile,self.layout,"document-001",self.examples)
        partial=next(a for a in first if a.get("partial"))
        self.assertEqual(partial["token_ids"],self.tags["partial"])
        following,tags=layout_fixture(page=2)
        second=predict(self.profile,following,"document-001",previous={"id":partial["id"],"family":partial["family"]})
        fragment=next(a for a in second if a.get("continuation_of"))
        self.assertEqual(fragment["continuation_of"],partial["id"])
        self.assertIn(tags["continuation-name"][0],fragment["token_ids"])
        amount=next(a for a in second if a.get("row_id")==fragment["id"] and a["field"]=="transaction.amount")
        self.assertEqual(amount["token_ids"],[tags["continuation-end"][-1]])

    def test_saved_example_or_confirmation_still_carries_to_next_page(self):
        first=recognize_page(self.profile,self.layout,"document-001",self.examples)
        pending=next(a for a in first["suggestions"] if a.get("partial"))
        for kind in ("example","confirmed"):
            with self.subTest(kind=kind):
                existing=self.examples+[{**pending,"kind":kind}]
                outcome=recognize_page(self.profile,self.layout,"document-001",existing)
                self.assertEqual(outcome["carry"]["id"],pending["id"])
                self.assertFalse(any(a["id"]==pending["id"] for a in outcome["suggestions"]))
                following,_=layout_fixture(page=2)
                second=recognize_page(self.profile,following,"document-001",previous=outcome["carry"])
                self.assertTrue(any(row.get("continuation_of")==pending["id"] for row in second["rows"]))
                fragment=next(a for a in second["suggestions"] if a.get("continuation_of"))
                confirmed=recognize_page(self.profile,following,"document-001",existing=[{**fragment,"kind":"confirmed"}],previous=outcome["carry"])
                self.assertTrue(any(row.get("continuation_of")==pending["id"] for row in confirmed["rows"]))

    def test_new_predictions_are_versioned_and_marginal_text_is_not_a_header(self):
        stamp=self.layout["tokens"][-1]
        self.workspace["documents"][0]["annotations"].append(sample("bad-stamp","owner.name",[stamp["id"]]))
        self.workspace["documents"][0]["annotations"].append(sample("bad-body-name","owner.name",self.tags["debit-name"]))
        profile=compile_profile(self.workspace,lambda d,p:self.layout)
        self.assertEqual(profile["ignored_example_count"],2)
        result=recognize_page(profile,self.layout,"document-001")
        self.assertTrue(all(a["recognition_revision"]==RECOGNITION_REVISION for a in result["suggestions"]))
        self.assertFalse(any(stamp["id"] in a["token_ids"] for a in result["suggestions"]))

    def test_manual_amount_and_value_date_are_linked_to_detected_booking(self):
        tags=self.tags
        for kind in ("example","confirmed"):
            with self.subTest(kind=kind):
                amount={**sample("existing-amount","transaction.amount",tags["debit-end"][-2:]),"kind":kind}
                value={**sample("existing-value","transaction.value_date",[tags["debit-end"][-3]]),"kind":kind}
                original=json.dumps([amount,value],sort_keys=True)
                outcome=recognize_page(self.profile,self.layout,"document-001",self.examples+[amount,value])
                root=next(a for a in outcome["suggestions"] if a["field"]=="transaction.row" and tags["debit-start"][0] in a["token_ids"])
                links={link["id"]:link["row_id"] for link in outcome["field_links"]}
                self.assertEqual(links["existing-amount"],root["id"])
                self.assertEqual(links["existing-value"],root["id"])
                self.assertFalse(any(a["id"] in ("existing-amount","existing-value") for a in outcome["suggestions"]))
                self.assertEqual(json.dumps([amount,value],sort_keys=True),original)

    def test_wrong_existing_parent_is_repaired_to_existing_confirmed_row(self):
        initial=recognize_page(self.profile,self.layout,"document-001")
        row=next(a for a in initial["suggestions"] if a["field"]=="transaction.row" and self.tags["debit-start"][0] in a["token_ids"])
        row={**row,"id":"saved-row","kind":"confirmed"}
        amount={**sample("saved-amount","transaction.amount",self.tags["debit-end"][-2:]),"row_id":"old-removed-row","kind":"confirmed"}
        outcome=recognize_page(self.profile,self.layout,"document-001",self.examples+[row,amount])
        self.assertTrue(any(link["id"]=="saved-amount" and link["row_id"]=="saved-row" for link in outcome["field_links"]))

    def test_unambiguous_missing_links_are_repaired_without_recognition(self):
        root={**sample("root","transaction.row",self.tags["debit"]),"kind":"suggestion","recognition_revision":RECOGNITION_REVISION}
        amount=sample("amount","transaction.amount",self.tags["debit-end"][-2:])
        workspace={"documents":[{"annotations":[root,amount]}]}
        self.assertEqual(repair_missing_parents(workspace),1)
        self.assertEqual(amount["row_id"],"root")
        self.assertEqual(amount["kind"],"example")
        self.assertEqual(amount["token_ids"],self.tags["debit-end"][-2:])
        self.assertEqual(repair_missing_parents(workspace),0)
        amount["row_id"]=None
        workspace["documents"][0]["annotations"].append({**root,"id":"overlapping-row"})
        self.assertEqual(repair_missing_parents(workspace),0)
        self.assertIsNone(amount["row_id"])

    def test_last_booking_excludes_account_balances_and_totals(self):
        layout,tags=layout_fixture(page=2)
        # Artificial statement summary, matching the layout but not the values
        # of the user's screenshot. All four boxes sit below the booking table.
        next_id=max(t["id"] for t in layout["tokens"])+1
        for line_id,y,entries in [(50,.67,[(.12,"alter",.045),(.175,"Kontostand",.10),(.36,"Summe",.06),(.43,"der",.03),(.47,"Belastungen",.12),(.62,"Summe",.06),(.69,"der",.03),(.73,"Gutschriften",.12),(.87,"neuer",.05),(.93,"Kontostand",.065)]),
                                  (51,.71,[(.12,"123,45",.08),(.43,"300,00-",.1),(.69,"100,00",.1),(.91,"876,54",.08)])]:
            for x,text,width in entries:
                layout["tokens"].append({"id":next_id,"text":text,"box":[x,y,width,.012],"line":line_id})
                next_id+=1
        result=recognize_page(self.profile,layout,"document-001")
        row=next(a for a in result["suggestions"] if a["field"]=="transaction.row")
        amount=next(a for a in result["suggestions"] if a["field"]=="transaction.amount" and a["row_id"]==row["id"])
        self.assertEqual(amount["token_ids"],[tags["card-end"][-1]])
        self.assertTrue(all(t["box"][1]<.67 for t in layout["tokens"] if any(t["id"] in a["token_ids"] for a in result["suggestions"] if a["field"].startswith("transaction."))))

    def test_opening_balance_and_incidental_body_phrase_do_not_end_table(self):
        layout,_=layout_fixture(page=2)
        next_id=max(t["id"] for t in layout["tokens"])+1
        for line_id,y,entries in [(70,.345,[(.12,"alter",.05),(.18,"Kontostand",.12),(.91,"123,45",.08)]),
                                  (71,.51,[(.2,"Hinweis:",.09),(.3,"neuer",.07),(.38,"Kontostand",.12)])]:
            for x,text,width in entries:
                layout["tokens"].append({"id":next_id,"text":text,"box":[x,y,width,.012],"line":line_id})
                next_id+=1
        self.assertIsNone(summary_boundary(layout))
        self.assertEqual(len(transaction_blocks(self.profile,layout)),1)

    def test_whole_booking_excludes_next_row_and_captions(self):
        blocks=transaction_blocks(self.profile,self.layout)
        block=next(b for b in blocks if self.tags["debit-name"][0] in {t["id"] for t in b["tokens"]})
        self.assertEqual({t["id"] for t in block["tokens"]},set(self.tags["debit"]))

    def test_inline_purchase_date_cannot_start_a_booking_without_left_date(self):
        layout,tags=layout_fixture(page=2)
        layout["tokens"]=[t for t in layout["tokens"] if t["id"]!=tags["card-start"][0]]
        self.assertEqual(transaction_blocks(self.profile,layout),[])

    def test_full_text_keeps_inline_amounts_and_all_continuation_lines(self):
        result=predict(self.profile,self.layout,"document-001")
        root=next(a for a in result if a["field"]=="transaction.row" and set(self.tags["card-start"])<=set(a["token_ids"]))
        body=next(a for a in result if a["field"]=="transaction.full_text" and a["row_id"]==root["id"])
        self.assertIn(self.tags["card-start"][2],body["token_ids"]) # inline amount retained
        self.assertIn(self.tags["card-start"][3],body["token_ids"]) # purchase date retained
        self.assertNotIn(self.tags["card-start"][0],body["token_ids"])
        self.assertNotIn(self.tags["card-end"][-1],body["token_ids"])
        debit=next(a for a in result if a["field"]=="transaction.row" and set(self.tags["debit-start"])<=set(a["token_ids"]))
        body=next(a for a in result if a["field"]=="transaction.full_text" and a["row_id"]==debit["id"])
        self.assertIn(self.tags["debit-name"][0],body["token_ids"])
        self.assertGreater(len(body["token_ids"]),3)


if __name__=="__main__":
    unittest.main()
