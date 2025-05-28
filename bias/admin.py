from django.contrib import admin
from .models import UploadedDataset,BiasAnalysisResult,BiasCorrectionSuggestion

# Register your models here.
admin.site.register(UploadedDataset)
admin.site.register(BiasAnalysisResult)
admin.site.register(BiasCorrectionSuggestion)