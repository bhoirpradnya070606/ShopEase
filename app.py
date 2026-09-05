from flask import Flask, render_template, redirect, url_for, request, session, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "shopease_secret_key_2026"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "pradnya070606",
    "database": "shopease"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    """Create/upgrade the database tables needed by ShopEase."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            category VARCHAR(50) NOT NULL,
            description TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            address TEXT NOT NULL,
            payment_method VARCHAR(50) NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(30) DEFAULT 'Placed'
        )
    """)

    # Upgrade an older orders table if it was created before status existed.
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='orders' AND COLUMN_NAME='status'
    """, (DB_CONFIG["database"],))
    if cur.fetchone()[0] == 0:
        cur.execute("ALTER TABLE orders ADD COLUMN status VARCHAR(30) DEFAULT 'Placed'")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    # Seed admin only if it doesn't exist.
    cur.execute("SELECT id FROM admins WHERE email=%s", ("admin@shopease.com",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO admins (name,email,password) VALUES (%s,%s,%s)",
            ("ShopEase Admin", "admin@shopease.com",
             generate_password_hash("admin123"))
        )
    else:
        # Existing legacy plaintext admin password is upgraded automatically.
        cur.execute("SELECT password FROM admins WHERE email=%s", ("admin@shopease.com",))
        stored = cur.fetchone()[0]
        if stored == "admin123":
            cur.execute(
                "UPDATE admins SET password=%s WHERE email=%s",
                (generate_password_hash("admin123"), "admin@shopease.com")
            )

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        products = [
            ("T-Shirt", 499, "Fashion", "Comfortable cotton T-Shirt"),
            ("Headphones", 1299, "Electronics", "Wireless Bluetooth Headphones"),
            ("Smart Watch", 1999, "Electronics", "Fitness Smart Watch"),
            ("Backpack", 899, "Accessories", "College laptop backpack"),
            ("Notebook", 149, "Books", "Premium ruled notebook"),
            ("Table Lamp", 699, "Home", "LED study table lamp")
        ]
        cur.executemany(
            "INSERT INTO products (name,price,category,description) VALUES (%s,%s,%s,%s)",
            products
        )

    conn.commit()
    cur.close()
    conn.close()

def cart_items():
    ids = session.get("cart", {})
    if not ids:
        return [], Decimal("0.00")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    product_ids = [int(x) for x in ids.keys()]
    placeholders = ",".join(["%s"] * len(product_ids))
    cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", product_ids)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    items = []
    total = Decimal("0.00")
    for p in rows:
        qty = int(ids.get(str(p["id"]), 0))
        if qty <= 0:
            continue
        subtotal = Decimal(str(p["price"])) * qty
        total += subtotal
        items.append({"product": p, "quantity": qty, "subtotal": subtotal})
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
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except Error as e:
            conn.rollback()
            if getattr(e, "errno", None) == 1062:
                flash("Email already registered. Please login.", "error")
            else:
                flash("Registration failed. Check your database connection.", "error")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        valid = user and check_password_hash(user["password"], password)
        # Support the older plaintext records created during development.
        if user and not valid and user["password"] == password:
            valid = True
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password=%s WHERE id=%s",
                (generate_password_hash(password), user["id"])
            )
            conn.commit()
            cur.close()
            conn.close()

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
    cur = conn.cursor(dictionary=True)
    query = "SELECT * FROM products WHERE 1=1"
    values = []

    if search:
        query += " AND (name LIKE %s OR description LIKE %s)"
        values += [f"%{search}%", f"%{search}%"]
    if category:
        query += " AND category=%s"
        values.append(category)

    query += " ORDER BY id DESC"
    cur.execute(query, values)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        "products.html", products=rows, search=search, category=category
    )

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))
    return render_template("product_detail.html", product=product)

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM products WHERE id=%s", (product_id,))
    exists = cur.fetchone()
    cur.close()
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
        cart[key] += 1
        session["cart"] = cart
    return redirect(url_for("cart_page"))

@app.route("/decrease_quantity/<int:product_id>")
def decrease_quantity(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    if key in cart:
        cart[key] -= 1
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
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO orders
            (customer_name,email,phone,address,payment_method,total_amount,status)
            VALUES (%s,%s,%s,%s,%s,%s,'Placed')
        """, (name, email, phone, address, payment, total))
        order_id = cur.lastrowid

        for item in items:
            p = item["product"]
            cur.execute("""
                INSERT INTO order_items
                (order_id,product_name,quantity,price)
                VALUES (%s,%s,%s,%s)
            """, (order_id, p["name"], item["quantity"], p["price"]))

        conn.commit()
        session["cart"] = {}
        return render_template(
            "order_success.html",
            order_id=order_id,
            name=name, email=email, phone=phone,
            address=address, payment=payment, total=total
        )
    except Error:
        conn.rollback()
        flash("Could not place order. Please try again.", "error")
        return redirect(url_for("checkout"))
    finally:
        cur.close()
        conn.close()

@app.route("/my_orders")
def my_orders():
    if "user_email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM orders
        WHERE email=%s
        ORDER BY order_date DESC
    """, (session["user_email"],))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("my_orders.html", orders=orders)

# ---------------- ADMIN ----------------

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin = cur.fetchone()
        cur.close()
        conn.close()

        valid = admin and check_password_hash(admin["password"], password)
        if admin and not valid and admin["password"] == password:
            valid = True
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE admins SET password=%s WHERE id=%s",
                (generate_password_hash(password), admin["id"])
            )
            conn.commit()
            cur.close()
            conn.close()

        if valid:
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
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM products")
    total_products = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cur.fetchone()["total"]
    cur.execute("SELECT COALESCE(SUM(total_amount),0) AS total FROM orders")
    total_sales = cur.fetchone()["total"]
    cur.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_sales=total_sales
    )

@app.route("/admin/products")
def admin_products():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products ORDER BY id DESC")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_products.html", products=products)

@app.route("/admin/add_product", methods=["GET", "POST"])
def add_product():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        name = request.form["name"].strip()
        price = request.form["price"]
        category = request.form["category"]
        description = request.form["description"].strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO products (name,price,category,description)
            VALUES (%s,%s,%s,%s)
        """, (name, price, category, description))
        conn.commit()
        cur.close()
        conn.close()
        flash("Product added successfully.", "success")
        return redirect(url_for("admin_products"))

    return render_template("add_product.html")

@app.route("/admin/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("admin_products"))

    if request.method == "POST":
        cur.execute("""
            UPDATE products
            SET name=%s, price=%s, category=%s, description=%s
            WHERE id=%s
        """, (
            request.form["name"].strip(),
            request.form["price"],
            request.form["category"],
            request.form["description"].strip(),
            product_id
        ))
        conn.commit()
        cur.close()
        conn.close()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_products"))

    cur.close()
    conn.close()
    return render_template("edit_product.html", product=product)

@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/orders")
def admin_orders():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM orders ORDER BY order_date DESC")
    orders = cur.fetchall()
    cur.close()
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
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    return redirect(url_for("admin_login"))

if __name__ == "__main__":
    try:
        init_db()
        print("ShopEase database check complete.")
        print("Open: http://127.0.0.1:5000")
        print("Admin: http://127.0.0.1:5000/admin_login")
        app.run(debug=True)
    except Error as e:
        print("DATABASE ERROR:", e)
        print("Check MySQL is running and DB_CONFIG password is correct.")
