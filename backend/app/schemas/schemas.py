from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    department: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MonitoringTopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    category: str = "Public Policy"
    keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    data_source_ids: list[int] = Field(default_factory=list)
    time_range_days: int = Field(default=30, ge=1, le=365)
    language: str = "all"
    status: Literal["active", "paused", "archived"] = "active"


class MonitoringTopicUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[list[str]] = None
    excluded_keywords: Optional[list[str]] = None
    data_source_ids: Optional[list[int]] = None
    time_range_days: Optional[int] = Field(default=None, ge=1, le=365)
    language: Optional[str] = None
    status: Optional[Literal["active", "paused", "archived"]] = None


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    provider_type: Literal["csv", "rss", "public_api", "synthetic_stream"]
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    is_synthetic: bool = True
    is_enabled: bool = True
    schedule_interval_minutes: int = Field(default=60, ge=5, le=1440)
    rate_limit_per_min: int = Field(default=60, ge=1, le=600)


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_enabled: Optional[bool] = None
    schedule_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    rate_limit_per_min: Optional[int] = Field(default=None, ge=1, le=600)


class RunIngestionRequest(BaseModel):
    monitoring_topic_id: Optional[int] = None
    batch_size: int = Field(default=18, ge=1, le=100)
    use_celery: bool = False


class AnnotationUpsertRequest(BaseModel):
    is_bookmarked: Optional[bool] = None
    is_verified: Optional[bool] = None
    note: Optional[str] = None
    tags: Optional[list[str]] = None
    report_section_tag: Optional[str] = None


class ClassificationOverrideRequest(BaseModel):
    overridden_topic: Optional[str] = None
    overridden_sentiment: Optional[Literal["positive", "neutral", "mixed", "negative"]] = None
    override_reason: str = Field(min_length=5, max_length=1000)


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    event_type: str = "Civic Event"
    location: str = "Metro Area"
    start_time: datetime
    end_time: datetime
    baseline_days: int = Field(default=7, ge=1, le=30)
    monitoring_topic_ids: list[int] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    subtitle: str = ""
    monitoring_topic_id: Optional[int] = None
    event_id: Optional[int] = None
    days: int = Field(default=30, ge=1, le=180)
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None


class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    executive_summary: Optional[str] = None
    status: Optional[Literal["draft", "reviewed", "published"]] = None
    analyst_commentary: Optional[str] = None
