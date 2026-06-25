from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, func
from app.db.base import Base
import enum

class NotificationStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    
    channel = Column(String, nullable=False) # EMAIL, PUSH, WEBSOCKET
    event_type = Column(String, nullable=False) # ASSIGNED, PICKED_UP, NEAR_DELIVERY, DELIVERED
    
    status = Column(Enum(NotificationStatus), default=NotificationStatus.RETRY, nullable=False)
    error_message = Column(String, nullable=True)
    
    attempted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
