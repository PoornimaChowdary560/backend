from rest_framework import serializers
from .models import UploadedDataset,BiasAnalysisResult,BiasCorrectionSuggestion

class DatasetUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedDataset
        fields = ['id', 'file', 'uploaded_at', 'processed']

class BiasAnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiasAnalysisResult
        fields = '__all__'

class BiasCorrectionSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiasCorrectionSuggestion
        fields = ['id', 'analysis', 'suggestion_text', 'applied', 'category', 'created_at']
