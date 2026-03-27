from django.urls import include, path

urlpatterns = [
    path("", include("catalog.urls")),
    path("accounts/", include("accounts.urls")),
]
