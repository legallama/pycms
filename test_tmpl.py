from flask import Flask, render_template, Blueprint
import os

# Create dummy templates
os.makedirs("temp_templates/admin", exist_ok=True)
with open("temp_templates/admin/test.html", "w") as f:
    f.write("OK")

app = Flask(__name__, template_folder="temp_templates")

# Blueprint with subfolder as template root
bp = Blueprint("test_bp", __name__, template_folder="temp_templates/admin")

@app.route("/test")
def test():
    try:
        # If we specify "admin/test.html", it will look for temp_templates/admin/admin/test.html?
        return render_template("admin/test.html")
    except Exception as e:
        return str(e)

with app.test_client() as client:
    print(client.get("/test").get_data(as_text=True))
