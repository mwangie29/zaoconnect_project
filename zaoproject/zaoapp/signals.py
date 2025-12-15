from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import Cart, UserProfile


@receiver(post_save, sender=User)
def create_user_related_objects(sender, instance, created, **kwargs):
    """
    Automatically create related objects when a new User is created.

    - Cart: used for the shopping cart feature.
    - UserProfile: stores custom fields such as the seller role.
    """
    if created:
        Cart.objects.create(user=instance)
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_related_objects(sender, instance, **kwargs):
    """Ensure related objects are saved if they already exist."""
    if hasattr(instance, "cart"):
        instance.cart.save()
    if hasattr(instance, "userprofile"):
        instance.userprofile.save()
