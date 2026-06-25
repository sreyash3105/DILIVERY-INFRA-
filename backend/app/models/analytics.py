from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, func
from app.db.base import Base

class TripAnalytics(Base):
    __tablename__ = "trip_analytics"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    actual_delivery_time = Column(Float, nullable=True) # in seconds
    eta_accuracy = Column(Float, nullable=True) # percentage deviation
    distance_traveled = Column(Float, nullable=True) # in meters
    pickup_delay = Column(Float, nullable=True) # in seconds
    driver_idle_time = Column(Float, nullable=True) # in seconds
    assignment_time = Column(Float, nullable=True) # in seconds

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class DriverAnalytics(Base):
    __tablename__ = "driver_analytics"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    acceptance_rate = Column(Float, default=0.0, nullable=False)
    rejection_rate = Column(Float, default=0.0, nullable=False)
    timeout_rate = Column(Float, default=0.0, nullable=False)
    avg_pickup_time = Column(Float, default=0.0, nullable=False) # in seconds
    avg_delivery_time = Column(Float, default=0.0, nullable=False) # in seconds
    eta_accuracy = Column(Float, default=0.0, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class TenantAnalytics(Base):
    __tablename__ = "tenant_analytics"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    total_deliveries = Column(Integer, default=0, nullable=False)
    avg_delivery_time = Column(Float, default=0.0, nullable=False) # in seconds
    avg_assignment_time = Column(Float, default=0.0, nullable=False) # in seconds
    notification_success_rate = Column(Float, default=100.0, nullable=False)
    driver_acceptance_rate = Column(Float, default=100.0, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class TenantUsageHourly(Base):
    __tablename__ = "tenant_usage_hourly"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    hour = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
