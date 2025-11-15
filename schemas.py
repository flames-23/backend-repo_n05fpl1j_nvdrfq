"""
Database Schemas for JerseyKraft

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase of the class name.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# Core domain models
class PricingTier(BaseModel):
    name: str = Field(..., description="Tier name e.g. Starter, Pro, Elite")
    base_price: float = Field(..., ge=0, description="Base price per jersey")
    min_quantity: int = Field(1, ge=1, description="Minimum quantity for this tier")
    features: List[str] = Field(default_factory=list, description="Included features")

class JerseyTemplate(BaseModel):
    sport: Literal["cricket", "football", "basketball", "kabaddi", "hockey", "badminton"] = Field(
        ..., description="Sport type"
    )
    name: str = Field(..., description="Template name")
    colors: List[str] = Field(default_factory=lambda: ["#0A66C2", "#FF6F00"], description="Primary accent colors")
    preview_url: Optional[str] = Field(None, description="Preview image URL")
    svg: Optional[str] = Field(None, description="Optional SVG template markup")
    is_public: bool = Field(True, description="Visible in catalog")

class TeamRosterEntry(BaseModel):
    name: str
    number: str
    size: Literal["XS", "S", "M", "L", "XL", "XXL"]

class Team(BaseModel):
    team_name: str
    sport: str
    roster: List[TeamRosterEntry] = Field(default_factory=list)
    logo_url: Optional[str] = None
    sponsor_logo_url: Optional[str] = None

class JerseyDesign(BaseModel):
    front_color: str = Field("#0A66C2")
    back_color: str = Field("#0A66C2")
    accents: List[str] = Field(default_factory=lambda: ["#FF6F00"])  # saffron
    text_elements: List[dict] = Field(default_factory=list, description="Draggable text layers")
    logo_elements: List[dict] = Field(default_factory=list, description="Draggable logo layers")

class PaymentIntent(BaseModel):
    order_id: Optional[str] = None
    amount: float = Field(..., ge=0)
    currency: str = Field("INR")
    method: Literal["upi", "card", "netbanking"]
    status: Literal["created", "processing", "paid", "failed"] = "created"

class JerseyOrder(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: str
    shipping_address: str
    team_id: Optional[str] = None
    template_id: Optional[str] = None
    design: JerseyDesign
    quantity: int = Field(1, ge=1)
    pricing_tier: Optional[str] = None
    amount: float = Field(..., ge=0)
    payment_status: Literal["pending", "paid", "failed"] = "pending"
    status: Literal["Confirmed", "In Production", "QC", "Shipped"] = "Confirmed"

# Minimal admin user for access control (can be expanded later)
class AdminUser(BaseModel):
    email: str
    role: Literal["admin", "manager"] = "admin"

# The Flames database viewer reads from GET /schema
SCHEMAS_REGISTRY = {
    "pricingtier": PricingTier.model_json_schema(),
    "jerseytemplate": JerseyTemplate.model_json_schema(),
    "teamrosterentry": TeamRosterEntry.model_json_schema(),
    "team": Team.model_json_schema(),
    "jerseydesign": JerseyDesign.model_json_schema(),
    "paymentintent": PaymentIntent.model_json_schema(),
    "jerseyorder": JerseyOrder.model_json_schema(),
    "adminuser": AdminUser.model_json_schema(),
}
