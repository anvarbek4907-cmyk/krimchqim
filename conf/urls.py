from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from finance import web

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", web.index, name="home"),
    path("web/login/", web.login_view),
    path("web/register/", web.register_view),
    path("web/logout/", web.logout_view),
    path("web/state/", web.state),
    path("web/stats/", web.stats),
    path("web/operation/add/", web.add_operation),
    path("web/operation/delete/", web.delete_operation),
    path("web/account/add/", web.add_account),
    path("web/category/add/", web.add_category),

    path("api/", include("finance.urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]