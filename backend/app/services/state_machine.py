from typing import Dict, Set
from app.models.order import OrderStatus
from app.core.exceptions import InvalidTransitionError

class OrderStateMachine:
    # Key represents the current state, value represents the set of next valid states
    VALID_TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
        OrderStatus.CREATED: {OrderStatus.DRIVER_PENDING, OrderStatus.CANCELLED},
        OrderStatus.DRIVER_PENDING: {OrderStatus.ASSIGNED, OrderStatus.NO_DRIVER_AVAILABLE, OrderStatus.CANCELLED},
        OrderStatus.ASSIGNED: {OrderStatus.PICKED_UP, OrderStatus.DRIVER_PENDING, OrderStatus.CANCELLED},
        OrderStatus.PICKED_UP: {OrderStatus.IN_TRANSIT},
        OrderStatus.IN_TRANSIT: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),
        OrderStatus.CANCELLED: set(),
        OrderStatus.NO_DRIVER_AVAILABLE: {OrderStatus.DRIVER_PENDING, OrderStatus.CANCELLED}
    }

    @classmethod
    def validate_transition(cls, current_status: OrderStatus, next_status: OrderStatus) -> OrderStatus:
        """
        Validates the state transition. Raises InvalidTransitionError if it is not allowed.
        Returns the new state.
        """
        if next_status == current_status:
            return next_status  # Idempotent state transitions are valid
            
        allowed_next_states = cls.VALID_TRANSITIONS.get(current_status, set())
        if next_status not in allowed_next_states:
            raise InvalidTransitionError(current_status.value, next_status.value)
        return next_status
