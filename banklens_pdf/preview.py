"""Loopback-only review UI. Original pages are for the user's eyes only.

Page previews stay in memory. The separate proof mode creates sanitized copies
only after selection. Original images and document strings are never logged.
"""

from __future__ import annotations

import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import tempfile
from functools import lru_cache
from bisect import bisect_right
import re
import threading

import pypdfium2 as pdfium

from .inspect import quiet_parser
from .fields import FIELDS, compile_profile, extract_layout, recognize_page, transaction_blocks, block_body_tokens, repair_missing_parents
from .version import APP_VERSION, API_VERSION, RECOGNITION_REVISION


WEB = Path(__file__).with_name("web")
MAX_BODY = 16_000_000
RENDER_LOCK = threading.RLock()


@contextlib.contextmanager
def quiet_renderer():
    """Also discard native PDFium diagnostics, not just Python logging."""
    # PDFium and process-wide diagnostic redirection must remain serialized,
    # while idle browser sockets must never block unrelated HTTP requests.
    with RENDER_LOCK, quiet_parser(), open(os.devnull, "w") as sink:
        copies = [os.dup(fd) for fd in (1, 2)]
        try:
            for fd in (1, 2):
                os.dup2(sink.fileno(), fd)
            yield
        finally:
            for fd, copy in zip((1, 2), copies):
                os.dup2(copy, fd)
                os.close(copy)


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Review:
    def __init__(self, directory: Path, state_directory: Path):
        directory = directory.resolve(strict=True)
        state_directory = state_directory.resolve()
        if not directory.is_dir() or state_directory.is_relative_to(directory):
            raise ValueError("invalid_directories")
        self.directory = directory
        self.paths = {}
        self.documents = []
        self.state_directory = state_directory
        self.plan_path = state_directory / "review-plan.json"
        paths = sorted((p for p in directory.iterdir() if p.suffix.lower() == ".pdf"
                        and not p.is_symlink() and p.is_file()), key=lambda p: p.name)
        if not paths:
            raise ValueError("no_documents")
        for index, path in enumerate(paths, start=1):
            document_id = f"document-{index:03d}"
            fingerprint = digest_file(path)
            with quiet_renderer(), pdfium.PdfDocument(str(path)) as document:
                page_count = len(document)
            self.paths[document_id] = path
            self.documents.append({"document_id": document_id,
                                   "source_sha256": fingerprint,
                                   "page_count": page_count, "regions": []})
        set_key = hashlib.sha256("".join(d["source_sha256"] for d in self.documents).encode()).hexdigest()[:24]
        self.workspace_path = state_directory / f"field-workspace-{set_key}.json"
        self.profile_path = state_directory / "field-profile.json"

    def text_layout(self, document_id, number):
        descriptor = next(d for d in self.documents if d["document_id"] == document_id)
        if type(number) is not int or not 1 <= number <= descriptor["page_count"] or not self.source_is_current(document_id):
            raise ValueError("page_unavailable")
        return self._cached_text_layout(document_id,number)

    @lru_cache(maxsize=8)
    def _cached_text_layout(self, document_id, number):
        with quiet_renderer(), pdfium.PdfDocument(str(self.paths[document_id])) as document:
            page = document[number-1]
            try:
                return extract_layout(page, number)
            finally:
                page.close()

    def empty_workspace(self):
        return {"schema_version": 2, "profile_name": "Bank Austria",
                "anonymization_performed": False,
                "documents": [{"document_id":d["document_id"],"source_sha256":d["source_sha256"],
                               "page_count":d["page_count"],"annotations":[]} for d in self.documents]}

    def validate_workspace(self, payload):
        if not isinstance(payload,dict) or payload.get("schema_version") != 2:
            raise ValueError("invalid_workspace")
        clean = self.empty_workspace()
        name = payload.get("profile_name", "Bank Austria")
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("invalid_profile_name")
        clean["profile_name"] = name.strip()
        supplied = payload.get("documents")
        if not isinstance(supplied,list) or len(supplied) != len(clean["documents"]):
            raise ValueError("different_documents")
        identifiers, total = set(), 0
        for incoming, document in zip(supplied,clean["documents"]):
            if not isinstance(incoming,dict) or any(incoming.get(k)!=document[k] for k in ("document_id","source_sha256","page_count")):
                raise ValueError("different_documents")
            annotations = incoming.get("annotations")
            if not isinstance(annotations,list):
                raise ValueError("invalid_annotations")
            for annotation in annotations:
                total += 1
                if total > 50_000 or not isinstance(annotation,dict):
                    raise ValueError("invalid_annotations")
                identifier, field = annotation.get("id"), annotation.get("field")
                if not isinstance(identifier,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",identifier) or identifier in identifiers or field not in FIELDS:
                    raise ValueError("invalid_annotation")
                identifiers.add(identifier)
                page, ids, kind = annotation.get("page"), annotation.get("token_ids"), annotation.get("kind")
                if type(page) is not int or not 1 <= page <= document["page_count"] or kind not in ("example","suggestion","confirmed","rejected"):
                    raise ValueError("invalid_annotation")
                if not isinstance(ids,list) or not 1 <= len(ids) <= 4000 or any(type(i) is not int or not 0 <= i <= 10_000_000 for i in ids):
                    raise ValueError("invalid_tokens")
                row_id = annotation.get("row_id")
                if row_id is not None and (not isinstance(row_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",row_id)):
                    raise ValueError("invalid_parent")
                document["annotations"].append({"id":identifier,"field":field,"page":page,
                    "token_ids":sorted(set(ids)),"kind":kind,"row_id":row_id})
                target=document["annotations"][-1]
                revision=annotation.get("recognition_revision")
                if revision is not None:
                    if not isinstance(revision,str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}",revision):
                        raise ValueError("invalid_revision")
                    target["recognition_revision"]=revision
                entity=annotation.get("entity_id")
                if entity is not None:
                    if not isinstance(entity,str) or not re.fullmatch(r"holder-[1-9][0-9]?",entity):
                        raise ValueError("invalid_holder")
                    target["entity_id"]=entity
                if "partial" in annotation:
                    if type(annotation["partial"]) is not bool:
                        raise ValueError("invalid_partial_flag")
                    target["partial"]=annotation["partial"]
                if "family" in annotation:
                    if annotation["family"] not in ("card","direct_debit","transfer","generic"):
                        raise ValueError("invalid_family")
                    target["family"]=annotation["family"]
                continuation=annotation.get("continuation_of")
                if continuation is not None:
                    if not isinstance(continuation,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",continuation):
                        raise ValueError("invalid_continuation")
                    target["continuation_of"]=continuation
                if "continued_on" in annotation:
                    if type(annotation["continued_on"]) is not int or not page<annotation["continued_on"]<=document["page_count"]:
                        raise ValueError("invalid_continuation_page")
                    target["continued_on"]=annotation["continued_on"]
        return clean

    def load_workspace(self):
        if not self.workspace_path.exists():
            return self.empty_workspace()
        if self.workspace_path.is_symlink() or self.workspace_path.stat().st_size > MAX_BODY:
            raise ValueError("invalid_workspace")
        workspace=self.canonical_workspace(self.validate_workspace(json.loads(self.workspace_path.read_text(encoding="utf-8"))))
        repaired=repair_missing_parents(workspace)
        if repaired:
            workspace["repaired_parent_links"]=repaired
        return workspace

    def canonical_workspace(self, workspace):
        # PDF character indexes preserve earlier selections when rotated words
        # are regrouped. Saved files change only on an explicit user save.
        for document in workspace["documents"]:
            by_page={}
            for annotation in document["annotations"]:
                by_page.setdefault(annotation["page"],[]).append(annotation)
            for number,annotations in by_page.items():
                tokens=sorted(self.text_layout(document["document_id"],number)["tokens"],key=lambda t:t["id"])
                starts=[t["id"] for t in tokens]
                for annotation in annotations:
                    mapped=[]
                    for old in annotation["token_ids"]:
                        index=bisect_right(starts,old)-1
                        token=tokens[index] if index>=0 else None
                        mapped.append(token["id"] if token and old<token.get("char_end",token["id"]+1) else old)
                    annotation["token_ids"]=sorted(set(mapped))
        return workspace

    def private_write(self, path, payload):
        data = json.dumps(payload,ensure_ascii=True,indent=2).encode("utf-8")
        if len(data) > MAX_BODY:
            raise ValueError("workspace_too_large")
        self.state_directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd,name = tempfile.mkstemp(prefix=".fields-",dir=self.state_directory)
        temporary = Path(name)
        try:
            with os.fdopen(fd,"wb") as stream:
                stream.write(data)
            os.replace(temporary,path)
        finally:
            temporary.unlink(missing_ok=True)

    def learn(self, payload):
        workspace = self.canonical_workspace(self.validate_workspace(payload))
        for document in self.documents:
            if not self.source_is_current(document["document_id"]):
                raise ValueError("source_changed")
        return compile_profile(workspace,self.text_layout)

    def save_workspace(self, payload):
        clean = self.canonical_workspace(self.validate_workspace(payload))
        repaired=repair_missing_parents(clean)
        profile = self.learn(clean)
        self.private_write(self.workspace_path,clean)
        if profile["header_rules"] or profile["anchors"] or profile.get("auto_table"):
            self.private_write(self.profile_path,profile)
        return {"saved":True,"anonymization_performed":False,
                "repaired_parent_links":repaired,
                "profile_updated":bool(profile["header_rules"] or profile["anchors"] or profile.get("auto_table"))}

    def validate_profile(self, profile):
        if not isinstance(profile,dict) or profile.get("schema_version") != 1 or profile.get("engine") not in ("layout-examples-v1","layout-examples-v2"):
            raise ValueError("invalid_profile")
        # Validate only structural, typed rules; never executable expressions.
        def numeric(values, count, low, high):
            return isinstance(values,list) and len(values)==count and all(type(v) in (int,float) and math.isfinite(v) and low<=v<=high for v in values)
        kinds = ("date","amount","iban","currency","text")
        if not isinstance(profile.get("profile_name"),str) or len(profile["profile_name"]) > 80:
            raise ValueError("invalid_profile")
        for key in ("amount_column","value_column"):
            if key in profile and not numeric(profile[key],2,0,1):
                raise ValueError("invalid_profile")
        if "amount_terminal" in profile and type(profile["amount_terminal"]) is not bool:
            raise ValueError("invalid_profile")
        for key in ("anchors","header_rules","row_rules","transaction_rules"):
            rules = profile.get(key)
            if not isinstance(rules,list) or len(rules)>1000:
                raise ValueError("invalid_profile")
            for rule in rules:
                if not isinstance(rule,dict) or rule.get("value_type") not in kinds:
                    raise ValueError("invalid_profile")
                if key == "anchors":
                    if not numeric(rule.get("column"),2,0,1) or rule["value_type"] != "date":
                        raise ValueError("invalid_profile")
                else:
                    if rule.get("field") not in FIELDS or not numeric(rule.get("box"),4,0,1) or rule.get("page_scope") not in ("first","following"):
                        raise ValueError("invalid_profile")
                    if key != "header_rules" and (not numeric(rule.get("column"),2,0,1) or not numeric(rule.get("dy"),2,-1,1)):
                        raise ValueError("invalid_profile")
                    for name in ("line_offset","line_count"):
                        if name in rule and (type(rule[name]) is not int or not 0<=rule[name]<=10000):
                            raise ValueError("invalid_profile")
                    if "family" in rule and rule["family"] not in ("card","direct_debit","transfer","generic"):
                        raise ValueError("invalid_profile")
                    if "entity_id" in rule and not re.fullmatch(r"holder-[1-9][0-9]?",str(rule["entity_id"])):
                        raise ValueError("invalid_profile")
        return profile

    def load_profile(self):
        if self.profile_path.is_symlink() or self.profile_path.stat().st_size > MAX_BODY:
            raise ValueError("invalid_profile")
        return self.validate_profile(json.loads(self.profile_path.read_text(encoding="utf-8")))

    def public_documents(self):
        return [{"document_id": d["document_id"], "page_count": d["page_count"]}
                for d in self.documents]

    def empty_plan(self):
        return {"schema_version": 1, "anonymization_performed": False,
                "documents": [dict(d) for d in self.documents]}

    def source_is_current(self, document_id):
        path = self.paths[document_id]
        expected = next(d["source_sha256"] for d in self.documents if d["document_id"] == document_id)
        return not path.is_symlink() and digest_file(path) == expected

    def render(self, document_id: str, number: int) -> bytes:
        descriptor = next(d for d in self.documents if d["document_id"] == document_id)
        if not 1 <= number <= descriptor["page_count"] or not self.source_is_current(document_id):
            raise ValueError("page_unavailable")
        # Native rendering is serialized by RENDER_LOCK. No disk cache, no OCR,
        # no text extraction, no original PDF response, no annotation execution.
        with quiet_renderer(), pdfium.PdfDocument(str(self.paths[document_id])) as document:
            page = document[number - 1]
            try:
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    raise ValueError("invalid_page")
                scale = min(1.7, 1800 / max(width, height))
                bitmap = page.render(scale=scale, may_draw_forms=False)
                try:
                    image = bitmap.to_pil()
                    try:
                        output = io.BytesIO()
                        image.save(output, format="PNG")
                        return output.getvalue()
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()

    def validate_plan(self, payload):
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("invalid_plan")
        documents = payload.get("documents")
        if not isinstance(documents, list) or len(documents) != len(self.documents):
            raise ValueError("different_documents")
        cleaned = self.empty_plan()
        count = 0
        for supplied, expected, target in zip(documents, self.documents, cleaned["documents"]):
            if not isinstance(supplied, dict) or any(supplied.get(k) != expected[k]
                    for k in ("document_id", "source_sha256", "page_count")):
                raise ValueError("different_documents")
            regions = supplied.get("regions")
            if not isinstance(regions, list):
                raise ValueError("invalid_regions")
            target["regions"] = []
            for region in regions:
                count += 1
                if count > 20_000 or not isinstance(region, dict):
                    raise ValueError("too_many_regions")
                page = region.get("page")
                if type(page) is not int or not 1 <= page <= expected["page_count"]:
                    raise ValueError("invalid_page")
                box = region.get("box")
                if not isinstance(box, list) or len(box) != 4 or any(
                        type(v) not in (int, float) or not math.isfinite(v) for v in box):
                    raise ValueError("invalid_box")
                x, y, width, height = box
                if min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001:
                    raise ValueError("invalid_box")
                label, replacement = region.get("label"), region.get("replacement")
                if not isinstance(label, str) or not 1 <= len(label) <= 80:
                    raise ValueError("invalid_label")
                if not isinstance(replacement, str) or len(replacement) > 300:
                    raise ValueError("invalid_replacement")
                target["regions"].append({"page": page, "box": list(box),
                    "label": label, "replacement": replacement})
        return cleaned

    def load(self):
        if not self.plan_path.exists():
            return self.empty_plan()
        if self.plan_path.is_symlink() or self.plan_path.stat().st_size > MAX_BODY:
            raise ValueError("invalid_saved_plan")
        return self.validate_plan(json.loads(self.plan_path.read_text(encoding="utf-8")))

    def save(self, payload):
        cleaned = self.validate_plan(payload)
        if any(not self.source_is_current(d["document_id"]) for d in self.documents):
            raise ValueError("source_changed")
        data = json.dumps(cleaned, ensure_ascii=True, indent=2).encode("utf-8")
        if len(data) > MAX_BODY:
            raise ValueError("plan_too_large")
        self.state_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".plan-", dir=self.state_directory)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(temporary, self.plan_path)
        finally:
            temporary.unlink(missing_ok=True)
        return sum(len(d["regions"]) for d in cleaned["documents"])


class DirectoryError(ValueError):
    """Fixed error codes only; never expose filesystem exception messages."""


def open_directory(value, state_directory):
    if not isinstance(value,str) or not value.strip() or len(value)>4096 or "\x00" in value:
        raise DirectoryError("invalid_directory")
    value=value.strip()
    if len(value)>=2 and value[0]==value[-1] and value[0] in ("'",'"'):
        value=value[1:-1]
    try:
        directory=Path(value).expanduser()
        if not directory.is_absolute():
            raise DirectoryError("absolute_directory_required")
        directory=directory.resolve(strict=True)
        if not directory.is_dir():
            raise DirectoryError("not_a_directory")
        if state_directory.resolve().is_relative_to(directory):
            raise DirectoryError("directory_contains_state")
        return Review(directory,state_directory)
    except DirectoryError:
        raise
    except FileNotFoundError:
        raise DirectoryError("directory_not_found") from None
    except ValueError as error:
        code="no_pdfs" if str(error)=="no_documents" else "directory_unreadable"
        raise DirectoryError(code) from None
    except Exception:
        raise DirectoryError("directory_unreadable") from None


class ReviewSession:
    """Each opened folder has its own URLs, review and in-memory proof index."""
    def __init__(self,review,token):
        self.review=review
        self.prefix=f"/{token}/"
        self.proof_service=None
        self.proof_lock=threading.Lock()

    def proofs(self):
        with self.proof_lock:
            if self.proof_service is None:
                from .proof import ProofService
                self.proof_service=ProofService(self.review)
        return self.proof_service

    def source(self):
        return {"directory":str(self.review.directory),"document_count":len(self.review.documents),
                "page_count":sum(d["page_count"] for d in self.review.documents)}


def make_server(review: Review, port=0, token=None):
    token = token or secrets.token_urlsafe(32)
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}",token):
        raise ValueError("invalid_session_token")
    prefix = f"/{token}/"
    sessions={token:ReviewSession(review,token)}
    sessions_lock=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        # Never let HTTP access/error logs echo URLs, private values or paths.
        def log_message(self, *args):
            pass

        def send_error(self, code, message=None, explain=None):
            self.respond(code, b'{"error":"request_failed"}', "application/json")

        def respond(self, status, body, mime, filename=None):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            if filename:
                self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def json_response(self, status, value):
            self.respond(status, json.dumps(value).encode("utf-8"), "application/json")

        def session(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                return None
            parts=self.path.split("/",2)
            if len(parts)!=3 or parts[0]:
                return None
            with sessions_lock:
                return sessions.get(parts[1])

        def do_GET(self):
            try:
                session=self.session()
                if session is None:
                    return self.send_error(404)
                review,prefix,proofs=session.review,session.prefix,session.proofs
                route = self.path[len(prefix):]
                assets = {"": ("index.html", "text/html; charset=utf-8"),
                          "app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "style.css": ("style.css", "text/css; charset=utf-8"),
                          "proof.html":("proof.html","text/html; charset=utf-8"),
                          "proof.js":("proof.js","text/javascript; charset=utf-8"),
                          "proof.css":("proof.css","text/css; charset=utf-8")}
                assets["source.js"]=("source.js","text/javascript; charset=utf-8")
                if route in assets:
                    name, mime = assets[route]
                    return self.respond(200, (WEB / name).read_bytes(), mime)
                if route == "api/documents":
                    return self.json_response(200, review.public_documents())
                if route == "api/source":
                    return self.json_response(200,session.source())
                if route == "api/plan":
                    return self.json_response(200, review.load())
                if route == "api/workspace":
                    return self.json_response(200, review.load_workspace())
                if route == "api/config":
                    return self.json_response(200,{"fields":FIELDS,"profile_available":review.profile_path.is_file(),
                        "app_version":APP_VERSION,"api_version":API_VERSION,"recognition_revision":RECOGNITION_REVISION})
                if route == "api/profile":
                    return self.json_response(200,review.load_profile())
                if route=="api/proof/status":
                    return self.json_response(200,proofs().state())
                if route.startswith("api/proof/download/"):
                    target=proofs().download(route[len("api/proof/download/"):])
                    mime="application/zip" if target.suffix==".zip" else "application/pdf"
                    return self.respond(200,target.read_bytes(),mime,target.name)
                parts = route.split("/")
                if len(parts)==4 and parts[:2]==["api","text"] and parts[3].endswith(".json"):
                    return self.json_response(200,review.text_layout(parts[2],int(parts[3][:-5])))
                if len(parts) == 4 and parts[:2] == ["api", "page"] and parts[3].endswith(".png"):
                    image = review.render(parts[2], int(parts[3][:-4]))
                    return self.respond(200, image, "image/png")
                return self.send_error(404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.json_response(409, {"error": "local_operation_failed"})

        def do_POST(self):
            try:
                session=self.session()
                if session is None:
                    return self.send_error(403)
                review,prefix,proofs=session.review,session.prefix,session.proofs
                origin = f"http://127.0.0.1:{self.server.server_port}"
                proof_routes={prefix+"api/proof/"+suffix for suffix in ("index","cancel","search","preview","export")}
                routes = {prefix+"api/plan",prefix+"api/workspace",prefix+"api/learn",prefix+"api/recognize",prefix+"api/block",prefix+"api/source/load"}|proof_routes
                if self.path not in routes or self.headers.get("Origin") != origin or self.headers.get("X-BankLens-Request") != "1":
                    return self.send_error(403)
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    return self.send_error(413)
                if self.headers.get("Content-Type") != "application/json":
                    return self.send_error(415)
                payload = json.loads(self.rfile.read(size))
                if self.path==prefix+"api/source/load":
                    try:
                        if not isinstance(payload,dict):
                            raise DirectoryError("invalid_directory")
                        with sessions_lock:
                            if len(sessions)>=64:
                                raise DirectoryError("too_many_directories")
                        opened=open_directory(payload.get("directory"),review.state_directory)
                        opened_token=secrets.token_urlsafe(32)
                        opened_session=ReviewSession(opened,opened_token)
                        with sessions_lock:
                            if len(sessions)>=64:
                                raise DirectoryError("too_many_directories")
                            sessions[opened_token]=opened_session
                        return self.json_response(200,{**opened_session.source(),"session_path":opened_session.prefix})
                    except DirectoryError as error:
                        return self.json_response(400,{"error":str(error)})
                if self.path in proof_routes:
                    from .proof import ProofError
                    try:
                        service=proofs()
                        if self.path.endswith("/index"):
                            return self.json_response(200,service.start_index())
                        if self.path.endswith("/cancel"):
                            service.cancel.set()
                            return self.json_response(200,{"cancel_requested":True})
                        if self.path.endswith("/search"):
                            return self.json_response(200,service.search(payload.get("query","")))
                        if self.path.endswith("/preview"):
                            return self.respond(200,service.preview(payload.get("selected_ids"),payload.get("document_id"),payload.get("page")),"image/png")
                        return self.json_response(200,service.start_export(payload.get("selected_ids")))
                    except ProofError as error:
                        return self.json_response(400,{"error":str(error)})
                if self.path == prefix+"api/workspace":
                    return self.json_response(200,review.save_workspace(payload))
                if self.path == prefix+"api/learn":
                    return self.json_response(200,review.learn(payload))
                if self.path == prefix+"api/block":
                    profile=review.learn(payload["workspace"])
                    layout=review.text_layout(payload["document_id"],payload["page"])
                    ids=payload["token_ids"]
                    if not isinstance(ids,list) or not ids or len(ids)>4000 or any(type(i) is not int for i in ids):
                        raise ValueError("invalid_selection")
                    wanted=set(ids)
                    blocks=[b for b in transaction_blocks(profile,layout) if wanted & {t["id"] for t in b["tokens"]}]
                    if not blocks:
                        return self.json_response(200,{"found":False,"token_ids":[]})
                    block=max(blocks,key=lambda b:len(wanted & {t["id"] for t in b["tokens"]}))
                    return self.json_response(200,{"found":True,"token_ids":[t["id"] for t in block["tokens"]],"full_text_ids":[t["id"] for t in block_body_tokens(block)],"partial":block["partial"]})
                if self.path == prefix+"api/recognize":
                    profile = review.validate_profile(payload["profile"])
                    document_id,number = payload["document_id"],payload["page"]
                    # Reuse workspace validation for untrusted annotations.
                    small = review.empty_workspace()
                    document = next(d for d in small["documents"] if d["document_id"]==document_id)
                    document["annotations"] = payload.get("existing",[])
                    validated = review.validate_workspace(small)
                    existing = next(d for d in validated["documents"] if d["document_id"]==document_id)["annotations"]
                    previous=payload.get("previous")
                    if previous is not None and (not isinstance(previous,dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",str(previous.get("id",""))) or previous.get("family") not in ("card","direct_debit","transfer","generic") or number<=1):
                        raise ValueError("invalid_previous_block")
                    return self.json_response(200,recognize_page(profile,review.text_layout(document_id,number),document_id,existing,previous))
                count = review.save(payload)
                self.json_response(200, {"saved": True, "region_count": count,
                                          "anonymization_performed": False})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.json_response(400, {"error": "plan_not_saved"})

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 32
        def handle_error(self, request, client_address):
            # No traceback with document-derived exception values.
            pass

    server = Server(("127.0.0.1", port), Handler)
    return server, f"http://127.0.0.1:{server.server_port}{prefix}"


def serve(directory, state_directory, port=0, token=None):
    review = Review(directory, state_directory)
    server, url = make_server(review, port, token)
    print(json.dumps({"preview_url": url, "document_count": len(review.documents),
                      "anonymization_performed": False}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
