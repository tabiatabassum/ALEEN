
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path(
        'the-atelier/',
        views.atelier,
        name='atelier'
    ),

    path(
        'find-your-bloom/',
        views.gift_finder,
        name='gift_finder'
    ),
]
