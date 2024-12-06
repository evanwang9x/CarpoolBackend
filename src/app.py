from flask import Flask, request
import json
from db import db, User, Carpool

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


@app.route("/api/users/")
def get_users():
    """
    Endpoint for getting all users, does not include passwords
    """
    return success_response({"users": [c.safe_serialize() for c in User.query.all()]}, 200)


@app.route("/api/users/", methods=["POST"])
def create_user():
    """
    Endpoint for creating a user
    """
    body = json.loads(request.data)
    if not body.get("first_name") or not body.get("last_name") or not body.get("email"):
        return failure_response("Missing required fields: first_name, last_name, or email", 400)
    
    new_user = User(
        first_name=body.get("first_name"),
        last_name=body.get("last_name"),
        email=body.get("email"),
        phone_number=body.get("phone_number", ""),
        username=body.get("username"),
        password=body.get("password"),
        image=body.get("image")
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


@app.route("/api/carpools/", methods=["POST"])
def create_carpool():
    """
    Endpoint for creating a new carpool
    """
    body = json.loads(request.data)
    required_fields = ["start_location", "end_location", "start_time", 
                      "total_capacity", "price", "car_type", 
                      "license_plate", "driver_id"]
    
    if not all(key in body for key in required_fields):
        return failure_response("Missing required fields", 400)

    driver = User.query.filter_by(id=body.get("driver_id")).first()
    if driver is None:
        return failure_response("Driver not found!", 404)

    new_carpool = Carpool(
        start_location=body.get("start_location"),
        end_location=body.get("end_location"),
        start_time=body.get("start_time"),
        total_capacity=body.get("total_capacity"),
        price=body.get("price"),
        car_type=body.get("car_type"),
        license_plate=body.get("license_plate"),
        driver_id=body.get("driver_id")
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

@app.route("/api/carpools/<int:carpool_id>/join/", methods=["POST"])
def join_carpool(carpool_id):
    """
    Endpoint for requesting to join a carpool as a pending rider
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_email = body.get("email")
    if user_email is None:
        return failure_response("Missing email field", 400)

    user = User.query.filter_by(email=user_email).first()
    if user is None:
        return failure_response("User not found!")

    current_riders = [carpool.driver.email] + [p.email for p in carpool.passengers]
    pending_riders = [p.email for p in carpool.pending_passengers]

    if user_email in current_riders:
        return failure_response("User is already a current rider!", 400)

    if user_email in pending_riders:
        return failure_response("User is already a pending rider!", 400)

    carpool.pending_passengers.append(user)
    db.session.commit()
    return success_response(carpool.serialize())

@app.route("/api/carpools/<int:carpool_id>/leave/", methods=["POST"])
def leave_carpool(carpool_id):
    """
    Endpoint for leaving a carpool using email
    """
    carpool = Carpool.query.filter_by(id=carpool_id).first()
    if carpool is None:
        return failure_response("Carpool not found!")

    body = json.loads(request.data)
    user_email = body.get("email")
    if user_email is None:
        return failure_response("Missing email field", 400)

    user = User.query.filter_by(email=user_email).first()
    if user is None:
        return failure_response("User not found!")

    if user not in carpool.passengers:
        return failure_response("User is not in this carpool!", 400)

    carpool.passengers.remove(user)
    db.session.commit()
    return success_response(carpool.serialize())


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

    user = User.query.filter_by(email=body.get("email")).first()

    if user is None:
        return failure_response("User not found", 404)

    if user.password != body.get("password"):
        return failure_response("Invalid password", 401)

    return success_response({
        "message": "Successfully logged in",
        "user": user.serialize()
    })



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)