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
    return success_response({"courses": [c.serialize() for c in User.query.all()]}, 200)


@app.route("/api/users/", methods=["POST"])
def create_user():
    """
    Endpoint for creating a user
    """
    body = json.loads(request.data)
    if not body.get("name") or not body.get("email"):
        return failure_response("Missing name or email field", 400)
    new_user = User(
        name=body.get("name"),
        email=body.get("email"),
        username=body.get("username"),
        password=body.get("password")
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
    if not all(key in body for key in ["departure_location", "destination", "departure_time",
                                       "meeting_point", "total_seats", "driver_id"]):
        return failure_response("Missing required fields", 400)

    driver = User.query.filter_by(id=body.get("driver_id")).first()
    if driver is None:
        return failure_response("Driver not found!", 404)

    new_carpool = Carpool(
        departure_location=body.get("departure_location"),
        destination=body.get("destination"),
        departure_time=body.get("departure_time"),
        meeting_point=body.get("meeting_point"),
        total_seats=body.get("total_seats"),
        driver_id=body.get("driver_id")
    )
    db.session.add(new_carpool)
    db.session.commit()
    return success_response(new_carpool.serialize(), 201)


@app.route("/api/carpools/", methods=["POST"])
def get_carpools():
    """
    Endpoint for getting filtered carpools
    """
    body = json.loads(request.data)
    destination = body.get("destination")
    departure_location = body.get("departure_location")
    min_time = body.get("min_time")
    max_time = body.get("max_time")

    query = Carpool.query

    if destination:
        query = query.filter(Carpool.destination.like(f"%{destination}%"))
    if departure_location:
        query = query.filter(Carpool.departure_location.like(f"%{departure_location}%"))
    if min_time:
        query = query.filter(Carpool.departure_time >= int(min_time))
    if max_time:
        query = query.filter(Carpool.departure_time <= int(max_time))

    carpools = query.all()
    return success_response({"carpools": [c.serialize() for c in carpools]})


@app.route("/api/carpools/<int:carpool_id>/join/", methods=["POST"])
def join_carpool(carpool_id):
    """
    Endpoint for joining a carpool
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

    if len(carpool.passengers) >= carpool.total_seats:
        return failure_response("Carpool is full!", 400)

    if user in carpool.passengers:
        return failure_response("User already joined this carpool!", 400)

    carpool.passengers.append(user)
    db.session.commit()
    return success_response(carpool.serialize())


@app.route("/api/carpools/<int:carpool_id>/leave/", methods=["POST"])
def leave_carpool(carpool_id):
    """
    Endpoint for leaving a carpool
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


@app.route("/api/login/")
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
