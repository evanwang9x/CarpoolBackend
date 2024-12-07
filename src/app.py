from flask import Flask, request
import json
from db import db, User, Carpool, Asset
import re
from datetime import datetime
app = Flask(__name__)
db_filename = "carpool.db"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///%s" % db_filename
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True

db.init_app(app)
with app.app_context():
    db.create_all()


def success_response(data, code=200):
    return json.dumps(data), code


def failure_response(message, code=404):
    return json.dumps({"error": message}), code

def validate_time_format(time_str):
    """
    Validates if a time string is in correct format and not in the past.
    Args:
        time_str (str): Time string in format 'YYYY-MM-DD HH:MM:SS'
    Returns:
        tuple: (is_valid: bool, converted_time: datetime or None)
    Will fail if:
    - time_str is None or empty
    - time_str is not in correct format
    - time_str represents a past date/time
    """
    try:
        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        if time <= current_time:
            return False, None
        return True, time
    except (ValueError, TypeError):
        return False, None

def check_driver_availability(driver_id, start_time):
    """
    Checks if driver has any existing carpools within 2 hours of given time.
    Args:
        driver_id (int): Valid user ID of the driver
        start_time (str): Time string in format 'YYYY-MM-DD HH:MM:SS'
    Returns:
        bool: True if driver is available, False if conflict exists
    Will fail if:
    - driver_id doesn't exist in database
    - start_time is not in correct format
    - Database query fails
    """
    existing_carpools = Carpool.query.filter_by(driver_id=driver_id).all()
    new_ride_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    
    for carpool in existing_carpools:
        existing_time = datetime.strptime(carpool.start_time, "%Y-%m-%d %H:%M:%S")
        time_difference = abs((existing_time - new_ride_time).total_seconds() / 3600)
        if time_difference < 2:
            return False
    return True
def validate_email_syntax(email):
    """
    Validates email syntax using regex pattern.

    Args:
        email (str): Email address to validate

    Returns:
        bool: True if email format is valid, False otherwise
        
    Will fail if:
    - email is None or empty string
    - email doesn't match standard email format (user@domain.tld)
    """
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

def check_passenger_availability(user_id, start_time):
    """
    Checks if user has any conflicting carpools within 2 hours of given time,
    either as driver or passenger.
    Args:
        user_id (int): Valid user ID to check
        start_time (str): Time string in format 'YYYY-MM-DD HH:MM:SS'
    Returns:
        bool: True if user is available, False if conflict exists
    Will fail if:
    - user_id doesn't exist in database
    - start_time is not in correct format
    - Database query fails
    """
    driver_carpools = Carpool.query.filter_by(driver_id=user_id).all()
    passenger_carpools = Carpool.query.join(Carpool.passengers).filter_by(id=user_id).all()
    all_carpools = driver_carpools + passenger_carpools
    new_ride_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    
    for carpool in all_carpools:
        existing_time = datetime.strptime(carpool.start_time, "%Y-%m-%d %H:%M:%S")
        time_difference = abs((existing_time - new_ride_time).total_seconds() / 3600)
        if time_difference < 2: 
            return False
    return True


@app.route("/api/users/")
def get_users():
    """
    Endpoint for getting all users, does not include passwords
    """
    return success_response({"users": [c.simple_serialize() for c in User.query.all()]}, 200)


@app.route("/api/users/", methods=["POST"])
def create_user():
    """
    Endpoint for creating a user
    """
    body = json.loads(request.data)
    
    if not body.get("username"):
        return failure_response("Missing required field: username", 400)
    if not body.get("email"):
        return failure_response("Missing required field: email", 400)
    
    if not validate_email_syntax(body.get("email")):
        return failure_response("Invalid email format", 400)

    existing_user = User.query.filter_by(username=body.get("username")).first()
    if existing_user is not None:
        return failure_response("Username already exists", 400)

    existing_email = User.query.filter_by(email=body.get("email")).first()
    if existing_email is not None:
        return failure_response("Email already exists", 400)

    new_user = User(
        first_name=body.get("first_name"),
        last_name=body.get("last_name"),
        email=body.get("email"),
        phone_number=body.get("phone_number", ""),
        username=body.get("username"),
        password=body.get("password"),
    )

    db.session.add(new_user)
    db.session.commit()
    return success_response(new_user.serialize(), 201)

@app.route("/api/users/<int:user_id>/")
def get_user(user_id):
    """
    Get a specific user by id
    """
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")
    return success_response(user.serialize())


@app.route("/api/login/", methods=["POST"])
def login():
    """
    Endpoint for user login authentication
    Takes email and password in request body
    Returns user data if credentials are valid
    """
    body = json.loads(request.data)
    if not body.get("email") or not body.get("password"):
        return failure_response("Missing email or password field", 400)

    if not validate_email_syntax(body.get("email")):
        return failure_response("Invalid email format", 400)

    user = User.query.filter_by(email=body.get("email")).first()

    if user is None:
        return failure_response("User not found", 404)

    if user.password != body.get("password"):
        return failure_response("Invalid password", 401)

    return success_response({
        "message": "Successfully logged in",
        "user": user.serialize()
    })

@app.route("/api/carpools/", methods=["POST"])
def create_carpool():
    body = json.loads(request.data)
    
    required_fields = ["start_location", "end_location", "start_time", 
                      "total_capacity", "price", "car_type", 
                      "license_plate", "driver_id"]
    
    for field in required_fields:
        if not body.get(field):
            return failure_response(f"Missing required field: {field}", 400)
    
    price = body.get("price")
    try:
        price = float(price)
        if price < 0:
            return failure_response("Price cannot be negative", 400)
    except (TypeError, ValueError):
        return failure_response("Invalid price format", 400)
    
    try:
        total_capacity = int(body.get("total_capacity"))
        if total_capacity <= 1:
            return failure_response("Total capacity must be greater than 1", 400)
    except (TypeError, ValueError):
        return failure_response("Invalid total capacity format", 400)
    
    start_time = body.get("start_time")
    try:
        datetime_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        
        if datetime_obj <= datetime.now():
            return failure_response("Start time cannot be in the past", 400)
            
        formatted_start_time = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
        
    except ValueError:
        return failure_response("Invalid start time format. Please use YYYY-MM-DD HH:MM:SS format", 400)
    
    driver_id = body.get("driver_id")
    driver = User.query.filter_by(id=driver_id).first()
    if driver is None:
        return failure_response("Driver not found", 404)
    
    if not check_driver_availability(driver_id, formatted_start_time):
        return failure_response("Driver already has a carpool scheduled around this time", 400)

    new_carpool = Carpool(
        start_location=body.get("start_location"),
        end_location=body.get("end_location"),
        start_time=formatted_start_time,
        total_capacity=total_capacity,
        price=price,
        car_type=body.get("car_type"),
        license_plate=body.get("license_plate"),
        image=body.get("image"),
        driver_id=driver_id
    )
    
    db.session.add(new_carpool)
    db.session.commit()
    return success_response(new_carpool.serialize(), 201)
@app.route("/api/carpools/all/")
def get_all_carpools():
    """
    Endpoint for getting all carpools without any filters
    """
    carpools = Carpool.query.all()
    return success_response({
        "carpools": [c.serialize() for c in carpools]
    })


@app.route("/api/carpools/<int:carpool_id>/")
def get_carpool(carpool_id):
    """
    Endpoint for getting a specific carpool by id
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/join/", methods=["POST"])
def join_carpool(carpool_id):
    """
    Endpoint for requesting to join a carpool as a pending rider
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400)

    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")
        
    if len(carpool.passengers) >= carpool.total_capacity - 1:
        return failure_response("Carpool is full!", 400)

    current_riders = [carpool.driver_id] + [p.id for p in carpool.passengers]
    pending_riders = [p.id for p in carpool.pending_passengers]

    if user_id in current_riders:
        return failure_response("User is already a current rider!", 400)

    if user_id in pending_riders:
        return failure_response("User is already a pending rider!", 400)

    if not check_passenger_availability(user_id, carpool.start_time):
        return failure_response("User has a conflicting carpool at this time!", 400)

    carpool.pending_passengers.append(user)
    db.session.commit()
    return success_response(carpool.serialize())

@app.route("/api/carpools/<int:carpool_id>/leave/", methods=["POST"])
def leave_carpool(carpool_id):
    """
    Endpoint for leaving a carpool by id
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400) 

    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")

    if user not in carpool.passengers:
        return failure_response("User is not in this carpool!", 400)

    carpool.passengers.remove(user)
    db.session.commit()
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/cancel_pending/", methods=["POST"])
def cancel_pending_request(carpool_id):
    """
    Endpoint for canceling a pending ride request
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400)

    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")

    if user not in carpool.pending_passengers:
        return failure_response("User is not in pending riders list!", 400)

    carpool.pending_passengers.remove(user)
    db.session.commit()
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/accept_rider/", methods=["POST"])
def accept_rider(carpool_id):
    """
    Endpoint for accepting a pending rider into the carpool
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400)

    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")

    if user not in carpool.pending_passengers:
        return failure_response("User is not in pending riders list!", 400)

    if len(carpool.passengers) >= carpool.total_capacity - 1:
        return failure_response("Carpool is full!", 400)

    carpool.pending_passengers.remove(user)
    carpool.passengers.append(user)

    db.session.commit()
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/decline_rider/", methods=["POST"])
def decline_rider(carpool_id):
    """
    Endpoint for declining a pending rider's request to join the carpool
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400)

    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return failure_response("User not found!")

    if user not in carpool.pending_passengers:
        return failure_response("User is not in pending riders list!", 400)

    carpool.pending_passengers.remove(user)

    db.session.commit()
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/", methods=["DELETE"])
def delete_carpool(carpool_id):
    """
    Endpoint for deleting a carpool. ONLY DRIVER CAN DELETE
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_id = body.get("user_id")
    if user_id is None:
        return failure_response("Missing user_id field", 400)
    if user_id != carpool.driver_id:
        return failure_response("Only the driver can delete this carpool!", 403)

    carpool.passengers.clear()
    carpool.pending_passengers.clear()

    db.session.delete(carpool)
    db.session.commit()

    return success_response({
        "message": "Carpool successfully deleted"
    })


@app.route("/api/upload/", methods=["POST"])
def upload():
    """
    Endpoint for uploading an image to the server
    temporary, used for testing
    """
    body = json.loads(request.data)
    image_data = body.get("image_data")
    if image_data is None:
        return failure_response("No Base64 URL provided")

    asset = Asset(image_data=image_data)
    db.session.add(asset)
    db.session.commit()
    return success_response(asset.serialize(), 201)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
