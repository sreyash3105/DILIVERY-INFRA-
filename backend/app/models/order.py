from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, Enum, Float
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    DRIVER_PENDING = "DRIVER_PENDING"
    ASSIGNED = "ASSIGNED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    NO_DRIVER_AVAILABLE = "NO_DRIVER_AVAILABLE"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.CREATED, nullable=False)
    
    # Lat/Lng floats for pickup and dropoff
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="orders")
    driver = relationship("Driver", back_populates="orders")
    transitions = relationship("OrderStateTransition", back_populates="order", cascade="all, delete-orphan")
