import copy
import json
import unittest

from banklens_pdf.fields import compile_profile, predict, normalize_box


def artificial_layout(page=1, locations=(.4,.5,.6), suffix="A"):
    words, lines = [], []
    def line(y, entries):
        line_id = len(lines)
        ids = []
        for x,text,width in entries:
            identifier = len(words)
            words.append({"id":identifier,"text":text,"box":[x,y,width,.012],"line":line_id})
            ids.append(identifier)
        lines.append({"id":line_id,"token_ids":ids})
    line(.1,[(.08,"PRIVATE_OWNER_"+suffix,.18)])
    # Unrelated date must not become a transaction when amount is required.
    line(.15,[(.08,"31.12.2026",.10),(.3,"Auszugsdatum",.16)])
    for index,y in enumerate(locations):
        line(y,[(.08,f"0{index+1}.01.2026",.10),(.28,"RECIPIENT_"+suffix+str(index),.22),(.8,f"-{index+2}0,00",.10)])
        line(y+.018,[(.28,"REFERENCE_"+suffix+str(index),.20)])
    return {"page":page,"rotation":0,"recognition_supported":True,"tokens":words,"lines":lines}


def example(identifier,field,ids):
    return {"id":identifier,"page":1,"field":field,"token_ids":ids,"kind":"example","row_id":None}


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.layout = artificial_layout()
        self.annotations = [example("owner","owner.name",[0]),example("row","transaction.row",[3,4,5,6]),
                            example("date","transaction.booking_date",[3]),
                            example("recipient","transaction.recipient",[4]),
                            example("amount","transaction.amount",[5]),
                            example("reference","transaction.reference",[6])]
        self.workspace = {"profile_name":"Synthetic bank","documents":[{"document_id":"document-001","annotations":self.annotations}]}
        self.profile = compile_profile(self.workspace,lambda d,p:self.layout)

    def test_profile_contains_structure_but_no_example_values(self):
        encoded = json.dumps(self.profile)
        for word in self.layout["tokens"]:
            self.assertNotIn(word["text"],encoded)
        self.assertTrue(self.profile["anchors"])
        self.assertTrue(self.profile["row_requires_amount"])

    def test_one_multiline_example_finds_other_rows_and_subfields(self):
        results = predict(self.profile,self.layout,"document-001",self.annotations)
        self.assertEqual(sum(a["field"]=="transaction.row" for a in results),2)
        for field in ("transaction.booking_date","transaction.recipient","transaction.amount","transaction.reference"):
            self.assertEqual(sum(a["field"]==field for a in results),2,field)
        row_ids={a["id"] for a in results if a["field"]=="transaction.row"}|{"row"}
        for annotation in results:
            if annotation["field"].startswith("transaction.") and annotation["field"]!="transaction.row":
                self.assertIn(annotation["row_id"],row_ids)
        self.assertFalse(any(1 in a["token_ids"] for a in results))

    def test_profile_transfers_to_changed_values_and_vertical_positions(self):
        target = artificial_layout(page=2,locations=(.22,.34,.53),suffix="B")
        results = predict(self.profile,target,"document-002")
        self.assertEqual(sum(a["field"]=="transaction.row" for a in results),3)
        self.assertEqual(sum(a["field"]=="transaction.amount" for a in results),3)
        # First-page owner rules must not label continuation-page text.
        self.assertFalse(any(a["field"]=="owner.name" for a in results))

    def test_rejections_survive_recognition_and_do_not_train(self):
        results=predict(self.profile,self.layout,"document-001",self.annotations)
        rejected=next(a for a in results if a["field"]=="transaction.recipient")
        rejected={**rejected,"kind":"rejected"}
        again=predict(self.profile,self.layout,"document-001",self.annotations+[rejected])
        self.assertFalse(any(a["id"]==rejected["id"] for a in again))
        supplied=copy.deepcopy(self.workspace)
        supplied["documents"][0]["annotations"].append(rejected)
        self.assertEqual(compile_profile(supplied,lambda d,p:self.layout),self.profile)

    def test_suggestions_and_bulk_confirmations_do_not_become_training_examples(self):
        supplied=copy.deepcopy(self.workspace)
        suggestions=predict(self.profile,self.layout,"document-001",self.annotations)
        supplied["documents"][0]["annotations"].extend({**a,"kind":"confirmed"} for a in suggestions)
        self.assertEqual(compile_profile(supplied,lambda d,p:self.layout),self.profile)

    def test_crop_and_rotation_map_to_display_coordinates(self):
        for actual,expected in zip(normalize_box((10,20,30,40),(10,20,110,220),0),(0,.9,.2,.1)):
            self.assertAlmostEqual(actual,expected)
        x,y,w,h=normalize_box((10,20,30,40),(10,20,110,220),90)
        for actual,expected in zip((x,y,w,h),(0,0,.1,.2)):
            self.assertAlmostEqual(actual,expected)


if __name__=="__main__":
    unittest.main()
