from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class UserProfile(models.Model):
    """Extended profile for each user to store their role and optional seller info."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="userprofile")
    # True means this user is a Seller; False means they are a Buyer
    is_seller = models.BooleanField(default=False)
    farm_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        role = "Seller" if self.is_seller else "Buyer"
        return f"{self.user.username} ({role})"

class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.email})"


class Product(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    image = models.CharField(max_length=255, blank=True, null=True)  # Placeholder for image path
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def image_url(self) -> str:
        """
        Return a usable URL for the product image.

        Supports both:
        - ImageField/FileField-like objects (have `.url`)
        - Plain string paths stored in `image` (CharField), assumed to live under MEDIA_URL/products/
        """
        if not self.image:
            return ""

        # If this ever becomes an ImageField/FileField, Django will provide `.url`
        if hasattr(self.image, "url"):
            try:
                return self.image.url  # type: ignore[attr-defined]
            except Exception:
                # Fall back to string handling below
                pass

        img = str(self.image).strip()
        if not img:
            return ""

        # Already an absolute URL
        if img.startswith("http://") or img.startswith("https://"):
            return img

        # Already an absolute path
        if img.startswith("/"):
            return img

        # Normalize: if DB stored just filename, assume it lives in media/products/
        if not img.startswith("products/"):
            img = f"products/{img}"

        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if not media_url.endswith("/"):
            media_url += "/"
        return f"{media_url}{img}"

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    def get_total(self):
        return sum(item.get_subtotal() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product')

    def get_subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Order(models.Model):
    """Order created at checkout; linked to M-Pesa STK Push result."""

    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=20)  # e.g. 254712345678
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # M-Pesa fields
    checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    mpesa_response = models.TextField(blank=True)  # raw callback JSON for debugging
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} - {self.status}"


class PasswordResetToken(models.Model):
    """Store password reset verification codes with expiration."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    code = models.CharField(max_length=6)  # 6-digit verification code
    is_verified = models.BooleanField(default=False)  # Has the code been verified?
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ('-created_at',)
    
    def __str__(self):
        return f"Reset token for {self.user.username} - {'verified' if self.is_verified else 'pending'}"
    
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at





class PaymentAnalytics(models.Model):
    """Track payment metrics for analytics dashboard."""
    
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_analytics')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    payment_method = models.CharField(max_length=50, default='mpesa')
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=20)

    class Meta:
        ordering = ('-initiated_at',)

    def __str__(self):
        return f"Payment {self.order.id} - {self.status}"
