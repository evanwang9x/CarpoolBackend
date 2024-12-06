from flask_sqlalchemy import SQLAlchemy
import base64
import boto3
import datetime
import io
from io import BytesIO
from mimetypes import guess_extension, guess_type
import os
from PIL import Image
import random
import re
import string

db = SQLAlchemy()

EXTENSIONS = ["png", "gif", "jpg", "jpeg"]
BASE_DIR = os.getcwd()
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.us-east-1.amazonaws.com"

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
    username = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    hosted_carpools = db.relationship("Carpool")
    joined_carpools = db.relationship("Carpool", secondary=passenger_table, back_populates="passengers")
    pending_carpools = db.relationship("Carpool", secondary=pending_passenger_table, back_populates="pending_passengers")
    
    def __init__(self, **kwargs):
        self.first_name = kwargs.get("first_name", "")
        self.last_name = kwargs.get("last_name", "")
        self.email = kwargs.get("email", "")
        self.phone_number = kwargs.get("phone_number", "")
        self.username = kwargs.get("username", "")
        self.password = kwargs.get("password", "")

    def serialize(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "email": self.email,
            "phone_number": self.phone_number,
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
            "full_name": f"{self.first_name} {self.last_name}",
            "email": self.email,
            "phone_number": self.phone_number
        }


class Carpool(db.Model):
    __tablename__ = "carpools"
    id = db.Column(db.Integer, primary_key=True)
    start_location = db.Column(db.String, nullable=False)
    end_location = db.Column(db.String, nullable=False)
    start_time = db.Column(db.Integer, nullable=False)
    total_capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    car_type = db.Column(db.String, nullable=False)
    license_plate = db.Column(db.String, nullable=False)
    image = db.Column(db.String)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def __init__(self, **kwargs):
        self.start_location = kwargs.get("start_location")
        self.end_location = kwargs.get("end_location")
        self.start_time = kwargs.get("start_time")
        self.total_capacity = kwargs.get("total_capacity")
        self.price = float(kwargs.get("price", 0)) 
        self.car_type = kwargs.get("car_type")
        self.license_plate = kwargs.get("license_plate")
        self.image = kwargs.get("image")
        self.driver_id = kwargs.get("driver_id")
    def serialize(self):
        driver = User.query.filter_by(id=self.driver_id).first()
        current_riders = [driver.email] + [p.email for p in self.passengers]
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
            "image": self.image,
            "driver": driver.simple_serialize(),
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
            "license_plate": self.license_plate,
            "image": self.image
        }


class Asset(db.Model):
    """
    Asset model
    """

    __tablename__ = "asset"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    base_url = db.Column(db.String, nullable=True)
    salt = db.Column(db.Integer, nullable=False)
    extension = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs):
        """
        Initializes an Asset object
        """
        self.create(kwargs.get("image_data"))

    def serialize(self):
        return {
            "url": f"{self.base_url}/{self.salt}.{self.extension}",
            "created_at": str(self.created_at)
        }


    def create(self, image_data):
        """
        Given an image in base64 form, does the following:
            1. Rejects the image if it's not supported filetype
            2. Generates a random string for the image filename
            3. Decodes the image and attempts to upload it to AWS
        """
        try:
            ext = guess_extension(guess_type(image_data)[0])[1:]
            if ext not in EXTENSIONS:
                raise Exception(f"Unsupported file type: {ext}")

            # securely generate a random string for image name
            salt = "".join(
                random.SystemRandom().choice(
                    string.ascii_uppercase + string.digits
                )
                for _ in range(16)
            )

            # remove base64 header
            img_str = re.sub("^data:image/.+;base64,", "", image_data)
            img_data = base64.b64decode(img_str)
            img = Image.open(BytesIO(img_data))

            self.base_url = S3_BASE_URL
            self.salt = salt
            self.extension = ext
            self.width = img.width
            self.height = img.height
            self.created_at = datetime.datetime.now()

            img_filename = f"{self.salt}.{self.extension}"
            self.upload(img, img_filename)
        except Exception as e:
            print(f"Error while creating image: {e}")

    def upload(self, img, img_filename):
        """
        Attempt to upload the image into S3 bucket
        """
        print(img_filename)
        try:
            img_temploc = f"{BASE_DIR}/{img_filename}"
            img.save(img_temploc)
            s3_client = boto3.client("s3")
            s3_client.upload_file(img_temploc, S3_BUCKET_NAME, img_filename)
            s3_resource = boto3.resource("s3")
            object_acl = s3_resource.ObjectAcl(S3_BUCKET_NAME, img_filename)  # NOT DONE
            object_acl.put(ACL="public-read")
            os.remove(img_temploc)
        except Exception as e:
            print(f"Error while uploading image: {e}")
