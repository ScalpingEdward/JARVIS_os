from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator

class ControlState(str, Enum): DRAFT='draft'; ACTIVE='active'; RETIRED='retired'
class EvidenceState(str, Enum): CURRENT='current'; STALE='stale'; REVOKED='revoked'
class FindingSeverity(str, Enum): LOW='low'; MEDIUM='medium'; HIGH='high'; CRITICAL='critical'
class FindingState(str, Enum): OPEN='open'; ACCEPTED='accepted'; REMEDIATION='remediation'; RESOLVED='resolved'
class ReportState(str, Enum): DRAFT='draft'; APPROVED='approved'; FINAL='final'; ARCHIVED='archived'

class ControlCreate(BaseModel):
    workspace_id:str=Field(min_length=1,max_length=120); owner_id:str=Field(min_length=1,max_length=120); framework:str=Field(min_length=1,max_length=120); control_key:str=Field(min_length=1,max_length=160,pattern=r'^[A-Za-z0-9_.-]+$'); title:str=Field(min_length=1,max_length=300); description:str=Field(default='',max_length=5000); target_modules:list[str]=Field(default_factory=list,max_length=300); evidence_requirements:list[str]=Field(default_factory=list,max_length=300); review_interval_days:int=Field(default=90,ge=1,le=3650); human_approved:bool=True; automatic_certification:bool=False
    @model_validator(mode='after')
    def safe(self):
        if not self.human_approved: raise ValueError('human approval is required')
        if self.automatic_certification: raise ValueError('automatic certification is disabled')
        return self
class ControlRecord(ControlCreate):
    id:UUID=Field(default_factory=uuid4); state:ControlState=ControlState.DRAFT; created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); updated_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))

class EvidenceCreate(BaseModel):
    workspace_id:str=Field(min_length=1,max_length=120); owner_id:str=Field(min_length=1,max_length=120); control_id:UUID; source_module:str=Field(min_length=1,max_length=160); evidence_type:str=Field(min_length=1,max_length=160); reference:str=Field(min_length=1,max_length=1000); checksum:str=Field(min_length=8,max_length=256); summary:str=Field(default='',max_length=5000); valid_days:int=Field(default=90,ge=1,le=3650); metadata:dict[str,Any]=Field(default_factory=dict); human_verified:bool=True; raw_secret:str|None=None; external_upload:bool=False
    @model_validator(mode='after')
    def safe(self):
        if not self.human_verified: raise ValueError('human verification is required')
        if self.raw_secret: raise ValueError('raw secrets are not accepted as evidence')
        if self.external_upload: raise ValueError('automatic external evidence upload is disabled')
        return self
class EvidenceRecord(BaseModel):
    id:UUID=Field(default_factory=uuid4); workspace_id:str; owner_id:str; control_id:UUID; source_module:str; evidence_type:str; reference:str; checksum:str; summary:str; metadata:dict[str,Any]; state:EvidenceState=EvidenceState.CURRENT; collected_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); expires_at:datetime

class FindingCreate(BaseModel):
    workspace_id:str=Field(min_length=1,max_length=120); owner_id:str=Field(min_length=1,max_length=120); control_id:UUID; title:str=Field(min_length=1,max_length=300); description:str=Field(min_length=1,max_length=5000); severity:FindingSeverity; remediation_owner:str=Field(min_length=1,max_length=120); due_at:datetime|None=None; evidence_ids:list[UUID]=Field(default_factory=list,max_length=300); human_approved:bool=True; automatic_remediation:bool=False
    @model_validator(mode='after')
    def safe(self):
        if not self.human_approved: raise ValueError('human approval is required')
        if self.automatic_remediation: raise ValueError('automatic remediation is disabled')
        return self
class FindingRecord(FindingCreate):
    id:UUID=Field(default_factory=uuid4); state:FindingState=FindingState.OPEN; resolution_note:str|None=None; created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); updated_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))

class ReportCreate(BaseModel):
    workspace_id:str=Field(min_length=1,max_length=120); owner_id:str=Field(min_length=1,max_length=120); framework:str=Field(min_length=1,max_length=120); title:str=Field(min_length=1,max_length=300); control_ids:list[UUID]=Field(default_factory=list,max_length=1000); period_start:datetime; period_end:datetime; human_approved:bool=True; external_submission:bool=False
    @model_validator(mode='after')
    def safe(self):
        if self.period_end<=self.period_start: raise ValueError('period_end must be after period_start')
        if not self.human_approved: raise ValueError('human approval is required')
        if self.external_submission: raise ValueError('automatic external report submission is disabled')
        return self
class ReportRecord(BaseModel):
    id:UUID=Field(default_factory=uuid4); workspace_id:str; owner_id:str; framework:str; title:str; control_ids:list[UUID]; period_start:datetime; period_end:datetime; state:ReportState=ReportState.DRAFT; controls_total:int=0; controls_with_current_evidence:int=0; open_findings:int=0; critical_findings:int=0; coverage_percent:float=0.0; generated_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); approved_by:str|None=None; finalized_at:datetime|None=None

class Mutation(BaseModel):
    requester_id:str=Field(min_length=1,max_length=120); reason:str=Field(default='',max_length=3000); human_approved:bool=True
    @model_validator(mode='after')
    def safe(self):
        if not self.human_approved: raise ValueError('human approval is required')
        return self
class AuditRecord(BaseModel):
    id:UUID=Field(default_factory=uuid4); workspace_id:str; action:str; entity_type:str; entity_id:UUID|None=None; actor_id:str; details:dict[str,Any]=Field(default_factory=dict); created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class ComplianceStatus(BaseModel):
    version:str='9.5'; controls:int; evidence_items:int; findings:int; reports:int; automatic_certification_enabled:bool=False; automatic_remediation_enabled:bool=False; external_submission_enabled:bool=False; executes_actions:bool=False
