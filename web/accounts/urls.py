from django.urls import path

from accounts import views

urlpatterns = [
    path(
        "login/human-challenge/",
        views.human_challenge_refresh_view,
        name="login_human_challenge_refresh",
    ),
    path("login/", views.login_view, name="login"),
    path("login/code/", views.login_code_view, name="login_code"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/password/", views.change_password_view, name="change_password"),
    path("users/<uuid:user_id>/profile/", views.user_profile_edit_view, name="user_profile_edit"),
    path("select-organisation/", views.select_organisation_view, name="select_organisation"),
    path("organisations/new/", views.create_organisation_view, name="create_organisation"),
    path("organisations/users/", views.manage_organisation_users_view, name="organisation_users_manage"),
    path("invite/", views.invite_user_platform_view, name="invite_user_platform"),
    path("invite/organisation/", views.invite_user_organisation_view, name="invite_user_organisation"),
    path("verify-email/", views.verify_email_view, name="verify_email"),
]
