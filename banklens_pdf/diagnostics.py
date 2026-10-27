"""Read-only diagnostic counts. Never return input strings or token IDs."""
from .fields import compile_profile, block_structure, transaction_blocks, recognize_page, summary_boundary
from .preview import Review
from .version import APP_VERSION,RECOGNITION_REVISION


def diagnose(directory,state_directory,document_number,page_number):
    review=Review(directory,state_directory)
    document_id=f"document-{document_number:03d}"
    layout=review.text_layout(document_id,page_number)
    workspace=review.load_workspace()
    learned=review.learn(workspace)
    automatic=compile_profile(review.empty_workspace(),review.text_layout)
    def counts(profile):
        anchors,amounts,values,footer,continues,context=block_structure(profile,layout)
        blocks=transaction_blocks(profile,layout)
        return {"table_header_found":context is not None,"booking_starts":len(anchors),
                "blocks":len(blocks),"complete_blocks":sum(not b["partial"] for b in blocks),
                "open_blocks":sum(b["partial"] for b in blocks),"continuation_footer":continues}
    annotations=next(d for d in workspace["documents"] if d["document_id"]==document_id)["annotations"]
    page_annotations=[a for a in annotations if a["page"]==page_number]
    carry=None
    outcome=None
    for number in range(1,page_number+1):
        incoming=carry
        outcome=recognize_page(learned,review.text_layout(document_id,number),document_id,
            [a for a in annotations if a["page"]==number and a["kind"]!="suggestion"],carry)
        carry=outcome["carry"]
    fresh=recognize_page(learned,layout,document_id,previous=incoming)
    lookup={t["id"]:t for t in layout["tokens"]}
    roots={a["id"] for a in page_annotations if a["field"]=="transaction.row" and a["kind"]!="rejected"}
    structural_fields=[a for a in page_annotations if a["field"] in ("transaction.amount","transaction.value_date") and a["kind"]!="rejected"]
    summary_top=summary_boundary(layout)
    last_blocks=transaction_blocks(learned,layout)
    last_amount=last_blocks[-1]["amount"] if last_blocks else None
    return {"operation":"diagnostic_counts_only","app_version":APP_VERSION,"recognition_revision":RECOGNITION_REVISION,"document_id":document_id,"page":page_number,
            "page_rotation":layout["rotation"],"recognition_supported":layout["recognition_supported"],
            "horizontal_words":sum(t.get("rotation",0)==0 for t in layout["tokens"]),
            "other_orientation_words":sum(t.get("rotation",0)!=0 for t in layout["tokens"]),
            "automatic":counts(automatic),"from_examples":counts(learned),
            "ignored_examples":learned.get("ignored_example_count",0),
            "saved_examples_on_page":sum(a["kind"]=="example" for a in page_annotations),
            "saved_suggestions_on_page":sum(a["kind"]=="suggestion" for a in page_annotations),
            "unversioned_suggestions_on_page":sum(a["kind"]=="suggestion" and a.get("recognition_revision")!=RECOGNITION_REVISION for a in page_annotations),
            "linked_incoming_fragments":sum(bool(r.get("continuation_of")) for r in outcome["rows"]),
            "fresh_amount_fields":sum(a["field"]=="transaction.amount" for a in fresh["suggestions"]),
            "summary_boundary_found":summary_top is not None,
            "last_booking_amount_before_summary":bool(summary_top is not None and last_amount and last_amount["box"][1]+last_amount["box"][3]<=summary_top),
            "transaction_amounts_in_summary":sum(a["field"]=="transaction.amount" and any(lookup[i]["box"][1]>=summary_top for i in a["token_ids"] if i in lookup) for a in fresh["suggestions"]) if summary_top is not None else 0,
            "saved_amount_fields":sum(a["field"]=="transaction.amount" and a["kind"]!="rejected" for a in page_annotations),
            "saved_current_amount_suggestions":sum(a["field"]=="transaction.amount" and a["kind"]=="suggestion" and a.get("recognition_revision")==RECOGNITION_REVISION for a in page_annotations),
            "rejected_amount_fields":sum(a["field"]=="transaction.amount" and a["kind"]=="rejected" for a in page_annotations),
            "rejected_value_date_fields":sum(a["field"]=="transaction.value_date" and a["kind"]=="rejected" for a in page_annotations),
            "structural_fields_without_parent":sum(not a.get("row_id") for a in structural_fields),
            "structural_fields_with_missing_parent":sum(bool(a.get("row_id")) and a["row_id"] not in roots for a in structural_fields),
            "structural_parent_links_to_repair":sum(link["field"] in ("transaction.amount","transaction.value_date") and any(a["id"]==link["id"] and a.get("row_id")!=link["row_id"] for a in page_annotations) for link in outcome["field_links"]),
            "parent_links_repaired_on_load":workspace.get("repaired_parent_links",0),
            "continuation_carried_forward":outcome["carry"] is not None,
            "fresh_suggestions_with_rotated_text":sum(any(lookup[i].get("rotation",0)!=0 for i in a["token_ids"] if i in lookup) for a in outcome["suggestions"]),
            "originals_modified":not all(review.source_is_current(d["document_id"]) for d in review.documents)}
