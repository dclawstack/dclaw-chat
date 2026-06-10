from pydantic import BaseModel, ConfigDict


class BillingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    plan: str
    status: str
    seats: int


class CheckoutRequest(BaseModel):
    # Where Stripe sends the user back after checkout (success or cancel).
    return_url: str


class CheckoutOut(BaseModel):
    checkout_url: str
