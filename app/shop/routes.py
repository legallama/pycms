import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from ..extensions import db
from ..models.shop import Product, Order, DiscountCode
from ..models.user import User, UserRole
from flask_login import login_required, current_user, login_user, logout_user
from ..auth import require_roles
from ..models.site_settings import SiteSettings
from ..templating import get_main_menu_items

shop_bp = Blueprint("shop", __name__)


def _render_shop_theme(template_name: str, **context):
    """Helper to render a template within the active theme for the shop with fallback."""
    settings = SiteSettings.load()
    theme = settings.active_theme
    try:
        return render_template(f"{theme}/templates/{template_name}", 
                               main_menu_items=get_main_menu_items(),
                               active_theme=theme,
                               **context)
    except:
        return render_template(template_name, 
                               main_menu_items=get_main_menu_items(),
                               active_theme=theme,
                               **context)

# --- PUBLIC SHOP ROUTES ---

@shop_bp.get("/shop")
def index():
    products = db.session.execute(db.select(Product).where(Product.is_active == True).order_by(Product.name.asc())).scalars().all()
    return _render_shop_theme("shop/index.html", products=products)

@shop_bp.get("/shop/product/<slug>")
def product_detail(slug: str):
    product = db.session.execute(db.select(Product).where(Product.slug == slug, Product.is_active == True)).scalar_one_or_none()
    if not product:
        abort(404)
    return _render_shop_theme("shop/product.html", product=product)

# --- CART ROUTES ---

@shop_bp.post("/cart/add/<int:product_id>")
def cart_add(product_id: int):
    from ..templating import slugify_filter
    p = db.session.get(Product, product_id)
    if not p or not p.is_active: abort(404)
    
    cart = session.get("cart", {})
    
    # Capture options
    selected_options = {}
    if p.options_json and p.options_json != '[]':
        try:
            options = json.loads(p.options_json)
            for opt in options:
                field_name = f"option_{slugify_filter(opt['name'])}"
                val = request.form.get(field_name)
                if val:
                    selected_options[opt['name']] = val
        except:
            pass
            
    # Key based on ID + Options
    opt_sig = "|".join([f"{k}:{v}" for k, v in selected_options.items()])
    cart_key = f"{product_id}_{opt_sig}" if opt_sig else str(product_id)

    if cart_key in cart:
        if cart[cart_key]["quantity"] + 1 > p.inventory:
            flash(f"Sorry, you've reached the maximum available stock for {p.name}.", "warning")
            return redirect(request.referrer or url_for("shop.index"))
        cart[cart_key]["quantity"] += 1
    else:
        if 1 > p.inventory:
            flash(f"Sorry, {p.name} is currently out of stock.", "danger")
            return redirect(request.referrer or url_for("shop.index"))
        cart[cart_key] = {
            "id": product_id,
            "name": p.name,
            "price": p.price,
            "image_url": p.image_url,
            "slug": p.slug,
            "quantity": 1,
            "options": selected_options
        }
    
    session["cart"] = cart
    session.modified = True
    flash(f"Added {p.name} to cart.", "success")
    return redirect(request.referrer or url_for("shop.index"))

@shop_bp.get("/cart")
def cart_view():
    cart = session.get("cart", {})
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    return _render_shop_theme("shop/cart.html", cart=cart, total=total)

@shop_bp.post("/cart/update")
def cart_update():
    cart = session.get("cart", {})
    for p_id_str, item in cart.items():
        qty = request.form.get(f"qty_{p_id_str}")
        if qty is not None and qty.isdigit():
            item["quantity"] = int(qty)
            
    session["cart"] = {k: v for k, v in cart.items() if v["quantity"] > 0}
    session.modified = True
    flash("Cart updated.", "info")
    return redirect(url_for("shop.cart_view"))

@shop_bp.post("/cart/remove/<cart_key>")
def cart_remove(cart_key: str):
    cart = session.get("cart", {})
    if cart_key in cart:
        del cart[cart_key]
        session["cart"] = cart
        session.modified = True
        flash("Item removed.", "info")
    return redirect(url_for("shop.cart_view"))

@shop_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("shop.index"))
    
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    settings = SiteSettings.load()
    
    if request.method == "POST":
        from ..models.crm import Contact, Lead, LeadNote
        from ..models.user import User, UserRole
        
        email = request.form.get("email")
        name = request.form.get("name")
        address = request.form.get("address")
        city = request.form.get("city")
        zip_code = request.form.get("zip")
        code_str = (request.form.get("discount_code") or "").strip().upper()
        
        # 0. Check Inventory
        for k, item in cart.items():
            p = db.session.get(Product, item['id'])
            if p and p.inventory < item['quantity']:
                flash(f"Sorry, {p.name} is out of stock or does not have enough inventory.", "danger")
                return redirect(url_for("shop.cart_view"))

        # 0.1 Check Discount
        discount = None
        discount_amt = 0.0
        if code_str:
            discount = db.session.execute(db.select(DiscountCode).where(DiscountCode.code == code_str, DiscountCode.is_active == True)).scalar_one_or_none()
            if discount:
                if total >= discount.min_purchase:
                    if discount.type == "percent":
                        discount_amt = total * (discount.value / 100.0)
                    else:
                        discount_amt = min(discount.value, total)
                    discount.usage_count += 1
                else:
                    flash(f"Discount code {code_str} requires a minimum purchase of ${discount.min_purchase:.2f}.", "warning")
            else:
                flash(f"Discount code {code_str} is invalid or expired.", "warning")

        if not email or not name:
            flash("Name and Email are required.", "danger")
            return redirect(url_for("shop.checkout"))
            
        # 1. Shop Order
        order = Order(
            user_id=current_user.id if current_user.is_authenticated else None,
            customer_name=name,
            customer_email=email,
            shipping_address=address,
            shipping_city=city,
            shipping_zip=zip_code,
            status="pending",
            items_json=json.dumps(cart),
            discount_code=discount.code if discount else None,
            discount_amount=discount_amt,
            total_amount=total - discount_amt
        )
        db.session.add(order)
        db.session.flush() # Get Order ID
        
        # 1.1 Decrement Inventory
        for k, item in cart.items():
            p = db.session.get(Product, item['id'])
            if p:
                p.inventory -= item['quantity']
        
        # 2. CRM Integration
        # ... (find or create contact)
        contact = db.session.execute(db.select(Contact).where(Contact.email == email)).scalar_one_or_none()
        if not contact:
            contact = Contact(name=name, email=email, address=address, city=city, zip_code=zip_code)
            db.session.add(contact)
            db.session.flush()
            
        # Create Lead
        lead = Lead(
            contact_id=contact.id,
            stage="new",
            source="Shop",
            value=int(total)
        )
        db.session.add(lead)
        db.session.flush()
        
        # Add Note
        admin = db.session.execute(db.select(User).where(User.role == UserRole.ADMIN)).scalars().first()
        admin_id = admin.id if admin else 1
        
        note_body = f"Order #{order.id} initiated via Shop. Total: ${total:.2f}. Items: {len(cart)}"
        note_body += f"\nShipping: {address}, {city}, {zip_code}"
        for k, item in cart.items():
            opts_str = f" ({', '.join([f'{ok}: {ov}' for ok, ov in item.get('options', {}).items()])})" if item.get('options') else ""
            note_body += f"\n- {item['name']} x{item['quantity']}{opts_str}"

        note = LeadNote(
            lead_id=lead.id,
            body=note_body,
            created_by_id=admin_id
        )
        db.session.add(note)
        
        db.session.commit()
        
        # 3. Email Integration (Postmark)
        try:
            from ..utils.email import send_email
            
            # Email to Customer
            customer_subject = f"Order Confirmation #{order.id} - {settings.site_name}"
            customer_body = f"<h2>Thank you for your order, {name}!</h2>"
            customer_body += f"<p>We've received your order #{order.id} and will contact you soon for payment.</p>"
            customer_body += "<h4>Order Summary:</h4><ul>"
            for k, item in cart.items():
                opts_str = f" ({', '.join([f'{ok}: {ov}' for ok, ov in item.get('options', {}).items()])})" if item.get('options') else ""
                customer_body += f"<li>{item['name']} x{item['quantity']}{opts_str} - ${item['price'] * item['quantity']:.2f}</li>"
            customer_body += f"</ul><p><strong>Total: ${total:.2f}</strong></p>"
            
            send_email(customer_subject, email, customer_body)
            
            # Email to Admin (if configured)
            if settings.postmark_sender_email:
                admin_subject = f"New Order Recieved: #{order.id}"
                admin_body = f"<h3>New Order from {name}</h3>"
                admin_body += f"<p>Email: {email}</p><p>Total: ${total:.2f}</p>"
                admin_body += f"<p><a href='{request.host_url}admin/shop/orders'>View in Dashboard</a></p>"
                send_email(admin_subject, settings.postmark_sender_email, admin_body)
        except Exception as e:
            # Don't fail the whole checkout if email fails, just log it.
            print(f"Checkout Email Error: {str(e)}")

        # Clear cart
        session["cart"] = {}
        session.modified = True
        
        flash("Order placed successfully! We will contact you soon for payment.", "success")
        return _render_shop_theme("shop/success.html", order=order)

    return _render_shop_theme("shop/checkout.html", cart=cart, total=total)

# --- ACCOUNT ROUTES ---

@shop_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("shop.index"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        name = request.form.get("name")
        
        if db.session.execute(db.select(User).where(User.email == email)).scalar():
            flash("Email already registered.", "danger")
            return redirect(url_for("shop.register"))
            
        user = User(email=email, role=UserRole.CUSTOMER.value)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        
        # Send Welcome Email
        try:
            from ..utils.email import send_email
            settings = SiteSettings.load()
            subject = f"Welcome to {settings.site_name}!"
            body = f"<h2>Welcome, {name or email}!</h2><p>Your account has been successfully created. You can now track your orders and manage your profile.</p>"
            send_email(subject, email, body)
        except:
            pass
            
        flash("Welcome! Your account has been created.", "success")
        return redirect(url_for("shop.account"))
        
    return _render_shop_theme("shop/register.html")

@shop_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.account"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("shop.account"))
        flash("Invalid email or password.", "danger")
    return _render_shop_theme("shop/login.html")

@shop_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("shop.index"))

@shop_bp.get("/account")
@login_required
def account():
    orders = db.session.execute(db.select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())).scalars().all()
    # Check for subscriptions (products of type subscription)
    # This is a bit advanced, but let's just show order history for now.
    return _render_shop_theme("shop/account.html", orders=orders)

@shop_bp.get("/admin/shop/products")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_products():
    products = db.session.execute(db.select(Product).order_by(Product.created_at.desc())).scalars().all()
    return render_template("admin/shop/products/list.html", products=products)

@shop_bp.route("/admin/shop/products/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_products_new():
    if request.method == "POST":
        p = Product(
            name=request.form.get("name"),
            slug=request.form.get("slug"),
            description=request.form.get("description"),
            price=float(request.form.get("price") or 0.0),
            inventory=int(request.form.get("inventory") or 0),
            image_url=request.form.get("image_url"),
            is_active=bool(request.form.get("is_active")),
            product_type=request.form.get("product_type"),
            options_json=request.form.get("options_json") or "[]",
            meta_description=request.form.get("meta_description"),
            meta_keywords=request.form.get("meta_keywords")
        )
        db.session.add(p)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("shop.admin_products"))
    return render_template("admin/shop/products/edit.html", product=None)

@shop_bp.route("/admin/shop/products/<int:id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_products_edit(id: int):
    p = db.session.get(Product, id)
    if not p: abort(404)
    if request.method == "POST":
        p.name = request.form.get("name")
        p.slug = request.form.get("slug")
        p.description = request.form.get("description")
        p.price = float(request.form.get("price") or 0.0)
        p.inventory = int(request.form.get("inventory") or 0)
        p.image_url = request.form.get("image_url")
        p.is_active = bool(request.form.get("is_active"))
        p.product_type = request.form.get("product_type")
        p.options_json = request.form.get("options_json") or "[]"
        p.meta_description = request.form.get("meta_description")
        p.meta_keywords = request.form.get("meta_keywords")
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("shop.admin_products"))
    return render_template("admin/shop/products/edit.html", product=p)

@shop_bp.get("/admin/shop/orders")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_orders():
    orders = db.session.execute(db.select(Order).order_by(Order.created_at.desc())).scalars().all()
    return render_template("admin/shop/orders/list.html", orders=orders)

@shop_bp.route("/admin/shop/settings", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def admin_settings():
    settings = SiteSettings.load()
    try:
        config = json.loads(settings.config_json or "{}")
    except:
        config = {}
    
    if request.method == "POST":
        config["stripe_publishable_key"] = request.form.get("stripe_publishable_key")
        config["stripe_secret_key"] = request.form.get("stripe_secret_key")
        config["paypal_client_id"] = request.form.get("paypal_client_id")
        config["paddle_vendor_id"] = request.form.get("paddle_vendor_id")
        config["currency"] = request.form.get("currency") or "USD"
        
        settings.config_json = json.dumps(config)
        db.session.commit()
        flash("Shop settings updated.", "success")
        return redirect(url_for("shop.admin_settings"))
        
    return render_template("admin/shop/settings.html", config=config)

# --- ADMIN DISCOUNT ROUTES ---

@shop_bp.get("/admin/shop/discounts")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_discounts():
    discounts = db.session.execute(db.select(DiscountCode).order_by(DiscountCode.created_at.desc())).scalars().all()
    return render_template("admin/shop/discounts/list.html", discounts=discounts)

@shop_bp.route("/admin/shop/discounts/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_discounts_new():
    if request.method == "POST":
        d = DiscountCode(
            code=request.form.get("code").strip().upper(),
            type=request.form.get("type"),
            value=float(request.form.get("value") or 0.0),
            min_purchase=float(request.form.get("min_purchase") or 0.0),
            is_active=bool(request.form.get("is_active"))
        )
        db.session.add(d)
        db.session.commit()
        flash("Discount code created.", "success")
        return redirect(url_for("shop.admin_discounts"))
    return render_template("admin/shop/discounts/edit.html", discount=None)

@shop_bp.route("/admin/shop/discounts/<int:id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def admin_discounts_edit(id: int):
    d = db.session.get(DiscountCode, id)
    if not d: abort(404)
    if request.method == "POST":
        d.code = request.form.get("code").strip().upper()
        d.type = request.form.get("type")
        d.value = float(request.form.get("value") or 0.0)
        d.min_purchase = float(request.form.get("min_purchase") or 0.0)
        d.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Discount code updated.", "success")
        return redirect(url_for("shop.admin_discounts"))
    return render_template("admin/shop/discounts/edit.html", discount=d)

@shop_bp.route("/admin/shop/discounts/<int:id>/delete", methods=["POST"])
@login_required
@require_roles(UserRole.ADMIN)
def admin_discounts_delete(id: int):
    d = db.session.get(DiscountCode, id)
    if d:
        db.session.delete(d)
        db.session.commit()
        flash("Discount code deleted.", "success")
    return redirect(url_for("shop.admin_discounts"))
