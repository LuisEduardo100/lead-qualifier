from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SAEnum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, UTC
import enum
from backend.database import Base


class LeadStatus(str, enum.Enum):
    new = "new"
    warm = "warm"
    hot = "hot"
    cold = "cold"
    lost = "lost"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class FollowUpAttempt(int, enum.Enum):
    first = 1
    second = 2


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    done = "done"
    failed = "failed"


class CampaignRecipientStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    instance_name: Mapped[str] = mapped_column(String(100), unique=True)
    channel_type: Mapped[str] = mapped_column(String(30), default="baileys")
    wa_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wa_phone_number_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    wa_business_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="disconnected")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    leads: Mapped[list["Lead"]] = relationship(back_populates="channel")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="channel")


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    phone: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str | None] = mapped_column(String(100))
    budget: Mapped[str | None] = mapped_column(String(100))
    project_type: Mapped[str | None] = mapped_column(String(50))
    interest: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(SAEnum(LeadStatus), default=LeadStatus.new)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    agent_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped["Channel"] = relationship(back_populates="leads")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="lead", order_by="Message.created_at"
    )
    followups: Mapped[list["FollowUpLog"]] = relationship(back_populates="lead")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    direction: Mapped[str] = mapped_column(SAEnum(MessageDirection))
    content: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # image | audio | document
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # thumbnail base64 for images
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    lead: Mapped["Lead"] = relationship(back_populates="messages")


class AgentConfig(Base):
    __tablename__ = "agent_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[str] = mapped_column(Text)


class FollowUpLog(Base):
    __tablename__ = "followup_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    attempt: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    lead: Mapped["Lead"] = relationship(back_populates="followups")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(200))


class AgentDocument(Base):
    __tablename__ = "agent_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    original_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("agent_documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    document: Mapped["AgentDocument"] = relationship(back_populates="chunks")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    filter_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(SAEnum(CampaignStatus), default=CampaignStatus.draft)
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    channel: Mapped["Channel"] = relationship(back_populates="campaigns")
    recipients: Mapped[list["CampaignRecipient"]] = relationship(back_populates="campaign")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    phone: Mapped[str] = mapped_column(String(30))
    delivery_status: Mapped[str] = mapped_column(
        SAEnum(CampaignRecipientStatus), default=CampaignRecipientStatus.pending
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    campaign: Mapped["Campaign"] = relationship(back_populates="recipients")
    lead: Mapped["Lead"] = relationship()
