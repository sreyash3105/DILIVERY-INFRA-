import pytest
from httpx import AsyncClient
from app.models.order import OrderStatus
from app.models.driver import DriverStatus

@pytest.mark.asyncio
async def test_auth_validation(client: AsyncClient, test_tenant):
    # Invalid key
    response = await client.post("/deliveries", json={
        "pickup_lat": 12.9716, "pickup_lng": 77.5946,
        "dropoff_lat": 12.9250, "dropoff_lng": 77.5896
    }, headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API Key"}

    # Valid key
    response = await client.post("/deliveries", json={
        "pickup_lat": 12.9716, "pickup_lng": 77.5946,
        "dropoff_lat": 12.9250, "dropoff_lng": 77.5896
    }, headers={"X-API-Key": test_tenant.api_key})
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_delivery_lifecycle(client: AsyncClient, test_tenant):
    headers = {"X-API-Key": test_tenant.api_key}

    # 1. Create Driver
    driver_response = await client.post("/drivers", json={
        "name": "John Doe",
        "phone": "+1234567890"
    })
    assert driver_response.status_code == 201
    driver = driver_response.json()
    assert driver["name"] == "John Doe"

    # 2. Create Delivery
    delivery_response = await client.post("/deliveries", json={
        "pickup_lat": 12.9716, "pickup_lng": 77.5946,
        "dropoff_lat": 12.9250, "dropoff_lng": 77.5896
    }, headers=headers)
    assert delivery_response.status_code == 201
    delivery = delivery_response.json()
    assert delivery["status"] == OrderStatus.CREATED.value

    # 3. Get Delivery
    get_response = await client.get(f"/deliveries/{delivery['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == delivery["id"]

    # 4. Manual Assignment of Driver
    assign_response = await client.post(
        f"/deliveries/{delivery['id']}/assign-driver", 
        json={"driver_id": driver["id"]},
        headers=headers
    )
    assert assign_response.status_code == 200
    updated_delivery = assign_response.json()
    assert updated_delivery["status"] == OrderStatus.ASSIGNED.value
    assert updated_delivery["driver_id"] == driver["id"]

    # 5. Transition order to PICKED_UP
    update_response = await client.patch(
        f"/deliveries/{delivery['id']}/status", 
        json={"status": OrderStatus.PICKED_UP.value},
        headers=headers
    )
    assert update_response.status_code == 200
    # The server auto-advances PICKED_UP -> IN_TRANSIT immediately,
    # so the returned status is always IN_TRANSIT.
    assert update_response.json()["status"] == OrderStatus.IN_TRANSIT.value


@pytest.mark.asyncio
async def test_driver_location_and_availability(client: AsyncClient):
    # 1. Create Driver
    driver_response = await client.post("/drivers", json={
        "name": "Jane Doe",
        "phone": "+19876543210"
    })
    assert driver_response.status_code == 201
    driver = driver_response.json()

    # 2. Update Location
    loc_response = await client.post(
        f"/drivers/{driver['id']}/location",
        json={"latitude": 12.9716, "longitude": 77.5946}
    )
    assert loc_response.status_code == 200
    updated_driver = loc_response.json()
    assert updated_driver["current_lat"] == 12.9716
    assert updated_driver["current_lng"] == 77.5946
    assert updated_driver["status"] == DriverStatus.ONLINE.value

    # 3. Update Availability
    avail_response = await client.patch(
        f"/drivers/{driver['id']}/availability",
        json={"is_available": False}
    )
    assert avail_response.status_code == 200
    assert avail_response.json()["is_available"] is False
