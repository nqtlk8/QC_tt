from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import schema,model
from sqlalchemy.orm import Session
from confluent_kafka import Producer
import json
from database import SessionLocal
from database import engine, Base

app = FastAPI()
Base.metadata.create_all(bind=engine)
# Cấu hình Kafka Producer
conf = {'bootstrap.servers': 'kafka:9092'}
producer = Producer(conf)

def delivery_report(err, msg):
    """Callback function for message delivery."""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

@app.post("/place_order", status_code=202)
def place_order(order_request: schema.OrderCreateRequest):
    """
    Receives a multi-product order, saves it to the database with a 'pending' status,
    and sends a message to Kafka for asynchronous processing.
    """
    db = SessionLocal()
    try:
        # 1. Tạo bản ghi Order chính với status 'pending'
        db_order = model.Order(user_id=order_request.user_id, status="pending")
        db.add(db_order)
        db.flush()  # Dùng flush để lấy order_id trước khi commit

        # 2. Tạo các bản ghi OrderDetail
        for product in order_request.products:
            db_detail = model.OrderDetail(
                order_id=db_order.id,
                product_id=product.product_id,
                quantity=product.quantity
            )
            db.add(db_detail)
        
        db.commit()
        db.refresh(db_order)

        # 3. Chuẩn bị và gửi thông điệp tới Kafka
        message_data = {
            "order_id": db_order.id,
            "user_id": db_order.user_id,
            "product_details": [p.dict() for p in order_request.products]
        }
        data = json.dumps(message_data)
        producer.produce(topic="order_requests", value=data.encode('utf-8'), callback=delivery_report)
        producer.flush()

        return {"message": "Order accepted and is being processed.", "order_id": db_order.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "order_placement"}