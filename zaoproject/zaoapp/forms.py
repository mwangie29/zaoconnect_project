from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django import forms
from django.core.exceptions import ValidationError

from .models import Product


class Registerform(forms.ModelForm):
    """Registration form that lets users choose whether they are a Buyer or Seller."""

    ROLE_CHOICES = (
        ("buyer", "Buyer"),
        ("seller", "Seller"),
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email address",
            }
        ),
        label="Email",
    )
    password = forms.CharField(
        min_length=6,
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password (minimum 6 characters)",
            }
        ),
        help_text="Password must be at least 6 characters.",
        label="Password",
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=True,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        label="Register as",
    )

    class Meta:
        model = User
        fields = ["email", "password"]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        """
        Create the User instance.

        The role (Buyer/Seller) is handled in the view where we also update
        the related UserProfile.is_seller flag.
        """
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  # Use email as username
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'is_active', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class UserProfileForm(forms.ModelForm):
    """Form for users to edit their profile (username, email, first_name, last_name)."""
    
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890',
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True,
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Styled password change form with Bootstrap classes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class ForgotPasswordForm(forms.Form):
    """Form to request password reset via email."""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('No account found with this email address.')
        return email


class ResetPasswordForm(forms.Form):
    """Form to set a new password during password reset."""

    new_password = forms.CharField(
        min_length=6,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password (minimum 6 characters)',
        }),
        label='New Password',
        help_text='Password must be at least 6 characters.'
    )
    confirm_password = forms.CharField(
        min_length=6,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
        }),
        label='Confirm Password'
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError('Passwords do not match.')
        return cleaned_data
