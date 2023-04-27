from django.urls import path
from . import views

urlpatterns = [
    path('', views.blackjack, name='blackjack'),
    path('ws/blackjack/', views.blackjack_ws),
]
