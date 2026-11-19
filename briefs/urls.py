from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/briefs/", views.generate, name="generate"),
    path("api/briefs/<uuid:run_id>/copied/", views.track_copy, name="track_copy"),
]
