from django.urls import include, path

urlpatterns = [path("", include("adapters.entrada.web.urls"))]
