from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)
app.secret_key = 'techshop_secret_key_2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Auto logout after 30 minutes

# Database configuration - UPDATE THESE!
db_config = {
    'host': 'localhost',
    'user': 'root',  # Change to your MySQL username
    'password': 'Bernice@123',  # Change to your MySQL password
    'database': 'ecommerce'  # Change to your database name
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return None

def ensure_user_has_cart(user_id):
    """Ensure user has at least one cart entry"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if user has any cart entries
        cursor.execute("SELECT cart_id FROM cart WHERE user_id = %s LIMIT 1", (user_id,))
        existing_cart = cursor.fetchone()
        
        if not existing_cart:
            # User has no cart entries, create one dummy entry
            cursor.execute("SELECT COALESCE(MAX(cart_id), 0) + 1 as next_id FROM cart")
            next_id_result = cursor.fetchone()
            new_cart_id = next_id_result['next_id'] if next_id_result else 1
            
            cursor.execute("""
                INSERT INTO cart (cart_id, user_id, date_added) 
                VALUES (%s, %s, %s)
            """, (new_cart_id, user_id, datetime.now().date()))
            conn.commit()
            print(f"Created cart {new_cart_id} for user {user_id}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error ensuring user cart: {e}")
        return False

def check_session_timeout():
    """Check if session has expired"""
    if 'user_id' in session:
        # Check if session has last activity time
        if 'last_activity' in session:
            last_activity_str = session['last_activity']
            try:
                # Parse the stored datetime string
                last_activity = datetime.fromisoformat(last_activity_str)
                # Make both datetimes naive for comparison
                current_time = datetime.now()
                if current_time > last_activity + app.config['PERMANENT_SESSION_LIFETIME']:
                    session.clear()
                    flash('Your session has expired. Please login again.', 'info')
                    return False
            except (ValueError, TypeError):
                # If there's an error parsing, just update the activity time
                pass
        
        # Update last activity time as ISO string
        session['last_activity'] = datetime.now().isoformat()
        session.permanent = True
    return True

@app.before_request
def before_request():
    """Run before each request to check session timeout"""
    if request.endpoint and not request.endpoint.startswith('static'):
        check_session_timeout()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cart_count = 0
    featured_products = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get user's cart count (total quantity of items)
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0) as total_quantity 
                FROM cart 
                WHERE user_id = %s AND product_id IS NOT NULL
            """, (session['user_id'],))
            cart_result = cursor.fetchone()
            cart_count = cart_result['total_quantity'] if cart_result else 0
            
            # Get featured products
            cursor.execute("""
                SELECT p.*, c.ctype, c.cname 
                FROM products p 
                JOIN category c ON p.cid = c.cid 
                LIMIT 6
            """)
            featured_products = cursor.fetchall()
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
    
    return render_template('index.html', 
                         cart_count=cart_count, 
                         featured_products=featured_products,
                         user_name=session.get('name'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('login.html')
            
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM users WHERE email_id = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['user_id']
                session['name'] = user['name']
                session['email'] = user['email_id']
                session['last_activity'] = datetime.now().isoformat()
                session.permanent = True
                
                # Ensure user has a cart entry
                ensure_user_has_cart(user['user_id'])
                
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
            flash('Login error occurred', 'error')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        pincode = request.form.get('pincode', '').strip()
        
        if not all([name, email, phone, password, address, city, pincode]):
            flash('Please fill in all fields', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed', 'error')
            return render_template('register.html')
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT user_id FROM users WHERE email_id = %s", (email,))
            if cursor.fetchone():
                flash('Email already exists', 'error')
            else:
                while True:
                    n = random.randint(10, 999)
                    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (n,))
                    if not cursor.fetchone():
                        break
                
                # Get the new user ID
                user_id = n

                address1 = address.split()
                cursor.execute("""
                    INSERT INTO users (user_id,name, email_id, ph_no, password, line_1,street, city, pincode) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id,name, email, phone, password, address1[0], address1[1], city, pincode))
                
                
                # Create a cart entry for the new user
                cursor.execute("SELECT COALESCE(MAX(cart_id), 0) + 1 as next_id FROM cart")
                next_id_result = cursor.fetchone()
                new_cart_id = next_id_result[0] if next_id_result else 1
                
                cursor.execute("""
                    INSERT INTO cart (cart_id, user_id, date_added,quantity,product_id,details) 
                    VALUES (%s, %s, %s,0,101,"Hard matte phone case")
                """, (new_cart_id, user_id, datetime.now().date()))
                
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
                
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/products')
def products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products_list = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT p.*, c.ctype, c.cname 
                FROM products p 
                JOIN category c ON p.cid = c.cid
            """)
            products_list = cursor.fetchall()
            cursor.close()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()
    
    return render_template('products.html', products=products_list)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # First, ensure user has a cart
        ensure_user_has_cart(session['user_id'])
        
        # Check if product already exists in user's cart
        cursor.execute("""
            SELECT * FROM cart 
            WHERE user_id = %s AND product_id = %s
        """, (session['user_id'], product_id))
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity if item exists
            cursor.execute("""
                UPDATE cart SET quantity = quantity + %s 
                WHERE user_id = %s AND product_id = %s
            """, (quantity, session['user_id'], product_id))
        else:
            # Get product details for the cart
            cursor.execute("SELECT details, price FROM products WHERE pid = %s", (product_id,))
            product = cursor.fetchone()
            
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            product_details = product['details']
            
            # Get next cart_id for the new cart item
            cursor.execute("SELECT COALESCE(MAX(cart_id), 0) + 1 as next_id FROM cart")
            next_id_result = cursor.fetchone()
            new_cart_id = next_id_result['next_id'] if next_id_result else 1
            
            # Insert new cart item
            cursor.execute("""
                INSERT INTO cart (cart_id, user_id, product_id, details, date_added, quantity) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (new_cart_id, session['user_id'], product_id, product_details, datetime.now().date(), quantity))
        
        conn.commit()
        # Return success but no message to avoid alert
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Add to cart error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cart_items = []
    total = 0
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get all cart items for this user (only those with products)
            cursor.execute("""
                SELECT c.*, p.details as product_name, p.price, p.brand, p.pid
                FROM cart c 
                JOIN products p ON c.product_id = p.pid
                WHERE c.user_id = %s AND c.product_id IS NOT NULL
            """, (session['user_id'],))
            cart_items = cursor.fetchall()
            
            total = sum(item['price'] * item['quantity'] for item in cart_items)
            cursor.close()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart WHERE cart_id = %s AND user_id = %s", (cart_id, session['user_id']))
            conn.commit()
            cursor.close()
            flash('Item removed from cart', 'success')
        except Exception as e:
            flash('Error removing item', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('cart'))

@app.route('/remove_from_cart_direct', methods=['POST'])
def remove_from_cart_direct():
    """Remove item from cart without confirmation"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    cart_id = request.form.get('cart_id')
    
    if not cart_id:
        return jsonify({'success': False, 'message': 'Cart ID required'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE cart_id = %s AND user_id = %s", (cart_id, session['user_id']))
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    cart_id = request.form.get('cart_id')
    quantity = int(request.form.get('quantity', 1))
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    try:
        cursor = conn.cursor()
        
        if quantity <= 0:
            # Remove item if quantity is 0 or less
            cursor.execute("DELETE FROM cart WHERE cart_id = %s AND user_id = %s", (cart_id, session['user_id']))
        else:
            # Update quantity
            cursor.execute("""
                UPDATE cart SET quantity = %s
                WHERE cart_id = %s AND user_id = %s
            """, (quantity, cart_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed', 'error')
        return redirect(url_for('cart'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get cart items and calculate total
        cursor.execute("""
            SELECT c.*, p.price 
            FROM cart c 
            JOIN products p ON c.product_id = p.pid
            WHERE c.user_id = %s AND c.product_id IS NOT NULL
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        
        if not cart_items:
            flash('Your cart is empty', 'error')
            return redirect(url_for('cart'))
        
        # Calculate total amount
        total_amt = sum(item['price'] * item['quantity'] for item in cart_items)
        
        # Create order
        cursor.execute("SELECT COALESCE(MAX(order_id), 1000) + 1 as next_order_id FROM orders")
        next_order_result = cursor.fetchone()
        new_order_id = next_order_result['next_order_id'] if next_order_result else 1001
        
        cursor.execute("""
            INSERT INTO orders (order_id, user_id, total_amt) 
            VALUES (%s, %s, %s)
        """, (new_order_id, session['user_id'], total_amt))
        
        # Create shipping details
        cursor.execute("SELECT COALESCE(MAX(shipping_id), 500) + 1 as next_shipping_id FROM shipping_details")
        next_shipping_result = cursor.fetchone()
        new_shipping_id = next_shipping_result['next_shipping_id'] if next_shipping_result else 501
        
        cursor.execute("""
            INSERT INTO shipping_details (shipping_id, estimated_delivery, status, order_id) 
            VALUES (%s, %s, %s, %s)
        """, (new_shipping_id, 5, 'processing', new_order_id))
        
        # Clear the cart (only remove product items, keep the cart structure)
        cursor.execute("DELETE FROM cart WHERE user_id = %s AND product_id IS NOT NULL", (session['user_id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'Order placed successfully! Order ID: #{new_order_id}', 'success')
        return redirect(url_for('orders'))
        
    except Exception as e:
        print(f"Checkout error: {e}")
        flash('Error processing order. Please try again.', 'error')
        return redirect(url_for('cart'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    orders_list = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.*, s.status, s.estimated_delivery 
                FROM orders o 
                LEFT JOIN shipping_details s ON o.order_id = s.order_id 
                WHERE o.user_id = %s 
                ORDER BY o.order_id DESC
            """, (session['user_id'],))
            orders_list = cursor.fetchall()
            cursor.close()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()
    
    return render_template('orders.html', orders=orders_list)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_data = None
    cart_count = 0
    orders_list = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get user details
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user_data = cursor.fetchone()
            
            # Get cart count (total quantity)
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0) as total_quantity 
                FROM cart 
                WHERE user_id = %s AND product_id IS NOT NULL
            """, (session['user_id'],))
            cart_result = cursor.fetchone()
            cart_count = cart_result['total_quantity'] if cart_result else 0
            
            # Get recent orders
            cursor.execute("""
                SELECT o.*, s.status 
                FROM orders o 
                LEFT JOIN shipping_details s ON o.order_id = s.order_id 
                WHERE o.user_id = %s 
                ORDER BY o.order_id DESC 
                LIMIT 3
            """, (session['user_id'],))
            orders_list = cursor.fetchall()
            
            cursor.close()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()
    
    return render_template('profile.html', user=user_data, cart_count=cart_count, orders=orders_list)

@app.route('/session_status')
def session_status():
    """Check session status"""
    if 'user_id' in session:
        last_activity = session.get('last_activity', 'Unknown')
        return jsonify({
            'logged_in': True,
            'user_id': session['user_id'],
            'user_name': session['name'],
            'last_activity': str(last_activity)
        })
    else:
        return jsonify({'logged_in': False})

@app.route('/test')
def test():
    return "✅ Server is working!"

if __name__ == '__main__':
    print("🚀 Starting TechShop...")
    print("📍 http://localhost:5000")
    print("⏰ Auto-logout after 30 minutes of inactivity")
    app.run(debug=True, host='0.0.0.0', port=5000)