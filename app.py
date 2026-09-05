import os
import sqlite3
from decimal import Decimal
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shopease_demo_secret_2026")

# FREE DEPLOYMENT MODE: SQLite is used so the app can run without a paid MySQL server.
# For local MySQL development, the original MySQL project can still be used separately.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join(BASE_DIR, "shopease.db"))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total_amount REAL NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Placed'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    admin = cur.execute("SELECT id, password FROM admins WHERE email=?", ("admin@shopease.com",)).fetchone()
    if admin is None:
        cur.execute(
            "INSERT INTO admins (name,email,password) VALUES (?,?,?)",
            ("ShopEase Admin", "admin@shopease.com", generate_password_hash("admin123"))
        )

    count = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        products = [
            ("T-Shirt", 499, "Fashion", "Comfortable cotton T-Shirt"),
            ("Headphones", 1299, "Electronics", "Wireless Bluetooth Headphones"),
            ("Smart Watch", 1999, "Electronics", "Fitness Smart Watch"),
            ("Backpack", 899, "Accessories", "College laptop backpack"),
            ("Notebook", 149, "Books", "Premium ruled notebook"),
            ("Table Lamp", 699, "Home", "LED study table lamp"),
        ]
        cur.executemany(
            "INSERT INTO products (name,price,category,description) VALUES (?,?,?,?)",
            products
        )

    conn.commit()
    conn.close()


def cart_items():
    cart = session.get("cart", {})
    if not cart:
        return [], Decimal("0.00")

    conn = get_db_connection()
    items = []
    total = Decimal("0.00")
    for product_id, quantity in cart.items():
        product = conn.execute("SELECT * FROM products WHERE id=?", (int(product_id),)).fetchone()
        if not product or int(quantity) <= 0:
            continue
        qty = int(quantity)
        subtotal = Decimal(str(product["price"])) * qty
        total += subtotal
        items.append({"product": product, "quantity": qty, "subtotal": subtotal})
    conn.close()
    return items, total


@app.context_processor
def inject_cart_count():
    return {"cart_count": sum(session.get("cart", {}).values())}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if len(password) < 4:
            flash("Password must contain at least 4 characters.", "error")
            return redirect(url_for("register"))
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (name,email,password) VALUES (?,?,?)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered. Please login.", "error")
        finally:
            conn.close()
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        valid = bool(user and check_password_hash(user["password"], password))
        if valid:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("products"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/products")
def products():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    conn = get_db_connection()
    query = "SELECT * FROM products WHERE 1=1"
    values = []
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        values.extend([f"%{search}%", f"%{search}%"])
    if category:
        query += " AND category=?"
        values.append(category)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, values).fetchall()
    conn.close()
    return render_template("products.html", products=rows, search=search, category=category)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))
    return render_template("product_detail.html", product=product)


@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    conn = get_db_connection()
    exists = conn.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not exists:
        flash("Product not found.", "error")
        return redirect(url_for("products"))
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = int(cart.get(key, 0)) + 1
    session["cart"] = cart
    flash("Product added to cart.", "success")
    return redirect(url_for("cart_page"))


@app.route("/cart")
def cart_page():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)


@app.route("/increase_quantity/<int:product_id>")
def increase_quantity(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    if key in cart:
        cart[key] = int(cart[key]) + 1
        session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/decrease_quantity/<int:product_id>")
def decrease_quantity(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    if key in cart:
        cart[key] = int(cart[key]) - 1
        if cart[key] <= 0:
            cart.pop(key)
        session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/checkout")
def checkout():
    if not session.get("cart"):
        flash("Your cart is empty.", "error")
        return redirect(url_for("products"))
    items, total = cart_items()
    return render_template("checkout.html", items=items, total=total)


@app.route("/place_order", methods=["POST"])
def place_order():
    if not session.get("cart"):
        flash("Your cart is empty.", "error")
        return redirect(url_for("products"))
    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    phone = request.form["phone"].strip()
    address = request.form["address"].strip()
    payment = request.form["payment"]
    items, total = cart_items()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("products"))
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """INSERT INTO orders
            (customer_name,email,phone,address,payment_method,total_amount,status)
            VALUES (?,?,?,?,?,?,'Placed')""",
            (name, email, phone, address, payment, float(total))
        )
        order_id = cur.lastrowid
        for item in items:
            p = item["product"]
            conn.execute(
                "INSERT INTO order_items (order_id,product_name,quantity,price) VALUES (?,?,?,?)",
                (order_id, p["name"], item["quantity"], float(p["price"]))
            )
        conn.commit()
        session["cart"] = {}
        return render_template("order_success.html", order_id=order_id, name=name, email=email,
                               phone=phone, address=address, payment=payment, total=total)
    except sqlite3.Error:
        conn.rollback()
        flash("Could not place order. Please try again.", "error")
        return redirect(url_for("checkout"))
    finally:
        conn.close()


@app.route("/my_orders")
def my_orders():
    if "user_email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE email=? ORDER BY order_date DESC",
        (session["user_email"],)
    ).fetchall()
    conn.close()
    return render_template("my_orders.html", orders=orders)


# ---------------- ADMIN ----------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password"], password):
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin email or password.", "error")
    return render_template("admin_login.html")


@app.route("/admin")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_sales = conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders").fetchone()[0]
    conn.close()
    return render_template("admin_dashboard.html", total_users=total_users,
                           total_products=total_products, total_orders=total_orders,
                           total_sales=total_sales)


@app.route("/admin/products")
def admin_products():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_products.html", products=products)


@app.route("/admin/add_product", methods=["GET", "POST"])
def add_product():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        conn = get_db_connection()
        conn.execute("INSERT INTO products (name,price,category,description) VALUES (?,?,?,?)",
                     (request.form["name"].strip(), request.form["price"], request.form["category"],
                      request.form["description"].strip()))
        conn.commit(); conn.close()
        flash("Product added successfully.", "success")
        return redirect(url_for("admin_products"))
    return render_template("add_product.html")


@app.route("/admin/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        conn.close(); flash("Product not found.", "error"); return redirect(url_for("admin_products"))
    if request.method == "POST":
        conn.execute("""UPDATE products SET name=?,price=?,category=?,description=? WHERE id=?""",
                     (request.form["name"].strip(), request.form["price"], request.form["category"],
                      request.form["description"].strip(), product_id))
        conn.commit(); conn.close()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_products"))
    conn.close()
    return render_template("edit_product.html", product=product)


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit(); conn.close()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
def admin_orders():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    orders = conn.execute("SELECT * FROM orders ORDER BY order_date DESC").fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/update_order/<int:order_id>", methods=["POST"])
def update_order(order_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    status = request.form["status"]
    allowed = {"Placed", "Confirmed", "Shipped", "Delivered", "Cancelled"}
    if status not in allowed:
        flash("Invalid order status.", "error")
        return redirect(url_for("admin_orders"))
    conn = get_db_connection()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit(); conn.close()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    return redirect(url_for("admin_login"))


# Initialize when imported by Gunicorn/Render as well as when run locally.
try:
    init_db()
except Exception as e:
    print("DATABASE INITIALIZATION ERROR:", e)

if __name__ == "__main__":
    print("ShopEase database check complete.")
    print("Open: http://127.0.0.1:5000")
    print("Admin: http://127.0.0.1:5000/admin_login")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
