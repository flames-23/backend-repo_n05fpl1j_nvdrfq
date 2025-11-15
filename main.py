import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from database import db, create_document, get_documents
from bson import ObjectId

# Pydantic models from schemas
from schemas import (
    JerseyTemplate, Team, TeamRosterEntry, JerseyDesign,
    PaymentIntent, JerseyOrder, PricingTier
)

app = FastAPI(title="JerseyKraft API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "JerseyKraft backend is running"}


@app.get("/schema")
def schema_registry():
    # Expose schemas so the DB viewer can use them
    from schemas import SCHEMAS_REGISTRY
    return SCHEMAS_REGISTRY


# Templates catalog
@app.get("/api/templates", response_model=List[JerseyTemplate])
def list_templates():
    try:
        docs = get_documents("jerseytemplate")
        # Convert Mongo docs to Pydantic models
        return [JerseyTemplate(**{k: v for k, v in d.items() if k != "_id"}) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates")
def create_template(template: JerseyTemplate):
    try:
        _id = create_document("jerseytemplate", template)
        return {"id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Team management
@app.post("/api/team/import")
def import_team(team_name: str = Form(...), sport: str = Form(...), csv: UploadFile = File(...)):
    """
    Import roster from a CSV file with headers: name,number,size
    """
    import csv as pycsv
    import io

    try:
        content = csv.file.read()
    except Exception:
        csv.file.seek(0)
        content = csv.file.read()

    try:
        text = content.decode("utf-8")
        reader = pycsv.DictReader(io.StringIO(text))
        roster: List[TeamRosterEntry] = []
        for row in reader:
            if not row:
                continue
            roster.append(TeamRosterEntry(
                name=row.get("name", "").strip(),
                number=str(row.get("number", "")).strip(),
                size=row.get("size", "M").strip().upper() or "M"
            ))
        team = Team(team_name=team_name, sport=sport, roster=roster)
        _id = create_document("team", team)
        return {"id": _id, "count": len(roster)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")


# AI-powered logo creation (placeholder stub - would call an external model/service)
class AILogoRequest(BaseModel):
    prompt: str
    style: Optional[str] = "sporty"

@app.post("/api/ai/logo")
def ai_logo(req: AILogoRequest):
    # For demo, return a generated placeholder URL and suggested placement guidelines
    return {
        "logo_url": "https://placehold.co/256x256/png?text=AI+Logo",
        "suggested_positions": [
            {"area": "front_center", "x": 0.5, "y": 0.25, "w": 0.3},
            {"area": "chest_left", "x": 0.28, "y": 0.22, "w": 0.18},
            {"area": "sleeve_right", "x": 0.82, "y": 0.35, "w": 0.2}
        ]
    }


# Orders + payments
class CheckoutRequest(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: str
    shipping_address: str
    team_id: Optional[str] = None
    template_id: Optional[str] = None
    design: JerseyDesign
    quantity: int
    method: str  # upi | card | netbanking

@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    try:
        # Simple pricing calculation using tiers (server-side guard)
        tier_doc = db["pricingtier"].find_one({"min_quantity": {"$lte": req.quantity}}, sort=[("min_quantity", -1)])
        base_price = float(tier_doc.get("base_price", 999.0)) if tier_doc else 999.0
        amount = round(base_price * req.quantity, 2)

        order = JerseyOrder(
            customer_name=req.customer_name,
            customer_email=req.customer_email,
            customer_phone=req.customer_phone,
            shipping_address=req.shipping_address,
            team_id=req.team_id,
            template_id=req.template_id,
            design=req.design,
            quantity=req.quantity,
            pricing_tier=tier_doc.get("name") if tier_doc else "Starter",
            amount=amount,
        )
        order_id = create_document("jerseyorder", order)

        # Simulate payment intent creation
        pay = PaymentIntent(order_id=order_id, amount=amount, method=req.method)
        payment_id = create_document("paymentintent", pay)

        return {"order_id": order_id, "payment_id": payment_id, "amount": amount, "currency": "INR"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateStatus(BaseModel):
    status: str  # Confirmed → In Production → QC → Shipped

@app.post("/api/orders/{order_id}/status")
def update_status(order_id: str, payload: UpdateStatus):
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="Invalid order id")
    try:
        db["jerseyorder"].update_one({"_id": ObjectId(order_id)}, {"$set": {"status": payload.status}})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="Invalid order id")
    doc = db["jerseyorder"].find_one({"_id": ObjectId(order_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.get("/api/orders")
def list_orders(limit: int = 50):
    docs = db["jerseyorder"].find().sort("_id", -1).limit(limit)
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


# Admin basic endpoints
@app.post("/api/admin/tiers")
def create_tier(tier: PricingTier):
    try:
        _id = create_document("pricingtier", tier)
        return {"id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/tiers")
def list_tiers():
    return get_documents("pricingtier")


# Utility/test endpoints
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            collections = db.list_collection_names()
            response["collections"] = collections[:10]
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
