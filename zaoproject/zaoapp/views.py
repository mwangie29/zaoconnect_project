from django.shortcuts import render
from django.shortcuts import redirect
from .models import Contact
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import Registerform


def index(request):
    return render(request, 'index.html')
def contact(request):
    if request.method == 'POST':
        full_name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        
        contact.objects.create(full_name=full_name, email=email, message=message)
        #returning the data to the template.
        #return render(request, 'contact.html', {'full_name': full_name})
    #When a user visits the contact page.
    return render(request, 'contact.html')

def shop(request):
    return render(request, 'shop.html')
def testimonials(request):
    return render(request, 'testimonials.html')

def register(request):
    if request.method == 'POST':
        form = Registerform(request.POST)
        if form.is_valid():
            form.save()
            # Redirect to a success page or login page
            return redirect('index')
    else:  #else render an empty form.
        form = Registerform()
    
    return render(request, 'register.html', {'form': form})
    

def user_login(request):
    form=AuthenticationForm(data=request.POST)
    if form.is_valid():
        user=form.get_user()
        login(request,user)
        return redirect('index')
    else:
        form=AuthenticationForm()
        return render(request, 'login.html', {'form': form})
    
@login_required
def profile(request):
    return render(request, 'profile.html')
def logout_user(request):
    logout(request)
    return redirect('index')
