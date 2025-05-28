from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import DatasetUploadView, BiasAnalysisView, GetAnalysisResultsView,BiasReportView,SuggestinView,ApplyFixesView,DownloadReportView

urlpatterns=[
    path('api/upload/', DatasetUploadView.as_view(), name="dataset-upload"),
    path('api/analyze/', BiasAnalysisView.as_view(), name='analyze-bias'),
    path('api/analysis/<int:analysis_id>/', GetAnalysisResultsView.as_view(), name='get-analysis'),
    path('api/bias-report/<int:analysis_id>/', BiasReportView.as_view(), name='get-report'),
    path('api/suggestion/<int:analysis_id>/', SuggestinView.as_view(), name='get-report'),
    path('api/apply-fixes/<int:analysis_id>/', ApplyFixesView.as_view(), name='apply-fixes'),
    path('api/download-report/<int:analysis_id>/', DownloadReportView.as_view(), name='download-report'),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)