from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('sessions/<int:session_id>/', views.session_detail, name='session_detail'),
    path('sessions/<int:session_id>/review/', views.session_review, name='session_review'),
    path('api/upload-audio/', views.upload_audio, name='upload_audio'),
    path('api/sessions/', views.session_list_api, name='session_list_api'),
    path('api/sessions/<int:session_id>/', views.session_detail_api, name='session_detail_api'),
    path('api/sessions/<int:session_id>/review/', views.session_review_api, name='session_review_api'),
]
