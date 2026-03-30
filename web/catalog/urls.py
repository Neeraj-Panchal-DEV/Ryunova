from django.urls import path

from catalog import views

urlpatterns = [
    path("", views.landing, name="home"),
    path("legal/privacy/", views.privacy_policy, name="privacy_policy"),
    path("legal/terms/", views.terms_of_service, name="terms_of_service"),
    path("contact/", views.contact, name="contact"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/scrape-preview/", views.product_scrape_preview, name="product_scrape_preview"),
    path("products/<uuid:product_id>/comments/", views.product_comments_api, name="product_comments_api"),
    path("products/<uuid:product_id>/", views.product_edit, name="product_edit"),
    path("products/<uuid:product_id>/delete/", views.product_delete, name="product_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/reorder/", views.category_reorder, name="category_reorder"),
    path("categories/sort-by-name/", views.category_sort_by_name, name="category_sort_by_name"),
    path("categories/<uuid:category_id>/edit/", views.category_edit, name="category_edit"),
    path("categories/<uuid:category_id>/set-active/", views.category_set_active, name="category_set_active"),
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/reorder/", views.brand_reorder, name="brand_reorder"),
    path("brands/sort-by-name/", views.brand_sort_by_name, name="brand_sort_by_name"),
    path("brands/<uuid:brand_id>/edit/", views.brand_edit, name="brand_edit"),
    path("brands/<uuid:brand_id>/set-active/", views.brand_set_active, name="brand_set_active"),
]
