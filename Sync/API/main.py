from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import status
import model, schemas
from database import SessionLocal, engine
import time
from typing import List


app = FastAPI()

# Dependency lấy session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#tạo bảng nếu chưa có
model.Base.metadata.create_all(bind=engine)

# Hàm kiểm tra số lượng sản phẩm trong kho
def check_product_stock(
    db: Session,
    products_to_order: List[schemas.OrderProduct]
) -> None:
    """
    Kiểm tra xem tất cả sản phẩm trong đơn hàng có đủ số lượng trong kho không.
    Nếu không đủ, raise HTTPException.
    """
    product_ids = [p.product_id for p in products_to_order]
    
    # Lấy thông tin stock của tất cả sản phẩm cần kiểm tra
    # Sử dụng select để xây dựng truy vấn an toàn và hiệu quả hơn
    stmt = select(model.Product).where(model.Product.id.in_(product_ids))
    db_products = db.execute(stmt).scalars().all()

    # Chuyển đổi danh sách sản phẩm thành dictionary để dễ dàng truy cập bằng ID
    # Ví dụ: {product_id: product_object}
    product_stock_map = {product.id: product for product in db_products}

    # Kiểm tra từng sản phẩm trong order_request
    for item in products_to_order:
        product_in_db = product_stock_map.get(item.product_id)
        
        if not product_in_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sản phẩm với ID {item.product_id} không tồn tại."
            )
        
        if product_in_db.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không đủ số lượng cho sản phẩm '{product_in_db.name}' (ID: {item.product_id}). "
                       f"Chỉ còn {product_in_db.stock} trong kho."
            )
            
    # Nếu tất cả đều đủ, không làm gì cả (hàm sẽ hoàn thành)


# Hàm ghi thông tin order và order_details vào database
def create_order_in_db(
    db: Session,
    user_id: int,
    products_to_order: List[schemas.OrderProduct]
) -> model.Order:
    """
    Tạo một đơn hàng mới và các chi tiết đơn hàng trong database.
    Đồng thời giảm số lượng sản phẩm trong kho.
    """
    # Bước 1: Tạo Order
    db_order = model.Order(user_id=user_id)
    db.add(db_order)
    db.flush() # flush để lấy db_order.id trước khi commit

    order_details_list = []
    
    # Lấy lại các sản phẩm để cập nhật stock
    product_ids = [p.product_id for p in products_to_order]
    stmt = select(model.Product).where(model.Product.id.in_(product_ids))
    db_products = db.execute(stmt).scalars().all()
    product_update_map = {product.id: product for product in db_products}

    # Bước 2: Tạo Order Details và cập nhật stock
    for item in products_to_order:
        # Tạo OrderDetail
        db_order_detail = model.OrderDetail(
            order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        order_details_list.append(db_order_detail)
        
        # Cập nhật số lượng trong kho
        product_update_map[item.product_id].stock -= item.quantity

    db.add_all(order_details_list) # Thêm tất cả chi tiết đơn hàng
    db.commit() # Commit tất cả thay đổi (Order, OrderDetails, Product stock)
    db.refresh(db_order) # Refresh để tải các relationship như order_details

    return db_order

# --- Endpoint FastAPI ---

@app.post("/orders/", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_request: schemas.OrderCreateRequest, # Sử dụng schema mới cho request
    db: Session = Depends(get_db)
):
    """
    Tạo một đơn hàng mới.
    - Kiểm tra số lượng sản phẩm có sẵn trong kho.
    - Ghi thông tin đơn hàng và chi tiết đơn hàng vào database.
    - Cập nhật số lượng sản phẩm trong kho.
    """
    # 1. Kiểm tra stock
    check_product_stock(db, order_request.products)
    
    # 2. Ghi vào database và giảm stock
    created_order = create_order_in_db(db, order_request.user_id, order_request.products)
    
    return created_order

@app.get("/health")
def health_check():
    return {"status": "ok"}

