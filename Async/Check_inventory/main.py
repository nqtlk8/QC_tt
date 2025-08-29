import json
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from confluent_kafka import Consumer, KafkaException
from sqlalchemy.orm import Session
import model
from database import SessionLocal, engine

# Khởi tạo database
model.Base.metadata.create_all(bind=engine)

# Kafka consumer config
conf = {
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'check-inventory-group',
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
topic = "order_requests"
consumer.subscribe([topic])

# Hàm kiểm tra tồn kho cho toàn bộ đơn hàng
def check_all_products_stock(products: list, db: Session) -> bool:
    """Checks inventory for all products in the list. Returns True if all are in stock, else False."""
    all_in_stock = True
    for product_item in products:
        product_id = product_item['product_id']
        quantity = product_item['quantity']

        # Tìm sản phẩm trong DB
        db_product = db.query(model.Product).filter(model.Product.id == product_id).first()
        if not db_product:
            print(f"Product with ID {product_id} not found.")
            all_in_stock = False
            break
        
        if db_product.stock < quantity:
            print(f"Product {product_id} has insufficient stock. Required: {quantity}, Available: {db_product.stock}.")
            all_in_stock = False
            break
    
    return all_in_stock

# Hàm cập nhật số lượng tồn kho
def update_stock(products: list, db: Session):
    for product_item in products:
        db_product = db.query(model.Product).filter(model.Product.id == product_item['product_id']).first()
        if db_product:
            db_product.stock -= product_item['quantity']
            print(f"Updated stock for product {db_product.id}. New stock: {db_product.stock}")

def kafka_consumer_job():
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue
                else:
                    print(f"Consumer error: {msg.error()}")
                    continue

            data = msg.value().decode('utf-8')
            print(f"Received message from Kafka: {data}")
            order_data = json.loads(data)

            db = SessionLocal()
            try:
                order_id = order_data['order_id']
                products_to_check = order_data['product_details']
                
                # 1. Tìm đơn hàng trong DB
                db_order = db.query(model.Order).filter(model.Order.id == order_id).first()
                if not db_order or db_order.status != "pending":
                    print(f"Order {order_id} not found or already processed. Skipping.")
                    continue

                # 2. Kiểm tra tồn kho
                if check_all_products_stock(products_to_check, db):
                    # Nếu đủ, cập nhật tồn kho và trạng thái
                    update_stock(products_to_check, db)
                    db_order.status = "success"
                    print(f"Order {order_id}: All products in stock. Status updated to 'success'.")
                else:
                    # Nếu không đủ, cập nhật trạng thái thành 'failed'
                    db_order.status = "failed"
                    print(f"Order {order_id}: Insufficient stock. Status updated to 'failed'.")
                
                # 3. Commit thay đổi
                db.commit()

            except Exception as e:
                db.rollback()
                print(f"Error processing order {order_data.get('order_id')}: {e}")
            finally:
                db.close()

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        print("Consumer closed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    thread = threading.Thread(target=kafka_consumer_job, daemon=True)
    thread.start()
    yield
    # Shutdown (if needed)

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Kafka inventory consumer running, listening to topic 'order_requests'."}