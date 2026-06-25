from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted in the state machine."""
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition from state '{from_state}' to '{to_state}'")


class TenantNotFoundError(Exception):
    """Raised when the API key does not correspond to any registered tenant."""
    pass


class OrderNotFoundError(Exception):
    """Raised when the requested delivery/order does not exist."""
    pass


class DriverNotFoundError(Exception):
    """Raised when the requested driver does not exist."""
    pass


class UnauthorizedTenantError(Exception):
    """Raised when a tenant attempts to access or mutate resources they do not own."""
    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidTransitionError)
    async def invalid_transition_handler(request: Request, exc: InvalidTransitionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Invalid state transition"}
        )

    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API Key"}
        )

    @app.exception_handler(OrderNotFoundError)
    async def order_not_found_handler(request: Request, exc: OrderNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Delivery not found"}
        )

    @app.exception_handler(DriverNotFoundError)
    async def driver_not_found_handler(request: Request, exc: DriverNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Driver not found"}
        )

    @app.exception_handler(UnauthorizedTenantError)
    async def unauthorized_tenant_handler(request: Request, exc: UnauthorizedTenantError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden access to this resource"}
        )
