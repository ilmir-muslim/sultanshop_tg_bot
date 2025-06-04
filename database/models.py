from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    BigInteger,
    func,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


class Banner(Base):
    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(15), unique=True)
    image: Mapped[str] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    purchase_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    image: Mapped[str] = mapped_column(String(150))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, default=1
    )
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(backref="products")
    order_item: Mapped[list["OrderItem"]] = relationship(back_populates="product")
    seller: Mapped["Seller"] = relationship(backref="products")


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(13), nullable=True)
    address: Mapped[str] = mapped_column(String(150), nullable=True)


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(String(150), nullable=True)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    user: Mapped["Users"] = relationship(backref="carts")
    product: Mapped["Product"] = relationship(backref="carts")


class WaitList(Base):
    __tablename__ = "wait_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["Users"] = relationship(backref="wait_list")
    product: Mapped["Product"] = relationship(backref="wait_list")


class Orders(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(150))
    deliverer_id: Mapped[int] = mapped_column(  # Переименовано
        ForeignKey("deliverers.id", ondelete="SET NULL"), nullable=True
    )
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    user: Mapped["Users"] = relationship(backref="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    deliverer: Mapped["Deliverer"] = relationship(
        backref="orders", foreign_keys=[deliverer_id]
    )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Связи
    order: Mapped["Orders"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_item")


class Deliverer(Base):
    __tablename__ = "deliverers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_name: Mapped[str] = mapped_column(String(150), nullable=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DelivererReview(Base):
    __tablename__ = "deliverer_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    deliverer_id: Mapped[int] = mapped_column(
        ForeignKey("deliverers.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_summary: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=True)

    user: Mapped["Users"] = relationship(backref="deliverer_reviews")
    deliverer: Mapped["Deliverer"] = relationship(backref="deliverer_reviews")


class FeedbackBook(Base):
    __tablename__ = "feedback_book"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    user: Mapped["Users"] = relationship(backref="feedback_book", uselist=False)

class PickupPoint(Base):
    __tablename__ = "pickup_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    google_map_location: Mapped[str] = mapped_column(Text, nullable=True)