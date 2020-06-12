"""xjy_recognition_master URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from imgProAPP import views
from django.conf.urls.static import static
from django.conf import settings

admin.site.site_header = '新教育 识别服务器后台管理'

urlpatterns = [
    path('check_app', views.check_app_view),  # 查看扫描仪APP更新

    path('scanners/active', views.active_scanner_view),  # 查看活跃扫描仪

    path('schools/<school_id>/scanners/<scanner_id>/update', views.update_school_scanner_view),  # 更新扫描仪和学校对应关系
    path('schools/<school_id>/scanners/<scanner_id>/upload', views.file_upload_view),  # 从扫描仪向服务器上传文件

    path('', admin.site.urls),  # Admin页面
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)