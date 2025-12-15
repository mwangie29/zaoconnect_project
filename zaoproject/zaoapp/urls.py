from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'), 
    path('base/', views.base, name='base'),  # Default URL/', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.register, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<int:user_id>/<str:token>/', views.reset_password, name='reset_password'),
    path('profile/', views.profile, name='profile'),
    path('cart/', views.cart, name='cart'),
    path('order/', views.order, name='order'),
    path('api/cart/get/', views.get_cart, name='get_cart'),
    path('api/cart/update/', views.update_cart, name='update_cart'),
    path('api/cart/clear/', views.clear_cart, name='clear_cart'),
    path('api/products/find/', views.find_product_by_name, name='find_product_by_name'),
    # Seller product management dashboard
    path('dashboard/products/', views.product_admin_list, name='product_admin_list'),
    path('dashboard/products/add/', views.product_create, name='product_create'),
    path('dashboard/products/<int:pk>/edit/', views.product_update, name='product_update'),
    path('dashboard/products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('dashboard/products/report/pdf/', views.product_admin_report_pdf, name='product_admin_report_pdf'),
    # Custom admin overview dashboard (separate from Django admin at /admin/)
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/report/pdf/', views.admin_dashboard_report_pdf, name='admin_dashboard_report_pdf'),
    path('dashboard/admin/users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('dashboard/admin/users/<int:user_id>/reset-password/', views.admin_reset_user_password, name='admin_reset_user_password'),
]
