from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from drf_spectacular.views import SpectacularAPIView,SpectacularRedocView,SpectacularSwaggerView,


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="app", permanent=False)),
    path("app/", TemplateView.as_view(template_name="app.html"), name="app"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("finance.urls")),
   
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
