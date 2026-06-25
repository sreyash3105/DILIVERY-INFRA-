from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.order import OrderStatus

class OrderStateTransition(Base):
    __tablename__ = "order_state_transitions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(Enum(OrderStatus), nullable=False)
    to_status = Column(Enum(OrderStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="transitions")
