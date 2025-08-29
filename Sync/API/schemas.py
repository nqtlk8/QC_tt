from pydantic import BaseModel,Field
from typing import List
from datetime import datetime

# Schema cho từng sản phẩm trong order
class OrderProduct(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Số lượng sản phẩm phải lớn hơn 0.")

# Schema chính cho toàn bộ order
class OrderCreateRequest(BaseModel):
    user_id: int
    products: List[OrderProduct] = Field(..., min_items=1, description="Danh sách sản phẩm không được rỗng.")

# Schema cho chi tiết của mỗi sản phẩm đã được lưu
class OrderDetailResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    created_at: datetime

    class Config:
        from_attributes = True # Dùng cho SQLAlchemy ORM

# Schema chính cho response của order
class OrderResponse(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    order_details: List[OrderDetailResponse] # Chi tiết các sản phẩm trong order

    class Config:
        from_attributes = True # Dùng cho SQLAlchemy ORM