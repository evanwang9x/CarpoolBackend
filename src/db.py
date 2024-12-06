from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

passenger_table = db.Table(
    "passenger",
    db.Model.metadata,
    db.Column("carpool_id", db.Integer, db.ForeignKey("carpools.id")),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"))
)

pending_passenger_table = db.Table(
    "pending_passenger",
    db.Model.metadata,
    db.Column("carpool_id", db.Integer, db.ForeignKey("carpools.id")),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"))
)


class User(db.Model):
    """
    User Model
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String, nullable=False)
    last_name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True)
    phone_number = db.Column(db.String, nullable=False)
    image = db.Column(db.String)  # TO BE REVISED
    username = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    hosted_carpools = db.relationship("Carpool", back_populates="driver")
    joined_carpools = db.relationship("Carpool", secondary=passenger_table, back_populates="passengers")
    pending_carpools = db.relationship("Carpool", secondary=pending_passenger_table, back_populates="pending_carpools")

    def __init__(self, **kwargs):
        self.first_name = kwargs.get("first_name", "")
        self.last_name = kwargs.get("last_name", "")
        self.email = kwargs.get("email", "")
        self.phone_number = kwargs.get("phone_number", "")
        self.image = kwargs.get("image")  # TO BE REVISED
        self.username = kwargs.get("username", "")
        self.password = kwargs.get("password", "")

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def serialize(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "image": self.image,  # TO BE REVISED
            "username": self.username,
            "hosted_carpools": [c.simple_serialize() for c in self.hosted_carpools],
            "joined_carpools": [c.simple_serialize() for c in self.joined_carpools],
            "pending_carpools": [c.simple_serialize() for c in self.pending_carpools]
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "image": self.image  # TO BE REVISED
        }

    def safe_serialize(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "username": self.username
        }


class Carpool(db.Model):
    """
    Carpool Model
    """

    __tablename__ = "carpools"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_location = db.Column(db.String, nullable=False)
    end_location = db.Column(db.String, nullable=False)
    start_time = db.Column(db.Integer, nullable=False)
    total_capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    car_type = db.Column(db.String, nullable=False)
    license_plate = db.Column(db.String, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    driver = db.relationship("User", back_populates="hosted_carpools")
    passengers = db.relationship("User", secondary=passenger_table, back_populates="joined_carpools")
    pending_passengers = db.relationship("User", secondary=pending_passenger_table, back_populates="pending_carpools")

    def __init__(self, **kwargs):
        self.start_location = kwargs.get("start_location", "")
        self.end_location = kwargs.get("end_location", "")
        self.start_time = kwargs.get("start_time", 0)
        self.total_capacity = kwargs.get("total_capacity", 0)
        self.price = kwargs.get("price", 0.0)
        self.car_type = kwargs.get("car_type", "")
        self.license_plate = kwargs.get("license_plate", "")
        self.driver_id = kwargs.get("driver_id")

    def serialize(self):
        current_riders = [self.driver.email] + [p.email for p in self.passengers]
        return {
            "id": self.id,
            "start_location": self.start_location,
            "end_location": self.end_location,
            "start_time": self.start_time,
            "total_capacity": self.total_capacity,
            "available_seats": self.total_capacity - len(self.passengers) - 1,
            "price": self.price,
            "car_type": self.car_type,
            "license_plate": self.license_plate,
            "driver": self.driver.serialize(),
            "current_riders": current_riders,
            "pending_riders": [p.email for p in self.pending_passengers]
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "start_location": self.start_location,
            "end_location": self.end_location,
            "start_time": self.start_time,
            "total_capacity": self.total_capacity,
            "available_seats": self.total_capacity - len(self.passengers) - 1,
            "price": self.price,
            "car_type": self.car_type,
            "license_plate": self.license_plate
        }