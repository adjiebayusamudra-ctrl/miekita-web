from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
from datetime import datetime
import qrcode
from io import BytesIO
import socket

app = Flask(__name__)
app.secret_key = "ganti-dengan-secret-key-anda"

DB = "database.db"


# =====================================================
# DATABASE
# =====================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()

    # Tabel menu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            harga INTEGER NOT NULL,
            kategori TEXT NOT NULL,
            deskripsi TEXT
        )
    """)

    # Tabel pesanan
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pesanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_pelanggan TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            alamat TEXT NOT NULL,
            total INTEGER NOT NULL,
            tanggal TEXT NOT NULL
        )
    """)

    # Detail pesanan
    conn.execute("""
        CREATE TABLE IF NOT EXISTS detail_pesanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pesanan_id INTEGER NOT NULL,
            menu_id INTEGER NOT NULL,
            jumlah INTEGER NOT NULL
        )
    """)

    # Menu awal
    if conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0] == 0:

        conn.executemany(
            """
            INSERT INTO menu
            (nama, harga, kategori, deskripsi)
            VALUES (?, ?, ?, ?)
            """,
            [

                (
                    "Mie Angel",
                    10000,
                    "Mie",
                    "Mie tanpa pedas, cocok untuk semua."
                ),

                (
                    "Mie Iblis",
                    11000,
                    "Mie",
                    "Mie pedas dengan rasa gurih."
                ),

                (
                    "Mie Setan",
                    11000,
                    "Mie",
                    "Mie pedas favorit dengan topping."
                ),

                (
                    "Dimsum Ayam",
                    12000,
                    "Dimsum",
                    "Dimsum ayam lembut dan gurih."
                ),

                (
                    "Udang Rambutan",
                    13000,
                    "Dimsum",
                    "Camilan udang renyah."
                ),

                (
                    "Es Teh",
                    5000,
                    "Minuman",
                    "Minuman segar untuk menemani makan."
                )

            ]
        )

    conn.commit()
    conn.close()


# =====================================================
# MENDAPATKAN IP KOMPUTER
# =====================================================

def get_local_ip():

    try:

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.connect(("8.8.8.8", 80))

        ip = s.getsockname()[0]

        s.close()

        return ip

    except:

        return "127.0.0.1"


# =====================================================
# HALAMAN BERANDA
# =====================================================

@app.route("/")
def home():

    conn = db()

    menu = conn.execute(
        "SELECT * FROM menu LIMIT 6"
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        menu=menu
    )


# =====================================================
# HALAMAN MENU
# =====================================================

@app.route("/menu")
def menu():

    conn = db()

    items = conn.execute(
        "SELECT * FROM menu ORDER BY kategori, id"
    ).fetchall()

    conn.close()

    return render_template(
        "menu.html",
        menu=items
    )


# =====================================================
# TAMBAH KE KERANJANG
# =====================================================

@app.post("/add/<int:menu_id>")
def add(menu_id):

    cart = session.get("cart", {})

    key = str(menu_id)

    cart[key] = cart.get(key, 0) + 1

    session["cart"] = cart

    return redirect(
        request.referrer or url_for("menu")
    )


# =====================================================
# KURANGI KERANJANG
# =====================================================

@app.post("/remove/<int:menu_id>")
def remove(menu_id):

    cart = session.get("cart", {})

    key = str(menu_id)

    if key in cart:

        cart[key] -= 1

        if cart[key] <= 0:

            del cart[key]

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


# =====================================================
# KERANJANG
# =====================================================

@app.route("/cart")
def cart():

    conn = db()

    items = []

    total = 0

    for mid, qty in session.get(
        "cart",
        {}
    ).items():

        item = conn.execute(
            "SELECT * FROM menu WHERE id=?",
            (mid,)
        ).fetchone()

        if item:

            subtotal = item["harga"] * qty

            total += subtotal

            items.append({

                "item": item,

                "qty": qty,

                "subtotal": subtotal

            })

    conn.close()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# =====================================================
# CHECKOUT
# =====================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    cart = session.get(
        "cart",
        {}
    )

    if not cart:

        return redirect(
            url_for("menu")
        )

    conn = db()

    items = []

    total = 0

    for mid, qty in cart.items():

        item = conn.execute(
            "SELECT * FROM menu WHERE id=?",
            (mid,)
        ).fetchone()

        if item:

            items.append(
                (item, qty)
            )

            total += (
                item["harga"] * qty
            )

    if request.method == "POST":

        nama = request.form["nama"]

        no_hp = request.form["no_hp"]

        alamat = request.form["alamat"]

        cur = conn.execute(
            """
            INSERT INTO pesanan
            (
                nama_pelanggan,
                no_hp,
                alamat,
                total,
                tanggal
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                nama,
                no_hp,
                alamat,
                total,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        order_id = cur.lastrowid

        for item, qty in items:

            conn.execute(
                """
                INSERT INTO detail_pesanan
                (
                    pesanan_id,
                    menu_id,
                    jumlah
                )
                VALUES (?, ?, ?)
                """,
                (
                    order_id,
                    item["id"],
                    qty
                )
            )

        conn.commit()

        conn.close()

        session["cart"] = {}

        return render_template(
            "success.html",
            order_id=order_id,
            total=total
        )

    conn.close()

    return render_template(
        "checkout.html",
        items=items,
        total=total
    )


# =====================================================
# QR CODE
# =====================================================

@app.route("/qr")
def qr():

    # Mengambil alamat website yang sedang dibuka
    url = request.host_url.rstrip("/") + "/menu"

    # Membuat QR Code
    img = qrcode.make(url)

    # Menyimpan QR di memory
    buffer = BytesIO()

    img.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="image/png"
    )

# =====================================================
# ADMIN
# =====================================================

@app.route("/admin")
def admin():

    conn = db()

    orders = conn.execute(
        """
        SELECT *
        FROM pesanan
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        orders=orders
    )


# =====================================================
# JALANKAN SERVER
# =====================================================

if __name__ == "__main__":

    init_db()

    ip = get_local_ip()

    print("")
    print("======================================")
    print("       WEBSITE MIEKITA")
    print("======================================")
    print("")
    print("Buka di komputer:")
    print("http://127.0.0.1:5000")
    print("")
    print("Buka di HP:")
    print(f"http://{ip}:5000")
    print("")
    print("QR Code:")
    print(f"http://{ip}:5000/qr")
    print("")
    print("======================================")

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )