import json
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .email_notifications import (
    send_payment_success_email,
    send_payment_failed_email,
    send_admin_payment_notification,
)
from .forms import (
    CustomPasswordChangeForm,
    ForgotPasswordForm,
    ProductForm,
    Registerform,
    ResetPasswordForm,
    UserProfileForm,
    VerifyResetCodeForm,
)
from .models import Cart, CartItem, Contact, Order, Product, UserProfile
from .mpesa import stk_push
from .constants import (
    SUCCESS_MESSAGES,
    ERROR_MESSAGES,
    OrderStatus,
    UserRole,
    Validation,
    MPesa,
)

logger = logging.getLogger(__name__)


def seller_required(view_func):
    """
    Decorator to allow access only to authenticated users who are registered as Sellers.

    - If the user is not authenticated, they are redirected to the login page.
    - If the user is authenticated but not a Seller, they are redirected to the homepage
      with an error message.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse("login")
            return redirect(f"{login_url}?next={request.path}")

        try:
            profile: UserProfile = request.user.userprofile
        except UserProfile.DoesNotExist:
            profile = None

        if not profile or not profile.is_seller:
            messages.error(request, ERROR_MESSAGES['SELLER_REQUIRED'])
            return redirect("index")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


@staff_member_required
def product_admin_report_pdf(request):
    """Generate a simple PDF report of products for staff users.

    This uses ReportLab; if ReportLab is not installed the view returns
    an error response asking to install it (pip install reportlab).
    """
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfgen import canvas # type: ignore
    except Exception:
        return HttpResponse(
            "Report generation requires ReportLab. Install with: pip install reportlab",
            status=500,
            content_type='text/plain'
        )

    buffer = BytesIO()
    page_size = A4
    c = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, height - 50, 'Products Report')
    c.setFont('Helvetica', 10)
    c.drawString(40, height - 70, f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}')

    # Table header
    y = height - 100
    c.setFont('Helvetica-Bold', 11)
    c.drawString(40, y, 'Name')
    c.drawString(300, y, 'Price')
    c.drawString(380, y, 'Stock')
    c.drawString(450, y, 'Active')
    y -= 18
    c.setFont('Helvetica', 10)

    products = Product.objects.all().order_by('name')
    line_height = 14
    for p in products:
        if y < 60:  # start new page
            c.showPage()
            y = height - 50
        name = (p.name[:50] + '...') if len(p.name) > 53 else p.name
        c.drawString(40, y, name)
        c.drawString(300, y, f'{p.price}')
        c.drawString(380, y, f'{p.stock}')
        c.drawString(450, y, 'Yes' if p.is_active else 'No')
        y -= line_height

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="products_report.pdf"'
    return resp


def index(request):
    products = Product.objects.filter(is_active=True)
    return render(request, 'index.html', {'products': products})

@login_required
def cart(request):
    """Cart page: requires login so cart is loaded from DB (persists across refresh and re-login)."""
    return render(request, 'cart.html')

@login_required
def order(request):
    """Checkout/order page: cart from DB, payment methods (M-Pesa STK Push)."""
    return render(request, 'order.html')

def base(request):
    return render(request, 'base.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')

        if name and email and message:
            Contact.objects.create(name=name, email=email, message=message)
            messages.success(request, SUCCESS_MESSAGES['CONTACT_MESSAGE_SENT'])
            return redirect('contact')
        messages.error(request, ERROR_MESSAGES['ALL_FIELDS_REQUIRED'])
    return render(request, 'contact.html')


def register(request):
    if request.method == 'POST':
        form = Registerform(request.POST)
        if form.is_valid():
            user = form.save()

            # Set the user's role via their UserProfile
            role = form.cleaned_data.get("role", "buyer")
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.is_seller = role == "seller"
            profile.save()

            messages.success(request, SUCCESS_MESSAGES['ACCOUNT_CREATED'])
            return redirect('index')
    else:
        form = Registerform()
    return render(request, 'register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


@login_required
def profile(request):
    """User profile page with edit form and password change."""
    user = request.user
    user_profile = getattr(user, "userprofile", None)
    profile_form = None
    password_form = None
    profile_updated = False
    password_updated = False

    # Handle profile form submission
    if request.method == 'POST' and 'update_profile' in request.POST:
        profile_form = UserProfileForm(request.POST, instance=user)
        if profile_form.is_valid():
            profile_form.save()
            # Store phone number in user's first_name as a workaround (no phone field on User)
            # Alternatively, extend User with a UserProfile model if needed
            messages.success(request, SUCCESS_MESSAGES['PROFILE_UPDATED'])
            profile_updated = True
            return redirect('profile')
        password_form = CustomPasswordChangeForm(user)
    # Handle password change form submission
    elif request.method == 'POST' and 'change_password' in request.POST:
        password_form = CustomPasswordChangeForm(user, request.POST)
        if password_form.is_valid():
            password_form.save()
            messages.success(request, SUCCESS_MESSAGES['PASSWORD_CHANGED'])
            password_updated = True
            return redirect('profile')
        profile_form = UserProfileForm(instance=user)
    else:
        profile_form = UserProfileForm(instance=user)
        password_form = CustomPasswordChangeForm(user)

    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'user_profile': user_profile,
    }
    return render(request, 'profile.html', context)


def logout_user(request):
    logout(request)
    return redirect('index')

@seller_required
def product_admin_list(request):
    # Sellers can only see and manage their own products
    products = Product.objects.filter(owner=request.user)
    return render(request, 'seller/products_list.html', {'products': products})


@seller_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.save()
            messages.success(request, 'Product created successfully.')
            return redirect('product_admin_list')
    else:
        form = ProductForm()
    return render(request, 'seller/product_form.html', {'form': form, 'action': 'Add'})


@seller_required
def product_update(request, pk):
    # Only allow a seller to edit their own product
    product = get_object_or_404(Product, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully.')
            return redirect('product_admin_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'seller/product_form.html', {'form': form, 'action': 'Edit', 'product': product})


@seller_required
def product_delete(request, pk):
    # Only allow a seller to delete their own product
    product = get_object_or_404(Product, pk=pk, owner=request.user)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully.')
        return redirect('product_admin_list')
    return render(request, 'seller/product_confirm_delete.html', {'product': product})


def _product_image_url(request, product):
    """Build absolute URL for product image (Product.image may be CharField path or ImageField)."""
    if not product.image:
        return None
    if hasattr(product.image, 'url'):
        return request.build_absolute_uri(product.image.url)
    # CharField storing path relative to MEDIA_ROOT
    path = (product.image if isinstance(product.image, str) else str(product.image)).lstrip('/')
    return request.build_absolute_uri(settings.MEDIA_URL + path)


@login_required
def get_cart(request):
    """Get the current user's cart as JSON. Cart is stored in DB so it persists across refresh and login."""
    user = request.user
    cart, created = Cart.objects.get_or_create(user=user)
    
    items = []
    for item in cart.items.select_related('product').all():
        items.append({
            'product_id': item.product.id,
            'name': item.product.name,
            'price': float(item.product.price),
            'quantity': item.quantity,
            'image_url': _product_image_url(request, item.product),
        })
    
    return JsonResponse({
        'items': items,
        'total': float(cart.get_total()),
    })


@login_required
def update_cart(request):
    """Add or update an item in the user's cart."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        if not product_id:
            return JsonResponse({'error': 'product_id required'}, status=400)
        if quantity < 0:
            return JsonResponse({'error': 'Invalid quantity'}, status=400)

        product = get_object_or_404(Product, id=product_id)
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        if quantity == 0:
            # Remove item
            CartItem.objects.filter(cart=cart, product=product).delete()
        else:
            # Add or update item
            cart_item, item_created = CartItem.objects.get_or_create(
                cart=cart, 
                product=product,
                defaults={'quantity': quantity}
            )
            if not item_created:
                cart_item.quantity = quantity
                cart_item.save()
        
        return JsonResponse({
            'success': True,
            'total': float(cart.get_total()),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def clear_cart(request):
    """Clear all items from the user's cart."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart.items.all().delete()
    
    return JsonResponse({'success': True})


# -----------------------------------------------------------------------------
# Checkout / M-Pesa STK Push (Daraja API – credentials in settings)
# -----------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def initiate_stk_push(request):
    """
    Create an Order, initiate Daraja STK Push, return checkout_request_id for polling.
    POST JSON: { "phone_number": "254712345678", "amount": 500 }
    Phone must be 12 digits (254 + 9 digits). Amount in KES (integer).
    """
    try:
        data = json.loads(request.body)
        phone_number = (data.get("phone_number") or "").strip().replace(" ", "")
        amount = data.get("amount")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if not phone_number or len(phone_number) != 12 or not phone_number.isdigit():
        return JsonResponse({"success": False, "error": "Phone must be 12 digits (e.g. 254712345678)"}, status=400)
    if amount is None:
        return JsonResponse({"success": False, "error": "amount required"}, status=400)
    try:
        amount = int(round(float(amount)))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid amount"}, status=400)
    if amount < 1:
        return JsonResponse({"success": False, "error": "Amount must be at least 1 KES"}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_total = float(cart.get_total())
    if amount != int(round(cart_total)):
        return JsonResponse({"success": False, "error": "Amount does not match cart total"}, status=400)

    callback_host = getattr(settings, "MPESA_CALLBACK_HOST", "").rstrip("/")
    if not callback_host:
        callback_host = request.build_absolute_uri("/").rstrip("/")
    callback_url = f"{callback_host}{reverse('mpesa_callback')}"

    order_obj = Order.objects.create(
        user=request.user,
        total_amount=amount,
        phone_number=phone_number,
        status=Order.STATUS_PENDING,
    )
    result = stk_push(
        phone_number=phone_number,
        amount=amount,
        account_reference=f"Zao{order_obj.id}",
        callback_url=callback_url,
    )
    if not result["success"]:
        order_obj.status = Order.STATUS_FAILED
        order_obj.mpesa_response = result.get("error_message", "")
        order_obj.save()
        return JsonResponse({"success": False, "error": result.get("error_message", "STK push failed")}, status=502)
    order_obj.checkout_request_id = result["checkout_request_id"]
    order_obj.save()
    return JsonResponse({
        "success": True,
        "checkout_request_id": result["checkout_request_id"],
        "order_id": order_obj.id,
    })


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    Daraja calls this URL with the STK Push result. Must be publicly reachable (e.g. via ngrok).
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"}, status=400)
    
    body_str = json.dumps(body)
    result = body.get("Body", {}).get("stkCallback", {})
    result_code = result.get("ResultCode")
    checkout_request_id = (result.get("CheckoutRequestID") or "").strip()
    
    if not checkout_request_id:
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    
    order_obj = Order.objects.filter(checkout_request_id=checkout_request_id).first()
    if not order_obj:
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    
    order_obj.mpesa_response = body_str
    
    if result_code == 0:
        callback_metadata = result.get("CallbackMetadata", {}).get("Item", [])
        receipt = ""
        for item in callback_metadata:
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = str(item.get("Value", ""))
                break
        
        order_obj.mpesa_receipt_number = receipt
        order_obj.status = Order.STATUS_PAID
        order_obj.updated_at = timezone.now()
        order_obj.save()
        
        # Send success emails
        send_payment_success_email(order_obj)
        send_admin_payment_notification(order_obj)
        
        logger.info(f"Payment successful for order {order_obj.id} with receipt {receipt}")
    else:
        order_obj.status = Order.STATUS_FAILED
        order_obj.updated_at = timezone.now()
        order_obj.save()
        
        # Send failure email
        send_payment_failed_email(order_obj)
        
        logger.warning(f"Payment failed for order {order_obj.id} with result code {result_code}")
    
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@login_required
def payment_status(request, checkout_request_id):
    """GET: return status of order for this checkout_request_id (for polling after Pay Now)."""
    order_obj = get_object_or_404(Order, checkout_request_id=checkout_request_id, user=request.user)
    return JsonResponse({
        "status": order_obj.status,
        "order_id": order_obj.id,
        "receipt_number": order_obj.mpesa_receipt_number or "",
    })


def find_product_by_name(request):
    """Find a product by name (exact or partial match) and return id/price.

    This is used as a fallback when a product tile on the page doesn't include
    a `data-product-id` attribute (static placeholders). The client may call
    this with ?name=... and receive a JSON response with product details.
    """
    name = request.GET.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'name parameter required'}, status=400)

    # Try exact case-insensitive match first, then a contains match
    product = Product.objects.filter(name__iexact=name).first()
    if not product:
        product = Product.objects.filter(name__icontains=name).first()

    if not product:
        return JsonResponse({'error': 'product not found'}, status=404)

    return JsonResponse({'id': product.id, 'name': product.name, 'price': float(product.price)})


def forgot_password(request):
    """Handle forgot password request - send verification code to email."""
    from django.core.mail import send_mail
    from django.utils import timezone
    from datetime import timedelta
    from .models import PasswordResetToken
    import random
    
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)
            
            # Generate 6-digit code
            code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Delete old tokens for this user
            PasswordResetToken.objects.filter(user=user).delete()
            
            # Create new token record
            expires_at = timezone.now() + timedelta(minutes=15)
            reset_token = PasswordResetToken.objects.create(
                user=user,
                code=code,
                expires_at=expires_at
            )
            
            # Send email with code
            try:
                send_mail(
                    subject='Password Reset Code - ZaoConnect',
                    message=f'''Hello {user.first_name or user.username},

You requested a password reset. Use this code to verify your identity:

{code}

This code will expire in 15 minutes.

If you didn't request this, please ignore this email.

Best regards,
ZaoConnect Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                messages.success(request, f'Verification code sent to {email}. Check your email.')
                return redirect('verify_reset_code', user_id=user.id)
            except Exception as e:
                messages.error(request, f'Error sending email. Please try again. {str(e)}')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'forgot_password.html', {'form': form})


def verify_reset_code(request, user_id):
    """Verify the reset code sent to user's email."""
    from .models import PasswordResetToken
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Invalid request.')
        return redirect('login')
    
    # Get the latest reset token for this user
    reset_token = PasswordResetToken.objects.filter(user=user, is_verified=False).latest('created_at')
    
    if not reset_token or reset_token.is_expired():
        messages.error(request, 'Verification code has expired. Please try again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = VerifyResetCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            
            if reset_token.code == code:
                # Mark token as verified
                reset_token.is_verified = True
                reset_token.save()
                
                messages.success(request, 'Code verified successfully. Please set your new password.')
                return redirect('reset_password', user_id=user.id, token_id=reset_token.id)
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
    else:
        form = VerifyResetCodeForm()
    
    return render(request, 'verify_reset_code.html', {'form': form, 'user': user})


def reset_password(request, user_id, token_id):
    """Handle password reset after verification."""
    from .models import PasswordResetToken
    
    try:
        user = User.objects.get(id=user_id)
        reset_token = PasswordResetToken.objects.get(id=token_id, user=user, is_verified=True)
    except (User.DoesNotExist, PasswordResetToken.DoesNotExist):
        messages.error(request, 'Invalid request.')
        return redirect('login')
    
    if reset_token.is_expired():
        messages.error(request, 'Reset token has expired. Please try again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            user.set_password(new_password)
            user.save()
            
            # Delete the used token
            reset_token.delete()
            
            messages.success(request, 'Password has been reset successfully. Please login with your new password.')
            return redirect('login')
    else:
        form = ResetPasswordForm()
    
    return render(request, 'reset_password.html', {'form': form, 'user': user})


@staff_member_required
def admin_dashboard(request):
    """
    Custom admin dashboard showing an overview of all user accounts and their carts,
    plus simple growth analytics for registrations and cart activity.
    """
    users = User.objects.all().select_related('userprofile').order_by('-date_joined')

    # High‑level metrics
    today = timezone.now().date()
    last_7 = today - timezone.timedelta(days=6)
    last_30 = today - timezone.timedelta(days=29)

    total_users = users.count()
    total_sellers = users.filter(userprofile__is_seller=True).count()
    total_buyers = total_users - total_sellers

    new_last_7 = users.filter(date_joined__date__gte=last_7).count()
    new_last_30 = users.filter(date_joined__date__gte=last_30).count()

    users_with_cart_items = (
        User.objects.filter(cart__items__isnull=False).distinct().count()
    )
    cart_users_last_7 = (
        User.objects.filter(
            cart__items__created_at__date__gte=last_7
        )
        .distinct()
        .count()
    )

    # Time‑series: registrations per day
    registration_series = (
        users.annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # Time‑series: users who added items to cart per day
    cart_series = (
        CartItem.objects.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('cart__user', distinct=True))
        .order_by('day')
    )

    # Per‑user overview rows used by the table
    user_rows = []
    for u in users:
        profile = getattr(u, 'userprofile', None)
        cart = getattr(u, 'cart', None)
        user_rows.append(
            {
                'user': u,
                'role': 'Seller' if profile and profile.is_seller else 'Buyer',
                # Phone is stored in first_name as a simple contact field (see UserProfileForm comment).
                'phone': u.first_name or '',
                'cart_items_count': cart.items.count() if cart else 0,
            }
        )

    context = {
        'metrics': {
            'total_users': total_users,
            'total_sellers': total_sellers,
            'total_buyers': total_buyers,
            'new_last_7_days': new_last_7,
            'new_last_30_days': new_last_30,
            'users_with_cart_items': users_with_cart_items,
            'cart_users_last_7_days': cart_users_last_7,
        },
        'registration_series': registration_series,
        'cart_series': cart_series,
        'user_rows': user_rows,
    }
    return render(request, 'admin/dashboard.html', context)


@staff_member_required
def admin_dashboard_report_pdf(request):
    """
    Generate a PDF snapshot of the admin dashboard metrics and user overview.
    """
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except Exception:
        return HttpResponse(
            "Report generation requires ReportLab. Install with: pip install reportlab",
            status=500,
            content_type="text/plain",
        )

    buffer = BytesIO()
    page_size = A4
    c = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    # Reuse same metrics as admin_dashboard
    users = User.objects.all().select_related('userprofile')
    today = timezone.now().date()
    last_7 = today - timezone.timedelta(days=6)
    last_30 = today - timezone.timedelta(days=29)

    total_users = users.count()
    total_sellers = users.filter(userprofile__is_seller=True).count()
    total_buyers = total_users - total_sellers
    new_last_7 = users.filter(date_joined__date__gte=last_7).count()
    new_last_30 = users.filter(date_joined__date__gte=last_30).count()
    users_with_cart_items = (
        User.objects.filter(cart__items__isnull=False).distinct().count()
    )
    cart_users_last_7 = (
        User.objects.filter(cart__items__created_at__date__gte=last_7)
        .distinct()
        .count()
    )

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 50, "Admin Dashboard Report")
    c.setFont("Helvetica", 10)
    c.drawString(
        40,
        height - 70,
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    )

    y = height - 100

    # Summary metrics
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Summary")
    y -= 18
    c.setFont("Helvetica", 10)
    lines = [
        f"Total users: {total_users} (Sellers: {total_sellers}, Buyers: {total_buyers})",
        f"New users (last 7 days): {new_last_7}",
        f"New users (last 30 days): {new_last_30}",
        f"Users with items in cart: {users_with_cart_items}",
        f"Users adding to cart in last 7 days: {cart_users_last_7}",
    ]
    for line in lines:
        c.drawString(40, y, line)
        y -= 14

    # Users table (basic)
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Users")
    y -= 18
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Username")
    c.drawString(180, y, "Email")
    c.drawString(360, y, "Role")
    c.drawString(420, y, "Joined")
    y -= 14
    c.setFont("Helvetica", 9)

    for u in users.order_by("-date_joined"):
        if y < 60:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, "Username")
            c.drawString(180, y, "Email")
            c.drawString(360, y, "Role")
            c.drawString(420, y, "Joined")
            y -= 14
            c.setFont("Helvetica", 9)

        profile = getattr(u, "userprofile", None)
        role = "Seller" if profile and profile.is_seller else "Buyer"
        c.drawString(40, y, (u.username or "")[:18])
        c.drawString(180, y, (u.email or "")[:25])
        c.drawString(360, y, role)
        c.drawString(
            420,
            y,
            u.date_joined.strftime("%Y-%m-%d"),
        )
        y -= 12

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="admin_dashboard_report.pdf"'
    return resp


@staff_member_required
def admin_user_detail(request, user_id: int):
    """
    Show detailed information for a single user, including:
    - Basic account info
    - Role (Buyer/Seller)
    - Contact number
    - Cart items and totals
    """
    user = get_object_or_404(User, pk=user_id)
    profile = getattr(user, 'userprofile', None)
    cart = getattr(user, 'cart', None)

    items = []
    if cart:
        items = cart.items.select_related('product').all()

    context = {
        'obj_user': user,
        'profile': profile,
        'phone': user.first_name or '',
        'cart': cart,
        'items': items,
    }
    return render(request, 'admin/user_detail.html', context)


@staff_member_required
def admin_reset_user_password(request, user_id: int):
    """
    Reset a user's password to a new temporary value.

    The new password is shown once on the confirmation page so it can be
    communicated securely to the account owner.
    """
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        new_password = secrets.token_urlsafe(8)
        user.set_password(new_password)
        user.save()
        messages.success(
            request,
            f"Password for {user.username} has been reset. "
            f"Temporary password: {new_password}",
        )
        return redirect('admin_user_detail', user_id=user.id)

    return render(request, 'admin/reset_user_password_confirm.html', {'obj_user': user})


@staff_member_required
def payment_analytics_dashboard(request):
    """Analytics dashboard showing payment metrics and trends."""
    from django.db.models import Q, Sum, Avg
    from datetime import timedelta
    
    # Get metrics for different time ranges
    def get_metrics(days):
        start_date = timezone.now() - timedelta(days=days)
        orders = Order.objects.filter(created_at__gte=start_date)
        
        total = orders.count()
        paid = orders.filter(status=Order.STATUS_PAID).count()
        failed = orders.filter(status=Order.STATUS_FAILED).count()
        revenue = float(orders.filter(status=Order.STATUS_PAID).aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
        avg_amount = float(orders.filter(status=Order.STATUS_PAID).aggregate(Avg('total_amount'))['total_amount__avg'] or 0)
        success_rate = round((paid / total * 100), 2) if total > 0 else 0
        
        return {
            'total': total,
            'paid': paid,
            'failed': failed,
            'revenue': revenue,
            'avg_amount': avg_amount,
            'success_rate': success_rate,
        }
    
    metrics_7days = get_metrics(7)
    metrics_30days = get_metrics(30)
    metrics_90days = get_metrics(90)
    
    # Daily breakdown for chart
    start_date = timezone.now() - timedelta(days=30)
    daily_data = (
        Order.objects.filter(created_at__gte=start_date)
        .extra(select={'date': 'DATE(created_at)'})
        .values('date')
        .annotate(
            transactions=Count('id'),
            successful=Count('id', filter=Q(status=Order.STATUS_PAID)),
            failed=Count('id', filter=Q(status=Order.STATUS_FAILED)),
            revenue=Sum('total_amount', filter=Q(status=Order.STATUS_PAID))
        )
        .order_by('date')
    )
    
    # Status breakdown pie chart
    status_breakdown = {
        'paid': Order.objects.filter(status=Order.STATUS_PAID).count(),
        'failed': Order.objects.filter(status=Order.STATUS_FAILED).count(),
        'pending': Order.objects.filter(status=Order.STATUS_PENDING).count(),
    }
    
    # Recent transactions
    recent_transactions = Order.objects.select_related('user').order_by('-created_at')[:20]
    
    context = {
        'metrics_7days': metrics_7days,
        'metrics_30days': metrics_30days,
        'metrics_90days': metrics_90days,
        'daily_data': list(daily_data),
        'status_breakdown': status_breakdown,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'admin/payment_analytics.html', context)
