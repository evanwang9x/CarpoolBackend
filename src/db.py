from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

passenger_table = db.Table(
    "passenger",
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
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    hosted_carpools = db.relationship("Carpool", back_populates="driver")
    joined_carpools = db.relationship("Carpool", secondary=passenger_table, back_populates="passengers")

    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.email = kwargs.get("email", "")

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "password": self.password,
            "hosted_carpools": [c.simple_serialize() for c in self.hosted_carpools],
            "joined_carpools": [c.simple_serialize() for c in self.joined_carpools]
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "password": self.password
        }

    def safe_serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username
        }


class Carpool(db.Model):
    """
    Carpool Model
    """
    __tablename__ = "carpools"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    departure_location = db.Column(db.String, nullable=False)
    destination = db.Column(db.String, nullable=False)
    departure_time = db.Column(db.Integer, nullable=False)
    meeting_point = db.Column(db.String, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    driver = db.relationship("User", back_populates="hosted_carpools")
    passengers = db.relationship("User", secondary=passenger_table, back_populates="joined_carpools")

    def __init__(self, **kwargs):
        self.departure_location = kwargs.get("departure_location", "")
        self.destination = kwargs.get("destination", "")
        self.departure_time = kwargs.get("departure_time", 0)
        self.meeting_point = kwargs.get("meeting_point", "")
        self.total_seats = kwargs.get("total_seats", 0)
        self.driver_id = kwargs.get("driver_id")

    def serialize(self):
        return {
            "id": self.id,
            "departure_location": self.departure_location,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "meeting_point": self.meeting_point,
            "total_seats": self.total_seats,
            "available_seats": self.total_seats - len(self.passengers),
            "driver": self.driver.simple_serialize(),
            "passengers": [p.simple_serialize() for p in self.passengers]
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "departure_location": self.departure_location,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "meeting_point": self.meeting_point,
            "total_seats": self.total_seats,
            "available_seats": self.total_seats - len(self.passengers)
        }
