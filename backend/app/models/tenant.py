from sqlalchemy import Column, Integer, String, DateTime, func, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)
    
    # SaaS Plan Details
    plan_name = Column(String, default="FREE", nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    monthly_quota = Column(Integer, default=10000, nullable=False)
    quota_exceeded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notification preferences structure: channel configurations
    notification_preferences = Column(JSON, default=lambda: {
        "ASSIGNED": ["WEBSOCKET", "PUSH"],
        "PICKED_UP": ["WEBSOCKET", "PUSH"],
        "NEAR_DELIVERY": ["PUSH"],
        "DELIVERED": ["WEBSOCKET", "PUSH", "EMAIL"]
    }, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
