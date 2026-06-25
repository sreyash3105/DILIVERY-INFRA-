import pytest
from app.models.order import OrderStatus
from app.services.state_machine import OrderStateMachine
from app.core.exceptions import InvalidTransitionError

def test_valid_transitions():
    # CREATED -> DRIVER_PENDING
    assert OrderStateMachine.validate_transition(OrderStatus.CREATED, OrderStatus.DRIVER_PENDING) == OrderStatus.DRIVER_PENDING
    # DRIVER_PENDING -> ASSIGNED
    assert OrderStateMachine.validate_transition(OrderStatus.DRIVER_PENDING, OrderStatus.ASSIGNED) == OrderStatus.ASSIGNED
    # ASSIGNED -> PICKED_UP
    assert OrderStateMachine.validate_transition(OrderStatus.ASSIGNED, OrderStatus.PICKED_UP) == OrderStatus.PICKED_UP
    # PICKED_UP -> IN_TRANSIT
    assert OrderStateMachine.validate_transition(OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT) == OrderStatus.IN_TRANSIT
    # IN_TRANSIT -> DELIVERED
    assert OrderStateMachine.validate_transition(OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED) == OrderStatus.DELIVERED
    # Idempotent state transitions (no change) should be valid
    assert OrderStateMachine.validate_transition(OrderStatus.CREATED, OrderStatus.CREATED) == OrderStatus.CREATED

def test_invalid_transitions():
    # Can't go CREATED -> ASSIGNED directly anymore without DRIVER_PENDING
    with pytest.raises(InvalidTransitionError):
        OrderStateMachine.validate_transition(OrderStatus.CREATED, OrderStatus.ASSIGNED)
        
    # Can't go CREATED -> DELIVERED directly
    with pytest.raises(InvalidTransitionError):
        OrderStateMachine.validate_transition(OrderStatus.CREATED, OrderStatus.DELIVERED)
        
    # Can't go DELIVERED -> ASSIGNED
    with pytest.raises(InvalidTransitionError):
        OrderStateMachine.validate_transition(OrderStatus.DELIVERED, OrderStatus.ASSIGNED)

def test_cancel_flow():
    # CREATED -> CANCELLED (allowed)
    assert OrderStateMachine.validate_transition(OrderStatus.CREATED, OrderStatus.CANCELLED) == OrderStatus.CANCELLED
    
    # DRIVER_PENDING -> CANCELLED (allowed)
    assert OrderStateMachine.validate_transition(OrderStatus.DRIVER_PENDING, OrderStatus.CANCELLED) == OrderStatus.CANCELLED
    
    # ASSIGNED -> CANCELLED (allowed)
    assert OrderStateMachine.validate_transition(OrderStatus.ASSIGNED, OrderStatus.CANCELLED) == OrderStatus.CANCELLED
    
    # PICKED_UP -> CANCELLED (not allowed)
    with pytest.raises(InvalidTransitionError):
        OrderStateMachine.validate_transition(OrderStatus.PICKED_UP, OrderStatus.CANCELLED)
