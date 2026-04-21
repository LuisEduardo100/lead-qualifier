from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SAEnum
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


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    instance_name: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="disconnected")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    leads: Mapped[list["Lead"]] = relationship(back_populates="channel")


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
    channel: Mapped["Channel"] = relationship(back_populates="leads")
    messages: Mapped[list["Message"]] = relationship(back_populates="lead", order_by="Message.created_at")
    followups: Mapped[list["FollowUpLog"]] = relationship(back_populates="lead")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    direction: Mapped[str] = mapped_column(SAEnum(MessageDirection))
    content: Mapped[str] = mapped_column(Text)
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
