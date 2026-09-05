# ShopEase – Online Shopping Management System

Mini Project-I | Flask + MySQL + HTML/CSS

## Features
- Customer registration and login
- Secure password hashing
- Product search and category filter
- Product details
- Session-based shopping cart
- Quantity increase/decrease/remove
- Checkout and order placement
- My Orders
- Admin login
- Admin dashboard
- Add/Edit/Delete products
- View orders and update order status
- Order items stored in database

## Requirements
- Python 3.x
- MySQL Server + MySQL Workbench
- VS Code

## Quick Setup

1. Open the ShopEase folder in VS Code.
2. Make sure MySQL Server is running.
3. Check the MySQL password in `app.py`:
   `DB_CONFIG["password"]`
4. If your root password is different, change only that value.
5. Open terminal in the project folder.
6. Create virtual environment:
   `python -m venv venv`
7. Activate it on Windows:
   `venv\Scripts\activate`
8. Install packages:
   `python -m pip install -r requirements.txt`
9. Start the application:
   `python app.py`
10. Open:
   http://127.0.0.1:5000

The application automatically creates/upgrades the required tables and sample products.

## Admin Login
Email: admin@shopease.com
Password: admin123

Admin URL:
http://127.0.0.1:5000/admin_login

## Important
For college demonstration this project uses a local MySQL account in `app.py`.
For a real deployment, move DB credentials and Flask secret key to environment variables.

## Project Structure
ShopEase/
├── app.py
├── requirements.txt
├── README.md
├── database/
│   └── setup.sql
├── templates/
└── static/
    ├── css/
    └── js/
