"""
Application constants and configuration values.
Centralized place for all hardcoded strings, status codes, and configuration.
"""

# ==============================================================================
# ORDER STATUS CONSTANTS
# ==============================================================================
class OrderStatus:
    """Order status choices."""
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (FAILED, 'Failed'),
        (CANCELLED, 'Cancelled'),
    ]
    
    STATUS_TRANSITIONS = {
        PENDING: [PAID, FAILED, CANCELLED],
        PAID: [CANCELLED],
        FAILED: [PENDING],  # Can retry
        CANCELLED: [],
    }


# ==============================================================================
# USER ROLES
# ==============================================================================
class UserRole:
    """User role choices."""
    BUYER = 'buyer'
    SELLER = 'seller'
    
    CHOICES = [
        (BUYER, 'Buyer'),
        (SELLER, 'Seller'),
    ]


# ==============================================================================
# SUCCESS MESSAGES
# ==============================================================================
SUCCESS_MESSAGES = {
    'ACCOUNT_CREATED': 'Account created successfully. You can now log in.',
    'LOGIN_SUCCESSFUL': 'Logged in successfully.',
    'LOGOUT_SUCCESSFUL': 'Logged out successfully.',
    'PROFILE_UPDATED': 'Profile updated successfully.',
    'PASSWORD_CHANGED': 'Password changed successfully.',
    'PASSWORD_RESET_EMAIL_SENT': 'Password reset link has been sent to your email.',
    'PASSWORD_RESET_SUCCESSFUL': 'Your password has been reset successfully. Please log in with your new password.',
    'CONTACT_MESSAGE_SENT': 'Thanks for reaching out. We will get back to you soon.',
    'PRODUCT_CREATED': 'Product created successfully.',
    'PRODUCT_UPDATED': 'Product updated successfully.',
    'PRODUCT_DELETED': 'Product deleted successfully.',
    'CART_ITEM_ADDED': 'Item added to cart.',
    'CART_ITEM_REMOVED': 'Item removed from cart.',
    'CART_CLEARED': 'Cart cleared.',
}

# ==============================================================================
# ERROR MESSAGES
# ==============================================================================
ERROR_MESSAGES = {
    'SELLER_REQUIRED': 'You must be registered as a Seller to access this page.',
    'STAFF_REQUIRED': 'You must be a staff member to access this page.',
    'INVALID_EMAIL': 'Invalid email address.',
    'EMAIL_ALREADY_REGISTERED': 'This email is already registered.',
    'EMAIL_NOT_FOUND': 'No account found with this email address.',
    'INVALID_CREDENTIALS': 'Invalid username or password.',
    'PASSWORDS_NOT_MATCH': 'Passwords do not match.',
    'INVALID_AMOUNT': 'Invalid amount.',
    'AMOUNT_TOO_LOW': 'Amount must be at least 1 KES.',
    'AMOUNT_MISMATCH': 'Amount does not match cart total.',
    'INVALID_PHONE_FORMAT': 'Phone must be 12 digits (e.g. 254712345678).',
    'INVALID_JSON': 'Invalid JSON in request body.',
    'PRODUCT_NOT_FOUND': 'Product not found.',
    'INVALID_CODE': 'Invalid or expired verification code.',
    'ALL_FIELDS_REQUIRED': 'All fields are required.',
    'STK_PUSH_FAILED': 'STK push failed. Please try again.',
    'PAYMENT_FAILED': 'Payment failed. Please try again.',
}

# ==============================================================================
# VALIDATION CONSTANTS
# ==============================================================================
class Validation:
    """Validation rules and limits."""
    # Password
    PASSWORD_MIN_LENGTH = 6
    
    # Phone number
    PHONE_NUMBER_LENGTH = 12  # +254 + 9 digits
    
    # Product
    PRODUCT_NAME_MAX_LENGTH = 150
    PRODUCT_DESCRIPTION_MAX_LENGTH = 5000
    PRODUCT_IMAGE_MAX_SIZE = 5242880  # 5MB in bytes
    
    # Cart
    CART_ITEM_MAX_QUANTITY = 1000
    MIN_ORDER_AMOUNT = 1  # KES
    
    # Code
    RESET_CODE_LENGTH = 6
    RESET_CODE_EXPIRY_MINUTES = 15
    
    # Contact form
    CONTACT_NAME_MAX_LENGTH = 100
    CONTACT_MESSAGE_MAX_LENGTH = 2000


# ==============================================================================
# M-PESA CONSTANTS
# ==============================================================================
class MPesa:
    """M-Pesa related constants."""
    PAYMENT_METHOD = 'mpesa'
    ACCOUNT_REFERENCE_PREFIX = 'Zao'  # Will be appended with order ID
    
    # Status codes from Daraja API
    SUCCESS_CODE = 0
    TIMEOUT_CODE = 1032
    CANCELLED_CODE = 1


# ==============================================================================
# EMAIL CONSTANTS
# ==============================================================================
class Email:
    """Email related constants."""
    DEFAULT_FROM = 'noreply@zaoconnect.com'
    ADMIN_EMAIL = 'admin@zaoconnect.com'
    
    # Email subjects
    SUBJECT_PASSWORD_RESET = 'Password Reset Code - ZaoConnect'
    SUBJECT_PASSWORD_RESET_CONFIRMATION = 'Password Reset Successful - ZaoConnect'
    SUBJECT_PAYMENT_SUCCESS = 'Payment Successful - Order #{order_id}'
    SUBJECT_PAYMENT_FAILED = 'Payment Failed - Order #{order_id}'
    SUBJECT_ADMIN_PAYMENT = 'New Payment Received - Order #{order_id}'
    
    # Email templates
    TEMPLATE_PASSWORD_RESET = 'emails/password_reset.html'
    TEMPLATE_PAYMENT_SUCCESS = 'emails/payment_success.html'
    TEMPLATE_PAYMENT_FAILED = 'emails/payment_failed.html'
    TEMPLATE_ADMIN_PAYMENT = 'emails/admin_payment_notification.html'


# ==============================================================================
# PAGINATION CONSTANTS
# ==============================================================================
class Pagination:
    """Pagination settings."""
    DEFAULT_PAGE_SIZE = 20
    PRODUCT_PAGE_SIZE = 12
    ADMIN_LIST_PAGE_SIZE = 25
    TRANSACTION_PAGE_SIZE = 50


# ==============================================================================
# ANALYTICS CONSTANTS
# ==============================================================================
class Analytics:
    """Analytics related constants."""
    DATE_RANGE_7DAYS = 7
    DATE_RANGE_30DAYS = 30
    DATE_RANGE_90DAYS = 90
    RECENT_TRANSACTIONS_LIMIT = 20


# ==============================================================================
# ERROR CODES
# ==============================================================================
class ErrorCode:
    """Custom error codes for API responses."""
    INVALID_REQUEST = 'INVALID_REQUEST'
    AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED'
    PERMISSION_DENIED = 'PERMISSION_DENIED'
    RESOURCE_NOT_FOUND = 'RESOURCE_NOT_FOUND'
    CONFLICT = 'CONFLICT'
    INTERNAL_ERROR = 'INTERNAL_ERROR'
    SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE'
