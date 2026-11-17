from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('signup/', views.signup, name='signup'),
    path('login/', LoginView.as_view(template_name='registration/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:id>/', views.group_detail, name='group_detail'),
    path('groups/<int:id>/members/add/', views.member_add, name='member_add'),
]
