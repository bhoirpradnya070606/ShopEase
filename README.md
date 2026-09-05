# ShopEase – Online Shopping Management System

Mini Project-I | Flask + SQLite + HTML/CSS/JavaScript

## Free online deployment
This version is prepared for a free Render demo. It uses SQLite so no paid MySQL service is required. Render Free web services have an ephemeral filesystem, so SQLite data can be lost after a restart/redeploy. For a college demonstration this is acceptable; for production, use a persistent database.

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

## Admin Login
Email: admin@shopease.com
Password: admin123

Admin URL: /admin_login

## Render settings
Build Command: `pip install -r requirements.txt`
Start Command: `gunicorn app:app`
Plan: Free

A `render.yaml` file is included for convenience.

## Local setup
1. Install Python 3.x.
2. Create a virtual environment: `python -m venv venv`
3. Activate it (Windows): `venv\\Scripts\\activate`
4. Install packages: `python -m pip install -r requirements.txt`
5. Run: `python app.py`
6. Open: http://127.0.0.1:5000

## Project structure
ShopEase/
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
├── database/
│   └── setup.sql
├── templates/
└── static/
    ├── css/
    └── js/
