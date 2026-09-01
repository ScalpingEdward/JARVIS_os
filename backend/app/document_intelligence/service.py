import hashlib
import re
from datetime import datetime, timezone
from difflib import ndiff
from uuid import UUID

from .document_ai_analyzer import AnthropicDocumentAnalyzer, DocumentAIAnalysisError
from .models import (
    AnalysisRecord,
    AnalysisRequest,
    AnalysisState,
    AnalysisType,
    AuditRecord,
    ConfidenceLevel,
    DocumentCategory,
    DocumentCreate,
    DocumentDifference,
    DocumentIntelligenceStatus,
    DocumentMutation,
    DocumentRecord,
    ExtractedField,
    ExtractedTable,
    RiskFinding,
)


class DocumentIntelligenceService:
    def __init__(self, ai_analyzer: AnthropicDocumentAnalyzer | None = None) -> None:
        self.documents: dict[UUID, DocumentRecord] = {}
        self.analyses: list[AnalysisRecord] = []
        self.audit: list[AuditRecord] = []
        self._ai_analyzer = ai_analyzer or AnthropicDocumentAnalyzer()

    def reset(self) -> None:
        ai_analyzer = self._ai_analyzer
        self.__init__(ai_analyzer=ai_analyzer)

    def status(self) -> DocumentIntelligenceStatus:
        return DocumentIntelligenceStatus(
            version="8.5",
            documents=len(self.documents),
            analyses=len(self.analyses),
            completed_analyses=sum(a.state == AnalysisState.COMPLETED for a in self.analyses),
            blocked_analyses=sum(a.state == AnalysisState.BLOCKED for a in self.analyses),
            extracted_fields=sum(len(a.extracted_fields) for a in self.analyses),
            extracted_tables=sum(len(a.extracted_tables) for a in self.analyses),
            risk_findings=sum(len(a.risks) for a in self.analyses),
            external_ai_execution=True,
        )

    def create_document(self, payload: DocumentCreate) -> DocumentRecord:
        digest = hashlib.sha256(payload.text_content.encode("utf-8")).hexdigest()
        for item in self.documents.values():
            if (
                item.workspace_id == payload.workspace_id
                and item.document_key == payload.document_key
                and item.version == payload.version
            ):
                raise ValueError("document key and version already exist")
            if item.workspace_id == payload.workspace_id and item.content_hash == digest and item.active:
                raise ValueError("duplicate active document content")
        record = DocumentRecord(**payload.model_dump(exclude={"human_approved", "automatic_cloud_upload", "external_ocr_request"}), content_hash=digest)
        self.documents[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "document.created", "document", str(record.id), {"version": record.version})
        return record

    def list_documents(self, workspace_id: str, include_inactive: bool = False) -> list[DocumentRecord]:
        return [d for d in self.documents.values() if d.workspace_id == workspace_id and (include_inactive or d.active)]

    def get_document(self, document_id: UUID, workspace_id: str) -> DocumentRecord | None:
        item = self.documents.get(document_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_active(self, document_id: UUID, workspace_id: str, payload: DocumentMutation, active: bool) -> DocumentRecord | None:
        item = self.get_document(document_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        item.active = active
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, "document.activated" if active else "document.archived", "document", str(item.id), {"reason": payload.reason})
        return item

    def analyze(self, payload: AnalysisRequest) -> AnalysisRecord:
        document = self.get_document(payload.document_id, payload.workspace_id)
        if not document or not document.active:
            return self._blocked(payload, "active document not found")
        comparison = None
        if payload.comparison_document_id:
            comparison = self.get_document(payload.comparison_document_id, payload.workspace_id)
            if not comparison or not comparison.active:
                return self._blocked(payload, "active comparison document not found")

        text = document.text_content
        category, confidence = self._classify(text, document.title)
        summary = self._summarize(text, payload.maximum_summary_sentences)
        fields = self._extract_fields(text, payload.field_schema)
        tables = self._extract_tables(text)
        risks = self._find_risks(text)
        differences = self._compare(comparison.text_content, text) if comparison else []
        ai_key_points: list[str] = []

        if payload.use_external_ai:
            try:
                ai_result = self._ai_analyzer.analyze(document.title, text, payload.maximum_summary_sentences)
            except DocumentAIAnalysisError as exc:
                return self._failed(payload, document, comparison, f"AI-based analysis failed: {exc}")
            try:
                category = DocumentCategory(ai_result.category)
            except ValueError:
                category = DocumentCategory.UNKNOWN
            confidence = ai_result.category_confidence
            summary = ai_result.summary
            # AI-found risks are real reasoning over the actual text, not
            # invented -- merged with (not replacing) the deterministic
            # regex-based findings, which catch different, complementary
            # patterns (explicit clause markers regex is good at, that a
            # summary-style read can miss).
            risks = [
                *risks,
                *[
                    RiskFinding(code="ai-flagged", severity="medium", description=risk_text)
                    for risk_text in ai_result.risks
                ],
            ]
            ai_key_points = ai_result.key_points

        requested = payload.analysis_type
        record = AnalysisRecord(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            document_id=document.id,
            comparison_document_id=comparison.id if comparison else None,
            analysis_type=requested,
            state=AnalysisState.COMPLETED,
            category=category if requested in {AnalysisType.CLASSIFY, AnalysisType.FULL} else DocumentCategory.UNKNOWN,
            category_confidence=confidence if requested in {AnalysisType.CLASSIFY, AnalysisType.FULL} else 0,
            summary=summary if requested in {AnalysisType.SUMMARIZE, AnalysisType.FULL} else "",
            extracted_fields=fields if requested in {AnalysisType.EXTRACT_FIELDS, AnalysisType.FULL} else [],
            extracted_tables=tables if requested in {AnalysisType.EXTRACT_TABLES, AnalysisType.FULL} else [],
            risks=risks if requested in {AnalysisType.FIND_RISKS, AnalysisType.FULL} else [],
            differences=differences if requested in {AnalysisType.COMPARE, AnalysisType.FULL} and comparison else [],
            citations=self._citations(text),
            external_ai_used=payload.use_external_ai,
            ai_key_points=ai_key_points if requested in {AnalysisType.SUMMARIZE, AnalysisType.FULL} else [],
        )
        self.analyses.append(record)
        self._audit(payload.workspace_id, payload.requester_id, "analysis.completed", "analysis", str(record.id), {"type": requested.value})
        return record

    def list_analyses(self, workspace_id: str, document_id: UUID | None = None) -> list[AnalysisRecord]:
        return [a for a in self.analyses if a.workspace_id == workspace_id and (document_id is None or a.document_id == document_id)]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]

    def _blocked(self, payload: AnalysisRequest, reason: str) -> AnalysisRecord:
        record = AnalysisRecord(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            document_id=payload.document_id,
            comparison_document_id=payload.comparison_document_id,
            analysis_type=payload.analysis_type,
            state=AnalysisState.BLOCKED,
            blocked_reason=reason,
        )
        self.analyses.append(record)
        self._audit(payload.workspace_id, payload.requester_id, "analysis.blocked", "analysis", str(record.id), {"reason": reason})
        return record

    def _failed(self, payload: AnalysisRequest, document: DocumentRecord, comparison: DocumentRecord | None, reason: str) -> AnalysisRecord:
        """Distinct from _blocked: the document/request were valid, but an
        opted-in capability (AI analysis) failed at runtime. Never silently
        falls back to the deterministic result and calls it a success --
        the caller asked for AI analysis and didn't get it."""
        record = AnalysisRecord(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            document_id=document.id,
            comparison_document_id=comparison.id if comparison else None,
            analysis_type=payload.analysis_type,
            state=AnalysisState.FAILED,
            blocked_reason=reason,
            external_ai_used=True,
        )
        self.analyses.append(record)
        self._audit(payload.workspace_id, payload.requester_id, "analysis.failed", "analysis", str(record.id), {"reason": reason})
        return record

    def _classify(self, text: str, title: str) -> tuple[DocumentCategory, float]:
        content = f"{title}\n{text}".lower()
        terms = {
            DocumentCategory.CONTRACT: ["agreement", "contract", "partei", "vertrag", "kündigung"],
            DocumentCategory.INVOICE: ["invoice", "rechnung", "vat", "umsatzsteuer", "total"],
            DocumentCategory.REPORT: ["report", "bericht", "executive summary", "findings"],
            DocumentCategory.MANUAL: ["manual", "handbuch", "instructions", "bedienung"],
            DocumentCategory.LEGAL: ["court", "gericht", "claim", "forderung", "anwalt"],
            DocumentCategory.TRADING: ["stop loss", "take profit", "drawdown", "lot size", "ftmo"],
            DocumentCategory.BUSINESS: ["revenue", "marketing", "business", "umsatz", "kunde"],
            DocumentCategory.TECHNICAL: ["api", "system", "error", "architecture", "schnittstelle"],
        }
        scores = {category: sum(term in content for term in words) for category, words in terms.items()}
        category = max(scores, key=scores.get)
        score = scores[category]
        return (category, min(0.55 + score * 0.1, 0.95)) if score else (DocumentCategory.UNKNOWN, 0.2)

    def _summarize(self, text: str, limit: int) -> str:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20]
        ranked = sorted(enumerate(sentences), key=lambda x: (len(set(re.findall(r"\w+", x[1].lower()))), len(x[1])), reverse=True)
        selected = sorted(ranked[:limit], key=lambda x: x[0])
        return " ".join(sentence for _, sentence in selected)

    def _extract_fields(self, text: str, schema) -> list[ExtractedField]:
        lines = text.splitlines()
        results: list[ExtractedField] = []
        for definition in schema:
            names = [definition.name, *definition.aliases]
            match = None
            for line_no, line in enumerate(lines, start=1):
                for name in names:
                    pattern = rf"(?i)\b{re.escape(name)}\b\s*[:=-]\s*(.+)$"
                    found = re.search(pattern, line)
                    if found:
                        match = (line_no, found.group(1).strip(), line.strip())
                        break
                if match:
                    break
            if match:
                confidence = 0.92 if names[0].lower() in match[2].lower() else 0.8
                results.append(ExtractedField(name=definition.name, value=match[1], confidence=confidence, confidence_level=ConfidenceLevel.HIGH, source_line=match[0], source_excerpt=match[2][:500]))
            elif definition.required:
                results.append(ExtractedField(name=definition.name, value="", confidence=0, confidence_level=ConfidenceLevel.LOW))
        return results

    def _extract_tables(self, text: str) -> list[ExtractedTable]:
        lines = text.splitlines()
        tables: list[ExtractedTable] = []
        start = None
        block: list[tuple[int, list[str]]] = []
        for line_no, line in enumerate(lines, start=1):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if "|" in line and len(cells) >= 2 and not all(set(cell) <= {"-", ":", " "} for cell in cells):
                if start is None:
                    start = line_no
                block.append((line_no, cells))
            elif block:
                tables.append(self._table_from_block(block, start))
                start, block = None, []
        if block:
            tables.append(self._table_from_block(block, start))
        return tables

    def _table_from_block(self, block, start) -> ExtractedTable:
        headers = block[0][1]
        rows = [cells for _, cells in block[1:] if len(cells) == len(headers)]
        return ExtractedTable(headers=headers, rows=rows, source_start_line=start, source_end_line=block[-1][0], confidence=0.85 if rows else 0.55)

    def _find_risks(self, text: str) -> list[RiskFinding]:
        rules = {
            "DEADLINE": ("high", ["deadline", "frist", "within 14 days", "innerhalb von"]),
            "PENALTY": ("high", ["penalty", "vertragsstrafe", "late fee", "mahngebühr"]),
            "AUTO_RENEWAL": ("medium", ["automatic renewal", "automatische verlängerung", "renews automatically"]),
            "TERMINATION": ("medium", ["termination", "kündigung", "terminate"]),
            "LIABILITY": ("high", ["liability", "haftung", "indemnify"]),
        }
        findings: list[RiskFinding] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            for code, (severity, terms) in rules.items():
                if any(term in low for term in terms):
                    findings.append(RiskFinding(code=code, severity=severity, description=f"Potential {code.lower().replace('_', ' ')} clause detected", source_line=line_no, source_excerpt=line.strip()[:500]))
        return findings[:100]

    def _compare(self, old: str, new: str) -> list[DocumentDifference]:
        differences: list[DocumentDifference] = []
        old_line = new_line = 0
        for item in ndiff(old.splitlines(), new.splitlines()):
            prefix, value = item[:2], item[2:]
            if prefix == "  ":
                old_line += 1
                new_line += 1
            elif prefix == "- ":
                old_line += 1
                differences.append(DocumentDifference(kind="removed", old_text=value, old_line=old_line))
            elif prefix == "+ ":
                new_line += 1
                differences.append(DocumentDifference(kind="added", new_text=value, new_line=new_line))
        return differences[:500]

    def _citations(self, text: str) -> list[str]:
        return [f"line:{i}" for i, line in enumerate(text.splitlines(), start=1) if line.strip()][:200]

    def _audit(self, workspace_id: str, actor_id: str, action: str, object_type: str, object_id: str, details: dict) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, object_type=object_type, object_id=object_id, details=details))


document_intelligence_service = DocumentIntelligenceService()
