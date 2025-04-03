from flask import Flask, request, render_template, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt
import os
import pytesseract
from PIL import Image
import google.generativeai as genai

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "c9a2bf37801fc6ea8680cda495421680f45e2787bce7b3a55102910149783518"

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

# MongoDB setup (Replace localhost with your MongoDB URL if deploying online)
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)

# Select database and collections
db = client["22bce366"]  # Change to your database name
users_collection = db["users"]

# Expense categories
categories = ["fees", "food", "transport", "stationary", "other"]

# Extract expenses from Gemini response
def extract_expenses(response_text):
    expenses = {category: 0 for category in categories}
    lines = response_text.splitlines()
    for line in lines:
        for category in categories:
            if category.lower() in line.lower():
                try:
                    amount = int(line.split()[-1])
                    expenses[category] += amount
                except ValueError:
                    pass
    return expenses

def get_gemini_response(text):
    input_prompt = f"Categorize expenses into: Fees, Food, Transport, Stationary, Other. Text: {text}"
    response = model.generate_content([input_prompt])
    return response.text

@app.route("/", methods=["GET", "POST"])
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        users_collection.insert_one({"_id": username, "password": hashed_password, "expenses": []})
        flash("Registration successful! Please login.", "success")
    except:
        flash("Username already exists!", "danger")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    user = users_collection.find_one({"_id": username})
    if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
        session["user"] = username
        return redirect(url_for("dashboard"))
    flash("Invalid credentials!", "danger")
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("home"))
    user_data = users_collection.find_one({"_id": session["user"]})
    return render_template("dashboard.html", expenses=user_data.get("expenses", []))

@app.route("/upload", methods=["POST"])
def upload_bill():
    if "file" not in request.files:
        flash("No file selected!", "danger")
        return redirect(url_for("dashboard"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected!", "danger")
        return redirect(url_for("dashboard"))

    image = Image.open(file)
    extracted_text = pytesseract.image_to_string(image)
    response_text = get_gemini_response(extracted_text)
    categorized_expenses = extract_expenses(response_text)

    users_collection.update_one(
        {"_id": session["user"]},
        {"$push": {"expenses": categorized_expenses}},
        upsert=True
    )

    flash("Bill uploaded and categorized successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
