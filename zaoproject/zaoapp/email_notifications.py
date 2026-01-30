"""Email notification utilities for M-Pesa payments."""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_payment_success_email(order):
    """
    Send email notification when payment is successful.
    
    Args:
        order: Order instance with successful payment
    """
    try:
        user = order.user
        subject = f"Payment Successful - Order #{order.id}"
        
        # Prepare context for email template
        context = {
            'user_name': user.first_name or user.username,
            'order_id': order.id,
            'amount': order.total_amount,
            'receipt_number': order.mpesa_receipt_number,
            'phone_number': order.phone_number,
            'created_at': order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'site_name': 'ZaoConnect',
        }
        
        # Create HTML and plain text versions
        html_message = render_to_string('emails/payment_success.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment success email sent to {user.email} for order {order.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment success email for order {order.id}: {str(e)}")
        return False


def send_payment_failed_email(order):
    """
    Send email notification when payment fails.
    
    Args:
        order: Order instance with failed payment
    """
    try:
        user = order.user
        subject = f"Payment Failed - Order #{order.id}"
        
        context = {
            'user_name': user.first_name or user.username,
            'order_id': order.id,
            'amount': order.total_amount,
            'phone_number': order.phone_number,
            'site_name': 'ZaoConnect',
        }
        
        html_message = render_to_string('emails/payment_failed.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment failed email sent to {user.email} for order {order.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment failed email for order {order.id}: {str(e)}")
        return False


def send_admin_payment_notification(order):
    """
    Send admin notification of successful payment.
    
    Args:
        order: Order instance with successful payment
    """
    try:
        admin_emails = [admin[1] for admin in settings.ADMINS]
        if not admin_emails:
            return False
        
        subject = f"New Payment Received - Order #{order.id}"
        
        context = {
            'order_id': order.id,
            'user_name': order.user.get_full_name() or order.user.username,
            'user_email': order.user.email,
            'amount': order.total_amount,
            'receipt_number': order.mpesa_receipt_number,
            'phone_number': order.phone_number,
            'created_at': order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        html_message = render_to_string('emails/admin_payment_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Admin payment notification sent for order {order.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send admin payment notification for order {order.id}: {str(e)}")
        return False
