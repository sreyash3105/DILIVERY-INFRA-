from sqlalchemy import Column, Integer, String, DateTime, func, Enum, Float, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class DriverStatus(str, enum.Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    BUSY = "BUSY"

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    status = Column(Enum(DriverStatus), default=DriverStatus.OFFLINE, nullable=False)
    
    # Lat/Lng floats for current location
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    
    # New platform features
    rating = Column(Float, default=5.0, nullable=True)
    is_available = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="driver")
