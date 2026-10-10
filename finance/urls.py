from django.urls import path

from . import views

urlpatterns = [
    path("categories/", views.CategoryListCreateView.as_view(), name="category-list"),
    path("categories/<int:pk>/", views.CategoryDetailView.as_view(), name="category-detail"),
    path("wallets/", views.WalletListCreateView.as_view(), name="wallet-list"),
    path("wallets/<int:pk>/", views.WalletDetailView.as_view(), name="wallet-detail"),
    path("transactions/", views.TransactionListCreateView.as_view(), name="transaction-list"),
    path("transactions/<int:pk>/",views.TransactionDetailView.as_view(),name="transaction-detail",),
    path("summary/", views.SummaryView.as_view(), name="summary"),
]
