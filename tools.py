from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams
from loguru import logger

order = {
    "order_id": "000",
    "customer_name": "John Doe",
    "items": [
        {"sku": "SKU-123", "name": "Wireless Mouse", "qty": 1, "price": 25.99},
        {"sku": "SKU-456", "name": "Mechanical Keyboard", "qty": 1, "price": 45.50},
    ],
    "subtotal": 71.49,
    "shipping": 5.00,
    "tax": 6.43,
    "total": 82.92,
    "currency": "USD",
    "status": "processing",
    "placed_at": "2025-08-22T10:15:00Z",
    "notes": "Leave at front desk if not home.",
}


def get_order_status(order_id: str) -> str:
    """Return the current status for the given order_id or 'not_found'."""
    logger.error("🟢🟢🟢🟢",order_id)
    if order.get("order_id") == order_id:
        return order.get("status", "unknown")
    return "not_found"



def cancel_order(order_id: str, reason: str | None = None) -> bool:
    """Attempt to cancel the order. Returns True if cancelled, False otherwise."""
    if order.get("order_id") != order_id:
        return False
    # Do not cancel if already finalized
    if order.get("status") in ("cancelled", "shipped", "delivered"):
        return False
    order["status"] = "cancelled"
    from datetime import datetime

    order["cancelled_at"] = datetime.utcnow().isoformat() + "Z"
    if reason:
        order["cancellation_reason"] = reason
    return True


def change_delivery_address(order_id: str, new_address: dict) -> bool:
    """Update the delivery/shipping address for the order. Returns True on success."""
    if order.get("order_id") != order_id:
        return False
    order["shipping_address"] = new_address
    # optional: record the change time
    from datetime import datetime

    order["address_updated_at"] = datetime.utcnow().isoformat() + "Z"
    return True


fs_get_order_details = FunctionSchema(
    name="get_order_details",
    description="Retrieve order details by order Id  .",
    properties={
        "order_id": {
            "type": "string",
            "description": "Order identifier to get order detail Eg: 000, 111 ",
        }
    },
    required=["order_id"],
)

fs_get_status = FunctionSchema(
    name="get_order_status",
    description="Get the current status for a specific order.",
    properties={
        "order_id": {
            "type": "string",
            "description": "Order identifier to check status for",
        }
    },
    required=["order_id"],
)

fs_cancel = FunctionSchema(
    name="cancel_order",
    description="Attempt to cancel an order. Returns true on success.",
    properties={
        "order_id": {
            "type": "string",
            "description": "Order identifier to cancel",
        },
        "reason": {
            "type": "string",
            "description": "Optional cancellation reason",
        },
    },
    required=["order_id"],
)

fs_change_address = FunctionSchema(
    name="change_delivery_address",
    description="Update the delivery/shipping address for an order.",
    properties={
        "order_id": {
            "type": "string",
            "description": "Order identifier to update",
        },
        "new_address": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "postal_code": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["street", "city", "country"],
        },
    },
    required=["order_id", "new_address"],
)


async def _handle_get_order(params: FunctionCallParams):
  
    await params.result_callback({"order": order})


async def _handle_get_status(params: FunctionCallParams):
    order_id = params.arguments.get("order_id")

    status = get_order_status(order_id)
    
    await params.result_callback({"order_id": order_id, "status": status})


async def _handle_cancel(params: FunctionCallParams):
    order_id = params.arguments.get("order_id")
    reason = params.arguments.get("reason")
    success = cancel_order(order_id, reason)
    await params.result_callback({"order_id": order_id, "cancelled": success})


async def _handle_change_address(params: FunctionCallParams):
    order_id = params.arguments.get("order_id")
    new_address = params.arguments.get("new_address")
    success = change_delivery_address(order_id, new_address)
    await params.result_callback({"order_id": order_id, "updated": success})
